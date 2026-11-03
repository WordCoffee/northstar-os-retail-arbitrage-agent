# Start (or stop) the local FLUX 3 media lane.
#
#   powershell -File scripts/start-flux3.ps1          # start, idempotent
#   powershell -File scripts/start-flux3.ps1 -Stop    # stop what this script started
#
# What "the lane" is, precisely:
#   ComfyUI  :8188  the local inference runtime (this box has no CUDA torch outside
#                   ComfyUI's venv, so it *is* the runtime, not an optional extra)
#   gateway  :8190  tools/flux3_gateway.py - one model (FLUX 3 Image Klein) behind
#                   GET /health and POST /generate, which tys_ops.graphics and
#                   studio_generation both speak.
#
# The gateway never launches ComfyUI itself (it reports 503 instead), so the
# starter does it, in that order, and refuses on the house resource floors rather
# than let Windows kill a render halfway.
#
# Pilots are read from the environment so this script stays policy-free:
#   FLUX3_UNET / FLUX3_TEXT_ENCODER / FLUX3_VAE  (defaults match the installed nvfp4 pair)
#   COMFYUI_URL                                  (default http://127.0.0.1:8188)

param(
    [switch]$Stop,
    [int]$Port = 8190,
    [int]$ComfyPort = 8188,
    [switch]$NoComfy,
    [int]$TimeoutSeconds = 45
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$pidFile = Join-Path $root "flux3.pids"
$outLog = Join-Path $root "reports\flux3_gateway.out.log"
$errLog = Join-Path $root "reports\flux3_gateway.err.log"

function Test-Health([int]$p) {
    try {
        $r = Invoke-WebRequest -Uri "http://127.0.0.1:$p/health" -TimeoutSec 4 -UseBasicParsing
        return $r.StatusCode -eq 200
    } catch { return $false }
}

if ($Stop) {
    if (-not (Test-Path $pidFile)) { Write-Host "flux3: no pid file, nothing to stop"; exit 0 }
    $pids = (Get-Content $pidFile -Raw).Trim().Split(",") | Where-Object { $_ }
    foreach ($id in $pids) {
        Stop-Process -Id ([int]$id) -Force -ErrorAction SilentlyContinue
        Write-Host "flux3: stopped pid $id"
    }
    Remove-Item $pidFile -ErrorAction SilentlyContinue
    exit 0
}

# ── house floors (the same numbers the operating constitution uses) ──────────
$freeGb = [math]::Round((Get-PSDrive C).Free / 1GB, 1)
if ($freeGb -lt 10) { Write-Host "flux3: REFUSED - free disk is $freeGb GB, the floor is 10 GB"; exit 2 }
$os = Get-CimInstance Win32_OperatingSystem
$freeRamGb = [math]::Round($os.FreePhysicalMemory / 1MB, 1)
if ($freeRamGb -lt 3) { Write-Host "flux3: REFUSED - free RAM is $freeRamGb GB, the floor is 3 GB"; exit 2 }

# ── gateway already up? make this idempotent ────────────────────────────────
if (Test-Health $Port) {
    Write-Host "flux3: gateway already answering on :$Port"
    exit 0
}

# ── runtime first: ComfyUI ───────────────────────────────────────────────────
$comfyUp = $false
try {
    $null = Invoke-WebRequest -Uri "http://127.0.0.1:$ComfyPort/system_stats" -TimeoutSec 4 -UseBasicParsing
    $comfyUp = $true
} catch { $comfyUp = $false }

if (-not $comfyUp -and -not $NoComfy) {
    $starter = Join-Path $root "tools\start_comfyui.ps1"
    if (-not (Test-Path $starter)) {
        Write-Host "flux3: ComfyUI is down and tools/start_comfyui.ps1 is missing"; exit 2
    }
    Write-Host "flux3: starting ComfyUI on :$ComfyPort"
    $comfy = Start-Process -FilePath "powershell" `
        -ArgumentList "-NoProfile","-ExecutionPolicy","Bypass","-File",$starter,"--cache-none" `
        -WindowStyle Hidden -PassThru
    # start_comfyui.ps1 already blocks until ComfyUI answers and then exits: wait for
    # ITS verdict rather than guessing a timeout. A cold start after a hard kill can
    # spend ~2-3 min importing torch and the custom nodes, which is why the old fixed
    # 180 s poll gave up while ComfyUI was still coming up.
    $null = $comfy.WaitForExit(240000)
    $deadline = (Get-Date).AddSeconds(60)
    while ((Get-Date) -lt $deadline) {
        try {
            $null = Invoke-WebRequest -Uri "http://127.0.0.1:$ComfyPort/system_stats" -TimeoutSec 3 -UseBasicParsing
            $comfyUp = $true; break
        } catch { Start-Sleep -Seconds 3 }
    }
    if (-not $comfyUp) { Write-Host "flux3: ComfyUI did not answer on :$ComfyPort (see $Root\comfyui-restart.log)"; exit 2 }
} elseif (-not $comfyUp) {
    Write-Host "flux3: -NoComfy given and ComfyUI is down; the gateway will report 503 by design"
}

# ── gateway ─────────────────────────────────────────────────────────────────
$env:COMFYUI_URL = "http://127.0.0.1:$ComfyPort"
if (-not $env:FLUX3_UNET)         { $env:FLUX3_UNET = "flux3-image-klein-nvfp4.safetensors" }
if (-not $env:FLUX3_TEXT_ENCODER) { $env:FLUX3_TEXT_ENCODER = "qwen3vl_4b_int8_convrot.safetensors" }
if (-not $env:FLUX3_VAE)          { $env:FLUX3_VAE = "flux2-vae.safetensors" }

Write-Host "flux3: starting gateway on :$Port"
$gw = Start-Process -FilePath "python" `
    -ArgumentList "tools\flux3_gateway.py","--host","127.0.0.1","--port","$Port" `
    -WorkingDirectory $root -WindowStyle Hidden -PassThru `
    -RedirectStandardOutput $outLog -RedirectStandardError $errLog

$deadline = (Get-Date).AddSeconds($TimeoutSeconds)
while ((Get-Date) -lt $deadline) {
    Start-Sleep -Seconds 2
    if (Test-Health $Port) { break }
}
if (-not (Test-Health $Port)) {
    Write-Host "flux3: gateway did not answer on :$Port (see $errLog)"
    exit 2
}

$pids = @($gw.Id)
if ($comfyUp -and $comfy) { $pids += $comfy.Id }
$pids -join "," | Out-File -FilePath $pidFile -Encoding UTF8

$h = (Invoke-WebRequest -Uri "http://127.0.0.1:$Port/health" -TimeoutSec 5 -UseBasicParsing).Content
Write-Host "flux3: ready - $h"
