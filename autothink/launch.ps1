# Northstar AutoThink launch script (PowerShell)
# Starts the local brain server on http://127.0.0.1:8100 as a hidden background process.
$ErrorActionPreference = "Stop"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $here

Write-Output "Starting Northstar OS AutoThink on http://127.0.0.1:8100 ..."
Start-Process -FilePath "python" -ArgumentList "-m", "uvicorn", "backend.server:app", "--host", "127.0.0.1", "--port", "8100", "--log-level", "info" `
  -WorkingDirectory $here -WindowStyle Hidden

Start-Sleep -Seconds 3
try {
  $r = Invoke-WebRequest -Uri "http://127.0.0.1:8100/health" -UseBasicParsing -TimeoutSec 5
  Write-Output "Health: $($r.StatusCode) $($r.Content)"
} catch {
  Write-Output "Health check failed: $($_.Exception.Message)"
}