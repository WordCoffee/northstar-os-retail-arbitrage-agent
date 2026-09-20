# A2 — Subscription Catalog Migration — Completion Report

**Date:** 2026-09-19T18:32Z (timestamp in filename)
**Scope:** A2 per approval (blueprint §8.1/§8.2 + A1 audit note). Read/write-limited. **Nothing committed** (staged locally only). No Stripe/billing/payment logic (per §18). No live/paid calls.

---

## 1. What changed

### 1.1 `shared/subscription-plans.json` — created (single source of truth)
- `catalog_version: 2`, `gates_always_off: true`, `currency: USD`, `$schema: subscription-plans-v2`.
- Tier catalog relocated **verbatim** from `auth.py::PLAN_ENTITLEMENTS`:
  Foundation $0 / Scout $29 / Mover $79 / AutothinK $149; gate arrays preserved **exactly** (scout 4, mover 6, autothink 9 — including `autothink_workspace`, in auth.py order); descriptions preserved verbatim.
- `services` per plan kept (existing consumer contract).

### 1.2 `Northstar_backend/auth.py` — `PLAN_ENTITLEMENTS` → thin loader
- Hard-coded dict removed; `PLAN_ENTITLEMENTS` is now built by `_load_plan_catalog()` reading `shared/subscription-plans.json`, projecting to the **same variable name and shape** `{plan_id: {name, price, gates, description}}`. Fail-closed on missing/malformed catalog or invariant breach (`gates_always_off`). No downstream call site changed (main.py routes, `register_user`, `user_has_entitlement`, `get_plan_info`).

### 1.3 `Northstar_backend/master_brain_subscribers.py` — repointed to the shared file
- `PLANS_PATH` → `shared/subscription-plans.json` (was `master-brain/subscription-plans.json`).
- `LIVE_GATES` registry **completed** with `autothink_workspace` (the canonical autothink gate array entitles it; without the registry entry the catalog would fail the loader's unknown-gate check). This is a registry completion — **no tier/pricing/gate-array content changed**.
- `load_plans()` normalizes each plan's `blurb` from the canonical `description` (single-field source; legacy consumers unaffected).
- Module docstring updated to name the new canonical path.

### 1.4 `master-brain/subscription-plans.json` — deleted (superseded)
- Was the separate v1 source. **It had already drifted from `auth.py`**: autothink lacked `autothink_workspace` and gate order differed (`socialpulse_publish` before `socialpulse_attrib`). Removing it ends the two-source state the Gate-0 audit flagged. Verified not a protected fixture (`fixtures/protected_hashes.json` has no entry); no code reads it anymore.

### 1.5 `Northstar_backend/main.py` — additive endpoint
- `GET /api/v1/plans` unchanged (reads the catalog automatically via `auth.PLAN_ENTITLEMENTS`).
- **`GET /api/v1/plans/{plan_id}` added** — returns `{plan: {...}}`; unknown id → `404` (never fabricated).

### 1.6 Tests (new)
- `Northstar_backend/test_subscription_catalog_smoke.py` (6 tests): **loader disagreement guard** — auth view vs subscribers catalog must match on plan ids, names, prices, descriptions, and **ordered** gate arrays; both loaders point at the same `shared/...` file; `catalog_version` present; `gates_always_off` invariant; **no "unlimited" language anywhere in the JSON**.
- `Northstar_backend/test_plans_route.py` (5 tests): list matches catalog, prices/gates preserved (incl. autothink 9-gate array), per-plan by id (scout, autothink), unknown → 404.

---

## 2. What needed flagging

1. **Drift was already real (pre-existing, now fixed).** The old `master-brain/subscription-plans.json` autothink entry was missing `autothink_workspace` and had gate order reversed vs `auth.py`. The canonical file follows `auth.py` exactly; because the old source was removed, the two sources can never disagree again, and the smoke test enforces it.
2. **`LIVE_GATES` registry gained `autothink_workspace`.** Required so the (unchanged) canonical autothink gate array loads through the subscribers loader. Registry/meta-data completion only — no tier, price, or gate-array content changed.
3. **"Unlimited" language: none found.** Grep of both prior sources and the new JSON found no tier using the word; no rewrite was needed. The new JSON's own meta-description avoids the word entirely (says "No uncapped/unmetered promises") so the strict no-unlimited test passes.
4. **UI demo mirror out of scope (flagged, untouched).** `static/northstar-os/js/demo-data.js` still mirrors the OLD catalog (its `autothink` entitlements omit `autothink_workspace`) and its comment references the deleted `master-brain/subscription-plans.json`. That is a client-side demo fixture — not a loader — and is outside A2's backend scope. **Recommend re-syncing it in the A3+ UI/design-token pass.** No change made here.
5. **`00_STATE.json` history** contains a historical reference to the old file path (line 646) — left as historical record.

---

## 3. Test results

| Run | Result |
|---|---|
| A2 targeted (`test_subscription_catalog_smoke.py` + `test_plans_route.py` + `test_master_brain_subscribers.py`) | **30 passed, 0 failed** |
| py_compile (`auth.py`, `main.py`, `master_brain_subscribers.py`) | Clean |
| **Full sanitized suite** (`pytest -q --ignore=agents/golden_goose_finder/test_single_match.py`) | **2055 passed, 2 failed, 3 skipped, 48 subtests passed** |

- The 2 failures are the **same 2 pre-existing protected-hash drift** failures from A1 (`test_proof_batch_run.py` ×2 — `fixtures/protected_hashes.json` baseline for `scanner-search-cache.json` is stale `366c…` vs committed `7c0b…`). Unrelated to A2.
- Delta vs A1's sanitized baseline (2044 passed → 2055 passed) = **+11 new tests**: 6 in `test_subscription_catalog_smoke.py` + 5 in `test_plans_route.py` (the subscribers suite's 19 tests were already counted in the A1 baseline; the targeted 30-run = 6 smoke + 5 route + 19 subscribers).

## 4. Working-tree state (staged locally only — nothing committed)

```
 M FIXES_50.md
 M Northstar_backend/agents/golden_goose_finder/amazon_adapters.py
 M Northstar_backend/agents/golden_goose_finder/amazon_matcher.py
 M Northstar_backend/agents/golden_goose_finder/run_live_scan.py
 M Northstar_backend/agents/golden_goose_finder/tests/test_amazon_matcher.py
 M Northstar_backend/auth.py
 M Northstar_backend/main.py
 M Northstar_backend/master_brain_subscribers.py
 M docs/PRODUCTION_BLUEPRINT.md
 D master-brain/subscription-plans.json
?? Northstar_backend/agents/golden_goose_finder/tests/test_amazon_adapters.py
?? Northstar_backend/test_plans_route.py
?? Northstar_backend/test_subscription_catalog_smoke.py
?? docs/PHASE_B_SECURITY_ITEMS.md
?? shared/subscription-plans.json
```
(A1's files — FIXES_50, GG ASIN gate + tests, run_live_scan, PHASE_B_SECURITY_ITEMS — carried forward from the approved A1; `ops_handoff` + gate0 audit report remain pre-existing untracked.)

Suite-hygiene: the full-suite run's routine scratch (goose_scan reports, `reports/golden_goose/<ts>`, tmp-probe, `_test_quota_tmp.json`, discovery/failure manifests) was removed; incidentally-dirtied tracked files restored to HEAD. No protected fixtures modified.

---

## 5. Out of scope (per instructions) — untouched
No Stripe integration, billing state, or payment logic. No changes to `static/northstar-os/js/demo-data.js` (UI demo mirror, see §2.4). A3 (design tokens) not started.

Awaiting approval before proceeding to A3 or anything else.