@echo off
:: Установка необходимых библиотек
pip install speechrecognition pycaw pyaudio comtypes numpy pygame pytube yandex-music gtts psutil pystray pillow keyboard plyer pyautogui deep-translator PyQt6 python-telegram-bot dotenv vosk requests ollama python-dotenv webbrowser levenshtein --no-warn-script-location 

:: Копирование в автозагрузку
copy "%~dp0FridayStart.bat" "%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\"

echo Установка завершена! Пятница будет запускаться автоматически.
pause