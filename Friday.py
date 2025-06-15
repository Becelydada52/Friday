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
import webbrowser
from pytube import YouTube
from pygame import mixer
import time
from yandex_music import Client
import client_yandex

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
            'default': os.path.expanduser('~') + r'\AppData\Roaming\Microsoft\Windows\Start Menu\Programs\Яндекс Музыка.lnk',
            'spotify': os.path.expanduser('~') + r'\AppData\Roaming\Spotify\Spotify.exe',
            'yandex': r'C:\Program Files\Windows Media Player\wmplayer.exe',
        }
        
        self.app_paths = {
            'steam': r'C:\Program Files (x86)\Steam\steam.exe',
            'telegram': os.path.expanduser('~') + r'\AppData\Roaming\Telegram Desktop\Telegram.exe'
}

        self.weapon_url = "https://yandex.ru/pogoda/"

        # Состояние
        self.is_active = False
        self.should_exit = False
        self.last_activation = 0
        self.activation_phrases = [
            'пятница', 'пятницу', 'пятнича', 'пятничка',
            'friday', 'фрайди', 'эй пятница', 'привет пятница'
        ]

        self.youtube_base_url = "https://www.youtube.com/results?search_query="
        self.youtube_cache = {}

        self.yandex_music_client = None
        self.init_yandex_music()


    def init_yandex_music(self):
        try:
            self.yandex_music_client = Client("YOUR_YANDEX_MUSIC_TOKEN").init()
        except Exception as e:
            print(f"Ошибка авторизации Яндекс.Музыки:{e}")

    def play_in_yandex_music(self, query):
        try:
            if not self.yandex_music_client:
                self.speak("Ошибка подключения к Яндекс.Музыке")
                return
        
            search_result = self.yandex_music_client.search(query, type_="track")
            if not search_result.tracks or not search_result.tracks.results:
                self.speak("Трэк не найден")
                return

            track = search_result.tracks.results[0]
            track_url = f"https://music.yandex.ru/track/{track.id}"
            webbrowser.open(f"yandexmusic://track/{track.id}")
            self.speak(f"Включаю {track.title} — {', '.join(a.name for a in track.artists)}")

        except Exception as e:
            print(f"Ошибка: {e}")
            self.speak("Не удалось включить песню")

    def play_on_youtube(self, query):
        """Поиск и воспроизведение музыки на YouTube"""
        if query in self.youtube_cache:
            webbrowser.open(self.youtube_cache[query])
            self.speak("Включаю из кэша")
            return
        try:
            from pytube import Search
            import urllib.parse

            s = Search(query)
            if not s.results:
                self.speak("ничего не найдено")
                return

            video_url = f"https://youtube.com/watch?v={s.results[0].video_id}"
            webbrowser.open(video_url)
            self.speak(f"включаю {s.results[0].title}")

        except Exception as e:
            print(f"Ошибка при поиске на YouTube: {e}")
            search_url = f"https://www.youtube.com/results?search_query={urllib.parse.quote(query)}"
            webbrowser.open(search_url)
            self.speak(f"Ищу {query} на Youtube")

            

            self.youtube_cache[query] = video_url



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

    def show_weather(self, location=None):
        try:
            if location:
                location_mapping = {
                    "москве": "moscow",
                    "ярославле": "yaroslavl"
                }
                location_key = location.lower()
                if location_key in location_mapping:
                    url = f"{self.weapon_url}{location_mapping[location_key]}"
                else:
                    url = f"{self.weapon_url}{location.lower().replace(' ', '-')}"
            else:
                url = self.weather_url

            webbrowser.open(url)
            self.speak(f"Открываю погоду {'в ' + location if location else ''}")
        except Exception as e:
            print(f"Ошибка открытия погоды: {e}")
            self.speak("Не удалось открыть погоду")

    def launch_app(self, app_name):
        try:
            if app_name in self.app_paths:
                path = self.app_paths[app_name]
                if os.path.exists(path):
                    os.startfile(path)
                    self.speak(f"Запускаю {app_name}")
                    return True
                else:
                    self.speak(f"{app_name} не найден по указаному пути")
                    return False
                return False
        except Exception as e:
            print(f"Ошибка запуска {app_name}")
            self.speak(f"Не удалось запустить {app_name}")
            return False


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

        #steam
        elif any(cmd in command for cmd in["запусти стим", "открой стим", "запусти steam"]):
            if not self.launch_app('steam'):
                self.speak("Steam не найден")
        #Telegram
        elif any(cmd in command for cmd in ["запусти телеграмм", "открой телеграмм", "открой telegram"]):
            if not self.launch_app('telegram'):
                self.speak("Telegram не найден")

        # Погода
        elif 'погода' in command:
            location = None
            if "погода в" in command:
                location = command.split("погода в")[1].strip()
            elif "погода" in command and len(command.split()) > 1:
                location = command.split("погода")[1].strip()

            self.show_weather(location)


        #Поиск музыки
        elif any(cmd in command for cmd in["включи песню", "найди песню", "найди музыку", "включи музыку"]):
            song_name = command.replace("включи песню", "").replace("найди песню", "").replace("найди музыку", "").replace("включи музыку", "").strip()
            if song_name:
                self.play_on_youtube(song_name)
            else:
                self.speak("Пожалуйста укажите название")
        
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
        self.speak("Провожу калибровку микрофона.")
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
                self.speak("Пятница активирована.")
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