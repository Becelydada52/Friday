@echo off
:: Скрытое выполнение Python-скрипта
start /B pythonw "%~dp0Friday.py" > "%~dp0Friday.log" 2>&1
exit