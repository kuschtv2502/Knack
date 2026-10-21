@echo off
setlocal EnableExtensions DisableDelayedExpansion
title Knack V5 - Windows EXE erstellen

rem Diese Datei muss im entpackten Spielordner neben main.py liegen.
pushd "%~dp0"
if errorlevel 1 (
    echo [FEHLER] Der Spielordner kann nicht geoeffnet werden.
    pause
    exit /b 1
)

if not exist "main.py" (
    echo [FEHLER] main.py wurde nicht gefunden.
    echo Lege BUILD_KNACK_EXE.bat in den entpackten Ordner mit main.py.
    goto :fail
)
if not exist "knack\ui.py" (
    echo [FEHLER] knack\ui.py wurde nicht gefunden.
    echo Bitte das komplette RAR-Archiv entpacken, nicht nur die BAT.
    goto :fail
)

echo ============================================================
echo  KNACK V5 - EXE BUILD
echo ============================================================
echo.
echo [1/5] Python 3.10 oder neuer mit Tkinter suchen...
set "PY_CMD="
where py >nul 2>&1
if errorlevel 1 goto :try_python
py -3 -c "import sys, tkinter; sys.exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>&1
if not errorlevel 1 set "PY_CMD=py -3"

:try_python
if defined PY_CMD goto :python_found
where python >nul 2>&1
if errorlevel 1 goto :python_missing
python -c "import sys, tkinter; sys.exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>&1
if not errorlevel 1 set "PY_CMD=python"
if not defined PY_CMD goto :python_missing

:python_found
%PY_CMD% --version

echo.
echo [2/5] Isolierte Build-Umgebung vorbereiten...
if not exist ".build-venv\Scripts\python.exe" (
    %PY_CMD% -m venv ".build-venv"
    if errorlevel 1 goto :venv_error
)
set "VPY=%CD%\.build-venv\Scripts\python.exe"
"%VPY%" -c "import sys, tkinter; sys.exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>&1
if errorlevel 1 goto :venv_error

echo.
echo [3/5] PyInstaller in der Build-Umgebung installieren/aktualisieren...
echo       Beim ersten Aufruf wird eine Internetverbindung benoetigt.
"%VPY%" -m pip --disable-pip-version-check install --upgrade pyinstaller
if errorlevel 1 goto :pip_error

echo.
echo [4/5] Automatische Spieltests ausfuehren...
if exist "tests\test_engine.py" (
    "%VPY%" -m unittest discover -s tests
    if errorlevel 1 goto :test_error
) else (
    echo [INFO] Kein Tests-Ordner gefunden. Tests werden uebersprungen.
)

echo.
echo [5/5] Windows-EXE erstellen...
"%VPY%" -m PyInstaller ^
    --noconfirm ^
    --clean ^
    --onefile ^
    --windowed ^
    --name "Knack" ^
    --distpath "%CD%\dist" ^
    --workpath "%CD%\.build\work" ^
    --specpath "%CD%\.build" ^
    --paths "%CD%" ^
    "main.py"
if errorlevel 1 goto :build_error

if not exist "dist\Knack.exe" goto :build_error

echo.
echo ============================================================
echo  ERFOLG!  EXE erstellt:
echo  "%CD%\dist\Knack.exe"
echo ============================================================
echo.
echo Du kannst Knack.exe auf andere Windows-PCs kopieren.
echo Dort ist keine separate Python-Installation erforderlich.
echo Bei Netzwerkspielen muss die Firewall die EXE ggf. erlauben.
echo.
pause
popd
exit /b 0

:python_missing
echo.
echo [FEHLER] Python 3.10+ mit Tkinter wurde nicht gefunden.
echo Installiere Python fuer Windows von https://www.python.org/downloads/
echo Nutze die normale Windows-Installation inkl. Tcl/Tk/Tkinter.
echo Danach diese BAT erneut starten.
goto :fail

:venv_error
echo.
echo [FEHLER] Die Build-Umgebung konnte nicht eingerichtet werden.
echo Falls sie bereits besteht, loesche .build-venv und starte die BAT erneut.
goto :fail

:pip_error
echo.
echo [FEHLER] PyInstaller konnte nicht installiert werden.
echo Pruefe Internet, Proxy und pip-Fehlermeldungen oberhalb.
goto :fail

:test_error
echo.
echo [FEHLER] Die Spieltests sind fehlgeschlagen. Build abgebrochen.
goto :fail

:build_error
echo.
echo [FEHLER] PyInstaller konnte keine Knack.exe erzeugen.
echo Pruefe die Fehlermeldungen oberhalb.
goto :fail

:fail
echo.
pause
popd
exit /b 1
