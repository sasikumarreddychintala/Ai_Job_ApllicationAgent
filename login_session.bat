@echo off
title Log in & Save Persistent Session - AI Job Application Agent
cd /d "%~dp0"
echo ========================================================
echo   Interactive Persistent Login Setup Mode
echo ========================================================
echo Opening browser window...
echo Please log into LinkedIn, Naukri, Indeed, or Google.
echo Once logged in, your session cookies are saved permanently!
echo ========================================================
python agent.py --login
pause
