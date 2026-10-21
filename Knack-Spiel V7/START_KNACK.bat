@echo off
setlocal
cd /d "%~dp0"

where py >nul 2>nul
if not errorlevel 1 goto start_with_py

where python >nul 2>nul
if not errorlevel 1 goto start_with_python

echo Python wurde nicht gefunden.
echo Bitte Python 3.10 oder neuer von https://www.python.org/downloads/ installieren.
echo Bei der Installation "Add Python to PATH" aktivieren.
pause
exit /b 1

:start_with_py
py -3 main.py
if errorlevel 1 pause
exit /b

:start_with_python
python main.py
if errorlevel 1 pause
exit /b

