# Start the local ComfyUI the way the Design Studio expects it.
#
#   powershell -File tools/start_comfyui.ps1
#
# Why the flags matter (measured 2026-10-22 on this box: 15.4 GB RAM / 16 GB VRAM):
#
#   --cache-none   REQUIRED for the edit lane. Without it ComfyUI keeps the 8 GB
#                  text encoder resident while it loads the 12.3 GB
#                  qwen-image-edit model, the process peaks past the RAM/commit
#                  ceiling and Windows kills it mid-render. With it, peak drops to
#                  roughly the size of the largest single model. Cost: a small
#                  reload penalty between runs.
#
#   127.0.0.1:8188 must match studio_generation.DEFAULT_COMFYUI_URL. If you run it
#                  on another port, set COMFYUI_URL to match instead of editing code.

param(
    [int]$Port = 8188,
    [string]$Root = "C:\Users\T2Hol\ComfyUI"
)

$ErrorActionPreference = "Stop"
$url = "http://127.0.0.1:$Port"

if (Test-NetConnection 127.0.0.1 -Port $Port -InformationLevel Quiet -WarningAction SilentlyContinue) {
    Write-Host "ComfyUI is already listening on $url - nothing to do."
    exit 0
}

$python = Join-Path $Root "venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
    Write-Error "No venv python at $python"
    exit 1
}

$log = Join-Path $Root "comfyui-restart.log"
Start-Process -FilePath $python `
    -ArgumentList "main.py", "--listen", "127.0.0.1", "--port", "$Port", "--cache-none" `
    -WorkingDirectory $Root `
    -RedirectStandardOutput $log `
    -RedirectStandardError "$log.err" `
    -WindowStyle Hidden | Out-Null

for ($i = 0; $i -lt 90; $i++) {
    Start-Sleep -Seconds 2
    try {
        Invoke-RestMethod "$url/system_stats" -TimeoutSec 3 | Out-Null
        Write-Host "ComfyUI ready at $url (log: $log)"
        exit 0
    } catch { }
}

Write-Error "ComfyUI did not become ready within 180 s. See $log.err"
exit 1
