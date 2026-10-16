# ═══════════════════════════════════════════════════════════════════════════
# Create a partner invite (2026-10-16)
#
#   powershell -File tools/create-partner-invite.ps1 -Email partner@example.com
#
# Signs in as the platform admin (operator credentials come from the same env
# convention the harnesses use; nothing is printed), creates a founding-cohort
# invite, and prints the CODE (not any credential). The partner redeems it at
# /ui/sign-in (invite link flow) — see docs/RUNBOOK.md.
# ═══════════════════════════════════════════════════════════════════════════
param(
    [Parameter(Mandatory = $true)][string]$Email,
    [string]$Cohort = "partner",
    [string]$BaseUrl = "http://127.0.0.1:80"
)

$ErrorActionPreference = "Stop"
$loginId = $env:NS_TEST_EMAIL; if (-not $loginId) { $loginId = "t2" }
$loginPw = $env:NS_TEST_PASSWORD; if (-not $loginPw) { $loginPw = "T2holdings" }

$session = New-Object Microsoft.PowerShell.Commands.WebRequestSession
$login = Invoke-RestMethod -Method Post -Uri "$BaseUrl/api/v1/foundation/auth/login" `
    -ContentType "application/json" -WebSession $session `
    -Body (@{ email = $loginId; password = $loginPw } | ConvertTo-Json)

$invite = Invoke-RestMethod -Method Post -Uri "$BaseUrl/api/v1/invites" `
    -ContentType "application/json" -WebSession $session `
    -Body (@{ cohort = $Cohort; email = $Email } | ConvertTo-Json)

$code = $invite.invite.code
Write-Host ""
Write-Host "Invite created for $Email (cohort: $Cohort)" -ForegroundColor Green
Write-Host "  code : $code"
Write-Host "  send : the partner signs up at $BaseUrl/ui/sign-in, then redeems the code"
Write-Host "         (Beta Operations -> invites shows the same list)."
Write-Host ""
Write-Host "The code is shown once here; it is also listed in Beta Operations."
