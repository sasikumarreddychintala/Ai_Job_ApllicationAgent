@echo off
title AI Job Application Agent - Telegram Bot Listener
cd /d "%~dp0"

echo ========================================================
echo   Starting Telegram AI Job Assistant Listener...
echo ========================================================
echo.

call venv\Scripts\activate.bat 2>nul
if errorlevel 1 (
    echo [INFO] Running with Python...
    python -c "from src.notifications.telegram_bot import telegram_bot; import time; telegram_bot.start(); print('Telegram Bot Listening... (Press Ctrl+C to stop)'); [time.sleep(1) for _ in iter(int, 1)]"
) else (
    echo [INFO] Running with venv Python...
    python -c "from src.notifications.telegram_bot import telegram_bot; import time; telegram_bot.start(); print('Telegram Bot Listening... (Press Ctrl+C to stop)'); [time.sleep(1) for _ in iter(int, 1)]"
)

pause
