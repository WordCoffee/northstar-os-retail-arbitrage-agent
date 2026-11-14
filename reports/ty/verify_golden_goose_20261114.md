# Independent verification — Golden Goose (`golden-goose`, /golden-goose)

Verifier: separate session from the author. Date: 2026-11-14 (revised after the backend was restored).
Repo: `C:\Users\T2Hol\Desktop\Northstar OS Retail Arbitrage Agent`, branch `staging`,
HEAD **e060503d** ("product-finder G2: its own scan_products seller sample (0 -> 100; score 77 -> 90)").

Scope: reproduce the five launch gates for Golden Goose only. Read-only except this report.
No Amazon navigation, requests, scans or APIs; no marketplace call, purchase, spend or credential read.

## Environment as found, and the outage

| item | first run | revision run |
|---|---|---|
| Backend 127.0.0.1:8000 | **down** — `/health` and `/api/v1/health` returned connection refused; nothing listening on 8000 | **up** — listener pid **3124**, `/health` → `200 {"status":"ok","service":"northstar-backend","version":"1.0.0"}` |
| UI dev server 127.0.0.1:8101 | up (HTTP 200), node pid 6892, banner **`v2.0 build 83bcfd72`** | same |
| UI tree vs HEAD | — | still build **83bcfd72**, **28 commits behind HEAD e060503d** (the dev server was not restarted) |
| Free RAM | — | ~2.33 GB; all runs headless and loopback-only, one worker |

**Environment fact, not a code finding.** The backend was down for the first pass. Its observed
symptoms were a plain **connection refused** on `127.0.0.1:8000/health` (nothing bound to 8000) and,
in the browser, **"Internal Server Error"** rendered after clicking Evaluate — the Vite proxy
answering 500 because its upstream was absent. The outage was **restored by the director, not by
me**: I did not start, stop or restart any service. The gates that were BLOCKED for that reason were
re-run once the listener answered.

## Gate table

| gate | verdict | exact command | real output |
|---|---|---|---|
| **G1** evaluate → persist → read back through the UI | **AGREE** | `npx playwright test tests/e2e/g1_golden_goose_persist.spec.ts --reporter=line` | **2 passed, 0 failed (5.0 s)**. Both projects completed every assertion: evaluate rendered a decision, the page reloaded, the persisted queue contained the run's item id (`GG-E2E-…`), the item's own review route showed the id and stopped "loading", and `gg-review-not-found` count was 0. First pass, with the backend down, was **0 passed / 2 failed** at `spec.ts:27` (result element never appeared, page showed "Internal Server Error") |
| **G2** Golden Goose's own seller score | **AGREE** (unchanged) | `python -c "from tools.seller_tester.services import run_pass; ..."` (temp `proof.json` + `work/`) | `ty/seller_scores.json`: golden-goose mean **100.0**, scored **5**, passed **5**, path `golden_goose`, population `service-path`. Reproduced: selected 5, scored 5, passed 5, refused 0, mean 100.0. `network`: "none: every path runs against local fixtures and local code". `state/seller/services_proof.json` untouched (mtime 2026-11-13 21:00:29, git-clean) |
| **G3** workspace renders + click path, desktop and iPhone 12 WebKit | **AGREE** | same e2e run as G1 | **2 projects ran, 2 passed**: `chromium-desktop` → **chromium** (Desktop Chrome, 1280×720); `chromium-mobile` → **webkit** (iPhone 12 descriptor, 390×664, isMobile true). The Golden Goose workspace rendered (group "Golden Goose workspace", heading "Golden Goose Finder", evaluate panel, 10 gate selects, queue/review tabs) and the full click path — fill id, tick sample, Evaluate, reload, read queue, open review route — completed in **both** browsers |
| **G4** primary action callable, no missing credential, no unarmed gate | **AGREE**, with the live scan still refused | direct `POST /api/v1/foundation/golden-goose/evaluate`, then `GET /api/v1/foundation/golden-goose/GG-VERIFY-081110` and `GET .../queue`; plus the e2e above; plus the pure gate function `check_live_scan_gates()` | evaluate → **HTTP 200**, `"persisted": true`, `decision_state: APPROVAL_REQUIRED`, **`purchase_ready: false`** with **`sample: true` and all ten gates PASS** (the sample cannot be promoted). Read-back → **200**, `latest_decision.decision_state = APPROVAL_REQUIRED`, `purchase_ready 0`, org `org-t2`, timestamped. Queue → **200**, `basis: OBSERVED`, 13 items. No credential was requested anywhere on the path (dev auth: "DEV: AUTH DISABLED — local loopback only"). Live Amazon scan remains **unarmed**: both `GOLDEN_GOOSE_LIVE_OPERATOR_APPROVED` and `GOLDEN_GOOSE_LIVE_AUTH_PHRASE` are unset and `check_live_scan_gates()` returns `(False, "refused: … is not 1 (absent by default …)")`. I did not arm either, and I did not call the scan endpoint |
| **G5** the service's own backend tests | **AGREE** (unchanged count) | `python -m pytest Northstar_backend/agents/golden_goose_finder/tests -q --basetemp=...\pt` | **518 passed in 4.85 s**, 0 failed. Not re-run; counts did not change because no code changed |

Playwright projects: only `chromium-desktop` and `chromium-mobile` match this spec. The
`desktop-chromium` / `iphone-12-webkit` projects are `testMatch`-restricted to `tests/e2e/workspaces/`
(`playwright.config.ts:38,43`), so they were correctly skipped.

**Verdict sentence.** All five gate checks reproduce on HEAD `e060503d` with the backend up: G1 and
G3 pass end-to-end in Chromium and WebKit, G2's 100.0 / 5 / 5 is reproduced without touching repo
state, G4 returns 200 and persists with the sample row held at non-purchase-ready and the live scan
still refused, and the service's own suite is 518/518 — so the digest's "Golden Goose G1–G4, G5
missing" is now matched on G1–G4 and G5 additionally carries a reproduced test count.

## Spec text: the sample row really cannot be purchase-ready

Confirmed in the spec, the UI, the backend decision code and a live probe:

- `tests/e2e/g1_golden_goose_persist.spec.ts:8-9` — "Sample row only: a sample decision can never be purchase-ready". Line 23 ticks `#gg-sample` before clicking Evaluate.
- `northstar-os-ui/src/pages/internal/GoldenGoose.jsx:79` — labelled "Sample row (never purchase-ready)".
- `Northstar_backend/foundation/golden_goose_decision.py:140-143` — a labelled SAMPLE row can never be promoted past `APPROVAL_REQUIRED`.
- Live probe above: all ten gates PASS + `sample: true` → `purchase_ready: false`.

## Gating on the path (G4 detail)

- **Evaluate / decision** is a real backend decision control: mandatory gates plus explicit approval
  control `PURCHASE_READY`; a score alone never does (`golden_goose_decision.py:104,133-147`).
- **Auth, not credentials.** The foundation decision route needs a user with the approve permission
  (`test_decision_route_requires_approve_permission`: viewer 403, admin 200); the dev shim supplies
  the demo operator. No API key, model key or marketplace credential is on this path.
- **Live Amazon scan is gated and unarmed, correctly** (`live_scan_gate.py`): two operator-set env
  gates, both absent by default, neither ever self-set. Observed absent and refused.

## Discrepancies against `reports/ty/digest_2026-11-13.md`

1. **G1 previously unreproducible, now reproduced.** The digest records Golden Goose G1 as proved
   2026-11-11; my first pass could not confirm it because the backend was down. With the listener
   restored the spec passes 2/2, so the digest's G1–G4 claim now stands on reproduced evidence.
2. **G5.** The digest says G5 is "not reproduced by the verifier". The service's own suite is
   **518 passed / 0 failed**; that is a test count, not the independent gate the digest means, so
   G5 as a gate stays open while the count now exists.
3. **Two different numbers for Golden Goose.** The digest's launch table shows scorecard **89.4**;
   `ty/seller_scores.json` publishes **100.0** for the `service-path` population. Different
   populations (composite scorecard vs. the service's own path over 5 fixtures); never quote them as
   the same number.
4. **The UI under test is stale.** The running dev server still reports build **83bcfd72**, 28
   commits behind HEAD **e060503d**. Browser evidence describes that older UI tree; the backend
   answering on 8000 is the current one.
5. **First-pass environment claim.** The brief assumed a running dev stack; the backend was not
   running for the first pass (see "Environment as found").

## Verifier side effects (disclosed, none in source or config)

- The G2 seller path writes its own report under `reports/golden_goose/`. My run created
  `reports/golden_goose/20261114T080527/` (untracked); I removed it, and that report said **3
  evaluated, HIGH 0, MEDIUM 0, LOW 3** — nothing near purchase-readiness.
- G1 and the G4 probe persist rows through the product's own API into the dev database
  (`Northstar_backend/data/northstar.db`, already modified before I started): the spec's
  `GG-E2E-…` items and my `GG-VERIFY-081110`. That is the persistence under test, not an edit by me;
  the queue now reads `basis: OBSERVED`, 13 items.
- No source, test, fixture, config, `state/seller/services_proof.json`, soak/PAUSE/waiter file was
  written. `git status` shows only the pre-existing modifications plus this report.

## What this does NOT prove

It does not prove Golden Goose works against live market data: every path runs on local fixtures and
recorded samples (`network: none` in the seller pass), and no Amazon request was made by design, so
nothing here validates sourcing, pricing, eligibility or any purchase-readiness claim. The 100.0
seller score is fixture-level — five recorded briefs judged by the app's own checks — and says
nothing about whether an opportunity makes money. The sample row reaching no further than
`APPROVAL_REQUIRED` shows the safety interlock works for a sample; it does not show that a real,
non-sample opportunity can be correctly promoted, because no real opportunity was evaluated. The
browser evidence covers headless Chromium and headless WebKit on loopback only, against a UI tree 28
commits behind HEAD — not other browsers, real devices, accessibility conformance or performance.
The 518 backend tests are the service's own tests, written by the same author: they show the module's
stated behaviour holds, not that an independent party exercised the product. One pass of one spec is
not a regression baseline, and a single 200 from evaluate is not a concurrency, scale or
duplicate-id check. Finally, nothing here speaks to the other five core services, and G5 as the
digest defines it — an independent check of the claims — is still open.
