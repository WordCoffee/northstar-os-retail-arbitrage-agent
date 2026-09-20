# NO-LEAK AUDIT — Phase D1

**Date:** 2026-09-20 · **Baseline:** `2f010e7` (Phase A+B+C committed; tree clean)
**Method (offline only — no network, no live calls, no spend):** full-history
secret scan via `git grep` across all **200 commits** (`git rev-list --all`),
tracked-file inventory, `.gitignore` verification, client-bundle + BFF-boundary
review. Matched values were classified by **shape/prefix only** — no credential
values are reproduced in this document.

---

## 1. Scope checked

| Category | What was checked |
|---|---|
| Secrets in full git history | `git grep` over all 200 commits for key/token/password/secret shapes (literal `key=value`, `sk-`, `ghp_`, `AKIA`, `xoxb-`, JWT `eyJ`, PEM private keys) |
| `.env` / config files in history | `git log --all -- '.env'`, `'Northstar_backend/.env'`; tracked env-like file inventory at HEAD |
| `.gitignore` coverage | root + `Northstar_backend/.gitignore` |
| Client-shipped bundles | `static/`, `public/`, `functions/`, `autothink/ui/`, `src/**` — secret shapes, internal hosts, admin/server-only references |
| Provider credential references | all commits — credential VALUE presence (names alone are expected) |
| BFF boundary enforcement | admin/credits/GG routes + Pages Functions envelope-only behavior |

---

## 2. Findings

| # | Severity | Category | Finding | Status |
|---|---|---|---|---|
| F1 | **PASS** | Secrets | **No Northstar credential value is committed anywhere in history.** No `sk-`/`ghp_`/`AKIA`/`xoxb-`, no PEM private keys, no literal `api_key=…` credential lines, no `.env` (root or backend) ever committed; `.gitignore` covers `.env`, `.env.*`, `.env.local` (+ `venv*`), backend `.env`. | ✅ PASS |
| F2 | **P2** | Secrets (third-party artifact) | Old (Jul/Aug 2026) pipeline-output blobs at commit `009ac85` (`data/scored/*.json`, `data/normalized/*.json`, `data/scored/top-deals-*.csv`) embed a **JWT-shaped fragment inside a scraped Amazon URL query param** (classified: `eyJ…` in a `url/…` field). This is a third-party token embedded in scraped deal output, **not** a Northstar credential. | ⚠️ Open — remediation §4 |
| F3 | **PASS** | .env/config | Only `.env.example` is tracked (placeholders like `your_brightdata_api_key_here` — not real). No env-like/secret-named files tracked at HEAD. | ✅ PASS |
| F4 | **PASS** | Client bundles | No server-only secrets, no `admin_account_view`/`require_admin`/`password_hash`, no internal service hosts in browser-shipped code. Provider config references are **env-var names only** (`process.env.BRIGHTDATA_API_KEY`, `config.brightData.apiKey`). | ✅ PASS |
| F5 | **P3** | Internal URL (dev hint) | `index.html` (landing) and voice components reference `http://localhost:3001` (local voice server) inside shipped snippets. Dev-only hint, not a secret, not reachable externally; should be hidden/parametrized before production. | ⚠️ Open — remediation §4 |
| F6 | **PASS** | BFF boundary | `GET /api/v1/admin/accounts/{id}` → `Require(require_admin)` (403 without admin; whitelist `id/email/plan/created_at` only, never password hashes/tokens — covered by `test_security_boundaries.py`). `GET /api/v1/credits/me` → token-plan scoped; GG routes: `/scan` 403, category filters plan-gated via `/entitlements`, dry-run free; Pages Functions return bff/v1 envelopes only and are edge-gated by Cloudflare Access (documented in `CLOUDFLARE_DEPLOY.md`). Client admin workspace is role-gated AND server-re-enforced (double gate). | ✅ PASS |
| F7 | **PASS** | PII | No subscriber/customer PII exists (no external users on the platform). Demo identities are non-real (`demo@…`, `o@x.com`, `example.com`); operator identity appears intentionally in `master-brain/profiles/*` and historical chat exports (operator-owned archival docs). | ✅ PASS |

## 3. Summary

- **Secrets: PASS** (nothing of ours committed; `.env` never committed).
- **Client bundles: PASS** (no server-only secrets/internal hosts beyond one dev-only `localhost:3001` hint, F5).
- **BFF boundary: PASS** (server enforcement verified by tests; Functions envelope-only).
- **Open (non-blocking) findings:** F2 (historical pipeline-output third-party URL tokens) and F5 (dev localhost hint).

## 4. Remediation status

| # | Remediation | Status |
|---|---|---|
| F2 | (a) Scrub URL query tokens in pipeline exporters before writing `data/scored|normalized/*`; (b) add `data/scored/`, `data/normalized/` (or their export pattern) to `.gitignore` so output artifacts stop being committed; (c) historical blobs flagged for D4/exclusion — no rotation needed (tokens are third-party URL params, not Northstar credentials). | ⚠️ Tracked for D4 (code-change category: pipeline/output hygiene — flag before touching Phase C logic) |
| F5 | Parametrize the voice-server URL (`VOICE_SERVER_URL` env, default empty → snippet disabled) and ship the landing without the live `localhost:3001` script ref. | ⚠️ Tracked for D4 |

**Overall D1 verdict: PASS** (security boundary intact; two non-blocking hygiene findings tracked for D4 hardening).