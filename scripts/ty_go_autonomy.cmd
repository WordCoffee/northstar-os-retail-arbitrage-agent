@echo off
REM NorthstarOS - unattended Ty campaign over the OpenCode Go author lane.
REM Foreground only: closing this window ends the campaign. No service, no scheduler.
setlocal
cd /d "%~dp0.."
echo OpenCode Go author lane: opencode-go/deepseek-v4.1-flash
python scripts\go_usage.py --summary
echo.
python scripts\continuous_loop.py --status
echo.
python scripts\go_author.py --max-tasks 5
set RC=%ERRORLEVEL%
echo.
echo exit=%RC%
if "%RC%"=="1" echo One or more tasks failed or the quota gate halted the campaign.
pause
endlocal
