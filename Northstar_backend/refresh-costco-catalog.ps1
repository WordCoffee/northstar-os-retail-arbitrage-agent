# Northstar Costco discovery catalog refresh (scheduled weekly, off-peak).
# Zero automatic retries: the connector stops on the first
# block/rate-limit/error (401/403 = blocked, 429 = rate_limited) and this
# wrapper does not retry either. The next weekly run is the natural next
# attempt; a stopped run preserves the last-good archive/snapshot/CSV.
$ErrorActionPreference = 'Stop'

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectRoot = Split-Path -Parent $scriptDir
$logPath = Join-Path $projectRoot 'data\costco-refresh.log'

$py = (Get-Command python -ErrorAction SilentlyContinue).Source
if (-not $py) { $py = (Get-Command py -ErrorAction SilentlyContinue).Source }

Set-Location -LiteralPath $scriptDir

$stamp = Get-Date -Format 'yyyy-MM-dd HH:mm:ss zzz'
Add-Content -LiteralPath $logPath -Value "===== [$stamp] costco refresh start ====="

if (-not $py) {
    Add-Content -LiteralPath $logPath -Value "[$stamp] ERROR: python not found on PATH"
    exit 1
}

& $py .\costco_api_client.py refresh *>> $logPath
$code = $LASTEXITCODE

$stamp = Get-Date -Format 'yyyy-MM-dd HH:mm:ss zzz'
Add-Content -LiteralPath $logPath -Value "===== [$stamp] costco refresh done (exit $code) ====="
exit $code
