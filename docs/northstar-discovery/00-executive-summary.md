# NorthstarOS — Phase 0 Discovery Package

**Status:** READ-ONLY DISCOVERY COMPLETE — NO PRODUCTION IMPLEMENTATION, NO PAID PROVIDER EXECUTION, NO SECRET ACCESS.
**Date:** 2026-09-23
**Author:** Phase 0 audit (evidence states: STATICALLY_CONFIRMED / RUNTIME_CONFIRMED / HISTORICALLY_RECORDED / INFERRED / UNVERIFIED / UNKNOWN)

---

## 1. Scope and method

- Read-only inspection of the repository at `C:\Users\T2Hol\Desktop\Northstar OS Retail Arbitrage Agent`.
- Every count in this package was re-derived in this audit with explicit counting commands (see `17-evidence-index.md`).
- **Tests were NOT executed in this phase.** All test counts are STATICALLY_CONFIRMED (source inspection only). Runtime test status is UNVERIFIED.
- **No paid/cloud/external provider was invoked.** One **local Ollama** model call was executed during this audit for evidence R1 (fully disclosed in `17-evidence-index.md` §R1) — local engine only, no external service, no quota consumption. No `.env` values were read. No database write occurred (DB inspected read-only, `mode=ro`).
- **Git:** `git status --short` and `git ls-files docs/northstar-discovery` were executed (read-only) during validation; `git diff`/`git diff --stat`/`git log` and any `git add`/`git commit` were NOT executed (see `17` §G).
- Evidence-state legend used throughout: `STATICALLY_CONFIRMED` (source read), `RUNTIME_CONFIRMED` (validated in this audit at runtime), `HISTORICALLY_RECORDED` (past artifact/state), `INFERRED`, `UNVERIFIED`, `UNKNOWN`.

## 2. Repository at a glance

| Dimension | Finding | Evidence state |
|---|---|---|
| Backend | Single FastAPI app `Northstar_backend/main.py`, 69 route decorators + 7 Golden Goose router routes + separate AutothinK FastAPI app on :8100 (5 routes) | STATICALLY_CONFIRMED |
| Frontends | Four surfaces: (1) Analyst's Desk legacy static SPA (primary, demo/fixture), (2) `northstar-os-ui` React+Vite SPA on :8101, (3) single-file workbench `static/index.html` (735,352 B), (4) AutothinK UI (`autothink/ui/`) | STATICALLY_CONFIRMED |
| Database | SQLite `Northstar_backend/data/northstar.db` (716,800 B), 16 user tables, 1,024 `products` rows | STATICALLY_CONFIRMED (read-only query) |
| Tests discovered | 124 backend `test_*.py` files / 2,368 `def test_` functions (backend tree) + 3 autothink test files / 25 functions; 1,396 JS `assert(` calls across 4 `.cjs` contract suites | STATICALLY_CONFIRMED — **NOT EXECUTED** |
| Providers | ~20 distinct provider integrations (see `06`) | STATICALLY_CONFIRMED |
| Policy | Root `AGENTS.md` + `docs/OPERATING_CONSTITUTION.md` + ~10 policy docs | STATICALLY_CONFIRMED |

## 3. Capability summary (headline)

### RUNTIME_CONFIRMED in this audit
- **Local Ollama engine** — `POST /api/autothink/run` executed in this audit returned generated text from model `northstar-qwen3:rev1` (route `main.py:1025`, delegated to `autothink/backend/server.py`), evidence: terminal output during this session; command and artifact recorded in `17-evidence-index.md` §R1. Classified RUNTIME_CONFIRMED (local lane).
- **Backend health** — `GET /health` returned `{"status":"ok",...}` in this audit (RUNTIME_CONFIRMED).
- **SIGNAL React SPA connectivity** — `northstar-os-ui` dev server on :8101 proxies `/api` to :8000; browser session in this audit rendered live catalog + real generator output (RUNTIME_CONFIRMED for the SPA-to-backend proxy path; the SPA itself is not served by FastAPI).

### STATICALLY_CONFIRMED but RUNTIME-UNVERIFIED (implementation exists; not executed in this audit)
- Fee engine formulas (`fee_engine.py`, `fee_calculator.py`, `amazon_us_fee_rules_2026.py`, `pricing.py`, `finance.py`, `unit_economics.py`).
- Golden Goose pipeline (mock + gated live), opportunity scorer, breakdown economics.
- Master Brain gateway/learning/profiles/subscribers, memory bank, model router.
- Auth/JWT/RBAC (`auth.py`, `auth_deps.py`), alpha gate, rate limiter, security headers.
- Supplier CRUD routes + `SuppliersDB` DAO.
- Credit ledger engine (append-only; balance==allotment at runtime; consumption not wired).
- OfferChisel (`listing_forge.py`) and Town Crier (`social_pulse.py`) template/rule layers (LLM path exercised at runtime only via the generic `/api/autothink/run`, not via a dedicated service endpoint).

### UI-ONLY / MOCKED / HARD_CODED / CACHED-ONLY / BROKEN / MISSING (see `04` for detail)
- Analyst's Desk SPA service views render `demo-data.js` fixtures — **zero network by design** (`engine.js:5`), 8 gates all off.
- The Watch / RankLedger / Rival Board: skeleton views, no capture loop, no scheduler.
- Keyword/SEO graph and campaign tables exist but have **no live consumers** (dormant schema).
- Golden Goose live path: two-gate module `live_scan_gate.py` exists but the `/scan` route only enforces gate 1 (STATICALLY_CONFIRMED).
- Credits: `GET /api/v1/credits/me` returns `balance == allotment, consumed: 0` ("Offline alpha: no consumption tracked yet", `main.py:1717`).
- Unwrangle: HISTORICALLY_FAILED (403 credit-quota at 2026-09-13, `00_STATE.json:207`); CURRENTLY_UNVERIFIED.
- `src/tests/navigation-test.js`: broken (references undefined `navigationService`), wired into root `npm test`.

## 4. Critical and high risks (summary — full register in `13`)

| # | Risk | Severity | Area | Evidence |
|---|---|---|---|---|
| 1 | No canonical product identity — same ASIN in 4 disconnected stores | Critical | Data integrity | `08` |
| 2 | Dormant keyword/SEO + campaign intelligence (schema only) | High | Product capability | `08` |
| 3 | No scheduler/capture loop → Watch/Rank/Rival cannot track | High | Reliability | `04` |
| 4 | Credit consumption never debits ledger; balance is display-only | High | Financial | `04`, `07` |
| 5 | Golden Goose live route not fully two-gated | High | Control | `04` |
| 6 | React SPA untested and not served by FastAPI | High | Quality | `10` |
| 7 | `adapters/` + `importers/` orphaned (SP-API, Ads API unwired) | High | Maintainability | `01`, `06` |
| 8 | Unwrangle account blocked (historical); provider dependency risk | Medium | Reliability | `06` |

## 5. What prevents production SaaS readiness (top items)

1. **No canonical product/supplier/keyword identity** — services read different stores; reconciliation is ad hoc (`/api/products/finder`).
2. **No environment-mode architecture** (sandbox/production/operator/customer-view/impersonation).
3. **Billing/credits not operational** — meter/ledger not wired to consumption.
4. **No scheduled monitoring/alerting** — Watch/Rank/Rival have no data acquisition loop.
5. **Four divergent frontends** — the "primary" Analyst's Desk is fixture-only; the live SPA is not integrated with FastAPI serving.
6. **SP-API / Ads / supplier live paths are unwired or gated-off** — no production write capability exists for listings, ads, social publish, or purchases (by design, but therefore incomplete).

## 6. Route / screen / service tallies

- Routes audited: 69 (main.py) + 7 (Golden Goose router) + 5 (AutothinK app) = **81 backend route definitions**; plus ~24 documented frontend screens across the four surfaces (see `03`).
- Services audited: 11 service workspaces (Hub, Ledger, Prospector, Golden Goose, OfferChisel, Town Crier, Auctioneer, AutothinK, The Watch, RankLedger, Rival Board) + Account + shared/back-office (auth, plans, credits, suppliers, support, invites, memory, learning).

## 7. Owner decisions required before Phase 1 (top 5)

1. **Product identity**: confirm one canonical product record and the master key (ASIN + marketplace), and the ownership of refresh.
2. **Environment-mode model**: confirm sandbox/production/operator/customer-view semantics and whether impersonation is required.
3. **Billing**: confirm credit→USD conversion, meter wiring to consumption, and plan enforcement scope.
4. **Frontend target**: confirm which surface is the product (Analyst's Desk shell → SPA migration), and the SPA's serve path through FastAPI.
5. **Live-write boundaries**: confirm which write capabilities (Amazon listing, ads, social publish, purchases) are in-scope for production and their approval gates.

Full list in `15-open-questions.md`.

---

*All conclusions cite `file:line` in the evidence index. Nothing in this package modifies production code, policy files, databases, or providers.*
