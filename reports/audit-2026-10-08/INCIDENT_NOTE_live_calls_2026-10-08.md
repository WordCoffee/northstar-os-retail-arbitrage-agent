# INCIDENT NOTE — live provider calls during the audit

**Incident ID:** NS-AUDIT-2026-10-08-LIVE-01
**Severity:** P1 (unintended external spend + policy breach), escalated from P0-01 which it evidences
**Status:** OPEN — awaiting operator spend confirmation and the concurrent-session attribution
**Date of occurrence:** 2026-10-08, ~23:15–23:17 local
**Reporter:** the audit agent (self-reported; not discovered by monitoring)

---

## What happened

While executing a **read-only** GET sweep of 33 API endpoints, the audit's own instrumented socket probe recorded **19 outbound (non-loopback) HTTPS connections to `3.232.71.244:443`** — a Bright Data endpoint — all originating from a single endpoint:

```
GET /api/kirkland/scanner  -> 19 NON-LOOPBACK CONNECTS to ['3.232.71.244']
```

Every other swept endpoint (`/api/sourcescout`, `/api/products/finder`, `/api/kirkland/discovery`, `/api/golden-goose/health`, `/api/v1/status`, `/api/monitoring/error-alerts`, and the 8 `/api/v1/noncreative/*` routes) recorded **0** outbound connects.

Server logs from the same window show live pagination being performed:
```
[Bright Data] keyword='kirkland' page=1/10 cards=48 kept=44
[Bright Data] keyword='kirkland' page=2/10 cards=48 kept=86
[Bright Data] keyword='kirkland' page=3/10 cards=0  kept=86
```

## Root cause

`Northstar_backend/.env` contains **`SCANNER_LIVE_ALLOWED=1`**. `amazon_search.py:44` calls `load_dotenv()`, which resolves `Northstar_backend/.env`, arming `live_gate.live_enabled()`. With the gate armed, `search_products()` (`amazon_search.py:352-353`) no longer short-circuits and the plain GET reaches the Bright Data search path (`:356-370`).

The gate code is **correct** — the docstring at `:338-343` states the containment boundary precisely. The *environment* overrode the intended safe default.

## Why this is a breach of standing rules

- `docs/northstar-phase1/00-owner-decisions.md` §5: *"No normal GET/page load may trigger: paid provider activity, external writes, background enrichment, or credit debits."*
- `00-owner-decisions.md` §6.7: *"Standard UI loads = cache/database only."*
- `00-owner-decisions.md` §6.8: *"Live refresh = explicit command with scope, budget, provider, audit trail."*

None of the three held.

## What was NOT done (disclosure)

- **No retry was attempted.** After the attribution probe returned 19 connects, that probe was stopped and no provider-touching endpoint was called again.
- No other GET, POST, or CLI path was exercised against any provider.
- No credential was read, printed, written, or committed.
- No source, fixture, benchmark, or protected file was modified.

## Spend accounting — CANNOT BE COMPLETED FROM THE REPO

The exact cost of the 19 requests is **not determinable from any local artifact**. Determining it requires access to the operator's Bright Data billing dashboard, which this audit cannot and should not access. What can be said:

| Question | Answer available |
|---|---|
| How many outbound provider connections occurred? | **19** (instrumented, exact) |
| Which endpoint caused them? | `GET /api/kirkland/scanner` |
| Was it one sweep or several? | Two probe runs hit the endpoint (a status sweep and then the attribution run). **The 19 figure is from the attribution run only.** A conservative upper bound for the whole audit is therefore higher than 19 and must be confirmed. |
| Did any response carry billable data? | Yes — `cards=48 / kept=44`, indicating HTTP 200 responses with parsed results. |
| Exact USD spend | **UNKNOWN — requires operator dashboard access** |
| Audit-trail entry in the product | **UNKNOWN** — `/api/kirkland/*` routes write no per-request ledger entry. Verify in the Northstar audit log whether a scanner request was recorded at `2026-10-08T23:15Z`–`23:17Z`. |

**Operator action needed:** read the Bright Data dashboard for `2026-10-08`, confirm the request count and spend, and record it here. If the count exceeds 19, the additional requests came from the second probe run.

## Open sub-question — concurrent session

Untracked `Northstar_backend/data/golden-goose-reports/goose_scan_20261009_*.json` files and live commits on `feature/product-designer-studio` show another session was working in this repository during and after the incident window.

**The audit cannot attribute those to a person or session.** What it can state:
- The commits are authored on branch `feature/product-designer-studio`.
- No operator authorization for their activity is recorded in any file this audit can read.
- **If that session also ran live provider calls, they are not included in the 19 above and are not accounted for here.**

**Operator action needed:** determine who was running scans, whether live provider access was authorized for them, and add their spend to this note. If it was not authorized, stop that session before disarming anything (disarming first would destroy the evidence of what it did).

## Immediate containment (pending your A1 decision)

1. **Do not yet flip `SCANNER_LIVE_ALLOWED`** until the concurrent session is identified — flipping it now both interferes with an active scan and destroys the reproduction path for this incident.
2. Once attribution is done: set `SCANNER_LIVE_ALLOWED` to a non-opt-in value, per A1.
3. Then add the startup guard so this cannot recur silently (P0-01, second half).

## Reproduction (for the post-fix verification)

```powershell
cd Northstar_backend
python -m uvicorn main:app --host 127.0.0.1 --port 8017
python $env:TEMP\opencode\ns_attr_probe.py   # attributes outbound connects per endpoint
```
**Post-fix expected:** `GET /api/kirkland/scanner -> 0 outbound connects`, with the endpoint returning `live_allowed: false` in its summary block.

## Evidence

- `reports/audit-2026-10-08/evidence/live-call-attribution.txt` — per-endpoint attribution (19 connects)
- `reports/audit-2026-10-08/evidence/api-get-sweep.txt` — the 33-endpoint status sweep
- `reports/audit-2026-10-08/TEST_RESULTS.md` §7 and §10 — the disclosure and the incident statement
