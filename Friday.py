import speech_recognition as sr
from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
from ctypes import cast, POINTER
from comtypes import CLSCTX_ALL
import re
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
from yandex_music import Client
import urllib
from gtts import gTTS
import tempfile
import pyautogui
import keyboard
import re
from threading import Thread
import pickle
import hashlib

# Инициализация pygame mixer
mixer.init()

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
        self.volume_control = self.init_volume()
        self.recognizer = sr.Recognizer()
        
        # Настройка распознавателя
        self.configure_recognizer()
        
        # История для анализа звука
        self.energy_history = deque(maxlen=15)

        self.tts_cache = {}
        self.load_tts_cache()
        
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

        self.weather_url = "https://yandex.ru/pogoda/"
        self.yandex_music_path = os.path.expanduser('~') + r'\AppData\Roaming\Microsoft\Windows\Start Menu\Programs\Яндекс Музыка.lnk'

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

        self.preload_common_phrases()


    def preload_common_phrases(self):
        common_phrases = [
            'Да, слушаю вас',
            'Я здесь',
            "Чем могу помочь",
            "Готова помочь",
            "Не расслышала команду",
            "Не удалось выполнить действие",
            "Пятница активирована",
            "Выключаюсь"
        ]
        for phrase in common_phrases:
            self.async_speak(phrase)

    def load_tts_cache(self):
        cache_file = os.path.join(tempfile.gettempdir(), 'friday_tts_cache.plk')
        try:
            if os.path.exists(cache_file):
                with open(cache_file, "rb") as f:
                    self.tts_cache = pickle.load(f)
                print(f"Загружен кэш из TTS: {cache_file}")
        except Exception as e:
                print("Ошибка загрузки кэша: {e}")


    def save_tts_cache(self):
        cache_file = os.path.join(tempfile.gettempdir(), 'friday_tts_cache.pkl')
        try:
            with open(cache_file, 'wb') as f:
                pickle.dump(self.tts_cache, f)
        except Exception as e:
            print(f"Ошибка сохранения кэша TTS: {e}")

    def get_tts_filename(self, text):
        # Создаем хеш от текста для имени файла
        text_hash = hashlib.md5(text.encode('utf-8')).hexdigest()
        return os.path.join(tempfile.gettempdir(), f'tts_{text_hash}.mp3')


    def init_yandex_music(self):
        try:
            self.yandex_music_client = Client("").init()

            queues = self.yandex_music_client.queues_list()
            if queues:
                self.yandex_music_client.queue(queues[0].id)
            print("Яндекс.Музыка: авторизация успешна")
        except Exception as e:
            print(f"Ошибка авторизации Яндекс.Музыки: {e}")


    def control_yandex_music(self, action):
        try:
            # Проверяем, запущено ли приложение
            if not self.is_yandex_music_running():
                os.startfile(self.yandex_music_path)
                time.sleep(1) 


            # Управление горячими клавишами
            if action == 'play_pause':
                keyboard.press_and_release('play/pause media')
                time.sleep(0.1)
                status = "Пауза" if self.is_music_playing() else "Продолжаю"
                self.async_speak(status)
                
            elif action == "next":
                keyboard.press_and_release('next track')
                self.async_speak("Следующий трек")
                
            elif action == "previous":
                keyboard.press_and_release('previous track')
                self.async_speak("Предыдущий трек")
                
            elif action == "stop":
                keyboard.press_and_release('play/pause media')
                self.async_speak("Остановлено")
                
        except Exception as e:
            print(f"Ошибка управления Яндекс Музыкой: {e}")
            self.async_speak("Не удалось выполнить действие")

    def is_yandex_music_running(self):
        try:
            output = subprocess.check_output('tacklist', shell=True).decode('cp866', 'ignore')
            return 'Яндекс Музыка' in output
        except:
            return False

    def is_music_playing(self):
        return self.is_yandex_music_running()

                    

    def play_in_yandex_music(self, query):
        try:
        # Путь к Яндекс.Музыке
            yandex_music_path = r"C:\Users\panas\AppData\Roaming\Microsoft\Windows\Start Menu\Programs\Яндекс Музыка.lnk"
        
        # Проверяем и запускаем приложение, если оно не запущено
            if not self.is_yandex_music_running():
                os.startfile(yandex_music_path)
                time.sleep(1)  # Даем приложению время на запуск
        
        # Очищаем запрос от лишних слов
            clean_query = re.sub(r'(пожалуйста|включи|найди|песню|трек|музыку|в яндекс музыке)', '', 
                           query, flags=re.IGNORECASE).strip()
        
            if not clean_query:
                self.async_speak("Не услышала название песни")
                return
        

        

        
        # Даем время на обработку команды
            time.sleep(0.5)
        
        # Нажимаем Enter для выбора первого результата
            pyautogui.press('enter')
        
            self.async_speak(f"Ищу {clean_query} в Яндекс.Музыке...")
        
        except Exception as e:
            print(f"Ошибка: {e}")
            self.async_speak("Не удалось включить песню в Яндекс.Музыке")

        
    

    def play_on_youtube(self, query):
        """Поиск и воспроизведение музыки на YouTube"""
        if query in self.youtube_cache:
            webbrowser.open(self.youtube_cache[query])
            self.async_speak("Включаю из кэша")
            return
        try:
            from pytube import Search
            import urllib.parse

            s = Search(query)
            if not s.results:
                self.async_speak("ничего не найдено")
                return

            video_url = f"https://youtube.com/watch?v={s.results[0].video_id}"
            webbrowser.open(video_url)
            self.async_speak(f"включаю {s.results[0].title}")

            self.youtube_cache[query] = video_url

        except Exception as e:
            print(f"Ошибка при поиске на YouTube: {e}")
            search_url = f"https://www.youtube.com/results?search_query={urllib.parse.quote(query)}"
            webbrowser.open(search_url)
            self.async_speak(f"Ищу {query} на Youtube")

    def configure_recognizer(self):
        """Настройка параметров распознавания речи"""
        self.recognizer.dynamic_energy_threshold = False
        self.recognizer.pause_threshold = self.pause_threshold
        self.recognizer.phrase_threshold = self.phrase_threshold
        self.recognizer.non_speaking_duration = 0.2
        self.recognizer.energy_threshold = self.initial_energy_threshold

    def init_volume(self):
        """Инициализация контроля громкости"""
        devices = AudioUtilities.GetSpeakers()
        interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
        return cast(interface, POINTER(IAudioEndpointVolume))

    def speak(self, text):
        """Произнесение текста с использованием Google TTS и pygame.mixer"""
        print(f"[Пятница]: {text}")
        try:
            cache_file = self.get_tts_filename(text)

            if text in self.tts_cache and os.path.exists(self.tts_cache[text]):
                mixer.music.load(self.tts_cache[text])
                mixer.music.play()

                while mixer.music.get_busy():
                    time.sleep(0.1)
            else:
                
                tts = gTTS(text=text, lang='ru')
                tts.save(cache_file)

                self.tts_cache[text] = cache_file
                mixer.music.load(cache_file)
                mixer.music.play()

                while mixer.music.get_busy():
                    time.sleep(0.1)
        except Exception as e:
            print(f"Ошибка воспроизведения: {e}")
            print(f"(Ошибка TTS): {text}")

    def async_speak(self, text):
        thread = Thread(target=self.speak, args=(text,))
        thread.start()

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
                timeout=1.5,
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
                    if current_time - self.last_activation > 2:
                        self.last_activation = current_time
                        return True
                        
            except sr.UnknownValueError:
                self.recognizer.energy_threshold = min(
                    self.recognizer.energy_threshold * 1.1,
                    6000
                )
            except sr.RequestError as e:
                print(f"Ошибка сервиса распознавания: {e}")
                
        except sr.WaitTimeoutError:
            self.recognizer.energy_threshold = max(
                self.recognizer.energy_threshold * 0.95,
                300
            )
            
        return False

    def wake_up(self):
        """Активация ассистента"""
        self.is_active = True
        self.async_speak(random.choice([
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
                    timeout=3,
                    phrase_time_limit=5
                )
                command = self.recognizer.recognize_google(audio, language="ru-RU").lower()
                self.process_command(command)
                
            except sr.UnknownValueError:
                self.async_speak("Не расслышала команду")
            except Exception as e:
                print(f"Ошибка: {e}")
            finally:
                self.return_to_sleep()

    def calculate(self, expression):
        try:
            cleaned_expr = re.sub(r'[^\d+\-*/.()]', '', expression)
            if not cleaned_expr:
                raise ValueError("Пустое выражение")

            result = eval(cleaned_expr, {'__builtins__': None}, {})
            self.async_speak(f"Результат: {result}")
        except Exception as e:
            print(f"Ошибка вычисления: {e}")
            self.async_speak("Не удалось вычислить выражение")


    def start_music_player(self, player_name=None):
        """Запуск музыкального приложения"""
        try:
            app_name = player_name or 'default'
            if app_name in self.music_apps:
                path = self.music_apps[app_name]
                if os.path.exists(path):
                    os.startfile(path)
                    self.async_speak(f"Запускаю {app_name}")
                    return
            
            commands = {
                'default': 'start yandexmusic:',
                'spotify': 'start spotify:',
                'yandex': 'start wmplayer'
            }
            subprocess.run(commands.get(app_name, commands['default']), shell=True)
            self.async_speak(f"Запускаю {app_name}")
            
        except Exception as e:
            print(f"Ошибка запуска плеера: {e}")
            self.async_speak("Не удалось запустить музыку")

    def set_volume(self, level):
        """Установка уровня громкости"""
        try:
            vol = max(0.0, min(1.0, level/100.0))
            self.volume_control.SetMasterVolumeLevelScalar(vol, None)
            self.async_speak(f"Громкость {int(level)}%")
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
                    url = f"{self.weather_url}{location_mapping[location_key]}"
                else:
                    url = f"{self.weather_url}{location.lower().replace(' ', '-')}"
            else:
                url = self.weather_url

            webbrowser.open(url)
            self.async_speak(f"Открываю погоду {'в ' + location if location else ''}")
        except Exception as e:
            print(f"Ошибка открытия погоды: {e}")
            self.async_speak("Не удалось открыть погоду")

    def launch_app(self, app_name):
        try:
            if app_name in self.app_paths:
                path = self.app_paths[app_name]
                if os.path.exists(path):
                    os.startfile(path)
                    self.async_speak(f"Запускаю {app_name}")
                    return True
                else:
                    self.async_speak(f"{app_name} не найден по указаному пути")
                    return False
                return False
        except Exception as e:
            print(f"Ошибка запуска {app_name}")
            self.async_speak(f"Не удалось запустить {app_name}")
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

        #Управление музыкой
        elif any(cmd in command for cmd in ["пауза", "останови музыку", "приостанови музыку"]):
            self.control_yandex_music("play_pause")
        elif any(cmd in command for cmd in ["продолжить", "возобновить музыку"]):
            self.control_yandex_music("play_pause")
        elif any(cmd in command for cmd in ["следующий трек", "следующая песня", "дальше"]):
            self.control_yandex_music("next")
        elif any(cmd in command for cmd in ["предыдущий трек", "предыдущая песня", "назад"]):
            self.control_yandex_music("previous")
        elif any(cmd in command for cmd in ["останови музыку", "стоп"]):
            self.control_yandex_music("stop")

        #steam
        elif any(cmd in command for cmd in["запусти стим", "открой стим", "запусти steam"]):
            if not self.launch_app('steam'):
                self.async_speak("Steam не найден")
        #Telegram
        elif any(cmd in command for cmd in ["запусти телеграмм", "открой телеграмм", "открой telegram"]):
            if not self.launch_app('telegram'):
                self.async_speak("Telegram не найден")

        #калькулятор
        elif any(cmd in command for cmd in ["посчитай", "вычисли", "сколько будет", "калькулятор"]):
            expr = command.replace("посчитай", "").replace("вычисли", "").replace("сколько будет", "").strip()
            if expr:
                self.calculate(expr)
            else:
                self.async_speak("Пожалуйста, назовите выражение для вычисления")

        # Погода
        elif 'погода' in command:
            location = None
            if "погода в" in command:
                location = command.split("погода в")[1].strip()
            elif "погода" in command and len(command.split()) > 1:
                location = command.split("погода")[1].strip()

            self.show_weather(location)

        #Поиск музыки
        elif "яндекс музыке" in command or "яндекс музыку" in command:
            try:
                if "включи" in command:
                    song_name = command.split("включи")[1].split("в яндекс музыке")[0].strip()
                elif "найди" in command:
                    song_name = command.split("найди")[1].split("в яндекс музыке")[0].strip()
                else:
                    song_name = command.split("в яндекс музыке")[0].strip()
        
                if song_name:
                    self.play_in_yandex_music(song_name)
                else:
                    self.async_speak("Пожалуйста, назовите песню")
            except Exception as e:
                print(f"Ошибка обработки команды: {e}")
                self.async_speak("Не удалось обработать команду")
                
        
        elif any(cmd in command for cmd in ["включи песню", "найди песню", "найди музыку", "включи музыку"]):
            song_name = command.replace("включи песню", "").replace("найди песню", "").replace("найди музыку", "").replace("включи музыку", "").strip()
            if song_name:
                self.play_on_youtube(song_name)
            else:
                self.async_speak("Пожалуйста укажите название")

        
        # Калибровка
        elif "калибровка" in command:
            self.speak("Начинаю калибровку микрофона")
            self.calibrate_microphone(source=sys._getframe(1).f_locals.get('source'))
        
        # Прочие команды
        elif "спасибо" in command:
            self.async_speak("Всегда пожалуйста!")
        elif any(cmd in command for cmd in ["выход", "закройся"]):
            self.should_exit = True
            self.async_speak("Выключаюсь")
        else:
            self.async_speak("Не поняла команду")

    def return_to_sleep(self):
        """Возврат в режим ожидания"""
        self.is_active = False
        print("Возврат в режим ожидания...")

    def calibrate_microphone(self, source):
        """Калибровка микрофона"""
        self.async_speak("Провожу калибровку микрофона.")
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
    try:
        assistant.run()
    finally:
        assistant.save_tts_cache