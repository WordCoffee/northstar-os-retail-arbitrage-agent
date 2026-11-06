# Northstar OS — All Tests Runner (A5)
#
# Single local runner for the four sanctioned suites:
#   1. Backend sanitized full suite   (pytest, --ignore=agents/golden_goose_finder/test_single_match.py)
#   2. Golden Goose module suite      (pytest agents/golden_goose_finder/tests)
#   3. SPA UI contract suite          (node test_ui_display.cjs)
#   4. Shell contract suite           (node legacy/northstar-os/tests/test_shell.cjs)
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

# -SelfTest runs the pytest-summary parser against known summary shapes and
# exits. The parser is the canary's only measuring instrument: when it failed to
# read a green suite the whole aggregate went RED and nobody could tell a real
# regression from a parsing bug. It is exercised here instead of trusted.
param([switch]$SelfTest)

$ErrorActionPreference = "Stop"

function Parse-PytestSummary($text) {
    # The summary is the LAST line that reports a pass count with a duration.
    # Counting the tokens independently is deliberate: a single regex that
    # assumed "passed, skipped, <n> subtests passed" silently failed the moment
    # pytest inserted anything between them (an xfailed count, an error count, a
    # warnings count), which is exactly what happened on 2026-11-05.
    $line = ($text -split "`r?`n" |
        Where-Object { $_ -match '\bpassed\b' -and $_ -match ' in \d' } |
        Select-Object -Last 1)
    if (-not $line) { return $null }
    $count = {
        param($pattern, $default)
        $m = [regex]::Match($line, $pattern)
        if ($m.Success) { return [int]$m.Groups[1].Value }
        return $default
    }
    return @{
        passed   = (& $count '(\d+)\s+passed' 0)
        failed   = (& $count '(\d+)\s+failed' 0)
        errors   = (& $count '(\d+)\s+error' 0)
        skipped  = (& $count '(\d+)\s+skipped' 0)
        subtests = (& $count '(\d+)\s+subtests\s+passed' 0)
        line     = $line
    }
}

if ($SelfTest) {
    $cases = @(
        @{ name = "green with xfailed"; text = "6105 passed, 117 skipped, 2 xfailed, 18 warnings, 89 subtests passed in 956.78s (0:15:56)"; passed = 6105; failed = 0; skipped = 117; subtests = 89 },
        @{ name = "failures and xfailed"; text = "5918 passed, 10 failed, 117 skipped, 2 xfailed, 89 subtests passed in 774.83s"; passed = 5918; failed = 10; skipped = 117; subtests = 89 },
        @{ name = "decorated summary"; text = "===== 42 passed, 3 skipped in 1.20s ====="; passed = 42; failed = 0; skipped = 3; subtests = 0 },
        @{ name = "short suite, warning token"; text = "3 passed, 1 warning in 0.42s"; passed = 3; failed = 0; skipped = 0; subtests = 0 },
        @{ name = "errors are failures"; text = "7 passed, 2 errors in 3.10s"; passed = 7; failed = 2; skipped = 0; subtests = 0 },
        @{ name = "nothing collected"; text = "no tests ran in 0.12s"; passed = $null; failed = $null; skipped = $null; subtests = $null }
    )
    $bad = 0
    foreach ($case in $cases) {
        $got = Parse-PytestSummary $case.text
        $ok = $true
        if ($null -eq $case.passed) {
            $ok = ($null -eq $got)
        } elseif ($null -eq $got) {
            $ok = $false
        } else {
            # failed and errors are summed the same way the runner does it.
            $ok = ($got.passed -eq $case.passed) -and
                  (($got.failed + $got.errors) -eq $case.failed) -and
                  ($got.skipped -eq $case.skipped) -and ($got.subtests -eq $case.subtests)
        }
        if ($ok) { Write-Host ("PASS  " + $case.name) }
        else { Write-Host ("FAIL  " + $case.name) -ForegroundColor Red; $bad = $bad + 1 }
    }
    if ($bad -eq 0) { Write-Host "RUNNER SELF-TEST OK"; exit 0 }
    Write-Host ("RUNNER SELF-TEST FAILED: $bad case(s)") -ForegroundColor Red
    exit 1
}

$Root        = (Get-Item (Join-Path $PSScriptRoot "..")).FullName
$BaselinePath = Join-Path $Root "tests\BASELINE.json"
$BackendDir  = Join-Path $Root "Northstar_backend"
$ShellDir    = Join-Path $Root "legacy\northstar-os"
$TmpDir      = if ($env:TEMP) { $env:TEMP } else { $Root }
# Harness-only: disable the edge rate limiter so the shared test process
# (one client id) is not throttled by the anonymous 30/min production limit.
# Product limits are unchanged — this only affects the runner's own runs.
$env:NORTHSTAR_DISABLE_RATE_LIMIT = "1"
# Fresh per-run pytest temp root. A stale or ACL-locked pytest-of-* dir in the
# user temp (WinError 5 on os.scandir) would otherwise error every tmp_path
# fixture and false-fail the whole suite. Isolation only - counts must still
# match BASELINE.json exactly.
$FreshTmp = Join-Path $TmpDir ("northstar-pt-" + $PID + "-" + (Get-Date -Format "yyyyMMddHHmmss"))
New-Item -ItemType Directory -Force -Path $FreshTmp | Out-Null
$env:TEMP = $FreshTmp
$env:TMP  = $FreshTmp

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
$hasFunctions = ($null -ne $base.baseline.functions)

# ---------- 1. backend sanitized full suite ----------
Write-Host "== [1/4] Backend sanitized full suite (pytest) =="
# Name-based regression guard (M0.2): the run emits junit so a test can be
# compared BY NAME. Counting alone made the canary go RED whenever the loop
# added a test, which would have had it "fixing" its own new tests.
$JunitPath = Join-Path $TmpDir ("ns_ids_" + $PID + ".json")
$r = Run-Suite $BackendDir "python -m pytest -q -p no:cacheprovider -p pytest_idlist --idlist=`"$JunitPath`""
# Parsed by Parse-PytestSummary (defined above and exercised by -SelfTest):
# a missing token is 0, and the line may carry xfailed/warning tokens.
$sm = Parse-PytestSummary $r.text
if (-not $sm) {
    $bParsed = $false
    Write-Host "  ERROR: could not parse backend summary (pytest exit code $($r.code))" -ForegroundColor Red
    $unrun = $unrun + 1
} else {
    $bParsed = $true
    $bFailed  = $sm.failed + $sm.errors
    $bPassed  = $sm.passed
    $bSkipped = $sm.skipped
    $bSub     = $sm.subtests
    $bIds     = @(Parse-FailIds $r.text)
    $unexpected = @()
    foreach ($id in $bIds) {
        $k = $false
        foreach ($kf in $known) { if ($id -eq $kf) { $k = $true; break } }
        if (-not $k) { $unexpected += $id }
    }
    $bExp = $base.baseline.backend
    # M0.2: identity is checked BY NAME (below, from junit). Counting is now only a
    # floor - "we did not lose tests" - because the loop adds tests every cycle and
    # strict equality turned the canary red on its own progress.
    $bOk = ($bPassed -ge [int]$bExp.passed) -and ($bFailed -eq [int]$bExp.failed) -and ($unexpected.Count -eq 0)
    $bLabel = if ($bOk) { "OK" } else { "MISMATCH" }
    Write-Host ("  {0} passed, {1} known pre-existing failures, {2} unexpected | skipped {3} | subtests {4} | {5}" -f $bPassed, $bFailed, $unexpected.Count, $bSkipped, $bSub, $bLabel)
    if (-not $bOk) {
        $mismatch = $mismatch + 1
        if ($bPassed -lt [int]$bExp.passed) { Write-Host ("    diff: backend passed {0} < baseline {1} (tests lost?)" -f $bPassed, $bExp.passed) -ForegroundColor Yellow }
        if ($bSkipped -ne [int]$bExp.skipped) { Write-Host ("    note: skipped {0} vs baseline {1} (informational)" -f $bSkipped, $bExp.skipped) -ForegroundColor DarkGray }
        if ($bSub -ne [int]$bExp.subtests) { Write-Host ("    note: subtests {0} vs baseline {1} (informational)" -f $bSub, $bExp.subtests) -ForegroundColor DarkGray }
        if ($bFailed -ne [int]$bExp.failed) { Write-Host ("    diff: backend failed {0} != baseline {1}" -f $bFailed, $bExp.failed) -ForegroundColor Yellow }
        foreach ($u in $unexpected) { Write-Host "    UNEXPECTED FAILURE: $u" -ForegroundColor Red }
    }
}

# Name-based regression guard (M0.2). Additions are fine; a removed test or a
# failing test blocks, by name, with the junit the run just produced.
if (Test-Path $JunitPath) {
    $nr = Run-Suite $Root "python tools\check_regression.py --idlist `"$JunitPath`""
    $nameLine = ($nr.text -split "`r?`n" | Where-Object { $_ -match 'tests, baseline' } | Select-Object -Last 1)
    if ($nr.code -eq 0) {
        Write-Host ("  by name: {0}" -f $nameLine)
    } else {
        Write-Host ("  by name: REGRESSION - {0}" -f $nameLine) -ForegroundColor Red
        foreach ($l in ($nr.text -split "`r?`n" | Where-Object { $_ -match 'REMOVED|FAILED' } | Select-Object -First 10)) {
            Write-Host ("    " + $l.Trim()) -ForegroundColor Red
        }
        $mismatch = $mismatch + 1
    }
    try { Remove-Item $JunitPath -Force } catch {}
} else {
    Write-Host "  by name: SKIPPED (no junit produced)" -ForegroundColor Yellow
    $unrun = $unrun + 1
}

# ---------- 2. golden goose module suite ----------
Write-Host "== [2/4] Golden Goose module suite (pytest) =="
$r = Run-Suite $BackendDir "python -m pytest -q -p no:cacheprovider agents\golden_goose_finder\tests"
$gm = [regex]::Match($r.text, "(\d+)\s+passed")
if (-not $gm.Success) {
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

# ---------- 5. Cloudflare Functions contract suite ----------
Write-Host "== [5/5] Cloudflare Functions contract suite (node test_functions_contract.cjs) =="
$r = Run-Suite $BackendDir "node test_functions_contract.cjs"
$fnPassed = ([regex]::Matches($r.text, "(?m)^PASS:")).Count
$fnFailed = ([regex]::Matches($r.text, "(?m)^FAIL:")).Count
$fnDone   = [regex]::IsMatch($r.text, "FUNCTIONS CONTRACT OK")
if ($hasFunctions) {
    $fnExp = [int]$base.baseline.functions.passed
    $fnOk = ($fnPassed -eq $fnExp) -and ($fnFailed -eq 0) -and $fnDone
    $fnLabel = if ($fnOk) { "OK" } else { "MISMATCH" }
    Write-Host ("  {0} passed, {1} failed | {2}" -f $fnPassed, $fnFailed, $fnLabel)
    if (-not $fnOk) { $mismatch = $mismatch + 1; Write-Host ("    diff: functions passed {0} != baseline {1} (or failures/missing marker)" -f $fnPassed, $fnExp) -ForegroundColor Yellow }
} else {
    $fnOk = ($fnFailed -eq 0) -and $fnDone
    $fnLabel = if ($fnOk) { "OK" } else { "MISMATCH" }
    Write-Host ("  {0} passed, {1} failed | baseline not recorded yet (will record after next baseline update) | {2}" -f $fnPassed, $fnFailed, $fnLabel)
    if (-not $fnOk) { $mismatch = $mismatch + 1 }
}

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