# ═══════════════════════════════════════════════════════════════════════════
# Create a partner invite (2026-10-16)
#
#   powershell -File tools/create-partner-invite.ps1 -Email partner@example.com
#
# Signs in as the operator (same env convention as the harnesses; nothing is
# printed), creates an invite through the FOUNDATION invites route (the one the
# Beta Operations UI uses), and prints the CODE only. CSRF: the login sets the
# ns_csrf cookie; state-changing calls must echo it in X-CSRF-Token.
# The partner redeems it at /ui/sign-in — see docs/RUNBOOK.md.
# ═══════════════════════════════════════════════════════════════════════════
param(
    [Parameter(Mandatory = $true)][string]$Email,
    [string]$Role = "organization_owner",
    [string]$BaseUrl = "http://127.0.0.1:80"
)

$ErrorActionPreference = "Stop"
$loginId = $env:NS_TEST_EMAIL; if (-not $loginId) { $loginId = "t2" }
$loginPw = $env:NS_TEST_PASSWORD; if (-not $loginPw) { $loginPw = "T2holdings" }

$session = New-Object Microsoft.PowerShell.Commands.WebRequestSession
Invoke-RestMethod -Method Post -Uri "$BaseUrl/api/v1/foundation/auth/login" `
    -ContentType "application/json" -WebSession $session `
    -Body (@{ email = $loginId; password = $loginPw } | ConvertTo-Json) | Out-Null

$csrf = ($session.Cookies.GetCookies($BaseUrl) | Where-Object { $_.Name -eq "ns_csrf" }).Value
if (-not $csrf) { throw "login did not set the ns_csrf cookie" }

$invite = Invoke-RestMethod -Method Post -Uri "$BaseUrl/api/v1/foundation/invites" `
    -ContentType "application/json" -WebSession $session `
    -Headers @{ "X-CSRF-Token" = $csrf } `
    -Body (@{ email = $Email; role = $Role } | ConvertTo-Json)

$code = $invite.invite_code
if (-not $code) { $code = $invite.invite.code }
if (-not $code) { $code = $invite.code }
Write-Host ""
Write-Host "Invite created for $Email (role: $Role)" -ForegroundColor Green
Write-Host "  code : $code"
Write-Host "  send : the partner signs up at $BaseUrl/ui/sign-in, then redeems the code."
Write-Host "         The same list lives in Beta Operations -> invites."
Write-Host ""
