# One improvement cycle. Safe to run from Task Scheduler:
#   - refuses to run when state/improvement/STOP exists
#   - never touches money, ads, or the marketplace
#   - writes a report and a rollback command for every promotion
$ErrorActionPreference = 'Continue'
$repo = Split-Path -Parent $PSScriptRoot
$state = Join-Path $repo 'state\improvement'
$reports = Join-Path $repo 'reports\improvement'
New-Item -ItemType Directory -Force -Path $state, $reports | Out-Null
$log = Join-Path $reports 'loop.log'

if (Test-Path (Join-Path $state 'STOP')) {
    "[$(Get-Date -Format s)] skipped: stop switch is set" | Out-File -FilePath $log -Append -Encoding utf8
    exit 0
}

Push-Location (Join-Path $repo 'Northstar_backend')
$env:PYTHONIOENCODING = 'utf-8'
"[$(Get-Date -Format s)] cycle start" | Out-File -FilePath $log -Append -Encoding utf8
python -m cie_loop --cycle *>> $log
"[$(Get-Date -Format s)] cycle end (exit $LASTEXITCODE)" | Out-File -FilePath $log -Append -Encoding utf8
Pop-Location
