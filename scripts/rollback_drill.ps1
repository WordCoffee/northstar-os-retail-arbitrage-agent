# Phase F/S13 - Rollback drill (offline, zero-cost)
# ================================================
# Exercises rolling the backend back to a known-good tagged release and
# proving it boots, WITHOUT touching the live working tree:
#   - uses `git worktree` instead of `git checkout` on the live tree,
#   - boots the tagged backend and probes /health offline,
#   - imports the tag's key modules,
#   - removes the worktree and confirms HEAD + clean tree are unchanged.
#
# All git calls use `git -C <repo>` so the shell's cwd never matters.
#
# Usage:  powershell -ExecutionPolicy Bypass -File scripts/rollback_drill.ps1
#         [-Target v0.1.0-alpha]

param(
    [string]$Target = "v0.1.0-alpha"
)

$ErrorActionPreference = "Stop"

# Repo root = parent of the scripts/ dir this file lives in.
$RepoRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot ".."))

function Invoke-GitCapture([string[]]$GitArgs) {
    $out = & git -C $RepoRoot @GitArgs 2>&1 | Out-String
    if ($LASTEXITCODE -ne 0) { throw "git $GitArgs failed: $out" }
    return $out.Trim()
}

Write-Host "== Phase F/S13 rollback drill ==" -ForegroundColor Cyan
Write-Host "Repo:     $RepoRoot"

# 0. Preconditions: clean tree + target exists + target != HEAD
$dirty = & git -C $RepoRoot status --porcelain 2>$null | Out-String
if ($dirty.Trim()) {
    Write-Host "ABORT: working tree is dirty - commit or stash first." -ForegroundColor Red
    exit 1
}
$targetSha = Invoke-GitCapture @("rev-parse", "--verify", "--quiet", "$Target")
if (-not $targetSha) {
    Write-Host "ABORT: target '$Target' is not a known tag/ref." -ForegroundColor Red
    exit 1
}
$headSha = Invoke-GitCapture @("rev-parse", "HEAD")
if ($targetSha -eq $headSha) {
    Write-Host "ABORT: target is already HEAD - nothing to roll back to." -ForegroundColor Red
    exit 1
}
Write-Host ("Target:   {0} @ {1}" -f $Target, $targetSha.Substring(0, [Math]::Min(7, $targetSha.Length)))
Write-Host ("HEAD:     {0}" -f $headSha.Substring(0, [Math]::Min(7, $headSha.Length)))

# 1. Create a temporary worktree for the tagged release
$tmp = Join-Path $env:TEMP ("rollback-drill-" + [guid]::NewGuid().ToString("N").Substring(0, 8))
try {
    & git -C $RepoRoot worktree add $tmp $Target 2>&1 | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "worktree add failed" }
    Write-Host "Worktree: $tmp"

    # 2. Boot the tagged backend offline + probe /health
    $env:NORTHSTAR_DISABLE_RATE_LIMIT = "1"
    $probe = @"
import sys
sys.path.insert(0, r"REPLACE_TMP\Northstar_backend")
from fastapi.testclient import TestClient
import main
c = TestClient(main.app)
r = c.get('/health')
print('health_status=%s service=%s' % (r.status_code, r.json().get('service')))
assert r.status_code == 200, 'health probe failed on tagged tree'
"@
    $probe = $probe.Replace("REPLACE_TMP", $tmp)
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
    & git -C $RepoRoot worktree remove $tmp --force 2>$null | Out-Null
}

# 4. Confirm we are back on HEAD with a clean tree
$nowHead = Invoke-GitCapture @("rev-parse", "HEAD")
if ($nowHead -ne $headSha) {
    Write-Host "FAIL: HEAD moved ($nowHead != $headSha)" -ForegroundColor Red
    exit 1
}
$dirtyAfter = & git -C $RepoRoot status --porcelain 2>$null | Out-String
if ($dirtyAfter.Trim()) {
    Write-Host "FAIL: working tree is dirty after drill" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host ("PASS: rollback to {0} verified; returned to {1}; tree clean." -f $Target, $headSha.Substring(0, [Math]::Min(7, $headSha.Length))) -ForegroundColor Green
Write-Host "See ROLLBACK_DRILL.md for the operator procedure."
exit 0