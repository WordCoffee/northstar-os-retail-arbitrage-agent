# STAGING RELEASE LOG — Phase D3

**Date:** 2026-09-20 · **Baseline:** `96f486d` (D2 approved) · **Deploy timestamp
(UTC):** 2026-09-20T00:5xZ (local staging run) · **Staging URL (local):**
`http://127.0.0.1:8123` (see §4 for Cloudflare staging path)

## 1. What was released to staging

The current build (HEAD `96f486d`) was verified **end-to-end on a local staging
stack matching the Phase B Cloudflare deploy alignment** (FastAPI backend at
`127.0.0.1:8123`, Pages-served SPA at `/workbench`, landing at `/`, Pages
Functions logic emulated by the envelope helpers). **No production resource was
touched**; staging env is fully scoped (see §3).

## 2. Smoke-test results (15/15 PASS)

| # | Check | Result |
|---|---|---|
| 1 | Staging server up | ✅ |
| 2 | Landing served at `/` | ✅ |
| 3 | SPA (workbench) served with `view-commandcenter` + `view-admin` | ✅ |
| 4 | **All four workspaces present** (Command Center, Commerce Ops, Creative Studio, Admin) | ✅ |
| 5 | Plans route 200 | ✅ |
| 6 | Credits meter (B3) — bff/v1 envelope, foundation balance 0 | ✅ |
| 7 | GG entitlements (B7) — envelope, foundation → no categories | ✅ |
| 8 | GG dry-run — bff/v1 envelope, `dry_run:true`, no provider, no write | ✅ |
| 9 | Admin route gated 403 for anonymous (B2/B4) | ✅ |
| 10 | Legal routes (`/legal/terms`) serve markdown (C9) | ✅ |
| 11 | `scan-mock` returns bff/v1 envelope with opportunities | ✅ |
| 12 | **Scan manifest written** (`scan_manifest_*.json`, FIXES_50 #23) | ✅ |
| 13 | **Report written atomically** — no `.tmp` residue (FIXES_50 #10) | ✅ |
| 14 | Manifest schema present: `inputs` / `env_flags` / `git_sha` | ✅ |
| 15 | GG opportunities envelope — **no `report_path` leak**, opaque `job_` id | ✅ |

Client-execution evidence for the four workspaces (rendering + interactions)
is covered by the UI contract suite that executes the same workspace logic:
**`test_ui_display.cjs` 1120 PASS / 0 FAIL** (includes Command Center card
rendering, Commerce Ops + Creative Studio honest-empty renders, Admin role
gate for member-vs-admin, SourceScout/ListingForge/AdPilot/SocialPulse/
AutothinK workspaces).

## 3. Env / secrets / binding scoping (staging)

- **No `.env` values read or written.** The only env override used in staging
  verification is `NORTHSTAR_DISABLE_RATE_LIMIT=1` — a harness-only opt-out of
  the edge rate limiter (documented in `rate_limiter.py`; production limits
  unchanged). It is **not** a secret and is never committed.
- **No production KV/data touched.** The GG `REPORT_DIR` writes during the
  smoke run (one scan report + one manifest) were **deleted after the run**;
  the working tree is clean.
- **No Golden Goose Alpha live data accessed** — `dry-run` and `scan-mock`
  only; `/scan` remains 403.

## 4. Cloudflare staging path (free tier) — READY, push is credential-gated

The Phase B alignment is deployed-free-tier-ready (Pages + Pages Functions,
`wrangler.toml`, `_routes.json`, `functions/api/_envelope.js`, Cloudflare
Access). To push the build to a real Cloudflare **staging** project:

```bash
# staging project: separate Pages project + STAGING KV namespace
wrangler pages project create northstar-alpha-staging --production-branch main
wrangler kv namespace create STAGING_DEALS_KV     # bind in a staging-only wrangler.staging.toml
wrangler pages deploy public --project-name northstar-alpha-staging
# env vars are runtime secrets set in the CF dashboard (project-scoped), never in code
```

**This actual push requires operator-supplied Cloudflare/Wrangler
authentication (credentials I do not handle) and is therefore NOT executed
here.** It is **free-tier (no spend)** — the only reason I did not run it is
the credential boundary, not cost. Staging runtime secrets (API keys used by Functions) must be entered by
the operator in the CF dashboard, scoped to the *staging* project only.
(no-change-no-op)

## 5. Outcome

Staging verification **PASS (15/15)**; Cloudflare push is staged-and-ready but
operator-credential-gated (no cost). Artifacts cleaned; tree clean.