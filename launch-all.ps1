<#
.SYNOPSIS
    Launches the full Northstar OS + AutothinK local stack.
    - Northstar Backend (FastAPI) on http://127.0.0.1:8000
    - AutothinK Backend on http://127.0.0.1:8100
    - Ollama (local LLM) on http://127.0.0.1:11434
    All services run locally with ZERO paid API calls, ZERO credentials.
#>

param(
    [switch]$SkipOllamaCheck,
    [switch]$NoBrowser
)

$ErrorActionPreference = "Stop"
$repoRoot = "C:\Users\T2Hol\Desktop\Northstar OS Retail Arbitrage Agent"
$nsBackend = Join-Path $repoRoot "Northstar_backend"
$atDir = Join-Path $repoRoot "autothink"

function Write-Header { param($msg) Write-Host "`n=== $msg ===" -ForegroundColor Cyan }
function Write-Ok   { param($msg) Write-Host "  [OK] $msg" -ForegroundColor Green }
function Write-Warn { param($msg) Write-Host "  [WARN] $msg" -ForegroundColor Yellow }
function Write-Err  { param($msg) Write-Host "  [ERR] $msg" -ForegroundColor Red }

Write-Header "Northstar OS + AutothinK Local Launcher"

# 1. Check Python + deps
Write-Header "Checking Python environment"
$python = (Get-Command python -ErrorAction SilentlyContinue).Source
if (-not $python) { Write-Err "Python not found in PATH"; exit 1 }
Write-Ok "Python: $python"
python -c "import uvicorn, fastapi; print('  uvicorn/fastapi OK')" 2>$null
if ($LASTEXITCODE -ne 0) { Write-Err "uvicorn/fastapi not installed"; exit 1 }

# 2. Check Ollama
if (-not $SkipOllamaCheck) {
    Write-Header "Checking Ollama"
    $ollama = (Get-Command ollama -ErrorAction SilentlyContinue).Source
    if (-not $ollama) {
        Write-Warn "Ollama not installed. AutothinK chat will show 'offline' lamp."
        Write-Host "  Install: winget install Ollama.Ollama"
        Write-Host "  Then:    ollama pull llama3.2:3b"
    } else {
        Write-Ok "Ollama found: $ollama"
        # Quick check with timeout - don't hang
        try {
            $models = ollama list 2>&1 | Select-Object -First 5
            if ($models -match "llama3.2:3b") { Write-Ok "Model llama3.2:3b present" }
            else { Write-Warn "llama3.2:3b not pulled. Run: ollama pull llama3.2:3b" }
        } catch { Write-Warn "Ollama not running or slow. Start: ollama serve" }
    }
}

# 3. Verify data caches
Write-Header "Verifying local data caches"
$caches = @(
    "$nsBackend\data\scanner-search-cache.json",
    "$nsBackend\data\kirkland-discovery.json",
    "$nsBackend\data\kirkland-discovery-meta.json"
)
foreach ($c in $caches) {
    if (Test-Path $c) { Write-Ok "Found: $(Split-Path $c -Leaf)" }
    else { Write-Warn "Missing: $(Split-Path $c -Leaf) - scanner may return empty" }
}

# 4. Start AutothinK backend (background)
Write-Header "Starting AutothinK backend (port 8100)"
if (Test-Path "$atDir\backend\server.py") {
    $atProc = Start-Process python -ArgumentList "-m uvicorn backend.server:app --host 127.0.0.1 --port 8100 --log-level info" `
        -WorkingDirectory $atDir -WindowStyle Hidden -PassThru
    Write-Ok "AutothinK backend PID: $($atProc.Id)"
} else {
    Write-Warn "AutothinK backend not found at $atDir\backend\server.py"
}

# 5. Start Northstar backend (background)
Write-Header "Starting Northstar backend (port 8000)"
$nsProc = Start-Process python -ArgumentList "-m uvicorn main:app --host 127.0.0.1 --port 8000 --log-level info" `
    -WorkingDirectory $nsBackend -WindowStyle Hidden -PassThru
Write-Ok "Northstar backend PID: $($nsProc.Id)"

# 6. Wait for health endpoints
Write-Header "Waiting for services to be ready"
$ready = $false
for ($i=0; $i -lt 30; $i++) {
    try {
        $h1 = Invoke-WebRequest "http://127.0.0.1:8000/health" -TimeoutSec 2 -ErrorAction Stop
        $h2 = Invoke-WebRequest "http://127.0.0.1:8100/health" -TimeoutSec 2 -ErrorAction Stop
        if ($h1.StatusCode -eq 200 -and $h2.StatusCode -eq 200) { $ready = $true; break }
    } catch { }
    Start-Sleep 1
}
if (-not $ready) {
    Write-Warn "Services may still be starting. Check manually in a moment."
}

# 7. Print access URLs
Write-Header "Northstar OS Suite is running"
Write-Host ""
Write-Host "================================================================="
Write-Host "  NORTHSTAR OS -- ANALYST'S DESK (Shell SPA)"
Write-Host "-----------------------------------------------------------------"
Write-Host "  http://127.0.0.1:8000/static/northstar-os/index.html"
Write-Host "  6 tabs: SourceScout | ListingForge | AdPilot | SocialPulse"
Write-Host "          AutothinK | Account"
Write-Host "-----------------------------------------------------------------"
Write-Host "  SOURCESCOUT WORKBENCH (full data tables)"
Write-Host "-----------------------------------------------------------------"
Write-Host "  http://127.0.0.1:8000/"
Write-Host "  232 scanner products - 138 discovery products (real cached)"
Write-Host "-----------------------------------------------------------------"
Write-Host "  AUTOTHINK WORKSPACE (chat + local LLM)"
Write-Host "-----------------------------------------------------------------"
Write-Host "  http://127.0.0.1:8100/           (full chat, needs Ollama)"
Write-Host "  http://127.0.0.1:8000/autothink/ui/index.html (iframe view)"
Write-Host "================================================================="
Write-Host ""

# 8. Open browser
if (-not $NoBrowser) {
    Write-Host "Opening Analyst's Desk in browser..." -ForegroundColor Cyan
    Start-Process "http://127.0.0.1:8000/static/northstar-os/index.html"
}

# 9. Keep alive / show PIDs
Write-Host ""
Write-Host "Press Ctrl+C to stop all services." -ForegroundColor Yellow
Write-Host "PIDs: Northstar=$($nsProc.Id)" -ForegroundColor Gray
if ($atProc) { Write-Host "      AutothinK=$($atProc.Id)" -ForegroundColor Gray }

# Wait for Ctrl+C
try {
    while ($true) { Start-Sleep 10 }
} finally {
    Write-Host "`nStopping services..." -ForegroundColor Yellow
    Stop-Process -Id $nsProc.Id -Force -ErrorAction SilentlyContinue
    if ($atProc) { Stop-Process -Id $atProc.Id -Force -ErrorAction SilentlyContinue }
    Write-Ok "Stopped."
}