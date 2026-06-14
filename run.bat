@echo off
cd /d "%~dp0"

if not exist venv (
    echo [RealtyVision] Creating virtual environment...
    python -m venv venv
    if errorlevel 1 (
        echo [ERROR] python not found. Install Python 3.10+ and add it to PATH.
        pause
        exit /b 1
    )
    call venv\Scripts\activate.bat
    echo [RealtyVision] Installing dependencies...
    pip install -r requirements.txt
    if errorlevel 1 (
        echo [ERROR] Failed to install dependencies.
        pause
        exit /b 1
    )
) else (
    call venv\Scripts\activate.bat
)

if not exist .env (
    copy .env.example .env > nul
    echo.
    echo [RealtyVision] .env file created from .env.example
    echo [RealtyVision] Open .env and fill in your API keys, then press any key.
    echo.
    pause > nul
)

echo.
echo [RealtyVision] Starting server at http://127.0.0.1:8000
echo [RealtyVision] Press Ctrl+C to stop.
echo.

python app.py
pause
