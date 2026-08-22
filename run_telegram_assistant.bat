@echo off
title AI Job Application Agent - Interactive Telegram Assistant
echo ======================================================================
echo    🤖 AI Job Application Agent - 2-Way Interactive Telegram Bot
echo ======================================================================
echo.
echo Starting Interactive Telegram Assistant...
echo You can now send commands from your phone:
echo   - /search Python Bengaluru
echo   - /top
echo   - /stats
echo   - /resume [job_id]
echo   - /letter [job_id]
echo   - /outreach [job_id]
echo   - /prep [job_id]
echo.
python agent.py --telegram-bot
pause
