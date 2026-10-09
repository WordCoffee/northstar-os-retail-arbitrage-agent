# verify-hosted-container.ps1 — build the single-service image, run it, and
# prove every UI-called route resolves (P0-03 / B-01).
#
# Usage:
#   powershell -ExecutionPolicy Bypass -File tools\verify-hosted-container.ps1
#   powershell -ExecutionPolicy Bypass -File tools\verify-hosted-container.ps1 -Keep
#
# Requirements: Docker with a running Linux engine, and the UI build available
# (the image builds it). No provider credential is needed and no live provider
# call is made: SCANNER_LIVE_ALLOWED is forced to 0 for the smoke container.

param(
    [int]$Port = 18000,
    [string]$Image = "northstar-api:hosted-smoke",
    [string]$Container = "ns-hosted-smoke",
    [switch]$Keep,
    [string]$EvidenceDir = "reports/audit-2026-10-08/evidence"
)

$ErrorActionPreference = "Stop"

# The route set the suite shell actually calls. 401/403 are correct answers for
# authenticated routes without a session; only 404/405 mean broken wiring.
$routes = @(
    "/health",
    "/health/detailed",
    "/openapi.json",
    "/api/v1/status",
    "/api/v1/foundation/health",
    "/api/v1/foundation/me",
    "/api/v1/reasoning/models",
    "/api/v1/foundation/reasoning/models",
    "/api/v1/foundation/creative/readiness",
    "/api/sourcescout",
    "/api/sourcescout/summary",
    "/api/monitoring/error-alerts",
    "/api/golden-goose/health",
    "/api/products/finder",
    "/api/v1/plans",
    "/api/v1/models",
    "/api/autothink/models",
    "/api/autothink/history",
    "/api/autothink/usage"
)

$spaRoutes = @("/ui/", "/ui/product-finder", "/ui/plan", "/autothink/ui/index.html")

Write-Host "building $Image (this builds the SPA inside the image) ..."
docker build -f Dockerfile.api -t $Image .
if ($LASTEXITCODE -ne 0) { throw "docker build failed" }

Write-Host "starting $Container on 127.0.0.1:$Port ..."
docker rm -f $Container 2>&1 | Out-Null
docker run -d --name $Container -p "${Port}:8000" `
    -e ENVIRONMENT=development `
    -e NORTHSTAR_DISABLE_RATE_LIMIT=1 `
    -e SCANNER_LIVE_ALLOWED=0 `
    -e NS_LIVE_PER_RUN_ARMED=0 `
    -e NS_LIVE_PER_RUN_CAP_CENTS=0 `
    -e NORTHSTAR_JWT_SECRET=hosted-smoke-not-a-real-secret `
    $Image | Out-Null
if ($LASTEXITCODE -ne 0) { throw "docker run failed" }

$ok = $false
for ($i = 0; $i -lt 30; $i++) {
    Start-Sleep -Seconds 2
    try {
        $r = Invoke-WebRequest -Uri "http://127.0.0.1:$Port/health" -TimeoutSec 5 -UseBasicParsing
        if ($r.StatusCode -eq 200) { $ok = $true; break }
    } catch { }
}
if (-not $ok) {
    docker logs $Container 2>&1 | Select-Object -Last 40
    throw "container did not become healthy"
}

$results = New-Object System.Collections.Generic.List[string]
$failures = New-Object System.Collections.Generic.List[string]

foreach ($path in $routes) {
    try {
        $r = Invoke-WebRequest -Uri ("http://127.0.0.1:$Port" + $path) -TimeoutSec 20 -UseBasicParsing
        $results.Add("$($r.StatusCode) GET $path")
        if ($r.StatusCode -eq 404 -or $r.StatusCode -eq 405) { $failures.Add("GET $path -> $($r.StatusCode)") }
    } catch {
        $code = $_.Exception.Response.StatusCode.value__
        if ($code) {
            $results.Add("$code GET $path")
            if ($code -eq 404 -or $code -eq 405) { $failures.Add("GET $path -> $code") }
        } else {
            $results.Add("ERR GET $path : $($_.Exception.Message)")
            $failures.Add("GET $path -> transport error")
        }
    }
}

foreach ($path in $spaRoutes) {
    try {
        $r = Invoke-WebRequest -Uri ("http://127.0.0.1:$Port" + $path) -TimeoutSec 20 -UseBasicParsing
        $results.Add("$($r.StatusCode) GET $path (SPA)")
        if ($r.StatusCode -ne 200) { $failures.Add("GET $path (SPA) -> $($r.StatusCode)") }
    } catch {
        $results.Add("ERR GET $path (SPA)")
        $failures.Add("GET $path (SPA) -> transport error")
    }
}

Write-Host ""
Write-Host "--- hosted container smoke ---"
$results | ForEach-Object { Write-Host $_ }

if (-not (Test-Path $EvidenceDir)) { New-Item -ItemType Directory -Force -Path $EvidenceDir | Out-Null }
$stamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss K"
$evidence = @(
    "# Hosted single-service container smoke — $stamp",
    "image: $Image (Dockerfile.api -> uvicorn main:app)",
    "container: $Container published 127.0.0.1:$Port -> 8000",
    "",
    "## routes",
    $results,
    "",
    "## failures",
    $(if ($failures.Count -eq 0) { "none" } else { $failures })
) -join "`n"
$path = Join-Path $EvidenceDir "hosted-container-smoke_$(Get-Date -Format yyyyMMdd).txt"
$evidence | Out-File -FilePath $path -Encoding utf8
Write-Host ""
Write-Host "evidence: $path"

if ($failures.Count -gt 0) {
    Write-Host ""
    Write-Host "FAILURES ($($failures.Count)):" -ForegroundColor Red
    $failures | ForEach-Object { Write-Host "  $_" -ForegroundColor Red }
    if (-not $Keep) { docker rm -f $Container 2>&1 | Out-Null }
    exit 1
}

Write-Host ""
Write-Host "PASS: every UI-called route resolves in the hosted container." -ForegroundColor Green
if (-not $Keep) { docker rm -f $Container 2>&1 | Out-Null }
exit 0
