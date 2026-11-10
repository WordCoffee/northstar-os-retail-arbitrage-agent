# ═══════════════════════════════════════════════════════════════════════════
# FULL REGRESSION RUNNER (2026-10-11 final pass)
#
# Runs every harness in the repo, one output file per harness, and writes a
# summary with exit codes. The output dir is passed as -Out.
#
# Posture expected: local stack up (API :8000, Caddy :80, test preview :8200),
# NORTHSTAR_DISABLE_RATE_LIMIT=1 + NORTHSTAR_LOGIN_THROTTLE_TEST_BYPASS=1 on the
# API container (harness runs only; tools/start-local.ps1 restores normal).
#
# Usage:  powershell -File tools/run-regression.ps1 -Out reports/regression_20261011_final
# ═══════════════════════════════════════════════════════════════════════════
param(
  [string]$Out = "reports/regression_20261011_final"
)

$ErrorActionPreference = "Continue"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
New-Item -ItemType Directory -Force -Path $Out | Out-Null
$summary = @()

function Run-Harness([string]$name, [string]$cmd, [string]$envTest = "no") {
  $file = Join-Path $Out "$name.txt"
  Write-Host "=== $name ==="
  if ($envTest -eq "test") {
    $env:HARNESS_MODE = "test"
    $env:HARNESS_BASE_URL = "http://127.0.0.1:8200/ui/"
  } else {
    Remove-Item Env:\HARNESS_MODE -ErrorAction SilentlyContinue
    Remove-Item Env:\HARNESS_BASE_URL -ErrorAction SilentlyContinue
  }
  $started = Get-Date
  cmd /c "$cmd > `"$file`" 2>&1"
  $code = $LASTEXITCODE
  $secs = [math]::Round(((Get-Date) - $started).TotalSeconds, 1)
  $last = ""
  if (Test-Path $file) { $last = (Get-Content $file -Tail 1) -join " " }
  $script:summary += [pscustomobject]@{ Harness = $name; Exit = $code; Seconds = $secs; Last = $last }
  Write-Host ("    exit {0} in {1}s :: {2}" -f $code, $secs, $last.Substring(0, [Math]::Min(90, $last.Length)))
  Remove-Item Env:\HARNESS_MODE -ErrorAction SilentlyContinue
  Remove-Item Env:\HARNESS_BASE_URL -ErrorAction SilentlyContinue
}

Run-Harness "01-compliance"            "node tools/test-compliance-rules.mjs"
Run-Harness "02-disclosure"            "node tools/test-disclosure.mjs"
Run-Harness "03-fidelity"              "node tools/test-fidelity-freshness.mjs"
Run-Harness "04-generation"            "node tools/test-generation.mjs"
Run-Harness "05-indexing"              "node tools/test-indexing-register.mjs"
Run-Harness "06-registry-claims"       "node tools/test-registry-claims.mjs"
Run-Harness "07-isolation"             "python tools/test_design_studio_isolation.py"
Run-Harness "08-login-throttle"        "python tools/test_login_throttle_bypass.py"
Run-Harness "09-import-fixtures"       "python tools/test_design_studio_imports.py"
Run-Harness "10-d10-fixtures"          "python tools/test_d10_identity_migration.py"
Run-Harness "11-rate-limit"            "python -m pytest Northstar_backend/test_rate_limit_posture.py -q"
Run-Harness "12-auth-guard"            "python -m pytest Northstar_backend/test_alpha_gate.py Northstar_backend/test_jwt_secret_posture.py Northstar_backend/test_security_boundaries.py -q"
Run-Harness "13-jsx"                   "python tools/check-jsx-imports.py"
Run-Harness "14-prod-bundle"           "node tools/check-prod-bundle.cjs"
Run-Harness "15-compose"               "node tools/check-compose-deploy.cjs"
Run-Harness "17-tenant-cleanup-dryrun" "python Northstar_backend/cleanup_test_tenants.py"
Run-Harness "18-no-amazon-linkage"     "python tools/test_no_amazon_linkage.py"
Run-Harness "19-amazon-files-unit"     "python tools/test_amazon_files.py"
Run-Harness "20-compositing-prod"      "node tools/test-compositing.cjs"
Run-Harness "21-compositing-test"      "node tools/test-compositing.cjs" "test"
Run-Harness "22-design-studio"         "node tools/verify-design-studio.cjs"
Run-Harness "23-migration-e2e"         "node tools/test-migration-e2e.cjs"
Run-Harness "24-operator-smoke"        "node tools/verify-operator-smoke.cjs"
Run-Harness "25-search-terms"          "node tools/verify-search-terms.cjs"
Run-Harness "26-d10-live"              "node tools/verify-d10-live.cjs"
Run-Harness "27-projects-gates"        "node tools/verify-projects-gates.cjs"
Run-Harness "28-render3d-gate"         "node tools/verify-render3d-gate.cjs"
Run-Harness "29-3d-editing"            "node tools/verify-3d-editing.cjs"
Run-Harness "30-title-contract"        "node tools/verify-title-contract.cjs"
Run-Harness "31-master-brain-panels"   "node tools/verify-master-brain-panels.cjs"
Run-Harness "32-shim-fail-closed"      "node tools/verify-shim-fail-closed.cjs"
Run-Harness "33-recheck-migration"     "node tools/_check-recheck-migration.cjs"
Run-Harness "34-fidelity-trial"        "node tools/fidelity-trial.cjs"
Run-Harness "35-amazon-files-api"      "node tools/verify-amazon-files.cjs"
Run-Harness "36-amazon-files-ui"       "node tools/verify-amazon-files-ui.cjs"
Run-Harness "37-section-evidence"      "node tools/capture-section-evidence.cjs"
Run-Harness "38-section-packs"         "node tools/verify-section-packs.cjs" "test"
Run-Harness "39-no-third-party"        "node tools/check-no-third-party.cjs"
Run-Harness "40-box-library"           "node tools/verify-box-library.cjs"

# 16 — the Postgres store harness runs INSIDE the API container (it needs the
# compose network for the postgres service).
$pgFile = Join-Path $Out "16-postgres-store.txt"
Write-Host "=== 16-postgres-store ==="
docker cp tools/test_design_studio_pg.py northstarosretailarbitrageagent-api-1:/app/Northstar_backend/test_design_studio_pg.py > $null 2>&1
cmd /c "docker exec northstarosretailarbitrageagent-api-1 python test_design_studio_pg.py > `"$pgFile`" 2>&1"
$pgCode = $LASTEXITCODE
$pgLast = (Get-Content $pgFile -Tail 1) -join " "
$summary += [pscustomobject]@{ Harness = "16-postgres-store"; Exit = $pgCode; Seconds = 0; Last = $pgLast }
Write-Host ("    exit {0} :: {1}" -f $pgCode, $pgLast)

$summary | Sort-Object Harness | Format-Table -AutoSize | Out-String -Width 200 | Tee-Object -FilePath (Join-Path $Out "SUMMARY.txt")
$fails = ($summary | Where-Object { $_.Exit -ne 0 }).Count
Write-Output ""
Write-Output ("REGRESSION: {0} harness(es), {1} non-zero exit" -f $summary.Count, $fails)
