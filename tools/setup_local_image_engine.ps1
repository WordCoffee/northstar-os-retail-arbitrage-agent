<#
.SYNOPSIS
  Localhost-only local image-engine (ComfyUI) setup for the creative dev lane.

.DESCRIPTION
  Prepared, owner-gated setup for running ComfyUI on 127.0.0.1 only. Every step
  that installs software, downloads weights, starts the engine, or arms the
  media gate is OWNER-GATED and requires -IUnderstandThisIsOwnerGated.

  -Check (default) is read-only and safe: it reports exactly what is present vs
  missing and the exact gated step each missing item needs. It installs nothing,
  downloads nothing, starts nothing, and never sets MEDIA_GEN_LIVE.

  Boundaries enforced here:
    * localhost only (--listen 127.0.0.1), never 0.0.0.0 / LAN / public
    * image only (video generation is out of scope)
    * one job at a time (ComfyUI queue default)
    * no cloud providers, no paid calls

.EXAMPLE
  pwsh -File tools/setup_local_image_engine.ps1 -Check

.EXAMPLE
  # OWNER-GATED (do not run without explicit approval):
  pwsh -File tools/setup_local_image_engine.ps1 -Install -DownloadWeights -IUnderstandThisIsOwnerGated
#>
[CmdletBinding()]
param(
  [switch]$Check,
  [switch]$Install,
  [switch]$DownloadWeights,
  [switch]$Start,
  [switch]$IUnderstandThisIsOwnerGated
)

$ErrorActionPreference = 'Stop'
$RepoRoot = Split-Path -Parent $PSScriptRoot
$ComfyHome = if ($env:COMFYUI_HOME) { $env:COMFYUI_HOME } else { Join-Path $RepoRoot 'ComfyUI' }
$ComfyUrl  = if ($env:COMFYUI_URL) { $env:COMFYUI_URL } else { 'http://127.0.0.1:8188' }

function Write-Gate([string]$msg) {
  Write-Host "OWNER-GATED: $msg" -ForegroundColor Yellow
}

function Assert-OwnerGated([string]$action) {
  if (-not $IUnderstandThisIsOwnerGated) {
    Write-Gate "$action requires -IUnderstandThisIsOwnerGated (owner approval)."
    throw "Refused: '$action' is owner-gated. Re-run with -IUnderstandThisIsOwnerGated only after explicit owner approval."
  }
}

function Show-Status {
  Write-Host "== Local image-engine status (read-only) ==" -ForegroundColor Cyan
  python (Join-Path $RepoRoot 'tools/local_image_engine_status.py')
}

# ---- default / -Check: read-only -------------------------------------------------
if ($Check -or (-not ($Install -or $DownloadWeights -or $Start))) {
  Show-Status
  Write-Host ""
  Write-Host "Remaining steps are OWNER-GATED:" -ForegroundColor Yellow
  Write-Host "  1) -Install          : clone ComfyUI + create venv + pip install torch/requirements"
  Write-Host "  2) -DownloadWeights  : download FLUX.1 Dev FP8 + VAE + CLIP into models/"
  Write-Host "  3) -Start            : start ComfyUI on 127.0.0.1:8188 (localhost only)"
  Write-Host "  4) set MEDIA_GEN_LIVE=1 (separate, explicit owner step) before any generation"
  exit 0
}

# ---- -Install (OWNER-GATED) ------------------------------------------------------
if ($Install) {
  Assert-OwnerGated "Install ComfyUI + Python deps"
  Write-Gate "Installing ComfyUI into $ComfyHome (localhost dev lane)."
  if (-not (Test-Path $ComfyHome)) {
    git clone https://github.com/comfyanonymous/ComfyUI.git $ComfyHome
  }
  Push-Location $ComfyHome
  try {
    python -m venv venv
    & (Join-Path $ComfyHome 'venv/Scripts/activate.ps1')
    pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu128
    pip install -r requirements.txt
  } finally {
    Pop-Location
  }
  Write-Host "Install complete. Next (gated): -DownloadWeights." -ForegroundColor Green
}

# ---- -DownloadWeights (OWNER-GATED) ----------------------------------------------
if ($DownloadWeights) {
  Assert-OwnerGated "Download model weights"
  Write-Gate "Downloading FLUX.1 Dev FP8 + encoders into $ComfyHome/models (large: ~18GB)."
  pip install huggingface-hub
  huggingface-cli download Kijai/flux-fp8 flux1-dev-fp8.safetensors --local-dir (Join-Path $ComfyHome 'models/unet')
  huggingface-cli download Kijai/flux-fp8 ae.safetensors --local-dir (Join-Path $ComfyHome 'models/vae')
  huggingface-cli download comfyanonymous/flux_text_encoders clip_l.safetensors --local-dir (Join-Path $ComfyHome 'models/clip')
  huggingface-cli download comfyanonymous/flux_text_encoders t5xxl_fp8_e4m3fn.safetensors --local-dir (Join-Path $ComfyHome 'models/clip')
  Write-Host "Weights downloaded. Next (gated): -Start." -ForegroundColor Green
}

# ---- -Start (OWNER-GATED, localhost only) ----------------------------------------
if ($Start) {
  Assert-OwnerGated "Start ComfyUI"
  Write-Gate "Starting ComfyUI on 127.0.0.1:8188 (localhost only; --lowvram for 16GB)."
  Push-Location $ComfyHome
  try {
    python main.py --lowvram --listen 127.0.0.1 --port 8188
  } finally {
    Pop-Location
  }
}
