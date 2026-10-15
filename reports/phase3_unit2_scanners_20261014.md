# Phase-3 Unit 2 — grype + osv-scanner (advisory vuln scanning) — 2026-10-14

- **Standing line:** 0 new / 0 known-active / 231 allowlisted. Owner-approved Phase-3 adoption (unit 2 of 7).
- **Adopted:** `anchore/grype` **v0.120.1** and `google/osv-scanner` **v2.7.0** — both **Apache-2.0** (verified in Phase-2; upstream pins `3e20d69159df…` / `f45535354688…`).
- **Installs (checksum-verified, dual-source):**
  - grype: `%LOCALAPPDATA%\grype\0.120.1\` — zip sha256 `32e3c811…65d` (matches release `checksums.txt` **and** the GitHub API asset digest).
  - osv-scanner: `%LOCALAPPDATA%\osv-scanner\2.7.0\` — exe sha256 `9964ed64…438` (matches `SHA256SUMS` **and** the API asset digest).
  - **No services, no ports, no startup entries** (plain CLIs).

## Local evidence runs
- **grype**: `grype db update` → "Vulnerability database updated to latest version!"; `grype dir:northstar` → **"No vulnerabilities found"**; `grype dir:.` (repo-wide) → npm advisories table: `axios 1.18.1 → 1.20.0` (multiple High/Medium), `braces 3.0.3` (High; no fix), `proxy-addr 2.0.7 → 2.0.8` (**Critical** 9.1), `qs 6.15.3 → 6.16.0`, `uuid 8.3.2 → 11.1.1`, `react-router 6.30.6 → 7.18.0`, `sprintf-js 1.0.3` (no fix).
- **osv-scanner**: `scan source -r .` → exit 1 (findings): **30 unique advisories across 9 packages** (`anyio, axios, braces, idna, proxy-addr, qs, react-router, sprintf-js, uuid`) in **6 lockfiles** (`motivation-quotes/`, `northstar-os-retail-arbitrage-agent/`, `northstar-os-ui/`, root `package-lock.json`, `quick-draw-app/`, `uv.lock`).
- **Cross-check nuance (recorded honestly):** osv flagged `anyio`/`idna` in `uv.lock` while the same-day `pip-audit` run reported "no known vulnerabilities" — likely advisory-record/fix-availability filtering differences between the tools; flagged for triage, not a contradiction of either result.

## CI wiring (advisory, `continue-on-error`)
Two jobs added to `.github/workflows/security.yml` (SHA-pinned actions only): `osv-scan` and `grype-scan`. Both verify the release **checksums-file against its pinned API digest**, then verify the linux binary against the checksums file, then run the scan with `|| true`. Advisory until the first triage cycle completes.

## Non-claims / follow-ups
- No fixes applied. The npm advisories live in the legacy app copies + UI lockfiles (other sessions'/domains) — **triage is a separate decision**; `northstar/` itself is clean.
- Windows installs are the local toolchain; CI uses the same pinned versions on linux.
