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

# Live grading only when the engine is actually up; otherwise the cycle still
# runs (knowledge work does not need the model) and the report says so.
$ollama = 0
try {
    $ollama = (Invoke-WebRequest 'http://127.0.0.1:11434/api/version' -TimeoutSec 3 -UseBasicParsing).StatusCode
} catch { $ollama = 0 }
if ($ollama -eq 200) {
    "[$(Get-Date -Format s)] live grading: on (5 questions)" | Out-File -FilePath $log -Append -Encoding utf8
    python -m cie_loop --cycle --live --live-limit 5 *>> $log
} else {
    "[$(Get-Date -Format s)] live grading: skipped (engine not answering)" | Out-File -FilePath $log -Append -Encoding utf8
    python -m cie_loop --cycle *>> $log
}
"[$(Get-Date -Format s)] cycle end (exit $LASTEXITCODE)" | Out-File -FilePath $log -Append -Encoding utf8
Pop-Location
