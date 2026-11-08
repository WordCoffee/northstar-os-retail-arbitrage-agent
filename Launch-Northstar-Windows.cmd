@echo off
REM ============================================================
REM Launch-Northstar-Windows.cmd
REM Double-click to start Northstar stack on native Windows.
REM Starts Ollama (Windows) + OpenCode for this project.
REM ============================================================

setlocal enabledelayedexpansion

REM --- config ---
set "PROJECT_ROOT=%~dp0.."
set "OPENCODE_PORT=4097"
set "OLLAMA_PORT=11434"
set "PASSWORD_FILE=%USERPROFILE%\.northstar\opencode-password.txt"
set "OLLAMA_LOG=%TEMP%\ollama-windows.log"
set "OPENCODE_LOG=%TEMP%\opencode-windows.log"

echo ============================================================
echo Northstar OS - Windows Launcher
echo ============================================================
echo Project root: %PROJECT_ROOT%
echo.

REM --- safety checks ---
echo [1/6] Checking for conflicting processes...

REM 1a) Ubuntu OpenCode service?
wsl -d Ubuntu -e bash -c "opencode service status" 2>nul | findstr /i "running" >nul
if !errorlevel! equ 0 (
    echo ERROR: OpenCode service is running in WSL Ubuntu.
    echo Run 'opencode service stop' in Ubuntu terminal first.
    pause
    exit /b 1
)

REM 1b) Ubuntu chromecontrol-mcp-server?
wsl -d Ubuntu -e bash -c "pgrep -f chromecontrol-mcp-server" 2>nul | findstr /r "." >nul
if !errorlevel! equ 0 (
    echo ERROR: chromecontrol-mcp-server is running in Ubuntu.
    echo Stop it there first.
    pause
    exit /b 1
)

REM 1c) Windows OpenCode process?
tasklist /FI "IMAGENAME eq opencode.exe" 2>nul | findstr /i "opencode.exe" >nul
if !errorlevel! equ 0 (
    echo ERROR: OpenCode is already running on Windows.
    echo Close the other OpenCode window first.
    pause
    exit /b 1
)

REM 1d) Windows chromecontrol-mcp-server?
tasklist /FI "IMAGENAME eq node.exe" 2>nul | findstr /i "chromecontrol-mcp-server" >nul
if !errorlevel! equ 0 (
    echo ERROR: chromecontrol-mcp-server is running on Windows.
    echo Stop it first.
    pause
    exit /b 1
)
echo   OK: no conflicting OpenCode/chromecontrol processes.

REM 2) Ollama conflict (Ubuntu side)
echo [2/6] Checking for Ubuntu Ollama...
wsl -d Ubuntu -e bash -c "pgrep -f ollama" 2>nul | findstr /r "." >nul
if !errorlevel! equ 0 (
    echo ERROR: ollama is running in Ubuntu. Stop it there first (pkill ollama).
    pause
    exit /b 1
)
echo   OK: no Ubuntu ollama running.

REM 3) Port checks
echo [3/6] Checking ports %OPENCODE_PORT% (OpenCode) and %OLLAMA_PORT% (Ollama)...
for %%P in (%OPENCODE_PORT% %OLLAMA_PORT%) do (
    netstat -an 2>nul | findstr ":%%P " >nul
    if !errorlevel! equ 0 (
        echo   WARNING: Port %%P is in use.
        netstat -ano 2>nul | findstr ":%%P " | findstr "LISTENING" | head -n 1
        echo   If this is an unknown process, stop it and retry.
    ) else (
        echo   OK: Port %%P is free.
    )
)

REM 4) Project path
echo [4/6] Verifying project path...
if not exist "%PROJECT_ROOT%" (
    echo ERROR: Project root not found: %PROJECT_ROOT%
    pause
    exit /b 1
)
echo   OK: %PROJECT_ROOT%

REM 5) Password file
echo [5/6] Reading OpenCode password...
if not exist "%PASSWORD_FILE%" (
    echo ERROR: Password file not found: %PASSWORD_FILE%
    echo Create it with: mkdir "%USERPROFILE%\.northstar" && echo your-password > "%PASSWORD_FILE%"
    echo (File must be outside the repo; never commit passwords.)
    pause
    exit /b 1
)
set /p OPENCODE_PASSWORD=<%PASSWORD_FILE%
if "!OPENCODE_PASSWORD!"=="" (
    echo ERROR: Password file is empty: %PASSWORD_FILE%
    pause
    exit /b 1
)
echo   OK: Password loaded (not printed).

REM 6) Project dir (done)
echo [6/6] All pre-flight checks passed.
echo.

REM --- start Ollama (Windows) ---
echo ============================================================
echo Starting Ollama (Windows) with optimized env...
echo ============================================================

REM Check if already listening
netstat -an 2>nul | findstr ":%OLLAMA_PORT% " | findstr "LISTENING" >nul
if !errorlevel! equ 0 (
    echo Ollama already listening on port %OLLAMA_PORT% - skipping start.
) else (
    echo Starting ollama serve with optimized env...
    set "OLLAMA_GPU_OVERHEAD=4294967296"
    set "OLLAMA_FLASH_ATTENTION=1"
    set "OLLAMA_MAX_LOADED_MODELS=1"
    set "OLLAMA_KEEP_ALIVE=30s"
    set "OLLAMA_CONTEXT_LENGTH=8192"
    REM No OLLAMA_NUM_GPU_LAYERS (not a real setting)

    start "Ollama" /B cmd /c "set OLLAMA_GPU_OVERHEAD=4294967296 && set OLLAMA_FLASH_ATTENTION=1 && set OLLAMA_MAX_LOADED_MODELS=1 && set OLLAMA_KEEP_ALIVE=30s && set OLLAMA_CONTEXT_LENGTH=8192 && ollama serve > \"%OLLAMA_LOG%\" 2>&1"
    echo   Started ollama (background), logging to %OLLAMA_LOG%

    echo Waiting for Ollama on port %OLLAMA_PORT% (timeout 30s)...
    for /l %%i in (1,1,30) do (
        curl -s http://127.0.0.1:%OLLAMA_PORT% >nul 2>&1
        if !errorlevel! equ 0 (
            echo   Ollama ready.
            goto :ollama_ready
        )
        timeout /t 1 /nobreak >nul
    )
    echo ERROR: Ollama did not become ready in 30s. Check %OLLAMA_LOG%
    pause
    exit /b 1
)
:ollama_ready
echo Ollama ready.

REM --- start OpenCode for this project ---
echo.
echo ============================================================
echo Starting OpenCode for project...
echo ============================================================

cd /d "%PROJECT_ROOT%"

REM Configure hostname/port (idempotent)
echo Setting OpenCode hostname to 127.0.0.1...
opencode service set hostname 127.0.0.1
echo Setting OpenCode port to %OPENCODE_PORT%...
opencode service set port %OPENCODE_PORT%

REM Check status and start if stopped
for /f "tokens=*" %%a in ('opencode service status 2^>nul') do set "OC_STATUS=%%a"
echo OpenCode status: !OC_STATUS!
echo !OC_STATUS! | findstr /i "stopped not" >nul
if !errorlevel! equ 0 (
    echo Starting OpenCode service...
    set "OPENCODE_SERVER_PASSWORD=!OPENCODE_PASSWORD!"
    start "OpenCode" /B cmd /c "set OPENCODE_SERVER_PASSWORD=!OPENCODE_PASSWORD! && opencode service start > \"%OPENCODE_LOG%\" 2>&1"
    echo   OpenCode service start triggered (background), logging to %OPENCODE_LOG%
) else (
    echo OpenCode service already running - skipping start.
)

REM --- summary ---
echo.
echo ============================================================
echo SUMMARY
echo ============================================================
echo Project: %PROJECT_ROOT%
opencode service status
echo.
echo Ollama log: %OLLAMA_LOG%
echo OpenCode log: %OPENCODE_LOG%
echo OpenCode port: %OPENCODE_PORT%
echo Ollama port: %OLLAMA_PORT%
echo.
echo ============================================================
echo HOW TO STOP
echo ============================================================
echo   OpenCode:  opencode service stop
echo   Ollama:    taskkill /IM ollama.exe /F
echo   All:       opencode service stop && taskkill /IM ollama.exe /F
echo.
echo Window will stay open. Services keep running.
echo Press Ctrl+C to exit this window (services continue in background).
pause