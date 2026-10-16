# Northstar OS - Private Alpha one-command launcher (Phase H)
# ===========================================================
# Brings up everything needed for operator-only alpha testing:
#   1. Ollama (local engine)            - started only if not already up
#   2. Northstar backend  :8000         - serves the suite shell + APIs
#   3. AutothinK          :8100         - the chat workspace (optional)
#   4. Cloudflare tunnel                - prints the public trycloudflare URL
#
# Usage:
#   powershell -ExecutionPolicy Bypass -File scripts\launch_alpha.ps1
#   powershell -ExecutionPolicy Bypass -File scripts\launch_alpha.ps1 -Check
#   powershell -ExecutionPolicy Bypass -File scripts\launch_alpha.ps1 -Stop
#
# Options:
#   -Email <addr>     allowlist email (default northstarosllc@gmail.com)
#   -Cloud            arm the cloud engine (sets CLOUD_MODEL_LIVE=1) - real spend
#   -NoTunnel         skip cloudflared (local-only)
#   -NoAutothink      skip the separate AutothinK process
#
# Nothing here spends money unless -Cloud is passed, and even then only your
# own test runs make calls. No credential values are read or printed.
# ASCII-only on purpose: PowerShell 5.1 misreads non-ASCII .ps1 without a BOM.

param(
    [string]$Email = "northstarosllc@gmail.com",
    [string]$CloudflaredPath = "",
    [switch]$Cloud,
    [switch]$Gate,
    [switch]$Restart,
    [switch]$NoTunnel,
    [switch]$NoAutothink,
    [switch]$Check,
    [switch]$Stop
)

# PS 5.1 emits informational stderr; keep it non-terminating.
$ErrorActionPreference = "Continue"

$RepoRoot    = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot ".."))
$BackendDir  = Join-Path $RepoRoot "Northstar_backend"
$AutoDir     = Join-Path $RepoRoot "autothink"
$StateFile   = Join-Path $env:TEMP "northstar-alpha-pids.json"
$TunnelLog   = Join-Path $env:TEMP "northstar-tunnel.log"

function Have-Cmd($name) { return [bool](Get-Command $name -ErrorAction SilentlyContinue) }

function Resolve-Cloudflared() {
    if ($CloudflaredPath -and (Test-Path $CloudflaredPath)) { return $CloudflaredPath }
    if (Have-Cmd "cloudflared") { return "cloudflared" }
    $candidates = @(
        (Join-Path $env:ProgramFiles "cloudflared\cloudflared.exe"),
        (Join-Path ${env:ProgramFiles(x86)} "cloudflared\cloudflared.exe"),
        (Join-Path $env:LOCALAPPDATA "cloudflared\cloudflared.exe"),
        (Join-Path $env:USERPROFILE "cloudflared.exe"),
        "C:\ProgramData\chocolatey\bin\cloudflared.exe"
    )
    foreach ($c in $candidates) { if ($c -and (Test-Path $c)) { return $c } }
    $wg = Get-ChildItem (Join-Path $env:LOCALAPPDATA "Microsoft\WinGet\Packages") -Filter "cloudflared.exe" -Recurse -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($wg) { return $wg.FullName }
    return $null
}

function Port-Busy($port) {
    try { return [bool](Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue) }
    catch { return $false }
}

function Ollama-Up() {
    try {
        $r = Invoke-WebRequest -Uri "http://localhost:11434/api/tags" -TimeoutSec 2 -UseBasicParsing
        return ($r.StatusCode -eq 200)
    } catch { return $false }
}

function Banner($text) { Write-Host $text -ForegroundColor Cyan }

function Stop-ProcessTree($procId) {
    # Kill the process and its children (uvicorn --reload parent shells +
    # worker pythons). taskkill /T walks the whole tree.
    try {
        taskkill /PID $procId /T /F 2>$null | Out-Null
    } catch { }
}

function Stop-Listeners($ports) {
    $failed = @()
    foreach ($port in $ports) {
        $conns = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
        $pids = @()
        foreach ($c in @($conns)) {
            if ($c.OwningProcess -and ($pids -notcontains $c.OwningProcess)) { $pids += $c.OwningProcess }
        }
        if ($pids.Count -eq 0) {
            Write-Host ("restart: :{0} already free" -f $port) -ForegroundColor DarkGray
            continue
        }
        foreach ($procId in $pids) {
            Stop-ProcessTree $procId
            Write-Host ("restart: stopped pid {0} on :{1}" -f $procId, $port) -ForegroundColor Yellow
        }
        # netstat/Get-NetTCPConnection can report a dead parent as the owner;
        # also kill any python/powershell whose command line pins this port.
        $candidates = Get-CimInstance Win32_Process -Filter "Name='python.exe' OR Name='powershell.exe'" -ErrorAction SilentlyContinue
        foreach ($proc in @($candidates)) {
            if ($proc.CommandLine -and ($proc.CommandLine -match ("--port\s+" + $port))) {
                try {
                    Stop-ProcessTree $proc.ProcessId
                    Write-Host ("restart: killed tree owner {0} on :{1}" -f $proc.ProcessId, $port) -ForegroundColor Yellow
                } catch { $failed += ("pid " + $proc.ProcessId + " on :" + $port) }
            }
        }
    }
    Start-Sleep -Milliseconds 1500
    foreach ($port in $ports) {
        if (Port-Busy $port) { $failed += ("port " + $port + " still busy") }
        else { Write-Host ("restart: :{0} verified free" -f $port) -ForegroundColor Green }
    }
    if ($failed.Count -gt 0) {
        Write-Host ("restart FAILED to free: {0}" -f ($failed -join "; ")) -ForegroundColor Red
        throw "Stop-Listeners could not free the requested ports. Resolve manually (elevated taskkill) and retry."
    }
}

function Shell-Assets-Ok() {
    try {
        $a = Invoke-WebRequest -Uri "http://127.0.0.1:8000/ui/" -TimeoutSec 3 -UseBasicParsing
        return ($a.StatusCode -eq 200)
    } catch { return $false }
}

# ---------------------------------------------------------------- -Stop
if ($Stop) {
    Banner "== Northstar alpha launcher: STOP =="
    if (-not (Test-Path $StateFile)) { Write-Host "No state file ($StateFile) - nothing to stop."; exit 0 }
    $state = Get-Content -Raw $StateFile | ConvertFrom-Json
    foreach ($p in @($state.processes)) {
        try {
            Stop-Process -Id ([int]$p.id) -Force -ErrorAction SilentlyContinue
            Write-Host ("stopped {0} (pid {1})" -f $p.name, $p.id)
        } catch { }
    }
    Remove-Item $StateFile -Force -ErrorAction SilentlyContinue
    Write-Host "Done. (Ollama, if it was already running before launch, is left running.)"
    exit 0
}

# ------------------------------------------------------------- prerequisites
Banner "== Northstar OS - Private Alpha launcher =="
Write-Host ("Repo:   {0}" -f $RepoRoot)
Write-Host ("Email:  {0}" -f $Email)
$cloudTxt = if ($Cloud) { 'ARMED (real spend on run)' } else { 'disarmed (local only)' }
Write-Host ("Cloud:  {0}" -f $cloudTxt)
$lockTxt = if ($Gate) { 'in-app allowlist gate ON' } else { 'no Access / no gate (URL-only) - solo test week' }
Write-Host ("Lock:   {0}" -f $lockTxt)

$cf = Resolve-Cloudflared
$missing = @()
if (-not (Have-Cmd "python"))      { $missing += "python" }
if (-not (Have-Cmd "ollama"))      { $missing += "ollama" }
if (-not $NoTunnel -and -not $cf)  { $missing += "cloudflared" }

if ($missing.Count -gt 0) {
    Write-Host ("MISSING tools: {0}" -f ($missing -join ", ")) -ForegroundColor Red
    Write-Host "Install them, or pass -NoTunnel to skip cloudflared."
    Write-Host "For cloudflared you can also pass -CloudflaredPath <path to cloudflared.exe>."
    exit 1
}

if ($Check) {
    Write-Host ""
    Write-Host "Prerequisites OK." -ForegroundColor Green
    $p8000 = if (Port-Busy 8000) { 'BUSY' } else { 'free' }
    $p8100 = if (Port-Busy 8100) { 'BUSY' } else { 'free' }
    $ol    = if (Ollama-Up) { 'already up' } else { 'will start' }
    $tn    = if ($NoTunnel) { 'skipped' } else { 'will start' }
    Write-Host ("  backend  : {0}  (port 8000 {1})" -f $BackendDir, $p8000)
    Write-Host ("  autothink: {0}  (port 8100 {1})" -f $AutoDir, $p8100)
    Write-Host ("  ollama   : {0}" -f $ol)
    Write-Host ("  tunnel   : {0}" -f $tn)
    Write-Host ("  cloudflared: {0}" -f $(if ($cf) { $cf } else { 'not found' }))
    Write-Host "Run without -Check to launch."
    exit 0
}

# ------------------------------------------------------------- -Restart
if ($Restart) {
    Write-Host "Restart: stopping any listener on :8000 / :8100 ..."
    Stop-Listeners @(8000, 8100)
}

# ------------------------------------------------------------- environment
# Child processes inherit these.
if ($Gate) { $env:NORTHSTAR_PRIVATE_ALPHA = "1" } else { Remove-Item Env:\NORTHSTAR_PRIVATE_ALPHA -ErrorAction SilentlyContinue }
$env:NORTHSTAR_ALPHA_ALLOWLIST = $Email
$env:NORTHSTAR_DISABLE_RATE_LIMIT = "0"
$env:NORTHSTAR_ROOT_TO_APP = "1"   # tunnel/local root lands in the workspace
$env:FOUNDATION_DB_PATH = Join-Path $BackendDir "data\foundation.db"   # persistent foundation store (owner sign-in, invites, sessions)

# Signing key for the hosted/cookie login (the foundation auth fails closed 503
# without it). Reuses the SAME out-of-repo store as tools/start-local.ps1:
# generated once, owner-only ACL, survives restarts, never printed/committed.
$secretsDir = Join-Path $env:LOCALAPPDATA "NorthstarOS"
$secretFile = Join-Path $secretsDir "jwt-secret.txt"
if (-not (Test-Path $secretsDir)) { New-Item -ItemType Directory -Force -Path $secretsDir | Out-Null }
if (Test-Path $secretFile) {
    $env:NORTHSTAR_JWT_SECRET = (Get-Content $secretFile -Raw).Trim()
    Write-Host "Signing key: loaded from the stored local secret (not printed)." -ForegroundColor DarkGray
} else {
    $bytes = New-Object byte[] 48
    [System.Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($bytes)
    $secret = -join ($bytes | ForEach-Object { "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789"[$_ % 62] })
    Set-Content -Path $secretFile -Value $secret -NoNewline -Encoding ascii
    try { icacls $secretFile /inheritance:r | Out-Null; icacls $secretFile /grant:r "$($env:USERNAME):(R,W)" | Out-Null } catch { }
    $env:NORTHSTAR_JWT_SECRET = $secret
    Write-Host "Signing key: generated + stored at $secretFile (owner-only; not printed)." -ForegroundColor DarkGray
}
if ($Cloud) { $env:CLOUD_MODEL_LIVE = "1" } else { Remove-Item Env:\CLOUD_MODEL_LIVE -ErrorAction SilentlyContinue }

$launched = @()

# ------------------------------------------------------------- 1. Ollama
if (Ollama-Up) {
    Write-Host "Ollama: already running (local engine ready)." -ForegroundColor Green
} else {
    Write-Host "Ollama: starting..."
    $o = Start-Process -FilePath "ollama" -ArgumentList "serve" -PassThru -WindowStyle Minimized
    $launched += @{ name = "ollama"; id = $o.Id }
    Start-Sleep -Seconds 2
}

# ------------------------------------------------------------- 2. Backend
if (Port-Busy 8000) {
    Write-Host "Backend: port 8000 already in use - leaving it as-is." -ForegroundColor Yellow
    Write-Host "  WARNING: a running backend may be STALE (old code). If the UI looks" -ForegroundColor Yellow
    Write-Host "  unstyled / buttons do nothing, relaunch with -Restart." -ForegroundColor Yellow
} else {
    Write-Host "Backend: starting on :8000..."
    $b = Start-Process -FilePath "powershell" -PassThru -WindowStyle Minimized -ArgumentList @(
        "-NoExit", "-Command", "cd '$BackendDir'; python -m uvicorn main:app --host 127.0.0.1 --port 8000"
    )
    $launched += @{ name = "backend"; id = $b.Id }
}

# ------------------------------------------------------------- 3. AutothinK
if (-not $NoAutothink) {
    if (Port-Busy 8100) {
        Write-Host "AutothinK: port 8100 already in use - leaving it as-is." -ForegroundColor Yellow
    } else {
        Write-Host "AutothinK: starting on :8100..."
        $a = Start-Process -FilePath "powershell" -PassThru -WindowStyle Minimized -ArgumentList @(
            "-NoExit", "-Command", "cd '$AutoDir'; python -m uvicorn backend.server:app --host 127.0.0.1 --port 8100"
        )
        $launched += @{ name = "autothink"; id = $a.Id }
    }
}

# wait for the backend to answer
$ready = $false
for ($i = 0; $i -lt 20; $i++) {
    Start-Sleep -Milliseconds 750
    try {
        $h = Invoke-WebRequest -Uri "http://127.0.0.1:8000/health" -TimeoutSec 2 -UseBasicParsing
        if ($h.StatusCode -eq 200) { $ready = $true; break }
    } catch { }
}

# ------------------------------------------------------------- 4. Tunnel
$tunnelUrl = $null
if (-not $NoTunnel) {
    Write-Host "Tunnel: starting cloudflared..."
    Remove-Item $TunnelLog -Force -ErrorAction SilentlyContinue
    $t = Start-Process -FilePath $cf -PassThru -WindowStyle Minimized -ArgumentList @(
        "tunnel", "--url", "http://127.0.0.1:8000", "--logfile", $TunnelLog
    )
    $launched += @{ name = "cloudflared"; id = $t.Id }
    for ($i = 0; $i -lt 30; $i++) {
        Start-Sleep -Milliseconds 700
        if (Test-Path $TunnelLog) {
            $m = Select-String -Path $TunnelLog -Pattern "https://[a-z0-9-]+\.trycloudflare\.com" -ErrorAction SilentlyContinue |
                 Select-Object -First 1
            if ($m) { $tunnelUrl = ($m.Matches[0].Value); break }
        }
    }
}

# ------------------------------------------------------------- summary
@{ processes = $launched } | ConvertTo-Json -Depth 4 | Set-Content -Path $StateFile -Encoding UTF8

Write-Host ""
Banner "== READY =="
$healthTxt = if ($ready) { '(health OK)' } else { '(health not responding yet)' }
Write-Host ("Local suite : http://127.0.0.1:8000/ui/   {0}" -f $healthTxt) -ForegroundColor Green
$assetsOk = $ready -and (Shell-Assets-Ok)
if (-not $assetsOk) {
    Write-Host "  WARNING: the shell's CSS/JS are NOT served -> the UI will look unstyled." -ForegroundColor Red
    Write-Host "           You are likely running a STALE backend. Relaunch with -Restart." -ForegroundColor Red
} else {
    Write-Host "  assets OK: stylesheets + scripts served (styled, interactive UI)" -ForegroundColor Green
}
Write-Host  "AutothinK   : http://127.0.0.1:8000/autothink/ui/index.html  (same-origin iframe)"
Write-Host  "Local engine: Ollama on 127.0.0.1:11434"
$cloudEngine = if ($Cloud) { 'ARMED - CLOUD_MODEL_LIVE=1' } else { 'disarmed (set -Cloud or CLOUD_MODEL_LIVE=1 to arm)' }
Write-Host ("Cloud engine: {0}" -f $cloudEngine)
if ($tunnelUrl) {
    Write-Host ""
    Write-Host ("Public URL  : {0}" -f $tunnelUrl) -ForegroundColor Yellow
    if ($Gate) {
        Write-Host "Locked by   : in-app allowlist gate. Register/log in with $Email to use the APIs."
    } else {
        Write-Host "Locked by   : nothing but the unguessable URL (option A, solo test week)." -ForegroundColor Yellow
        Write-Host "              Do NOT share this URL. For real access control:" -ForegroundColor Yellow
        Write-Host "                - buy a domain -> named tunnel + Cloudflare Access, OR" -ForegroundColor Yellow
        Write-Host "                - run with -Gate (in-app allowlist, requires login), OR" -ForegroundColor Yellow
        Write-Host "                - use Tailscale (private, free, no domain)." -ForegroundColor Yellow
    }
} elseif (-not $NoTunnel) {
    Write-Host "Tunnel URL not captured yet - check the cloudflared window / $TunnelLog." -ForegroundColor Yellow
}
Write-Host ""
Write-Host "Local URL   : http://127.0.0.1:8000/ui/   (no tunnel needed for same-machine testing)"
Write-Host "Gate on/off : launch with -Gate to enable the in-app allowlist"
Write-Host "After code changes : powershell -File scripts\launch_alpha.ps1 -Restart"
Write-Host "Stop everything : powershell -File scripts\launch_alpha.ps1 -Stop"
Write-Host "Runbook         : docs/PRIVATE_ALPHA_DEPLOY.md"
exit 0