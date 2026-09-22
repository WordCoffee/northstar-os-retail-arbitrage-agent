@echo off
title Northstar OS - Private Alpha Launcher
REM Double-click me to bring up the full alpha stack (Ollama + backend +
REM AutothinK + Cloudflare tunnel). Pass -Check or -Stop after the command
REM line if you want those modes instead.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\launch_alpha.ps1" %*
echo.
pause