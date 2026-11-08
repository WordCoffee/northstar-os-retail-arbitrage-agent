@echo off
REM ============================================================
REM Launch-Northstar-Ubuntu.cmd
REM Double-click to start Northstar stack inside WSL Ubuntu.
REM Calls: launchers\ubuntu-start.sh
REM ============================================================

setlocal enabledelayedexpansion

REM --- resolve project root (directory of this script) ---
set "SCRIPT_DIR=%~dp0"
set "PROJECT_ROOT=%SCRIPT_DIR%.."
set "UBUNTU_SCRIPT=%PROJECT_ROOT%launchers\ubuntu-start.sh"

echo ============================================================
echo Northstar OS - Ubuntu (WSL) Launcher
echo ============================================================
echo Project root: %PROJECT_ROOT%
echo Ubuntu script: %UBUNTU_SCRIPT%
echo.

REM --- safety: file exists ---
if not exist "%UBUNTU_SCRIPT%" (
    echo ERROR: ubuntu-start.sh not found at %UBUNTU_SCRIPT%
    echo Expected path: %PROJECT_ROOT%launchers\ubuntu-start.sh
    pause
    exit /b 1
)

REM --- convert to WSL path ---
REM %PROJECT_ROOT% like C:\Users\...\Northstar OS Retail Arbitrage Agent
REM WSL path: /mnt/c/Users/.../Northstar OS Retail Arbitrage Agent/launchers/ubuntu-start.sh
for %%A in ("%PROJECT_ROOT%") do set "ABS_ROOT=%%~fA"
set "WSL_PATH=/mnt/c%ABS_ROOT:~2%"
set "WSL_PATH=!WSL_PATH:\=/!"
set "WSL_SCRIPT=!WSL_PATH!/launchers/ubuntu-start.sh"

echo Resolved WSL script path: %WSL_SCRIPT%
echo.

REM --- launch in Ubuntu ---
echo Starting Northstar in WSL Ubuntu...
echo (This opens a bash window that stays open. Services keep running after you close it.)
echo.

wsl -d Ubuntu -e bash -c "bash \"%WSL_SCRIPT%\""

echo.
echo Ubuntu launcher finished. Services may still be running in background.
echo To stop: open Ubuntu terminal and run: opencode service stop && pkill ollama
pause