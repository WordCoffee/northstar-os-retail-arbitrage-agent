# Northstar OS — All Tests Runner (A5)
#
# Single local runner for the four sanctioned suites:
#   1. Backend sanitized full suite   (pytest, --ignore=agents/golden_goose_finder/test_single_match.py)
#   2. Golden Goose module suite      (pytest agents/golden_goose_finder/tests)
#   3. SPA UI contract suite          (node test_ui_display.cjs)
#   4. Shell contract suite           (node static/northstar-os/tests/test_shell.cjs)
#
# Known exceptions are BAKED IN (not hidden):
#   - test_single_match.py is excluded (import-time §3 env flip + no async plugin; tracked in
#     docs/PHASE_B_SECURITY_ITEMS.md B4).
#   - The two test_proof_batch_run protected-hash drift failures are EXPECTED and tracked in
#     tests/BASELINE.json known_exceptions; "green" is honest: baseline counts + known failures only.
#
# Regression canary: every count is diffed against tests/BASELINE.json. Any movement off the
# recorded baseline (or an UNKNOWN failure) fails the aggregate with a per-suite diff table.
#
# Usage (Windows / PowerShell):
#   powershell -NoProfile -File scripts/run_all_tests.ps1
# Exit code 0 = GREEN (baseline match, known failures only) ; 1 = regression / mismatch.
# No CI integration — local runner only. Nothing is committed by this script.

$ErrorActionPreference = "Stop"
$Root        = (Get-Item (Join-Path $PSScriptRoot "..")).FullName
$BaselinePath = Join-Path $Root "tests\BASELINE.json"
$BackendDir  = Join-Path $Root "Northstar_backend"
$ShellDir    = Join-Path $Root "Northstar_backend\static\northstar-os"
$TmpDir      = if ($env:TEMP) { $env:TEMP } else { $Root }

function Read-Text($path) {
    try { return Get-Content -Raw -Encoding UTF8 $path } catch {}
    try { return Get-Content -Raw -Encoding Default $path } catch {}
    return ""
}

function Run-Suite($workDir, $cmdLine) {
    $tmp = Join-Path $TmpDir ("ns_run_" + $PID + "_" + (Get-Random -Minimum 10000 -Maximum 99999) + ".txt")
    Push-Location $workDir
    try {
        cmd /c ($cmdLine + " > `"" + $tmp + "`" 2>&1")
        $code = $LASTEXITCODE
    } finally {
        Pop-Location
    }
    $text = Read-Text $tmp
    try { Remove-Item $tmp -Force } catch {}
    return @{ code = $code; text = $text }
}

function Parse-FailIds($text) {
    $ids = @()
    $ms = [regex]::Matches($text, "(?m)^(?:FAILED|ERROR)\s+(\S+)")
    foreach ($md in $ms) { $ids += $md.Groups[1].Value }
    return $ids
}

$mismatch = 0
$unrun    = 0

if (-not (Test-Path $BaselinePath)) {
    Write-Host "FATAL: baseline not found at $BaselinePath" -ForegroundColor Red
    exit 1
}
$baseText = Read-Text $BaselinePath
$base = $null
try { $base = $baseText | ConvertFrom-Json } catch {}
if ($base -eq $null) { Write-Host "FATAL: tests/BASELINE.json is not valid JSON" -ForegroundColor Red; exit 1 }
$known = @($base.known_exceptions.known_failures)

# ---------- 1. backend sanitized full suite ----------
Write-Host "== [1/4] Backend sanitized full suite (pytest) =="
$r = Run-Suite $BackendDir "python -m pytest -q --ignore=agents\golden_goose_finder\test_single_match.py"
$sm = [regex]::Match($r.text, "(\d+)\s+failed,\s+(\d+)\s+passed,\s+(\d+)\s+skipped,\s+(\d+)\s+subtests\s+passed")
if ($sm -eq $null) {
    $bParsed = $false
    Write-Host "  ERROR: could not parse backend summary (pytest exit code $($r.code))" -ForegroundColor Red
    $unrun = $unrun + 1
} else {
    $bParsed = $true
    $bFailed  = [int]$sm.Groups[1].Value
    $bPassed  = [int]$sm.Groups[2].Value
    $bSkipped = [int]$sm.Groups[3].Value
    $bSub     = [int]$sm.Groups[4].Value
    $bIds     = @(Parse-FailIds $r.text)
    $unexpected = @()
    foreach ($id in $bIds) {
        $k = $false
        foreach ($kf in $known) { if ($id -eq $kf) { $k = $true; break } }
        if (-not $k) { $unexpected += $id }
    }
    $bExp = $base.baseline.backend
    $bOk = ($bPassed -eq [int]$bExp.passed) -and ($bSkipped -eq [int]$bExp.skipped) -and ($bSub -eq [int]$bExp.subtests) -and ($bFailed -eq [int]$bExp.failed) -and ($unexpected.Count -eq 0)
    $bLabel = if ($bOk) { "OK" } else { "MISMATCH" }
    Write-Host ("  {0} passed, {1} known pre-existing failures, {2} unexpected | skipped {3} | subtests {4} | {5}" -f $bPassed, $bFailed, $unexpected.Count, $bSkipped, $bSub, $bLabel)
    if (-not $bOk) {
        $mismatch = $mismatch + 1
        if ($bPassed -ne [int]$bExp.passed) { Write-Host ("    diff: backend passed {0} != baseline {1}" -f $bPassed, $bExp.passed) -ForegroundColor Yellow }
        if ($bSkipped -ne [int]$bExp.skipped) { Write-Host ("    diff: backend skipped {0} != baseline {1}" -f $bSkipped, $bExp.skipped) -ForegroundColor Yellow }
        if ($bSub -ne [int]$bExp.subtests) { Write-Host ("    diff: backend subtests {0} != baseline {1}" -f $bSub, $bExp.subtests) -ForegroundColor Yellow }
        if ($bFailed -ne [int]$bExp.failed) { Write-Host ("    diff: backend failed {0} != baseline {1}" -f $bFailed, $bExp.failed) -ForegroundColor Yellow }
        foreach ($u in $unexpected) { Write-Host "    UNEXPECTED FAILURE: $u" -ForegroundColor Red }
    }
}

# ---------- 2. golden goose module suite ----------
Write-Host "== [2/4] Golden Goose module suite (pytest) =="
$r = Run-Suite $BackendDir "python -m pytest -q agents\golden_goose_finder\tests"
$gm = [regex]::Match($r.text, "(\d+)\s+passed")
if ($gm -eq $null) {
    Write-Host "  ERROR: could not parse GG summary (exit $($r.code))" -ForegroundColor Red
    $unrun = $unrun + 1
} else {
    $gPassed = [int]$gm.Groups[1].Value
    $gExp = [int]$base.baseline.golden_goose.passed
    $gIds = @(Parse-FailIds $r.text)
    $gOk = ($gPassed -eq $gExp) -and ($gIds.Count -eq 0)
    $gLabel = if ($gOk) { "OK" } else { "MISMATCH" }
    Write-Host ("  {0} passed, {1} failed | {2}" -f $gPassed, $gIds.Count, $gLabel)
    if (-not $gOk) { $mismatch = $mismatch + 1; Write-Host ("    diff: GG passed {0} != baseline {1}" -f $gPassed, $gExp) -ForegroundColor Yellow }
}

# ---------- 3. SPA UI contract suite ----------
Write-Host "== [3/4] SPA UI contract suite (node test_ui_display.cjs) =="
$r = Run-Suite $BackendDir "node test_ui_display.cjs"
$uiPassed = ([regex]::Matches($r.text, "(?m)^PASS:")).Count
$uiFailed = ([regex]::Matches($r.text, "(?m)^FAIL:")).Count
$uiDone   = [regex]::IsMatch($r.text, "ALL UI DISPLAY TESTS PASSED")
$uiExp = [int]$base.baseline.ui.passed
$uiOk = ($uiPassed -eq $uiExp) -and ($uiFailed -eq 0) -and $uiDone
$uiLabel = if ($uiOk) { "OK" } else { "MISMATCH" }
Write-Host ("  {0} passed, {1} failed | {2}" -f $uiPassed, $uiFailed, $uiLabel)
if (-not $uiOk) { $mismatch = $mismatch + 1; Write-Host ("    diff: UI passed {0} != baseline {1} (or failures/missing marker)" -f $uiPassed, $uiExp) -ForegroundColor Yellow }

# ---------- 4. shell contract suite ----------
Write-Host "== [4/4] Shell contract suite (node tests/test_shell.cjs) =="
$r = Run-Suite $ShellDir "node tests\test_shell.cjs"
$shPassed = ([regex]::Matches($r.text, "(?m)^PASS:")).Count
$shFailed = ([regex]::Matches($r.text, "(?m)^FAIL:")).Count
$shDone   = [regex]::IsMatch($r.text, "ALL GREEN")
$shExp = [int]$base.baseline.shell.passed
$shOk = ($shPassed -eq $shExp) -and ($shFailed -eq 0) -and $shDone
$shLabel = if ($shOk) { "OK" } else { "MISMATCH" }
Write-Host ("  {0} passed, {1} failed | {2}" -f $shPassed, $shFailed, $shLabel)
if (-not $shOk) { $mismatch = $mismatch + 1; Write-Host ("    diff: shell passed {0} != baseline {1} (or failures/missing marker)" -f $shPassed, $shExp) -ForegroundColor Yellow }

# ---------- aggregate ----------
Write-Host ""
$bp = if (Test-Path "variable:bPassed") { $bPassed } else { "?" }
$bf = if (Test-Path "variable:bFailed") { $bFailed } else { "?" }
if ($mismatch -eq 0 -and $unrun -eq 0) {
    Write-Host ("AGGREGATE: {0} backend passed, {1} known pre-existing failures, 0 unexpected -> GREEN" -f $bp, $bf) -ForegroundColor Green
    exit 0
} else {
    Write-Host ("AGGREGATE: {0} backend passed, {1} known pre-existing failures, {2} suite mismatch(es) / {3} unparsed -> RED" -f $bp, $bf, $mismatch, $unrun) -ForegroundColor Red
    exit 1
}