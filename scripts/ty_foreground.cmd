@echo off
REM NorthstarOS - foreground Ty campaign launcher.
REM Reuses scripts/continuous_loop.py and the frozen task registry.
REM Refuses before loading a model when the host cannot hold it plus the 3 GB floor.
REM Run in a visible terminal. No service, no scheduler, no elevation.
setlocal
cd /d "%~dp0.."
echo NorthstarOS foreground Ty campaign
echo.
python scripts\ty_foreground.py --max-tasks 3 --deadline-minutes 120 --max-consecutive-failures 2
set RC=%ERRORLEVEL%
echo.
echo exit=%RC%
if "%RC%"=="3" echo REFUSED: resource or readiness gate failed. Nothing was dispatched.
if "%RC%"=="4" echo Campaign ran but stopped without completing.
pause
endlocal
