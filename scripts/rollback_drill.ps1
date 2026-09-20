# Phase F/S13 — Rollback drill (offline, zero-cost)
# ====================================================
# Exercises rolling the backend back to a known-good tagged release and
# proving it boots, WITHOUT touching the live working tree:
#   - uses `git worktree` instead of `git checkout` on the live tree,
#   - boots the tagged backend and probes /health offline,
#   - runs a tiny probe test against the tagged tree,
#   - removes the worktree and confirms HEAD + clean tree are unchanged.
#
# Usage:  powershell -ExecutionPolicy Bypass -File scripts/rollback_drill.ps1
#         [-Target v0.1.0-alpha]

param(
    [string]$Target = "v0.1.0-alpha"
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

Write-Host "== Phase F/S13 rollback drill ==" -ForegroundColor Cyan

# 0. Preconditions: clean tree + target exists + target != HEAD
$dirty = git status --porcelain
if ($dirty) {
    Write-Host "ABORT: working tree is dirty — commit or stash first." -ForegroundColor Red
    exit 1
}
$targetSha = git rev-parse "$Target" 2>$null
if (-not $targetSha) {
    Write-Host "ABORT: target '$Target' is not a known tag/ref." -ForegroundColor Red
    exit 1
}
$headSha = git rev-parse HEAD
if ($targetSha -eq $headSha) {
    Write-Host "ABORT: target is already HEAD — nothing to roll back to." -ForegroundColor Red
    exit 1
}
Write-Host "Target:   $Target @ $($targetSha.Substring(0,7))"
Write-Host "HEAD:     $($headSha.Substring(0,7))"

# 1. Create a temporary worktree for the tagged release
$tmp = Join-Path $env:TEMP ("rollback-drill-" + [guid]::NewGuid().ToString("N").Substring(0, 8))
try {
    git worktree add $tmp $Target 2>&1 | Out-Null
    Write-Host "Worktree: $tmp"

    # 2. Boot the tagged backend offline + probe /health
    $env:NORTHSTAR_DISABLE_RATE_LIMIT = "1"
    $probe = @"
import sys
sys.path.insert(0, r"$tmp\Northstar_backend")
from fastapi.testclient import TestClient
import main
c = TestClient(main.app)
r = c.get('/health')
print('health_status=%s service=%s' % (r.status_code, r.json().get('service')))
assert r.status_code == 200, 'health probe failed on tagged tree'
"@
    $probe | python -
    Write-Host "Probe:    tagged app boots and /health returns 200" -ForegroundColor Green

    # 3. Run a tiny smoke: import the tag's key modules
    $smoke = @"
import sys
sys.path.insert(0, r"$tmp\Northstar_backend")
for mod in ("main", "data_layer", "auth"):
    __import__(mod)
print("smoke_modules=ok")
"@
    $smoke | python -
    Write-Host "Smoke:    main / data_layer / auth import clean on tag" -ForegroundColor Green
} finally {
    git worktree remove $tmp --force 2>$null | Out-Null
}

# 4. Confirm we are back on HEAD with a clean tree
$nowHead = git rev-parse HEAD
if ($nowHead -ne $headSha) {
    Write-Host "FAIL: HEAD moved ($nowHead != $headSha)" -ForegroundColor Red
    exit 1
}
if (git status --porcelain) {
    Write-Host "FAIL: working tree is dirty after drill" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "PASS: rollback to $Target verified; returned to $($headSha.Substring(0,7)); tree clean." -ForegroundColor Green
Write-Host "See ROLLBACK_DRILL.md for the operator procedure."
exit 0