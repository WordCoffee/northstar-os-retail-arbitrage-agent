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

# Native CLIs (git/pip/hf) write progress to stderr; 'Stop' would treat that as a
# terminating error. Use 'Continue' and rely on explicit `throw` for gating.
$ErrorActionPreference = 'Continue'
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
  $VenvDir = Join-Path $ComfyHome 'venv'
  $VenvPy  = Join-Path $VenvDir 'Scripts\python.exe'
  if (-not (Test-Path $VenvPy)) { python -m venv $VenvDir }
  & $VenvPy -m pip install --upgrade pip
  & $VenvPy -m pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu128
  & $VenvPy -m pip install -r (Join-Path $ComfyHome 'requirements.txt')
  Write-Host "Install complete. Next (gated): -DownloadWeights." -ForegroundColor Green
}

# ---- -DownloadWeights (OWNER-GATED) ----------------------------------------------
if ($DownloadWeights) {
  Assert-OwnerGated "Download model weights"
  Write-Gate "Downloading FLUX.1 Dev FP8 + encoders into $ComfyHome/models (large: ~18GB)."
  $VenvPy = Join-Path $ComfyHome 'venv\Scripts\python.exe'
  & $VenvPy -m pip install huggingface-hub
  # huggingface_hub >= 1.x deprecates `huggingface-cli`; use the `hf` entry point.
  $HfCli = Join-Path $ComfyHome 'venv\Scripts\hf.exe'
  if (-not (Test-Path $HfCli)) { $HfCli = Join-Path $ComfyHome 'venv\Scripts\huggingface-cli.exe' }
  & $HfCli download Kijai/flux-fp8 flux1-dev-fp8.safetensors --local-dir (Join-Path $ComfyHome 'models/unet')
  # VAE: the BFL repos' ae.safetensors is gated; the Kijai mirror's
  # flux-vae-bf16.safetensors is the same FLUX VAE and is not gated.
  & $HfCli download Kijai/flux-fp8 flux-vae-bf16.safetensors --local-dir (Join-Path $ComfyHome 'models/vae')
  & $HfCli download comfyanonymous/flux_text_encoders clip_l.safetensors --local-dir (Join-Path $ComfyHome 'models/clip')
  & $HfCli download comfyanonymous/flux_text_encoders t5xxl_fp8_e4m3fn.safetensors --local-dir (Join-Path $ComfyHome 'models/clip')
  Write-Host "Weights downloaded. Next (gated): -Start." -ForegroundColor Green
}

# ---- -Start (OWNER-GATED, localhost only) ----------------------------------------
if ($Start) {
  Assert-OwnerGated "Start ComfyUI"
  Write-Gate "Starting ComfyUI on 127.0.0.1:8188 (localhost only; --lowvram for 16GB)."
  $VenvPy = Join-Path $ComfyHome 'venv\Scripts\python.exe'
  Push-Location $ComfyHome
  try {
    & $VenvPy main.py --lowvram --listen 127.0.0.1 --port 8188
  } finally {
    Pop-Location
  }
}
