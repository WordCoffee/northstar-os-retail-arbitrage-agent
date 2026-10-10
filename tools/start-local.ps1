# start-local.ps1 — start the Northstar OS stack for local operator testing.
#
# Solves a real operational problem: NORTHSTAR_JWT_SECRET must be present or the
# hosted login refuses to mint a session (503) and the suite is unusable, but it
# must NOT live in the repo's .env (credential hygiene) and must SURVIVE a
# restart so sessions are not invalidated.
#
# The secret is generated once, stored OUTSIDE the repository with an owner-only
# ACL, and passed to the container through the process environment. It is never
# printed, echoed, or committed.

param(
    [switch]$Rebuild,
    [switch]$Logs
)

$ErrorActionPreference = "Stop"
$repo   = Split-Path -Parent $PSScriptRoot
$secrets = Join-Path $env:LOCALAPPDATA "NorthstarOS"
$secretFile = Join-Path $secrets "jwt-secret.txt"

if (-not (Test-Path $secrets)) { New-Item -ItemType Directory -Force -Path $secrets | Out-Null }

if (Test-Path $secretFile) {
    $secret = (Get-Content $secretFile -Raw).Trim()
    Write-Host "Using the stored signing key (not printed)."
} else {
    # 48 chars of A-Za-z0-9, generated with the CSPRNG.
    $bytes = New-Object byte[] 48
    [System.Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($bytes)
    $secret = -join ($bytes | ForEach-Object { "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789"[$_ % 62] })
    Set-Content -Path $secretFile -Value $secret -NoNewline -Encoding ascii
    try { icacls $secretFile /inheritance:r | Out-Null; icacls $secretFile /grant:r "$($env:USERNAME):(R,W)" | Out-Null } catch { }
    Write-Host "Generated a new signing key and stored it at $secretFile (owner-only)."
}

if (-not $secret) { throw "no signing key available" }

$env:NORTHSTAR_JWT_SECRET = $secret
$env:ENVIRONMENT = "development"
# Restore the edge rate limiter on every normal start (Phase 7 item 3). The
# harness opt-out may have been set for a test run; a plain start-local must
# always come back with the limiter ON. Harness runs that need the opt-out set
# it explicitly on their own docker compose invocation.
$env:NORTHSTAR_DISABLE_RATE_LIMIT = "0"

Push-Location $repo
try {
    if ($Rebuild) {
        Write-Host "Rebuilding the API image (this also rebuilds the SPA inside it)..."
        docker compose build api
        if ($LASTEXITCODE -ne 0) { throw "image build failed" }
    }
    Write-Host "Starting the stack..."
    docker compose up -d
    if ($LASTEXITCODE -ne 0) { throw "compose up failed" }

    Write-Host ""
    Write-Host "Waiting for the API to report healthy..."
    $ok = $false
    for ($i = 0; $i -lt 30; $i++) {
        Start-Sleep -Seconds 3
        try {
            $r = Invoke-WebRequest -Uri "http://127.0.0.1:80/health" -TimeoutSec 5 -UseBasicParsing
            if ($r.StatusCode -eq 200) { $ok = $true; break }
        } catch { }
    }
    if (-not $ok) { Write-Host "API did not become healthy. Check: docker compose logs api" -ForegroundColor Yellow }

    Write-Host ""
    Write-Host "Ready:"
    Write-Host "  Suite   http://localhost/ui/"
    Write-Host "  Sign in http://localhost/ui/sign-in"
    Write-Host ""
    Write-Host "Tail logs with: docker compose logs -f api"
    if ($Logs) { docker compose logs -f api }
} finally {
    Pop-Location
}
