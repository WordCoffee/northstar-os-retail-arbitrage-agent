# Harden the built UI against external reverse-engineering bots — on a COPY, opt-in.
#
# The live `dist/` is never modified by this script. It copies the build to a state directory,
# runs `bla-agents harden` (MIT, npm) against the copy, and prints the per-file result. Shipping
# the hardened copies is a separate review step: serve them and smoke-test before replacing dist.
#
#   powershell -File scripts/harden-ui.ps1
#   powershell -File scripts/harden-ui.ps1 -Source northstar-os-ui/dist -Out state/toolkit/hardened-ui

param(
    [string]$Source = "northstar-os-ui\dist",
    [string]$Out = "state\toolkit\hardened-ui"
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

if (-not (Test-Path $Source)) { Write-Host "harden-ui: $Source is missing; run 'npm run build' first" -ForegroundColor Yellow; exit 2 }
if (Test-Path $Out) { Write-Host "harden-ui: $Out exists; remove it or choose -Out" -ForegroundColor Yellow; exit 2 }

Write-Host "harden-ui: evaluating bla-agents"
python -m tools.ty_toolkit.hardening --evaluate
Write-Host "harden-ui: hardening a copy at $Out (the live build is untouched)"
python -m tools.ty_toolkit.hardening --harden $Source --out $Out --allow-install
Write-Host "harden-ui: hardened copies live under $Out\.bla-hardened; originals are untouched"
Write-Host "harden-ui: review, serve and smoke-test before shipping. This script never replaces dist."
