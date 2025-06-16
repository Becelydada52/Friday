@echo off
:: Установка необходимых библиотек
pip install speechrecognition pyttsx3 pycaw comtypes psutil numpy scipy pytube pyautogui gTTS googletrans==4.0.0-rc1 --no-warn-script-location

:: Копирование в автозагрузку
copy "%~dp0FridayStart.bat" "%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\"

echo Установка завершена! Пятница будет запускаться автоматически.
pause