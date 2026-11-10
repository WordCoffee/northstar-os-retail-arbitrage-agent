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
    [string]$Root = "C:\Users\T2Hol\ComfyUI",
    # The documented invocation is `tools/start_comfyui.ps1 --cache-none`, but the
    # flag is always applied below. Accept it (rather than fail parameter binding)
    # so docs and reality agree; anything else unknown is still refused.
    [switch]$CacheNone,
    [Parameter(ValueFromRemainingArguments = $true)][string[]]$Rest
)

$ErrorActionPreference = "Stop"

$unexpected = @($Rest | Where-Object { $_ -and $_ -notin @("--cache-none", "-cache-none") })
if ($unexpected.Count -gt 0) {
    Write-Error ("Unknown argument(s): {0}. Usage: tools/start_comfyui.ps1 [-Port 8188] [-Root <dir>] [--cache-none]" -f ($unexpected -join " "))
    exit 2
}
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
        # B3: record that this engine was started WITH --cache-none. The RAM-heavy
        # lanes refuse to run when the marker says otherwise; a missing marker is
        # "unknown", never "false".
        try {
            $repo = Split-Path -Parent $PSScriptRoot
            $markerDir = Join-Path $repo "Northstar_backend\data"
            New-Item -ItemType Directory -Force -Path $markerDir | Out-Null
            @{
                cache_none = $true
                started_at = (Get-Date).ToUniversalTime().ToString("o")
                argv       = "main.py --listen 127.0.0.1 --port $Port --cache-none"
            } | ConvertTo-Json | Set-Content -Path (Join-Path $markerDir "comfyui_launch.json") -Encoding utf8
        } catch { }
        exit 0
    } catch { }
}

Write-Error "ComfyUI did not become ready within 180 s. See $log.err"
exit 1
