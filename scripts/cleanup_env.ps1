# cleanup_env.ps1 — remove ACL-locked pytest artifacts left by a prior elevated run.
#
# These dirs (created by an elevated Python/pytest process) deny deletion to the
# normal user, so the test harness works around them with a fresh per-run temp
# root. Run THIS script from an ELEVATED PowerShell to remove them:
#
#   Start-Process powershell -Verb RunAs -ArgumentList '-ExecutionPolicy','Bypass','-File','scripts\cleanup_env.ps1'
#
# It removes only pytest caches + the pytest temp root; it never touches source.

$ErrorActionPreference = "Continue"
$repo = Split-Path -Parent $PSScriptRoot

$targets = @(
    (Join-Path $repo ".pytest_cache"),
    (Join-Path $repo "Northstar_backend\.pytest_cache"),
    (Join-Path $repo "autothink\.pytest_cache"),
    (Join-Path $env:TEMP "pytest-of-$env:USERNAME")
)

$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Host "WARNING: not elevated. Locked dirs cannot be removed without Administrator." -ForegroundColor Yellow
    Write-Host "Re-run from an elevated PowerShell." -ForegroundColor Yellow
}

foreach ($d in $targets) {
    if (-not (Test-Path -LiteralPath $d)) { Write-Host "absent  $d"; continue }
    & takeown /f "$d" /r /d y 2>&1 | Out-Null
    & icacls "$d" /grant "$($env:USERDOMAIN)\$($env:USERNAME):(F)" /T /C 2>&1 | Out-Null
    & cmd /c "rmdir /s /q `"$d`"" 2>&1 | Out-Null
    if (Test-Path -LiteralPath $d) { Write-Host "LOCKED  $d" -ForegroundColor Red }
    else { Write-Host "removed $d" -ForegroundColor Green }
}

Write-Host "cleanup_env done."
