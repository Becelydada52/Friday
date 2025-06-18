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
from googletrans import Translator, LANGUAGES


mixer.init()


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
        self.tts_volume = 0.5  
        
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

        self.translator = Translator()
        self.language_codes = {
            'английский': 'en',
            'русский': 'ru',
            'французский': 'fr',
            'немецкий': 'de',
            'испанский': 'es',
            'китайский': 'zh-cn',
            'японский': 'ja'
        }

        self.activation_phrases.extend([
            'переведи', 'перевод', 'как сказать'
        ])

    def translate_text(self, text, target_lang='ru'):
        try:
            lang_code = self.language_codes.get(target_lang, target_lang)
            translation = self.translator.translate(text, dest=lang_code)

            return {
                'text': translation.text,
                'pronunciation': getattr(translation, 'pronunciation', None),
                'src_lang': LANGUAGES.get(translation.src, translation.src),
                'dest_lang': LANGUAGES.get(lang_code, lang_code)
            }

        except Exception as e:
            print(f"ошибка перевода: {e}")
            return None

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
            cache_file = self.get_tts_filename(phrase)
            if not os.path.exists(cache_file):
                try:
                    tts = gTTS(text=phrase, lang='ru')
                    tts.save(cache_file)
                    self.tts_cache[phrase] = cache_file
                except Exception as e:
                    print(f"Ошибка предзагрузки фразы '{phrase}': {e}")

    def load_tts_cache(self):
        cache_file = os.path.join(tempfile.gettempdir(), 'friday_tts_cache.pkl')
        try:
            if os.path.exists(cache_file):
                with open(cache_file, "rb") as f:
                    self.tts_cache = pickle.load(f)
                print(f"Загружен кэш из TTS: {cache_file}")
        except Exception as e:
            print(f"Ошибка загрузки кэша: {e}")

    def save_tts_cache(self):
        cache_file = os.path.join(tempfile.gettempdir(), 'friday_tts_cache.pkl')
        try:
            with open(cache_file, 'wb') as f:
                pickle.dump(self.tts_cache, f)
        except Exception as e:
            print(f"Ошибка сохранения кэша TTS: {e}")

    def get_tts_filename(self, text):
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

    def get_playback_state(self):
        try:
            if not self.yandex_music_client:
                return None
        
            queues = self.yandex_music_client.queues_list()
            if not queues:
                return None
            
            queue = self.yandex_music_client.queue(queues[0].id)
            return queue.get_current_track()
        except Exception as e:
            print(f"Ошибка получения состояния: {e}")
            return None

    def control_yandex_music(self, action):
        try:
        # Проверяем авторизацию
            if not self.yandex_music_client:
                self.init_yandex_music()
            

            if not self.yandex_music_client:
                return self.fallback_music_control(action)
            
            current_track = self.get_playback_state()
        
            if action == 'play_pause':
                if current_track and current_track['is_playing']:
                    self.yandex_music_client.play_pause()
                    self.async_speak("Пауза")
                else:
                    self.yandex_music_client.play_pause()
                    self.async_speak("Продолжаю")
                return True
            
            elif action == "next":
                self.yandex_music_client.next_track()
                self.async_speak("Следующий трек")
                return True
            
            elif action == "previous":
                self.yandex_music_client.previous_track()
                self.async_speak("Предыдущий трек")
                return True
            
            elif action == "stop":
                self.yandex_music_client.pause()
                self.async_speak("Остановлено")
                return True
            
        except Exception as e:
            print(f"Ошибка управления Яндекс Музыкой: {e}")
            return self.fallback_music_control(action)

    def fallback_music_control(self, action):
        try:
            if not self.is_yandex_music_running():
                os.startfile(self.yandex_music_path)
                time.sleep(2)

            if action == 'play_pause':
                keyboard.press_and_release('play/pause media')
                self.async_speak("Управляю музыкой")
            elif action == "next":
                keyboard.press_and_release('next track')
                self.async_speak("Следующий трек")
            elif action == "previous":
                keyboard.press_and_release('previous track')
                self.async_speak("Предыдущий трек")
            elif action == "stop":
                keyboard.press_and_release('play/pause media')
                self.async_speak("Остановлено")
            return True
        except Exception as e:
            print(f"Ошибка резервного управления: {e}")
            self.async_speak("Не удалось управлять музыкой")
            return False

    def is_yandex_music_running(self):
        try:
            output = subprocess.check_output('tasklist', shell=True).decode('cp866', 'ignore')
            return 'Яндекс Музыка' in output
        except:
            return False

    def is_music_playing(self):
        return self.is_yandex_music_running()

    def play_in_yandex_music(self, query):
        try:
            yandex_music_path = r"C:\Users\panas\AppData\Roaming\Microsoft\Windows\Start Menu\Programs\Яндекс Музыка.lnk"
        
            if not self.is_yandex_music_running():
                os.startfile(yandex_music_path)
                time.sleep(1)
        
            clean_query = re.sub(r'(пожалуйста|включи|найди|песню|трек|музыку|в яндекс музыке)', '', 
                           query, flags=re.IGNORECASE).strip()
        
            if not clean_query:
                self.async_speak("Не услышала название песни")
                return False
        
            time.sleep(0.5)
            pyautogui.press('enter')
            self.async_speak(f"Ищу {clean_query} в Яндекс.Музыке...")
            return True
        
        except Exception as e:
            print(f"Ошибка: {e}")
            self.async_speak("Не удалось включить песню в Яндекс.Музыке")
            return False

    def play_on_youtube(self, query):
        if query in self.youtube_cache:
            webbrowser.open(self.youtube_cache[query])
            self.async_speak("Включаю из кэша")
            return True
        try:
            from pytube import Search
            import urllib.parse

            s = Search(query)
            if not s.results:
                self.async_speak("ничего не найдено")
                return False

            video_url = f"https://youtube.com/watch?v={s.results[0].video_id}"
            webbrowser.open(video_url)
            self.async_speak(f"включаю {s.results[0].title}")

            self.youtube_cache[query] = video_url
            return True

        except Exception as e:
            print(f"Ошибка при поиске на YouTube: {e}")
            search_url = f"https://www.youtube.com/results?search_query={urllib.parse.quote(query)}"
            webbrowser.open(search_url)
            self.async_speak(f"Ищу {query} на Youtube")
            return False

    def configure_recognizer(self):
        self.recognizer.dynamic_energy_threshold = False
        self.recognizer.pause_threshold = self.pause_threshold
        self.recognizer.phrase_threshold = self.phrase_threshold
        self.recognizer.non_speaking_duration = 0.2
        self.recognizer.energy_threshold = self.initial_energy_threshold

    def init_volume(self):
        devices = AudioUtilities.GetSpeakers()
        interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
        return cast(interface, POINTER(IAudioEndpointVolume))

    def speak(self, text):
        print(f"[Пятница]: {text}")
        try:
            cache_file = self.get_tts_filename(text)

            if text in self.tts_cache and os.path.exists(self.tts_cache[text]):
                mixer.music.load(self.tts_cache[text])
                mixer.music.set_volume(self.tts_volume)
                mixer.music.play()

                while mixer.music.get_busy():
                    time.sleep(0.1)
            else:
                tts = gTTS(text=text, lang='ru')
                tts.save(cache_file)

                self.tts_cache[text] = cache_file
                mixer.music.load(cache_file)
                mixer.music.set_volume(self.tts_volume)
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
        audio_buffer = np.frombuffer(audio_data.get_raw_data(), dtype=np.int16)
        if len(audio_buffer) == 0:
            return 0
        return 20 * np.log10(np.sqrt(np.mean(audio_buffer**2)) + 1e-10)

    def update_energy_threshold(self, current_energy):
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
        self.is_active = True
        self.async_speak(random.choice([
            "Да, слушаю вас",
            "Я здесь",
            "Чем могу помочь?",
            "Готова помочь"
        ]))
        Thread(target=self.active_listening).start()

    def active_listening(self):
        with sr.Microphone() as source:
            print("[АКТИВНЫЙ РЕЖИМ] Готов к командам...")
            while self.is_active and not self.should_exit:
                try:
                    audio = self.recognizer.listen(
                        source,
                        timeout=None,
                        phrase_time_limit=5
                    )
                    
                    time.sleep(1.0)
                    
                    command = self.recognizer.recognize_google(audio, language="ru-RU").lower()
                    print(f"Распознано: {command}")
                    
                    command_processed = self.process_command(command)
                    
                    if command_processed:
                        self.return_to_sleep()
                
                except sr.UnknownValueError:
                    self.async_speak("Не расслышала команду, повторите пожалуйста")
                    continue
                except Exception as e:
                    print(f"Ошибка: {e}")
                    self.async_speak("Произошла ошибка, попробуйте еще раз")

    def calculate(self, expression):
        try:
            cleaned_expr = re.sub(r'[^\d+\-*/.()]', '', expression)
            if not cleaned_expr:
                raise ValueError("Пустое выражение")

            result = eval(cleaned_expr, {'__builtins__': None}, {})
            self.async_speak(f"Результат: {result}")
            return True
        except Exception as e:
            print(f"Ошибка вычисления: {e}")
            self.async_speak("Не удалось вычислить выражение")
            return False

    def start_music_player(self, player_name=None):
        try:
            app_name = player_name or 'default'
            if app_name in self.music_apps:
                path = self.music_apps[app_name]
                if os.path.exists(path):
                    os.startfile(path)
                    self.async_speak(f"Запускаю {app_name}")
                    return True
            
            commands = {
                'default': 'start yandexmusic:',
                'spotify': 'start spotify:',
                'yandex': 'start wmplayer'
            }
            subprocess.run(commands.get(app_name, commands['default']), shell=True)
            self.async_speak(f"Запускаю {app_name}")
            return True
            
        except Exception as e:
            print(f"Ошибка запуска плеера: {e}")
            self.async_speak("Не удалось запустить музыку")
            return False

    def set_volume(self, level):
        try:
            vol = max(0.0, min(1.0, level/100.0))
            self.volume_control.SetMasterVolumeLevelScalar(vol, None)
            self.async_speak(f"Громкость {int(level)}%")
            return True
        except Exception as e:
            print(f"Ошибка громкости: {e}")
            return False

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
            return True
        except Exception as e:
            print(f"Ошибка открытия погоды: {e}")
            self.async_speak("Не удалось открыть погоду")
            return False

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
        except Exception as e:
            print(f"Ошибка запуска {app_name}: {e}")
            self.async_speak(f"Не удалось запустить {app_name}")
            return False

    def process_command(self, command):
        if not command:
            return False
            
        print(f"Обработка команды: {command}")
        
        # Управление громкостью
        if "громкость" in command:
            if num := re.search(r'\d+', command):
                return self.set_volume(int(num.group()))
            elif "максимум" in command:
                return self.set_volume(100)
            elif "минимум" in command:
                return self.set_volume(0)
            elif "половина" in command:
                return self.set_volume(50)
        
        # Запуск музыки
        elif any(cmd in command for cmd in ["включи музыку", "запусти музыку"]):
            if "яндекс" in command or "yandex" in command:
                return self.start_music_player('yandex')
            elif "spotify" in command:
                return self.start_music_player('spotify')
            else:
                return self.start_music_player()

        # Переводчик
        elif any(cmd in command for cmd in ["переведи", "перевод", "как сказать"]):
            try:
                target_lang = 'русский'
                for lang in self.language_codes:
                    if lang in command:
                        target_lang = lang
                        break

                if "на" in command:
                    text_to_translate = command.split("на")[0].replace("переведи", "").strip()
                else:
                    text_to_translate = command.replace("переведи", "").replace("как будет", "").strip()

                if text_to_translate:
                    result = self.translate_text(text_to_translate, target_lang)

                    if result:
                        response = f"перевод на {target_lang}: {result['text']}"
                        if result['pronunciation']:
                            response += f"\nПроизношение: {result['pronunciation']}"
                        self.async_speak(response)
                        return True
                    else:
                        self.async_speak("Не удалось выполнить перевод")
                        return False
                else:
                    self.async_speak("Пожалуйста укажите текст для перевода")
                    return False
            except Exception as e:
                print(f"Ошибка обработки перевода: {e}")
                self.async_speak("Произошла ошибка при переводе")
                return False                  

        # Управление музыкой
        elif any(cmd in command for cmd in ["пауза", "останови музыку", "приостанови музыку"]):
            return self.control_yandex_music("play_pause")
        elif any(cmd in command for cmd in ["продолжи", "возобнови музыку"]):
            return self.control_yandex_music("play_pause")  
        elif any(cmd in command for cmd in ["следующий трек", "следующая песня", "дальше"]):
            return self.control_yandex_music("next")
        elif any(cmd in command for cmd in ["предыдущий трек", "предыдущая песня", "назад"]):
            return self.control_yandex_music("previous")
        elif any(cmd in command for cmd in ["останови музыку", "стоп"]):
            return self.control_yandex_music("stop")

        # Steam
        elif any(cmd in command for cmd in["запусти стим", "открой стим", "запусти steam"]):
            if not self.launch_app('steam'):
                self.async_speak("Steam не найден")
                return False
            return True
        
        # Telegram
        elif any(cmd in command for cmd in ["запусти телеграмм", "открой телеграмм", "открой telegram"]):
            if not self.launch_app('telegram'):
                self.async_speak("Telegram не найден")
                return False
            return True

        # Калькулятор
        elif any(cmd in command for cmd in ["посчитай", "вычисли", "сколько будет", "калькулятор"]):
            expr = command.replace("посчитай", "").replace("вычисли", "").replace("сколько будет", "").strip()
            if expr:
                return self.calculate(expr)
            else:
                self.async_speak("Пожалуйста, назовите выражение для вычисления")
                return False

        # Погода
        elif 'погода' in command:
            location = None
            if "погода в" in command:
                location = command.split("погода в")[1].strip()
            elif "погода" in command and len(command.split()) > 1:
                location = command.split("погода")[1].strip()

            return self.show_weather(location)

        # Поиск музыки
        elif "яндекс музыке" in command or "яндекс музыку" in command:
            try:
                if "включи" in command:
                    song_name = command.split("включи")[1].split("в яндекс музыке")[0].strip()
                elif "найди" in command:
                    song_name = command.split("найди")[1].split("в яндекс музыке")[0].strip()
                else:
                    song_name = command.split("в яндекс музыке")[0].strip()
        
                if song_name:
                    return self.play_in_yandex_music(song_name)
                else:
                    self.async_speak("Пожалуйста, назовите песню")
                    return False
            except Exception as e:
                print(f"Ошибка обработки команды: {e}")
                self.async_speak("Не удалось обработать команду")
                return False
                
        elif any(cmd in command for cmd in ["включи песню", "найди песню", "найди музыку", "включи музыку"]):
            song_name = command.replace("включи песню", "").replace("найди песню", "").replace("найди музыку", "").replace("включи музыку", "").strip()
            if song_name:
                return self.play_on_youtube(song_name)
            else:
                self.async_speak("Пожалуйста укажите название")
                return False

        # Калибровка
        elif "калибровка" in command:
            self.speak("Начинаю калибровку микрофона")
            self.calibrate_microphone(source=sys._getframe(1).f_locals.get('source'))
            return True
        
        # Прочие команды
        elif "спасибо" in command:
            self.async_speak("Всегда пожалуйста!")
            return True
        elif any(cmd in command for cmd in ["выход", "закройся"]):
            self.should_exit = True
            self.async_speak("Выключаюсь")
            return True
        else:
            self.async_speak("Не поняла команду")
            return False

    def return_to_sleep(self):
        if self.is_active:
            self.is_active = False
            print("Возврат в режим ожидания...")

    def calibrate_microphone(self, source):
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
        with sr.Microphone() as source:
            self.calibrate_microphone(source)
            
            try:
                self.speak("Пятница активирована.")
                while not self.should_exit:
                    try:
                        if not self.is_active and self.listen_for_trigger(source):
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
        assistant.save_tts_cache()