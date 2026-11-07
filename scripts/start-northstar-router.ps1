# Start the NorthstarOS lane router (idempotent).
# The router listens on 127.0.0.1:8090 and fronts both llama.cpp lanes so
# OpenCode sees "NorthstarOS 27b Coder" and "NorthstarOS Thinking" under one provider.
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot

try {
  $h = (Invoke-WebRequest -UseBasicParsing -TimeoutSec 2 "http://127.0.0.1:8090/health").Content
  if ($h -match "ok") { Write-Host "lane router already running on 127.0.0.1:8090"; exit 0 }
} catch {}

$logDir = "$env:USERPROFILE\.config\northstar-llm"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
Start-Process -FilePath "python" `
  -ArgumentList (Join-Path $root "tools\northstar_lane_router.py") `
  -WorkingDirectory $root -WindowStyle Hidden `
  -RedirectStandardOutput (Join-Path $logDir "router.out") `
  -RedirectStandardError (Join-Path $logDir "router.err") | Out-Null

for ($i = 0; $i -lt 30; $i++) {
  Start-Sleep -Seconds 1
  try {
    if ((Invoke-WebRequest -UseBasicParsing -TimeoutSec 2 "http://127.0.0.1:8090/health").Content -match "ok") {
      Write-Host "lane router ready on http://127.0.0.1:8090/v1"; exit 0
    }
  } catch {}
}
throw "lane router did not become healthy"
