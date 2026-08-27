@echo off
title Setup 8:00 AM Daily Job Hunter - AI Job Application Agent
cd /d "%~dp0"
echo ========================================================
echo   Setting up 8:00 AM Daily Automated Job Discovery Task
echo ========================================================

schtasks /create /tn "AI_Job_Hunter_Daily" /tr ""%~dp0run_dashboard.bat"" /sc daily /st 08:00 /f /rl HIGHEST

if %ERRORLEVEL% equ 0 (
    echo.
    echo [SUCCESS] Daily 8:00 AM Job Hunter task scheduled in Windows Task Scheduler!
    echo Every morning at 08:00 AM, the agent will hunt for jobs, score matches, and alert your Telegram.
) else (
    echo.
    echo [NOTICE] If permission was denied, please right-click this file and choose 'Run as administrator'.
)
echo ========================================================
pause
