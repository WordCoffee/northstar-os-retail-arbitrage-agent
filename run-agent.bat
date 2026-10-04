@echo off
REM Northstar OS - local launcher.
REM The legacy "npm run pipeline" target does not exist. This now starts the
REM real local FastAPI backend (npm start). For the full local stack
REM (backend + AutothinK, optional Ollama) use launch-all.ps1; see
REM docs\LOCAL_RUNBOOK.md. No pipeline automation is implied or invented here.
setlocal
cd /d "%~dp0"

echo Northstar OS - starting the local backend (http://127.0.0.1:8000)...
echo.
echo   Full local stack (backend + AutothinK):  launch-all.ps1
echo   UI dev server:                           npm run dev
echo   Production UI build:                     npm run build
echo.

call npm start
if errorlevel 1 goto :fail

echo.
echo Backend exited normally.
pause
exit /b 0

:fail
echo.
echo Backend failed to start. See docs\LOCAL_RUNBOOK.md for prerequisites.
pause
exit /b 1