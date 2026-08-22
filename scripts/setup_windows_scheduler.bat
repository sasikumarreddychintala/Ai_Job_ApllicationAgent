@echo off
echo Setting up Automated Morning Job Discovery (with Wake-up support)...
powershell -Command "$action = New-ScheduledTaskAction -Execute 'python' -Argument '%~dp0..\agent.py --discover-jobs --analyze-jobs --match-jobs --tailor-resumes'; $trigger = New-ScheduledTaskTrigger -Daily -At 08:00AM; $settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -WakeToRun; Register-ScheduledTask -TaskName 'AI_Job_Agent_Morning_Discovery' -Action $action -Trigger $trigger -Settings $settings -Force"
echo.
echo [SUCCESS] Windows Scheduled Task registered with Wake-To-Run support!
echo Every morning at 8:00 AM, your computer will automatically:
echo  1. Wake up / run discovery across 10+ platforms
echo  2. Score each job against your resume
echo  3. Generate tailored PDF resumes for top matches
echo  4. Send mobile push alerts to your Telegram phone
pause
