# Phase-3 Unit 3 — OWASP ZAP (baseline DAST) — 2026-10-14

- **Standing line:** 0 new / 0 known-active / 231 allowlisted. Owner-approved Phase-3 adoption (unit 3 of 7).
- **Adopted:** `zaproxy/zap-stable` — **Apache-2.0** verified in Phase-2 (upstream pin `38ffe34a1b03…`; license sha256 `b40930bbc…`; README carries "ZAP by Checkmarx" branding — name/attribution only, no endorsement implied).
- **Install (stays STOPPED):** image pulled **by digest** `sha256:7aaa659b0d43078febd82e29bad112285c370727e86ab8340444220e17d9f0d2` (matches the resolved multi-arch digest exactly). **No container was created or started** — `docker ps` still shows only `northstar-lightpanda`; no ports opened by this unit; no startup entries.
- **Scan status: PENDING.** Owner rule: ZAP scans the local loopback stack only — and the app stack is not currently running. Nothing was scanned.
- **Draft script (NOT committed to `scripts/` pending review; kept at `%TEMP%\opencode\zap_baseline_draft.ps1`).** Full text for review:

```powershell
# NorthstarOS - OWASP ZAP baseline DAST (DRAFT - Phase-3 unit 3)
# Status: NOT committed to scripts/ pending operator review. Targets the LOCAL
# stack ONLY (owner rule: loopback scope). The stack must be running first.
# Usage:  powershell -NoProfile -File zap_baseline_draft.ps1 [-Target http://host.docker.internal:8000]

param(
  [string]$Target = "http://host.docker.internal:8000"
)
$ErrorActionPreference = "Stop"

# Pinned by digest (resolved + pulled 2026-10-14; image kept stopped).
$ZapImage = "zaproxy/zap-stable@sha256:7aaa659b0d43078febd82e29bad112285c370727e86ab8340444220e17d9f0d2"

# Loopback-only guard: refuse anything that is not the local machine.
$allowed = @("127.0.0.1", "localhost", "host.docker.internal")
try { $tHost = ([uri]$Target).Host } catch { throw "Unparseable target: $Target" }
if ($allowed -notcontains $tHost) {
  throw "Refused: ZAP may only scan the LOCAL loopback stack (got host '$tHost'). No third-party targets."
}

$outDir = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot "..\..\reports\zap"))
New-Item -ItemType Directory -Force $outDir | Out-Null
$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
"ZAP baseline -> $Target  (reports: $outDir\zap-baseline-$stamp.json/.html)"

# Baseline = spider + passive scan only (no active attacks). Exit codes: 0 pass / 1 fail / 2 warn.
docker run --rm -t -v "${outDir}:/zap/wrk:rw" $ZapImage `
  zap-baseline.py -t $Target `
  -J "/zap/wrk/zap-baseline-$stamp.json" `
  -r "/zap/wrk/zap-baseline-$stamp.html" `
  -m 5
"exit: $LASTEXITCODE"
```

- **To run (when the stack is up):** `powershell -NoProfile -File zap_baseline_draft.ps1` → reports land in `reports/zap/`. Review the findings before any promotion of the script into `scripts/`.
- **Non-claims:** no scan was performed; no findings exist yet; the script is a reviewed-candidate artifact, not committed tooling.
