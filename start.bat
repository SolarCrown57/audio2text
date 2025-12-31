@echo off
chcp 65001 >nul 2>&1
echo ========================================
echo   Audio2Text - Real-time Subtitle
echo ========================================
echo.

cd /d "%~dp0server"

REM Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [Error] Python not found, please install Python 3.10+
    pause
    exit /b 1
)

REM Check .env file
if not exist ".env" (
    echo [Warning] .env config file not found
    echo Creating from .env.example...
    copy .env.example .env >nul
    echo.
    echo [Important] Please edit server\.env and fill in your DASHSCOPE_API_KEY
    echo Get it from: https://dashscope.console.aliyun.com/apiKey
    echo.
    pause
    exit /b 1
)

REM Check dependencies
echo [1/2] Checking dependencies...
pip show websockets >nul 2>&1
if errorlevel 1 (
    echo Installing dependencies...
    pip install -r requirements.txt
)

echo [2/2] Starting service...
echo.
echo WebSocket Server: ws://localhost:8765
echo Subtitle window started
echo.
echo Press Ctrl+C to stop
echo ========================================
echo.

python main.py

pause
