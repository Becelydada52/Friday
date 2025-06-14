import speech_recognition as sr
from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
from ctypes import cast, POINTER
from comtypes import CLSCTX_ALL
import re
import pyttsx3
import time
import os
import subprocess
import numpy as np
from collections import deque
import random
import sys
import io

# Настройка кодировки для Windows
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

class FridayAssistant:
    def __init__(self):
        # Настройки чувствительности
        self.initial_energy_threshold = 4000
        self.dynamic_energy_ratio = 1.8
        self.pause_threshold = 1.0
        self.phrase_threshold = 0.5
        self.ambient_adjust_duration = 2
        
        # Инициализация компонентов
        self.engine = self.init_tts()
        self.volume_control = self.init_volume()
        self.recognizer = sr.Recognizer()
        
        # Настройка распознавателя
        self.configure_recognizer()
        
        # История для анализа звука
        self.energy_history = deque(maxlen=15)
        
        # Пути к приложениям
        self.music_apps = {
            'default': os.path.expanduser('~') + r'\AppData\Local\Yandex\YandexMusic\YandexMusic.exe',
            'spotify': os.path.expanduser('~') + r'\AppData\Roaming\Spotify\Spotify.exe',
            'yandex': r'C:\Program Files\Windows Media Player\wmplayer.exe'
        }
        
        # Состояние
        self.is_active = False
        self.should_exit = False
        self.last_activation = 0
        self.activation_phrases = [
            'пятница', 'пятницу', 'пятнича', 'пятничка',
            'friday', 'фрайди', 'эй пятница', 'привет пятница'
        ]

    def configure_recognizer(self):
        """Настройка параметров распознавания речи"""
        self.recognizer.dynamic_energy_threshold = False
        self.recognizer.pause_threshold = self.pause_threshold
        self.recognizer.phrase_threshold = self.phrase_threshold
        self.recognizer.non_speaking_duration = 0.3
        self.recognizer.energy_threshold = self.initial_energy_threshold

    def init_tts(self):
        """Инициализация синтезатора речи"""
        engine = pyttsx3.init()
        engine.setProperty('rate', 160)
        engine.setProperty('volume', 0.9)
        return engine

    def init_volume(self):
        """Инициализация контроля громкости"""
        devices = AudioUtilities.GetSpeakers()
        interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
        return cast(interface, POINTER(IAudioEndpointVolume))

    def speak(self, text):
        """Произнесение текста с выводом в консоль"""
        print(f"[Пятница]: {text}")
        self.engine.say(text)
        self.engine.runAndWait()

    def calculate_audio_energy(self, audio_data):
        """Вычисление уровня звука"""
        audio_buffer = np.frombuffer(audio_data.get_raw_data(), dtype=np.int16)
        if len(audio_buffer) == 0:
            return 0
        return 20 * np.log10(np.sqrt(np.mean(audio_buffer**2)) + 1e-10)

    def update_energy_threshold(self, current_energy):
        """Адаптивная настройка порога чувствительности"""
        self.energy_history.append(current_energy)
        
        if len(self.energy_history) > 5:
            background_level = np.percentile(self.energy_history, 75)
            new_threshold = background_level * self.dynamic_energy_ratio
            current_threshold = self.recognizer.energy_threshold
            smoothed_threshold = current_threshold * 0.8 + new_threshold * 0.2
            
            self.recognizer.energy_threshold = np.clip(
                smoothed_threshold,
                max(300, background_level * 1.3),
                min(6000, background_level * 3)
            )

    def listen_for_trigger(self, source):
        """Прослушивание триггерного слова"""
        try:
            print(f"[ОЖИДАНИЕ] Текущий порог: {self.recognizer.energy_threshold:.1f}")
            
            audio = self.recognizer.listen(
                source,
                timeout=2,
                phrase_time_limit=3
            )
            
            current_energy = self.calculate_audio_energy(audio)
            self.update_energy_threshold(current_energy)
            
            try:
                text = self.recognizer.recognize_google(
                    audio,
                    language="ru-RU",
                    show_all=False
                ).lower()
                
                print(f"Распознано: {text}")
                
                if any(phrase in text for phrase in self.activation_phrases):
                    current_time = time.time()
                    if current_time - self.last_activation > 3:
                        self.last_activation = current_time
                        return True
                        
            except sr.UnknownValueError:
                self.recognizer.energy_threshold = min(
                    self.recognizer.energy_threshold * 1.2,
                    6000
                )
            except sr.RequestError as e:
                print(f"Ошибка сервиса распознавания: {e}")
                
        except sr.WaitTimeoutError:
            self.recognizer.energy_threshold = max(
                self.recognizer.energy_threshold * 0.9,
                300
            )
            
        return False

    def wake_up(self):
        """Активация ассистента"""
        self.is_active = True
        self.speak(random.choice([
            "Да, слушаю вас",
            "Я здесь",
            "Чем могу помочь?",
            "Готова помочь"
        ]))
        self.active_listening()

    def active_listening(self):
        """Режим активного прослушивания команд"""
        with sr.Microphone() as source:
            try:
                print("[АКТИВНЫЙ РЕЖИМ]...")
                audio = self.recognizer.listen(
                    source,
                    timeout=5,
                    phrase_time_limit=5
                )
                command = self.recognizer.recognize_google(audio, language="ru-RU").lower()
                self.process_command(command)
                
            except sr.UnknownValueError:
                self.speak("Не расслышала команду")
            except Exception as e:
                print(f"Ошибка: {e}")
            finally:
                self.return_to_sleep()

    def start_music_player(self, player_name=None):
        """Запуск музыкального приложения"""
        try:
            app_name = player_name or 'default'
            if app_name in self.music_apps:
                path = self.music_apps[app_name]
                if os.path.exists(path):
                    os.startfile(path)
                    self.speak(f"Запускаю {app_name}")
                    return
            
            commands = {
                'default': 'start yandexmusic:',
                'spotify': 'start spotify:',
                'yandex': 'start wmplayer'
            }
            subprocess.run(commands.get(app_name, commands['default']), shell=True)
            self.speak(f"Запускаю {app_name}")
            
        except Exception as e:
            print(f"Ошибка запуска плеера: {e}")
            self.speak("Не удалось запустить музыку")

    def set_volume(self, level):
        """Установка уровня громкости"""
        try:
            vol = max(0.0, min(1.0, level/100.0))
            self.volume_control.SetMasterVolumeLevelScalar(vol, None)
            self.speak(f"Громкость {int(level)}%")
        except Exception as e:
            print(f"Ошибка громкости: {e}")

    def process_command(self, command):
        """Обработка распознанных команд"""
        if not command:
            return
            
        print(f"Обработка команды: {command}")
        
        # Управление громкостью
        if "громкость" in command:
            if num := re.search(r'\d+', command):
                self.set_volume(int(num.group()))
            elif "максимум" in command:
                self.set_volume(100)
            elif "минимум" in command:
                self.set_volume(0)
            elif "половина" in command:
                self.set_volume(50)
        
        # Запуск музыки
        elif any(cmd in command for cmd in ["включи музыку", "запусти музыку"]):
            if "яндекс" in command or "yandex" in command:
                self.start_music_player('yandex')
            elif "spotify" in command:
                self.start_music_player('spotify')
            else:
                self.start_music_player()
        
        # Калибровка
        elif "калибровка" in command:
            self.speak("Начинаю калибровку микрофона")
            self.calibrate_microphone(source=sys._getframe(1).f_locals.get('source'))
        
        # Прочие команды
        elif "спасибо" in command:
            self.speak("Всегда пожалуйста!")
        elif any(cmd in command for cmd in ["выход", "закройся"]):
            self.should_exit = True
            self.speak("Выключаюсь")
        else:
            self.speak("Не поняла команду")

    def return_to_sleep(self):
        """Возврат в режим ожидания"""
        self.is_active = False
        print("Возврат в режим ожидания...")

    def calibrate_microphone(self, source):
        """Калибровка микрофона"""
        self.speak("Провожу калибровку микрофона. Пожалуйста, сохраняйте тишину несколько секунд.")
        self.recognizer.adjust_for_ambient_noise(
            source,
            duration=self.ambient_adjust_duration
        )
        self.recognizer.energy_threshold = self.recognizer.energy_threshold * 1.3
        self.initial_energy_threshold = self.recognizer.energy_threshold
        self.energy_history.clear()
        self.speak("Калибровка завершена. Готова к работе.")

    def run(self):
        """Основной цикл работы"""
        with sr.Microphone() as source:
            self.calibrate_microphone(source)
            
            try:
                self.speak("Пятница активирована. Говорите 'Пятница' для активации.")
                while not self.should_exit:
                    try:
                        if self.listen_for_trigger(source):
                            self.wake_up()
                        time.sleep(0.05)
                            
                    except Exception as e:
                        print(f"Ошибка в основном цикле: {e}")
                        self.calibrate_microphone(source)
                        
            except KeyboardInterrupt:
                self.speak("Завершение работы")
            except Exception as e:
                print(f"Критическая ошибка: {e}")
                self.speak("Произошла системная ошибка. Попробуйте перезапустить меня.")

if __name__ == '__main__':
    assistant = FridayAssistant()
    assistant.run()