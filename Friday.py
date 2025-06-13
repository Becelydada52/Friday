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

class FridayAssistant:
    def __init__(self):
        # Настройки чувствительности
        self.energy_threshold = 4000
        self.dynamic_energy_ratio = 1.5
        self.pause_threshold = 0.8
        self.phrase_threshold = 0.3
        
        # Инициализация компонентов
        self.engine = self.init_tts()
        self.volume_control = self.init_volume()
        self.recognizer = sr.Recognizer()
        
        # Настройка распознавателя
        self.configure_recognizer()
        
        # История для анализа звука
        self.energy_history = deque(maxlen=20)
        
        # Пути к приложениям
        self.music_apps = {
            'yandex': os.path.expanduser('~') + r'\AppData\Local\Yandex\YandexMusic\YandexMusic.exe',
            'spotify': os.path.expanduser('~') + r'\AppData\Roaming\Spotify\Spotify.exe',
            'default': r'C:\Program Files\Windows Media Player\wmplayer.exe'
        }
        
        # Состояние
        self.is_active = False
        self.should_exit = False
        self.last_activation = 0

    def configure_recognizer(self):
        """Настройка параметров распознавания речи"""
        self.recognizer.dynamic_energy_threshold = True
        self.recognizer.pause_threshold = self.pause_threshold
        self.recognizer.phrase_threshold = self.phrase_threshold
        self.recognizer.non_speaking_duration = 0.2
        self.recognizer.energy_threshold = self.energy_threshold

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

    def calculate_rms(self, audio_data):
        """Вычисление уровня звука"""
        audio_buffer = np.frombuffer(audio_data.get_raw_data(), dtype=np.int16)
        return np.sqrt(np.mean(audio_buffer**2))

    def adaptive_energy_threshold(self, audio_data):
        """Адаптивная настройка чувствительности микрофона"""
        try:
            energy = self.calculate_rms(audio_data)
            self.energy_history.append(energy)
            
            if len(self.energy_history) > 5:
                median_energy = np.median(self.energy_history)
                new_threshold = median_energy * self.dynamic_energy_ratio
                self.recognizer.energy_threshold = np.clip(
                    new_threshold,
                    300,  # минимальный порог
                    6000  # максимальный порог
                )
        except Exception as e:
            print(f"Ошибка адаптации порога: {e}")
            self.recognizer.energy_threshold = 4000

    def listen_for_trigger(self, source):
        """Прослушивание триггерного слова"""
        try:
            print(f"🔴 Ожидание (порог: {self.recognizer.energy_threshold:.1f})...")
            audio = self.recognizer.listen(
                source,
                timeout=3,
                phrase_time_limit=2
            )
            
            self.adaptive_energy_threshold(audio)
            
            try:
                text = self.recognizer.recognize_google(audio, language="ru-RU").lower()
                print(f"Распознано: {text}")
                
                trigger_phrases = [
                    'пятница', 'пятницу', 'пятнича', 'пятничка',
                    'friday', 'фрайди', 'эй пятница'
                ]
                
                if any(phrase in text for phrase in trigger_phrases):
                    current_time = time.time()
                    if current_time - self.last_activation > 5:
                        self.last_activation = current_time
                        return True
                        
            except sr.UnknownValueError:
                pass
                
        except sr.WaitTimeoutError:
            pass
            
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
        return self.active_listening()

    def active_listening(self):
        """Режим активного прослушивания команд"""
        with sr.Microphone() as source:
            try:
                print("🟢 Активный режим...")
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
            
            # Альтернативный способ запуска
            commands = {
                'yandex': 'start yandexmusic:',
                'spotify': 'start spotify:',
                'default': 'start wmplayer'
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
        print("Возврат в спящий режим...")

    def calibrate_microphone(self, source, duration=3):
        """Калибровка микрофона"""
        self.speak("Калибровка микрофона... Не шумите несколько секунд")
        self.recognizer.adjust_for_ambient_noise(source, duration=duration)
        self.energy_threshold = self.recognizer.energy_threshold
        self.speak("Калибровка завершена")

    def run(self):
        """Основной цикл работы"""
        with sr.Microphone() as source:
            self.calibrate_microphone(source)
            
            try:
                self.speak("Пятница активирована и готова к работе")
                while not self.should_exit:
                    if self.listen_for_trigger(source):
                        self.wake_up()
                    time.sleep(0.1)
                        
            except KeyboardInterrupt:
                self.speak("Завершение работы")
            except Exception as e:
                print(f"Критическая ошибка: {e}")
                self.speak("Произошла системная ошибка")

if __name__ == '__main__':
    assistant = FridayAssistant()
    assistant.run()