@echo off
REM F5 EoS / EoL Finder - Windows launcher.
REM Creates a virtualenv on first run, installs deps, starts the web app,
REM and opens it in your browser.

setlocal
cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 (
    echo Error: Python is not installed or not on PATH.
    echo Install Python 3.10+ from https://www.python.org/downloads/
    echo During install, check "Add Python to PATH", then re-run this script.
    pause
    exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
    echo Setting up virtualenv ^(one-time, ~10 seconds^)...
    python -m venv .venv
)

call .venv\Scripts\activate.bat
python -m pip install --quiet --upgrade pip
python -m pip install --quiet -r requirements.txt

echo.
echo Starting F5 EoS / EoL Finder at http://127.0.0.1:5000
echo Press Ctrl+C to stop.
echo.

start "" http://127.0.0.1:5000
python app.py
