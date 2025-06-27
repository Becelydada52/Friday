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
from threading import Thread
import pickle
import hashlib
from deep_translator import GoogleTranslator
from deep_translator.exceptions import TranslationNotFound
import psutil
import pystray
from PIL import Image
import threading
import keyboard
from plyer import notification
import math

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
        self.volume_control = None
        self.recognizer = sr.Recognizer()
        self.configure_recognizer()
        self.energy_history = deque(maxlen=15)

        # TTS и кэш
        self.tts_cache = {}
        self.load_tts_cache()
        self.tts_volume = 0.5
        self.load_knowledge()

        self.custom_apps = {}




        # Пути к приложениям
        self.music_apps = {
            'default': os.path.expanduser('~') + r'\AppData\Roaming\Microsoft\Windows\Start Menu\Programs\Яндекс Музыка.lnk',
            'spotify': os.path.expanduser('~') + r'\AppData\Roaming\Spotify\Spotify.exe',
            'yandex': r'C:\Program Files\Windows Media Player\wmplayer.exe',
        }
        
        self.app_paths = {
            'steam': r'C:\Program Files (x86)\Steam\steam.exe',
            'telegram': os.path.expanduser('~') + r'\AppData\Roaming\Telegram Desktop\Telegram.exe',
            'explorer': 'explorer.exe'
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
        self.yandex_music_token = ""
        self.init_yandex_music()

        self.tray_icon = None
        self.tray_thread = None
        self.hotkey_thread = None
        self.setup_tray_icon()
        self.setup_hotkeys()

        # Личностные настройки
        self.personality = {
            'name': 'Пятница',
            'mood': 'neutral',
            'verbosity': 'normal',
            'learning_mode': False
        }
        
        # Эмоциональные реакции
        self.responses = {
            'greeting': {
                'neutral': ["Да, слушаю вас", "Я здесь"],
                'happy': ["Рада вас слышать!", "Привет! Чем могу помочь?"],
                'sad': ["Да...", "Слушаю..."]
            },
            'error': {
                'neutral': ["Не удалось выполнить действие"],
                'happy': ["Ой, что-то пошло не так, давайте попробуем еще раз!"],
                'sad': ["Не получилось... Извините..."]
            },
            'farewell': {
                'neutral': ["Выключаюсь"],
                'happy': ["До скорой встречи!"],
                'sad': ["Пока..."]
            }
        }

        self.app_name_mapping = {
            'проводник': 'explorer',
            'браузер': 'yandex',
            'телеграм': 'telegram',
            'стим': 'steam',
            'word': 'winword',
            'excel': 'excel',
            'дискорд': 'discord'
        }
        
        # История разговоров и база знаний
        self.conversation_history = deque(maxlen=10)
        self.knowledge_base = {
            'user_preferences': {},
            'learned_commands': {},
            'facts': {},
            'jokes': [
                "Почему программист всегда холодный? Потому что у него windows открыты!",
                "Что сказал один байт другому? Будем битами!"
            ]
        }
        
        # Переводчик
        self.language_codes = {
            'английский': 'en',
            'русский': 'ru',
            'французский': 'fr',
            'немецкий': 'de',
            'испанский': 'es',
            'китайский': 'zh-cn',
            'японский': 'ja'
        }

        self.activation_phrases.extend(['переведи', 'перевод', 'как сказать'])
        self.setup_learned_commands()
        self.preload_common_phrases()

        self.cleanup_old_tts_cache()

        self.volume_control = self.init_volume()

    # ========== Базовые функции ==========

    def cleanup_old_tts_cache(self, max_age_days=7):
        cache_dir = tempfile.gettempdir()
        now = time.time()
        cutoff = now - (max_age_days * 86400)

        for filename in os.listdir(cache_dir):
            if filename.startswith('tts_') and filename.endswith('.mp3'):
                filepath = os.path.join(cache_dir, filename)
                try:
                    if os.path.getmtime(filepath) < cutoff:
                        os.remove(filepath)
                except Exception as e:
                    print(f"Ошибка удаления кэша {filename}: {e}")

    def open_settings(self):
        self.settings_window = SettingsWindow()
        self.settings_window.show()
        self.async_speak("Открываю настройки")  

    def load_settings(self):
        self.tts_volume = self.settings.value("voice_volume", 50) / 100
        self.recognizer.energy_threshold = self.settings.value("mic_sensitivity", 4000)

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

    # ========== Функции личности ==========
    def get_response(self, response_type):
        mood_responses = self.responses.get(response_type, {}).get(self.personality['mood'], [])
        default_responses = self.responses.get(response_type, {}).get('neutral', ["..."])
        return random.choice(mood_responses if mood_responses else default_responses)

    def adjust_personality(self):
        recent_interactions = [i for i in list(self.conversation_history)[-5:] if isinstance(i, dict)]
        
        if recent_interactions:
            success_rate = sum(1 for i in recent_interactions if i.get('success', False)) / len(recent_interactions)
            avg_length = sum(len(i.get('command', '')) for i in recent_interactions) / len(recent_interactions)
            
            if success_rate > 0.8:
                self.personality['mood'] = 'happy'
            elif success_rate < 0.3:
                self.personality['mood'] = 'sad'
            else:
                self.personality['mood'] = 'neutral'
                
            if avg_length > 30:
                self.personality['verbosity'] = 'detailed'
            elif avg_length < 15:
                self.personality['verbosity'] = 'concise'
            else:
                self.personality['verbosity'] = 'normal'

    # ========== Функции обучения ==========
    def setup_learned_commands(self):
        self.learn_command(
            r'запомни что (.*) это (.*)',
            self._learn_fact_command,
            "Запоминание фактов: 'запомни что Земля это планета'"
        )
        
        self.learn_command(
            r'(какое|какой|что такое) (.*)\?',
            self._recall_fact_command,
            "Вспомнить факт: 'какое небо?'"
        )
        
        self.learn_command(
            r'(расскажи шутку|пошути|рассмеши меня)',
            self._tell_joke_command,
            "Рассказать шутку"
        )
        
        self.learn_command(
            r'(как тебя зовут|твое имя)',
            self._tell_name_command,
            "Представиться"
        )

    def learn_command(self, command_pattern, action_func, description=""):
        command_id = hashlib.md5(command_pattern.encode()).hexdigest()
        self.knowledge_base['learned_commands'][command_id] = {
            'pattern': command_pattern,
            'action': action_func,
            'description': description,
            'usage_count': 0
        }
        self.save_knowledge()

    def find_application(self, app_name):
        """Пытается найти приложение в стандартных местах с проверкой исполняемого файла"""
        common_paths = [
            r"C:\Program Files",
            r"C:\Program Files (x86)",
            os.path.expanduser("~") + r"\AppData\Roaming\Microsoft\Windows\Start Menu\Programs",
            os.path.expanduser("~") + r"\Desktop"
        ]
    
        # Проверяем известные расширения
        extensions = ['.exe', '.lnk', '.bat']
    
        for path in common_paths:
            for root, dirs, files in os.walk(path):
                for file in files:
                    # Ищем файлы, содержащие название приложения
                    if app_name.lower() in file.lower():
                        for ext in extensions:
                            if file.lower().endswith(ext):
                                full_path = os.path.join(root, file)
                                # Дополнительная проверка для .exe файлов
                                if ext == '.exe':
                                    try:
                                        # Проверяем, является ли файл исполняемым
                                        if os.access(full_path, os.X_OK):
                                            return full_path
                                    except:
                                        continue
                                else:
                                    return full_path
        return None

    def learn_from_interaction(self, command, success):
        clean_command = re.sub(r'\b(пожалуйста|сейчас|мне|можно|бы|ли)\b', '', command, flags=re.IGNORECASE).strip()
        
        if not success and self.personality['learning_mode']:
            self.async_speak("Я не знаю как ответить на это. Не могли бы вы научить меня?")
            
        self.conversation_history.append({
            'command': command,
            'success': success,
            'timestamp': time.time()
        })
        
        self.adjust_personality()

    def save_knowledge(self):
        try:
            with open('friday_knowledge.pkl', 'wb') as f:
                data = {
                    'facts': self.knowledge_base['facts'],
                    'jokes': self.knowledge_base['jokes'],
                    'learned_commands': self.knowledge_base['learned_commands'],
                    'custom_apps': self.custom_apps
                }
                pickle.dump(data, f)
        except Exception as e:
            print(f"Ошибка сохранения знаний: {e}")

    def load_knowledge(self):
        try:
            if os.path.exists('friday_knowledge.pkl'):
                with open('friday_knowledge.pkl', 'rb') as f:
                    if os.path.getsize('friday_knowledge.pkl') > 0:
                        data = pickle.load(f)
                        self.knowledge_base['facts'] = data.get('facts', {})
                        self.knowledge_base['jokes'] = data.get('jokes', [])
                        self.knowledge_base['learned_commands'] = data.get('learned_commands', {})
                        self.custom_apps = data.get('custom_apps', {})
        except Exception as e:
            print(f"Ошибка загрузки знаний: {e}")

            self.knowledge_base = {'facts': {}, 'jokes': [], 'learned_commands': {}}

    # ========== Обработчики изученных команд ==========
    def _learn_fact_command(self, command):
        match = re.match(r'запомни что (.*) это (.*)', command, re.IGNORECASE)
        if match:
            key, value = match.groups()
            self.knowledge_base['facts'][key.strip().lower()] = value.strip()
            self.save_knowledge()
            self.async_speak(f"Запомнила: {key} это {value}")
            return True
        return False
        
    def _recall_fact_command(self, command):
        match = re.match(r'(какое|какой|что такое) (.*)\?', command, re.IGNORECASE)
        if match:
            item = match.group(2).strip().lower()
            if item in self.knowledge_base['facts']:
                self.async_speak(f"{item.capitalize()} это {self.knowledge_base['facts'][item]}")
            else:
                self.async_speak(f"Я не знаю что такое {item}")
            return True
        return False

    def _tell_joke_command(self, command):
        if self.knowledge_base['jokes']:
            joke = random.choice(self.knowledge_base['jokes'])
            self.async_speak(joke)
            return True
        self.async_speak("Я пока не знаю шуток. Научите меня!")
        return False

    def _tell_name_command(self, command):
        moods = {
            'happy': f"Меня зовут {self.personality['name']}! Рада познакомиться!",
            'sad': f"{self.personality['name']}...",
            'neutral': f"Меня зовут {self.personality['name']}."
        }
        self.async_speak(moods.get(self.personality['mood'], moods['neutral']))
        return True

    def handle_unknown_command(self, command):
        if not command:
            return False
            
        self.async_speak("Я не знаю такой команды. Скажите 'Да', чтобы научить меня, или 'Нет', чтобы пропустить.")
        response = self.listen_for_response()

        if response and "да" in response.lower():
            self.async_speak("Что мне делать, когда вы говорите: " + command + "?")
            action_description = self.listen_for_response()

            if action_description:
                self.learn_new_command(
                    command_pattern=command,
                    action=lambda: self.execute_custom_action(action_description),
                    description=f"Пользовательская команда: {action_description}"
                )
                self.async_speak("Теперь я знаю эту команду! Попробуйте сказать её снова.")
                return True
            else:
                self.async_speak("Не расслышала действие. Попробуйте позже.")
                return False
        else:
            return False

    def execute_custom_action(self, action_description):
        try:
            action_description = action_description.lower()
        
            if "открой" in action_description:
                app_name = action_description.replace("открой", "").strip()
                # Проверяем системные имена приложений
                if app_name in self.app_name_mapping:
                    app_name = self.app_name_mapping[app_name]
                
                paths_to_check = [
                    r"C:\Program Files",
                    r"C:\Program Files (x86)",
                    os.path.expanduser("~") + r"\AppData\Roaming\Microsoft\Windows\Start Menu\Programs"
                ]
                
                for path in paths_to_check:
                    for root, dirs, files in os.walk(path):
                        if app_name + ".exe" in files:
                            os.startfile(os.path.join(root, app_name + ".exe"))
                            return True
                            
                # Если не нашли, пробуем стандартные пути
                if app_name in self.app_paths:
                    os.startfile(self.app_paths[app_name])
                    return True
                    
                self.async_speak(f"Не нашла приложение {app_name}.")
                return False
            
            elif "закрой" in action_description:
                app_name = action_description.replace("закрой", "").strip()
                return self.close_app(app_name)
            
            else:
                self.async_speak("Я пока не умею это делать.")
                return False
        except Exception as e:
            print(f"Ошибка: {e}")
            return False

    # ========== Основные функции ассистента ==========
    def speak(self, text):
        if not text:
            return
            
        print(f"[{self.personality['name']}]: {text}")
        try:
            cache_file = self.get_tts_filename(text)

            cache_dir = os.path.dirname(cache_file)
            if not os.path.exists(cache_dir):
                os.makedirs(cache_dir)

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
                    
            # Освобождаем ресурсы
            mixer.music.unload()
        except Exception as e:
            print(f"Ошибка воспроизведения: {e}")
            print(f"(Ошибка TTS): {text}")

    def get_running_apps(self):
        running_apps = {}
        for proc in psutil.process_iter(['name', 'pid', 'exe']):
            try:
                app_name = proc.info['name'].replace('.exe', '').lower()
                running_apps[app_name] = proc
            except Exception as e:
                continue
        return running_apps

    def async_speak(self, text):
        if not text:
            return
            
        thread = Thread(target=self.speak, args=(text,))
        thread.start()

    def calculate_audio_energy(self, audio_data):
        if not audio_data:
            return 0
            
        audio_buffer = np.frombuffer(audio_data.get_raw_data(), dtype=np.int16)
        if len(audio_buffer) == 0:
            return 0
        return 20 * np.log10(np.sqrt(np.mean(audio_buffer**2)) + 1e-10)

    def update_energy_threshold(self, current_energy):
        if current_energy <= 0:
            return
            
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

    def listen_for_response(self, timeout=5):
        with sr.Microphone() as source:
            print("Слушаю")
            try:
                audio = self.recognizer.listen(source, timeout=timeout)
                text = self.recognizer.recognize_google(audio, language="ru-RU").lower()
                return text
            except sr.UnknownValueError:
                return None
            except sr.RequestError:
                return None
            except Exception as e:
                print(f"Ошибка при прослушивании: {e}")
                return None

    def load_tray_image(self):
        try:
            icon_path = os.path.join("assets", "friday_icon.png")
            return Image.open(icon_path)
        except Exception as e:
            print(f"Ошибка загрузки иконки: {e}. Используется стандартная иконка.")
            image = Image.new('RGB', (64, 64), 'black')
            return image

    def setup_tray_icon(self):
        image = self.load_tray_image()
        menu = (
            pystray.MenuItem("Активировать", self.wake_up),
            pystray.MenuItem("Настройки", self.open_settings),
            pystray.MenuItem("Выход", self.exit_app),
        )
        self.tray_icon = pystray.Icon("Friday", image, "Friday Assistant", menu)
        threading.Thread(target=self.tray_icon.run, daemon=True).start()

    def apply_settings(self, settings):
        self.tts_volume = settings.value("voice_volume", 50) / 100
        self.recognizer.energy_threshold = settings.value("mic_sensivity", 4000)

    def setup_hotkeys(self):
        keyboard.add_hotkey('ctrl+alt+f', self.wake_up)
        self.hotkey_thread = threading.Thread(target=keyboard.wait, daemon=True)
        self.hotkey_thread.start()
   

    def exit_app(self):
        self.should_exit = True
        if self.tray_icon:
            self.tray_icon.stop()
        self.async_speak("Выключаюсь. До свидания!")
        sys.exit(0)

    def show_notification(self, title, message):
        try:
            notification.notify(
                title=title,
                message=message,
                app_name="Friday Assistant",
                timeout=5
            )
        except Exception as e:
            print(f"Ошибка уведомления: {e}")

    def wake_up(self):
        self.is_active = True
        self.async_speak(self.get_response('greeting'))
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
                    self.async_speak(self.get_response('error'))
                    continue
                except Exception as e:
                    print(f"Ошибка: {e}")
                    self.async_speak(self.get_response('error'))

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

    def learn_new_command(self, command_pattern, action_func, description=""):
        command_id = hashlib.md5(command_pattern.encode()).hexdigest()
        self.knowledge_base['learned_commands'][command_id] = {
            'pattern': command_pattern,
            'action': action_func,
            'description': description,
            'usage_count': 0
        }
        self.save_knowledge() 

    # ========== Функции приложений ==========
    def calculate(self, expression):
        try:
            if not expression:
                raise ValueError("Пустое выражение")

            # Безопасные математические функции
            safe_dict = {
                'abs': abs,
                'ceil': math.ceil,
                'floor': math.floor,
                'round': round,
                'sqrt': math.sqrt,
                'sin': math.sin,
                'cos': math.cos,
                'tan': math.tan,
                'pi': math.pi,
                'e': math.e
            }

            # Очищаем выражение от опасных символов
            cleaned_expr = re.sub(r'[^0-9+\-*/.()^% ]', '', expression)
            
            # Проверяем на наличие опасных конструкций
            if re.search(r'(__|import|exec|eval|open|file|lambda|compile)', cleaned_expr):
                raise ValueError("Недопустимое выражение")

            # Вычисляем с ограниченным контекстом
            result = eval(cleaned_expr, {'__builtins__': None}, safe_dict)
            self.async_speak(f"Результат: {result}")
            return True
        except Exception as e:
            print(f"Ошибка вычисления: {e}")
            self.async_speak("Не удалось вычислить выражение")
            return False
        
    def handle_system_commands(self, command):
        if not command:
            return False
            
        # Закрытие приложений
        if any(cmd in command for cmd in ["закрой приложение", "заверши процесс", "закрой программу"]):
            app_name = re.sub(r'(закрой|приложение|программу|процесс)', '', command, flags=re.IGNORECASE).strip()
            if not app_name:
                self.async_speak("Укажите название приложения, например: 'закрой приложение проводник'.")
                return False
            return self.close_app(app_name)
    
        # Список запущенных приложений
        elif any(cmd in command for cmd in ["какие приложения открыты", "список программ"]):
            running_apps = ", ".join(self.get_running_apps().keys())
            self.async_speak(f"Запущены: {running_apps}")
            return True
    
        return False
        
    def close_app(self, app_name):
        if not app_name:
            self.async_speak("Не услышала название приложения. Попробуйте ещё раз.")
            return False

        system_name = self.app_name_mapping.get(app_name.lower(), app_name.lower())
        running_apps = self.get_running_apps()

        if system_name not in running_apps:
            similar = [name for name in running_apps if app_name.lower() in name]
            if similar:
                self.async_speak(f"Найдены похожие приложения: {', '.join(similar)}. Уточните название.")
            else:
                self.async_speak(f"Приложение '{app_name}' не найдено.")
            return False

        try:
            proc = running_apps[system_name]
            proc.kill()
            self.async_speak(f"Закрываю {app_name}.")
            return True
        except Exception as e:
            print(f"Ошибка закрытия {app_name}: {e}")
            self.async_speak(f"Не удалось закрыть {app_name}.")
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

    def set_voice_volume(self, level):
        try:
            level = max(0, min(100, level))
            self.tts_volume = level / 100

            response = f"Громкость голоса установлена на {level}%"
            self.async_speak(response)
            return True
        except Exception as e:
            print(f"Ошибка установки уровня громкости голоса: {e}")
            self.async_speak("Не удалось изменить громкость голоса")
            return False

    def adjust_voice_volume(self, direction):
        try:
            step = 20
            current = int(self.tts_volume * 100)

            if direction == "up":
                new_level = min(100, current + step)
            else:
                new_level = max(0, current - step)

            return self.set_voice_volume(new_level)
        except Exception as e:
            print(f"Ошибка регулировки громкости: {e}")
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
            # Сначала проверяем стандартные приложения
            if app_name in self.app_paths:
                path = self.app_paths[app_name]
                if os.path.exists(path):
                    os.startfile(path)
                    self.async_speak(f"Запускаю {app_name}")
                    return True
                else:
                    self.async_speak(f"{app_name} не найден по указанному пути")
                    return False
        
            # Затем проверяем пользовательские приложения
            if app_name in self.custom_apps:
                path = self.custom_apps[app_name]
                if os.path.exists(path):
                    os.startfile(path)
                    self.async_speak(f"Запускаю {app_name}")
                    return True
                else:
                    del self.custom_apps[app_name]  # Удаляем нерабочий путь
                    self.save_knowledge()
        
            # Пытаемся найти приложение автоматически
            found_path = self.find_application(app_name)
            if found_path:
                self.custom_apps[app_name] = found_path
                self.save_knowledge()
                os.startfile(found_path)
                self.async_speak(f"Нашла и запускаю {app_name}")
                return True
        
            # Если не нашли, предлагаем обучение
            self.async_speak(f"Не знаю, где находится {app_name}. Хотите указать путь?")
            response = self.listen_for_response()
        
            if response and "да" in response.lower():
                self.async_speak("Пожалуйста, скажите полный путь к приложению")
                path_response = self.listen_for_response()
                if path_response:
                    # Очищаем путь от лишних слов
                    clean_path = re.sub(r'(путь|приложение|это|находится)', '', path_response, flags=re.IGNORECASE).strip()
                    if os.path.exists(clean_path):
                        self.custom_apps[app_name] = clean_path
                        self.save_knowledge()
                        os.startfile(clean_path)
                        self.async_speak(f"Запомнила и запускаю {app_name}")
                        return True
                    else:
                        self.async_speak("Не могу найти указанный путь. Попробуйте еще раз.")
                        return False
        
            self.async_speak(f"Не удалось запустить {app_name}")
            return False
        
        except Exception as e:
            print(f"Ошибка запуска {app_name}: {e}")
            self.async_speak(f"Не удалось запустить {app_name}")
            return False

    def control_yandex_music(self, action):
        """Управление музыкой с автоматическим fallback"""
        # Если есть клиент Яндекс.Музыки, пробуем использовать его
        if self.yandex_music_client:
            try:
                playback_state = self.get_playback_state()
            
                if action == 'play_pause':
                    keyboard.press_and_release('play/pause media')
                    self.async_speak("Пауза" if playback_state and playback_state['is_playing'] else "Продолжаю")
                    return True

                elif action == "next":
                    keyboard.press_and_release('next track')
                    self.async_speak("Следующий трек")
                    return True

                elif action == "previous":
                    keyboard.press_and_release('previous track')
                    self.async_speak("Предыдущий трек")
                    return True

                elif action == "stop":
                    keyboard.press_and_release('play/pause media')
                    self.async_speak("Остановлено")
                    return True
                
            except Exception as e:
                print(f"Ошибка управления Яндекс Музыкой: {e}")

                return self.fallback_music_control(action)
        
        return self.fallback_music_control(action)
        
    def init_yandex_music(self):
        """Инициализация клиента Яндекс.Музыки с проверкой токена"""
        if not self.yandex_music_token:
            print("Токен Яндекс.Музыки не указан, используется fallback-режим")
            self.yandex_music_client = None
            return False
            
        try:
            self.yandex_music_client = Client(self.yandex_music_token).init()
            print("Яндекс.Музыка: авторизация успешна")
            return True
        except Exception as e:
            print(f"Ошибка авторизации Яндекс.Музыки: {e}")
            self.yandex_music_client = None
            return False
    def get_playback_state(self):
        try:
            if not self.yandex_music_client:
                return None

            queues = self.yandex_music_client.queues_list()
            if not queues:
                return None
            
            queue = self.yandex_music_client.queue(queues[0].id)
            current_track = queue.get_current_track()
            return {
                'is_playing': queue.get_playing_state(),
                'track': current_track,
                'track_title': f"{current_track['title']} - {current_track['artists'][0]['name']}" if current_track else None
            }
        except Exception as e:
            print(f"Ошибка получения состояния: {e}")
            return None

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


    def fallback_play_music(self, query):
        """Fallback реализация для воспроизведения музыки"""
        self.async_speak("Использую резервный метод воспроизведения")
        return self.play_on_youtube(query)

    def is_yandex_music_running(self):
        try:
            output = subprocess.check_output('tasklist', shell=True).decode('cp866', 'ignore')
            return 'Яндекс Музыка' in output
        except:
            return False

    def play_in_yandex_music(self, query):
        """Поиск музыки с автоматическим fallback"""
        # Если нет клиента Яндекс.Музыки, используем fallback
        if not self.yandex_music_client:
            return self.fallback_play_music(query)
            
        try:
            if not self.is_yandex_music_running():
                os.startfile(self.yandex_music_path)
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
            return self.fallback_play_music(query)

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

    def translate_text(self, text, target_lang='ru'):
        try:
            lang_code = self.language_codes.get(target_lang, target_lang)
        

            translation = GoogleTranslator(
                source='auto',  
                target=lang_code
            ).translate(text)
        
            return {
                'text': translation,
                'pronunciation': None, 
                'src_lang': 'auto',
                'dest_lang': lang_code
            }
        
        except TranslationNotFound:
            print("Перевод не найден")
            return None
        except Exception as e:
            print(f"Ошибка перевода: {e}")
            return None

    def get_tts_filename(self, text):
        text_hash = hashlib.md5(text.encode('utf-8')).hexdigest()
        return os.path.join(tempfile.gettempdir(), f'tts_{text_hash}.mp3')

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

    def app_exists(self, app_name):
        """Проверяет, установлено ли приложение."""
        common_paths = [
            r"C:\Program Files",
            r"C:\Program Files (x86)",
            os.path.expanduser("~") + r"\AppData\Roaming\Microsoft\Windows\Start Menu\Programs"
        ]
        for path in common_paths:
            if os.path.exists(os.path.join(path, app_name + ".exe")):
                return True
        return False

    # ========== Обработка команд ==========
    def process_command(self, command):
        if not command:
            return False
        
    # 1. Проверяем изученные команды
        for cmd_id, cmd_data in self.knowledge_base['learned_commands'].items():
            if re.search(cmd_data['pattern'], command, re.IGNORECASE):
                try:
                    result = cmd_data['action'](command)
                    cmd_data['usage_count'] += 1
                    self.learn_from_interaction(command, True)
                    return result
                except Exception as e:
                    print(f"Ошибка выполнения команды: {e}")
    
    # 2. Проверяем встроенные команды
        command_processed = self._process_builtin_command(command)
        if command_processed:
            self.learn_from_interaction(command, True)
            return True
        
    # 3. Предлагаем обучение (если команда неизвестна)
        if self.handle_unknown_command(command):  
            return True
        else:  
            self.async_speak("Не поняла команду")
            return False
        
    def _process_builtin_command(self, command):
        """Обработка встроенных команд"""
        # Управление громкостью

        if "громкость" in command and not any(w in command for w in ['голоса', "речи", "голос"]):

            if num := re.search(r'\d+', command):
                return self.set_volume(int(num.group()))
            elif "максимум" in command:
                return self.set_volume(100)
            elif "минимум" in command:
                return self.set_volume(0)
            elif "половина" in command:
                return self.set_volume(50)


        elif any(phrase in command for phrase in ["громкость голоса", "громкость речи", "голос на", "речь на"]):
            if num := re.search(r'\d+', command):
                return self.set_voice_volume(int(num.group()))
            elif "максимум" in command:
                return self.set_voice_volume(100)
            elif "минимум" in command:
                return self.set_voice_volume(0)
            elif "половина" in command:
                return self.set_voice_volume(50)
            else:
                self.async_speak("Пожалуйста, укажите уровень громкости в процентах")
                return False
                
        # Регулировка громкости голоса
        elif any(phrase in command for phrase in ["громче голос", "громче речь", "сделай голос громче", "говори громче"]):
            return self.adjust_voice_volume("up")
            
        elif any(phrase in command for phrase in ["тише голос", "тише речь", "сделай голос тише", "говори тише"]):
            return self.adjust_voice_volume("down")
        
        # Запуск музыки
        elif any(cmd in command for cmd in ["включи музыку", "запусти музыку"]):
            if "яндекс" in command or "yandex" in command:
                return self.start_music_player('yandex')
            elif "spotify" in command:
                return self.start_music_player('spotify')
            else:
                return self.start_music_player()

        if command.startswith(("открой", "запусти")):
            app_name = re.sub(r'^(открой|запусти)\s*', '', command, flags=re.IGNORECASE).strip()
            if app_name:
                return self.launch_app(app_name)

        # Переводчик
        elif any(cmd in command for cmd in ["переведи", "перевод", "как сказать"]):
            try:
        # Определяем целевой язык
                target_lang = 'русский'
                for lang in self.language_codes:
                    if lang in command:
                        target_lang = lang
                        break

        # Извлекаем текст для перевода
                if "на" in command:
                    text_to_translate = command.split("на")[0].replace("переведи", "").strip()
                else:
                    text_to_translate = command.replace("переведи", "").replace("как будет", "").strip()

                if text_to_translate:
                    result = self.translate_text(text_to_translate, target_lang)
                if result:
                    response = f"Перевод на {target_lang}: {result['text']}"
                    self.async_speak(response)
                    return True
                else:
                    self.async_speak("Не удалось выполнить перевод")
                    return False
            except Exception as e:
                print(f"Ошибка обработки перевода: {e}")
                self.async_speak("Ошибка при переводе")
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
        
        if self.handle_system_commands(command):
            return True
        


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
            self.async_speak(self.get_response('farewell'))
            return True
        else:
            self.async_speak("Не поняла команду")
            return False

    def run(self):
        with sr.Microphone() as source:
            self.calibrate_microphone(source)
            
            try:
                self.async_speak(self.get_response('greeting'))
                
                while not self.should_exit:
                    try:
                        if not self.is_active and self.listen_for_trigger(source):
                            self.wake_up()
                            self.adjust_personality()
                            
                        time.sleep(0.05)
                            
                    except Exception as e:
                        print(f"Ошибка в основном цикле: {e}")
                        self.calibrate_microphone(source)
                        
            except KeyboardInterrupt:
                self.speak(self.get_response('farewell'))
            except Exception as e:
                print(f"Критическая ошибка: {e}")
                self.speak("Произошла системная ошибка. Попробуйте перезапустить меня.")
            finally:
                self.save_tts_cache()
                self.save_knowledge()

if __name__ == '__main__': 
    assistant = FridayAssistant()
    try:
        assistant.run()
    except KeyboardInterrupt:
        assistant.exit_app()
    finally:
        assistant.save_tts_cache()
        assistant.save_knowledge()