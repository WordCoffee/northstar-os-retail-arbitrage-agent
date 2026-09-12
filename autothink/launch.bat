@echo off
REM Northstar AutothinK launcher — starts the local brain server on http://127.0.0.1:8100
cd /d "%~dp0"
echo Starting Northstar OS AutothinK on http://127.0.0.1:8100 ...
start "Northstar AutothinK" /min python -m uvicorn backend.server:app --host 127.0.0.1 --port 8100 --log-level info
timeout /t 3 >nul
powershell -NoProfile -Command "try { (Invoke-WebRequest -Uri 'http://127.0.0.1:8100/health' -UseBasicParsing -TimeoutSec 5).Content } catch { Write-Host 'Health check failed - is Ollama running and port 8100 free?' }"