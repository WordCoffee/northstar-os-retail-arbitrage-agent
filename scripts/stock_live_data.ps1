# stock_live_data.ps1 — pour live free-tier data into the warehouse (Phase A/A3)
#
# Offline by default (dry summary). Pass -Live to fire real free-tier calls;
# this requires the §3 operator envelope already set in the environment:
#   $env:GOLDEN_GOOSE_LIVE_OPERATOR_APPROVED = "1"
#
# Usage:
#   powershell -File scripts\stock_live_data.ps1                 # offline summary
#   powershell -File scripts\stock_live_data.ps1 -Live           # real pulls
#   powershell -File scripts\stock_live_data.ps1 -Live -Query "gift for mom"

param(
    [switch]$Live,
    [string[]]$Query = @(),
    [string]$Wholesale = "",
    [int]$TtlSeconds = 0
)

$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent $PSScriptRoot
$backend = Join-Path $repo "Northstar_backend"

$pyArgs = @("stock_runner.py")
if ($Live) { $pyArgs += "--live" }
foreach ($q in $Query) { $pyArgs += @("--query", $q) }
if ($Wholesale) { $pyArgs += @("--wholesale", $Wholesale) }
if ($TtlSeconds -gt 0) { $pyArgs += @("--ttl-seconds", "$TtlSeconds") }

Write-Host "== stock_live_data (live=$Live) =="
Push-Location $backend
try {
    & python @pyArgs
    if ($LASTEXITCODE -ne 0) { throw "stock_runner failed (exit $LASTEXITCODE)" }
} finally {
    Pop-Location
}
