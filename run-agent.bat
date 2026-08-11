@echo off
cd /d "%~dp0"

echo Running Northstar OS Retail Arbitrage Agent...
echo.

call npm run pipeline
if errorlevel 1 goto :fail

echo.
echo Pipeline completed successfully.
pause
exit /b 0

:fail
echo.
echo Pipeline failed.
pause
exit /b 1