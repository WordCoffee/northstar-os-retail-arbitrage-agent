# Phase 3b — LIVE COMPATIBILITY RUN (first run, owner-approved sources)

- **Date:** 2026-10-11 · **Owner:** T2 Holdings LLC
- **Security scan state (standing line):** **0 new / 0 known-active / 231 allowlisted.**
- **Status:** run EXECUTED as one unit (25.8 s, 13/40 requests), audit chain VERIFIED — then stopped. **Partial results**: our own driver defect lost all non-ASCII pages. No sources added, no links followed, caps not widened.
- **Evidence:** runner `scripts/phase3b_compat_run.py` · raw results `reports/phase3b_compat_results_20261011.json` (UTF-8).

## 1. Cap compliance

| Rule | Enforced | Actual |
|---|---|---|
| ≤10 requests/source (robots included) | yes (counter + hard stop) | example 1/10 · docs 6/10 · books 4/10 · quotes 2/10 |
| ≤40 total | yes (kernel RunBudget) | **13/40** |
| ≥2 s spacing per domain | yes (2.1 s spacing + limiter guard) | honored |
| 10-min global budget | yes (kernel + runner guard) | 25.8 s used |
| Response-size cap | kernel (2 MB) | honored |
| No link-following / no widening | all URLs pre-listed, exact | honored |

## 2. Pass/fail table

| Source | Page | Loaded | JS executed | Content extracted | Failure reason | Escalate to Chrome Connect |
|---|---|---|---|---|---|---|
| example.com | (robots first) | — | — | — | **skipped: robots** (robots fetch failed) — per directive, no retry/workaround | n/a |
| docs.python.org | all 5 pages | fetch reached site | n/a | **no** | OUR DRIVER DEFECT (see §3) — content fetched by the container, lost to a Windows cp1252 decode crash | no (not a site limitation) |
| books.toscrape.com | catalog | **yes** | n/a | **yes** — "Books to Scrape" marker | — | no |
| books.toscrape.com | 2 product pages | **yes** | n/a | **yes** — £ price markers | — | no |
| quotes.toscrape.com | `/js/` | fetch reached site | **unknown** (never observed) | **no** | same driver defect | no (re-test required) |
| docs.python.org | robots.txt | yes (524 chars) | n/a | yes | — | — |
| books.toscrape.com | robots.txt | yes (32 chars) | n/a | yes | — | — |
| quotes.toscrape.com | robots.txt | yes (133 chars) | n/a | yes | — | — |

## 3. Root cause (own code, fixed)

`DockerLightpandaDriver` used `subprocess…text=True`, which decodes output as the Windows locale codec (**cp1252**). Pages containing bytes unmapped by cp1252 (e.g. `0x9d` in UTF-8 typography) crashed the stdout reader thread → empty stdout → `fetch_failed`. ASCII-tolerant responses (all robots files, and books.toscrape pages whose £ bytes map onto cp1252) passed. **Fix:** decode `encoding="utf-8", errors="replace"` (never `text=True`) + regression test pinning the kwargs and a non-ASCII round-trip. Committed separately from the run evidence.

## 4. Controls

| Control | Result |
|---|---|
| Prompt-injection fixture (local server, through the gateway) | **PASS** — enveloped as untrusted data, hostile text present as inert data, scripts stripped |
| Redirect-to-private-IP (policy chain) | DENIED — reason `robots_unknown` (denial landed on the robots gate because example.com's robots is unavailable; the private hop itself was not evaluated — honest nuance) |
| Direct private-IP fetch attempt (`127.0.0.1:9222`) | DENIED — reason `domain_not_allowed` (allowlist precedes SSRF for unlisted hosts; SSRF-first denial is covered by kernel acceptance tests) |
| Audit hash chain after run | **VERIFIED** (`audit_chain_ok: true`) |

## 5. Proposed completion slice (WITHIN the original caps — your approval requested)

No widening; same pipeline; exact arithmetic:

| Source | Remaining budget | Proposed | New total |
|---|---|---|---|
| docs.python.org | 4 (10−6) | re-run 4 of the 5 published doc pages | 10/10 |
| quotes.toscrape.com | 8 (10−2) | re-run the `/js/` page (observe JS execution) | 3/10 |
| books.toscrape.com | 6 | nothing — **already 3/3 PASS** | 4/10 |
| example.com | 9 | nothing — **"skipped: robots" is final** (no-retry rule) | 1/10 |
| Totals | | **+5 requests → 18/40** | within all caps |

On approval this runs as one unit and stops again. **Until then, no further requests to any source.**

## 6. Owner decisions added
- **D1:** approve the §5 completion slice (5 requests, within caps)? *yes/no*
