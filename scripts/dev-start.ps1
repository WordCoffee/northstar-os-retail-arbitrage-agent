# Dev start script: backend (loopback) + UI (Vite). Dev only.
# Records PIDs of processes it starts; stops only those on exit.
$ErrorActionPreference = "Stop"

$root = "C:\Users\T2Hol\Desktop\Northstar OS Retail Arbitrage Agent"
$backendDir = Join-Path $root "Northstar_backend"
$uiDir = Join-Path $root "northstar-os-ui"
$pidFile = Join-Path $root "dev-start.pids"
$checker = Join-Path $root "scripts\check_dev_safety.py"

# Dev-only environment (never production/staging defaults)
$env:ENVIRONMENT = "development"
$env:FOUNDATION_DB_PATH = Join-Path $backendDir "data\foundation.db"
$env:NORTHSTAR_TRUSTED_PROXIES = "127.0.0.1"
# Dev shim needs no JWT secret (loopback dev posture). Do NOT set NORTHSTAR_JWT_SECRET here.

# Fail-closed safety gate — refuse if any exposure condition is called.
Write-Host "Running dev safety gate: $checker"
& python $checker
if ($LASTEXITCODE -ne 0) {
    Write-Host "STOPPING dev start: safety gate failed (exit $LASTEXITCODE). Fix the conditions above, then re-run."
    exit 2
}
Write-Host "dev safety gate: OK"

# Backend refuses dev shim unless ENVIRONMENT=development AND bind host is 127.0.0.1.
# This is enforced by the backend at startup; the script passes --host 127.0.0.1 only.
$backend = Start-Process -FilePath "python" -ArgumentList "-m","uvicorn","main:app","--host","127.0.0.1","--port","8000" -WorkingDirectory $backendDir -WindowStyle Hidden -PassThru
$pids = @($backend.Id)
Write-Host "backend PID=$($backend.Id)"

# UI on 127.0.0.1:8101 (Vite host forced to 127.0.0.1 by vite.config.js)
$ui = Start-Process -FilePath "npm.cmd" -ArgumentList "run","dev" -WorkingDirectory $uiDir -WindowStyle Hidden -PassThru
$pids += $ui.Id
Write-Host "ui PID=$($ui.Id)"

# The FLUX 3 media lane ships WITH the stack. Arming a lane (MEDIA_GEN_LIVE=1)
# that nothing starts is how "generate" quietly stays unavailable, so the dev
# stack brings up ComfyUI + the :8190 gateway and stops them with everything else.
# Skip it with NORTHSTAR_NO_MEDIA=1 (headless test runs that never generate).
$flux3 = Join-Path $root "scripts\start-flux3.ps1"
if ((Test-Path $flux3) -and ($env:NORTHSTAR_NO_MEDIA -ne "1")) {
    Write-Host "starting the FLUX 3 media lane (scripts/start-flux3.ps1)"
    $sf = Start-Process -FilePath "powershell" `
        -ArgumentList "-NoProfile","-ExecutionPolicy","Bypass","-File",$flux3 `
        -WindowStyle Hidden -PassThru
    $null = $sf.WaitForExit(240000)
    $fpidFile = Join-Path $root "flux3.pids"
    if (Test-Path $fpidFile) {
        $fpids = (Get-Content $fpidFile -Raw).Trim().Split(",") |
            Where-Object { $_ } | ForEach-Object { [int]$_ }
        $pids += $fpids
        Write-Host "flux3 PIDs: $($fpids -join ', ')"
    } else {
        Write-Host "flux3: not started (see reports\flux3_gateway.err.log); the designer reports UNARMED"
    }
} else {
    Write-Host "flux3: skipped (NORTHSTAR_NO_MEDIA=1)"
}

# Record PIDs
$pids -join "," | Out-File -FilePath $pidFile -Encoding UTF8
Write-Host "PIDs recorded in $pidFile"

# Wait for readiness
Start-Sleep -Seconds 6
try {
    $r = Invoke-WebRequest -Uri "http://127.0.0.1:8000/health" -TimeoutSec 5 -ErrorAction Stop
    Write-Host "backend ready: $($r.Content)"
} catch { Write-Host "backend not ready: $($_.Exception.Message)" }
try {
    $r = Invoke-WebRequest -Uri "http://127.0.0.1:8101/health" -TimeoutSec 5 -ErrorAction Stop
    Write-Host "ui ready: $($r.Content)"
} catch { Write-Host "ui not ready: $($_.Exception.Message)" }

Write-Host "Dev servers running. Press Ctrl+C to stop (only the PIDs this script started)."
try {
    while ($true) { Start-Sleep -Seconds 5 }
} finally {
    foreach ($pid in $pids) {
        Stop-Process -Id $pid -ErrorAction SilentlyContinue
    }
    Remove-Item $pidFile -ErrorAction SilentlyContinue
    Write-Host "Stopped dev servers (PIDs: $($pids -join ', '))"
}
PY