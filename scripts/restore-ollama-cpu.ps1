# Restore the previous CPU-only Ollama configuration.
#
# The GPU configuration was a deliberate workaround for 16 GB of VRAM shared with
# ComfyUI (see reports/ty/gpu_env_restore.md, commit 01d97bfb). Run this to go back.
#
#   powershell -NoProfile -ExecutionPolicy Bypass -File scripts\restore-ollama-cpu.ps1
param([switch]$RestoreBojo = $false)

$ErrorActionPreference = "Continue"

Write-Host "restoring OLLAMA_LLM_LIBRARY=cpu, OLLAMA_NUM_GPU=0, OLLAMA_MAX_LOADED_MODELS=1 (User scope)"
[Environment]::SetEnvironmentVariable('OLLAMA_LLM_LIBRARY', 'cpu', 'User')
[Environment]::SetEnvironmentVariable('OLLAMA_NUM_GPU', '0', 'User')
[Environment]::SetEnvironmentVariable('OLLAMA_MAX_LOADED_MODELS', '1', 'User')

Write-Host "restarting the Ollama service so it inherits the restored environment"
Get-CimInstance Win32_Process | Where-Object { $_.Name -match '^ollama' } |
    ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
Start-Sleep -Seconds 3
$app = Join-Path $env:LOCALAPPDATA "Programs\Ollama\ollama app.exe"
if (Test-Path $app) {
    Start-Process $app -ArgumentList '--hide' -ErrorAction SilentlyContinue
} else {
    Write-Host "ollama app.exe not found at $app; start it manually"
}

if ($RestoreBojo) {
    Write-Host "restoring Bojo from quarantine (bojo:cpu-quarantine -> bojo:latest)"
    ollama cp bojo:cpu-quarantine bojo:latest
}

Write-Host "restored. Verify with:  ollama ps   and   nvidia-smi --query-gpu=memory.used --format=csv"
