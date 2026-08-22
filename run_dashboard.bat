@echo off
title Personal AI Job Application Agent
echo ========================================================
echo   Launching Personal AI Job Application Agent Dashboard
echo ========================================================
echo.
start http://localhost:8000
python agent.py --ui --port 8000
pause
