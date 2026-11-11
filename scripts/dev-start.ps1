# Dev start script: backend (loopback) + UI (Vite). Dev only.
# Records PIDs of processes it starts; stops only those on exit.
#
# D-009 (2026-11-11): the pid file was stale and partly wrong. Measured: it listed
# 11664,16960,23512,17252,25384 while 23512/17252/25384 no longer existed, and the live vite
# process (15472, child of 13944) was not in it — because the file recorded only the wrapper
# processes the script spawned and never resolved the children that do the serving. The record is
# now the *live* set, resolved from the listening sockets and the process tree, pruned of anything
# dead, with a role map beside it so "started by scripts/dev-start.ps1" is a claim the file supports.
param(
    [switch]$DryRun,
    [string]$PidFile = ""
)
$ErrorActionPreference = "Stop"

$root = "C:\Users\T2Hol\Desktop\Northstar OS Retail Arbitrage Agent"
$backendDir = Join-Path $root "Northstar_backend"
$uiDir = Join-Path $root "northstar-os-ui"
if (-not $PidFile) { $PidFile = Join-Path $root "dev-start.pids" }
$pidFile = $PidFile
$pidRolesFile = "$pidFile.json"
$checker = Join-Path $root "scripts\check_dev_safety.py"

function Get-DescendantPids {
    param([int]$Root)
    $found = @()
    try {
        $kids = Get-CimInstance Win32_Process -Filter "ParentProcessId=$Root" -ErrorAction Stop
        foreach ($kid in $kids) {
            $found += [int]$kid.ProcessId
            $found += Get-DescendantPids -Root ([int]$kid.ProcessId)
        }
    } catch { }
    return $found
}

function Get-ListenerPid {
    param([int]$Port)
    try {
        $row = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction Stop |
            Select-Object -First 1
        if ($row) { return [int]$row.OwningProcess }
    } catch { }
    return $null
}

function Get-AlivePid {
    param($Candidate)
    if (-not $Candidate) { return $null }
    $value = 0
    if (-not [int]::TryParse([string]$Candidate, [ref]$value)) { return $null }
    if (Get-Process -Id $value -ErrorAction SilentlyContinue) { return $value }
    return $null
}

function Write-PidRecord {
    param([string]$Path, [hashtable]$Roles)
    $live = @()
    $map = [ordered]@{}
    foreach ($role in ($Roles.Keys | Sort-Object)) {
        $pidValue = Get-AlivePid $Roles[$role]
        if ($null -eq $pidValue) { continue }
        $map[$role] = $pidValue
        if ($live -notcontains $pidValue) { $live += $pidValue }
        if ($role -ne "backend" -and $role -ne "ui") {
            foreach ($kid in (Get-DescendantPids -Root $pidValue)) {
                if ((Get-AlivePid $kid) -and ($live -notcontains $kid)) { $live += $kid }
            }
        }
    }
    # The listener is the authority for "who is serving this port": the wrapper the script
    # spawned can exit while its child keeps the socket.
    foreach ($row in @(@("ui", 8101), @("backend", 8000))) {
        $owner = Get-ListenerPid ([int]$row[1])
        if ($owner) {
            $map[$row[0]] = $owner
            if ($live -notcontains $owner) { $live += $owner }
        }
    }
    $live -join "," | Out-File -FilePath $Path -Encoding UTF8
    $map | ConvertTo-Json | Out-File -FilePath "$Path.json" -Encoding UTF8
    return $live
}

# Dev-only environment (never production/staging defaults)
$env:ENVIRONMENT = "development"
$env:FOUNDATION_DB_PATH = Join-Path $backendDir "data\foundation.db"
$env:NORTHSTAR_TRUSTED_PROXIES = "127.0.0.1"
# Dev shim needs no JWT secret (loopback dev posture). Do NOT set NORTHSTAR_JWT_SECRET here.

if ($DryRun) {
    # Proves the record without starting anything: prune what is dead, keep what is alive.
    $probe = @{ "probe-alive" = $PID; "probe-dead" = 999999 }
    $kept = Write-PidRecord -Path $pidFile -Roles $probe
    Write-Host "dry run: recorded $($kept -join ', ') in $pidFile"
    Write-Host "dry run: nothing was started"
    exit 0
}


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

# Record PIDs: resolved from the listeners and the process tree, pruned of anything dead.
$roles = @{ "backend-launcher" = $backend.Id; "ui-launcher" = $ui.Id }
if ($fpids) { $roles["flux3"] = ($fpids | Select-Object -First 1) }
$null = Write-PidRecord -Path $pidFile -Roles $roles
Write-Host "PIDs recorded in $pidFile (live set, role map beside it)"

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
    # Re-read the live record rather than trusting $pids: the record is what other tools act on.
    $recorded = @()
    if (Test-Path $pidFile) {
        $recorded = (Get-Content $pidFile -Raw).Trim().Split(",") |
            Where-Object { $_ } | ForEach-Object { Get-AlivePid $_ } | Where-Object { $_ }
    }
    if (-not $recorded) { $recorded = $pids }
    foreach ($processId in $recorded) {
        Stop-Process -Id $processId -ErrorAction SilentlyContinue
    }
    Remove-Item $pidFile -ErrorAction SilentlyContinue
    Remove-Item $pidRolesFile -ErrorAction SilentlyContinue
    Write-Host "Stopped dev servers (PIDs: $($recorded -join ', '))"
}
PY