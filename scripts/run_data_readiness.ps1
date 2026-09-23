# run_data_readiness.ps1 — per-service data readiness check (Phase A/A4)
#
# Offline by default. Pass -Live to also fire a small free-tier probe (requires
# the §3 operator envelope in the environment).
#
# Usage:
#   powershell -File scripts\run_data_readiness.ps1            # offline report
#   powershell -File scripts\run_data_readiness.ps1 -Live      # + live probe
#   powershell -File scripts\run_data_readiness.ps1 -Json      # full JSON

param(
    [switch]$Live,
    [switch]$Json
)

$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent $PSScriptRoot
$backend = Join-Path $repo "Northstar_backend"

$pyArgs = @("-m", "readiness")
if ($Live) { $pyArgs += "--live" }
if ($Json) { $pyArgs += "--json" }

Write-Host "== run_data_readiness (live=$Live) =="
Push-Location $backend
try {
    & python @pyArgs
    $code = $LASTEXITCODE
} finally {
    Pop-Location
}
if ($code -ne 0 -and -not $Json) {
    Write-Host "Readiness: NOT all services ready (exit $code)."
}
exit $code
