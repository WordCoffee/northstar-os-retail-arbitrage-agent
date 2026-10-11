# Northstar OS — local CI-equivalent security checks.
#
#   1. Offline secret scan (tracked files; allowlist + baseline aware)
#   2. Security test harness (tests/security)
#
# Baseline semantics: KNOWN-ACTIVE findings (owner-visible escalations) never
# fail; only NEW findings do. The summary line always prints the counts.
#
# Usage: powershell -NoProfile -File scripts/security_checks.ps1
# Exit 0 = green (no NEW findings, all tests pass); 1 = fail.
$ErrorActionPreference = "Stop"
$Root = (Get-Item (Join-Path $PSScriptRoot "..")).FullName

Push-Location $Root
try {
    Write-Host "== Offline secret scan (tracked; allowlist + baseline) =="
    python -m northstar.security.secret_scan --tracked
    $scanCode = $LASTEXITCODE

    Write-Host ""
    Write-Host "== Security tests (tests/security) =="
    python -m pytest tests/security -q
    $testCode = $LASTEXITCODE

    Write-Host ""
    if ($scanCode -eq 0 -and $testCode -eq 0) {
        Write-Host "SECURITY CHECKS: GREEN (no NEW findings; tests passed)" -ForegroundColor Green
        exit 0
    }
    Write-Host ("SECURITY CHECKS: RED (scan={0}, tests={1})" -f $scanCode, $testCode) -ForegroundColor Red
    exit 1
}
finally {
    Pop-Location
}
