REM filepath: c:\Users\Zach\Desktop\Python\run_weather.bat
@echo off
cd /d "%~dp0"
echo Checking and installing dependencies...
python -c "import pystray, PIL, requests" 2>nul
if errorlevel 1 (
    echo Installing missing packages...
    python -m pip install -r requirements.txt
    if errorlevel 1 (
        echo Failed to install packages. Please run as administrator or install manually.
        pause
        exit /b 1
    )
)
echo Starting Weather App...
pythonw TempRain.py
if errorlevel 1 (
    echo Failed to start with pythonw, trying python with console...
    python TempRain.py
    pause
)
