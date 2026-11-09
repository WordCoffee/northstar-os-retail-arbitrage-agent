# The registry says what each service does. The contract proves 20 of 29 actually do it.

2026-11-09, contract-01. Owner instruction: take every service's primary action
from `ty/service_registry.json`, call it against the real backend, prove it
reaches a mounted endpoint and — for a write — read the value back through a
different endpoint; wire the result into the scorecard; and make ProductFinder
call `/api/products/finder` for real.

## The rule

A service passes only when its primary action:

1. **reaches a mounted endpoint** — 404/405/501 is `endpoint_missing`, 403 is
   `permission_denied`;
2. **returns a substantive payload** — a non-empty row set, or at least three
   measured fields. Envelope keys (`kind`, `count`, `items`, `status`, …) do not
   count, so `200 {}` and `{"count":0,"items":[]}` fail;
3. **(write) reads back** through a *different* endpoint with the same id.

Read-only services have nothing to persist, so (3) does not apply.

Primary selection is deterministic: effect rank `delete > write > external >
read`, registry order breaks ties. Two deviations, both recorded per row in
`skipped_actions`:

- **An `external` action is never called.** Those routes spend paid model
  credits (standing gate a). `offerchisel` and `towncrier` have *only* external
  actions, so they fail as `every action is an external paid-model call`.
- **A higher-effect action with no provable probe is skipped, not hidden.** The
  only case is `golden-goose`: its decision write persists into a table with no
  read endpoint, and the item detail route 404s until an opportunity is
  ingested, so persistence cannot be demonstrated. `evaluate` was probed
  instead and the skip is in the artefact.

`product-finder` is an explicit override: the registry's `actions[]` is empty
(the reg-01 finding), the registry files are read-only for this task, and
`GET /api/products/finder` exists at `Northstar_backend/main.py:2875` and is now
wired to the page. The override says so in `state/contracts/service_contracts.json`.

## Results — 20 pass, 4 persist, 3 gaps, 6 fail

Artefact: `state/contracts/service_contracts.json` (gitignored `state/`, so it is
force-added). Live mode against `http://127.0.0.1:8000` with the dev-loopback
identity shim; the same tool runs in-process for pytest.

| service | primary action | endpoint | verdict | persisted | reason |
|---|---|---|---|---|---|
| `hub` | read catalog summary | `GET /api/sourcescout/summary` | **pass** | - | substantive payload |
| `ledger` | read credit balance | `GET /api/v1/credits/me` | **pass** | - | substantive payload |
| `prospector` | run / read scanner | `GET /api/kirkland/scanner` | **pass** | - | substantive payload |
| `goldengoose` | read scanner | `GET /api/kirkland/scanner` | **pass** | - | substantive payload |
| `offerchisel` | - | - | **fail** | - | every action is an external paid-model call |
| `towncrier` | - | - | **fail** | - | every action is an external paid-model call |
| `auctioneer` | compute economics | `POST /api/v1/foundation/economics/compute` | **pass** | - | substantive payload |
| `autothink` | read models | `GET /api/autothink/models` | **pass** | - | substantive payload |
| `thewatch` | read scanner | `GET /api/kirkland/scanner` | **pass** | - | substantive payload |
| `rankledger` | read scanner | `GET /api/kirkland/scanner` | **pass** | - | substantive payload |
| `rivalboard` | read scanner | `GET /api/kirkland/scanner` | **pass** | - | substantive payload |
| `account` | read entitlements | `GET /api/v1/foundation/entitlements` | **pass** | - | substantive payload |
| `foundation` | read providers | `GET /api/v1/foundation/providers` | **pass** | - | substantive payload |
| `jobs` | create durable job | `POST /api/v1/foundation/jobs-durable` | **pass** | **yes** | read back by id |
| `keywords` | submit import | `POST /api/v1/foundation/keywords/imports` | **pass** | **yes** | job read back by id |
| `beta` | - | - | **no_primary_action** | - | registry records no actions |
| `beta-support` | - | - | **no_primary_action** | - | registry records no actions |
| `beta-signup` | create beta account | `POST /api/v1/foundation/signup` | **permission_denied** | - | HTTP 403 `signup_denied` — invite-gated, no invite in the store |
| `beta-ops` | read admin dashboard | `GET /api/v1/foundation/admin/dashboard` | **permission_denied** | - | HTTP 403 `role_operator_lacks_platform_admin` |
| `design-studio` | upload asset | `POST /api/design-studio/assets/upload` | **pass** | **yes** | asset listed by id |
| `product-finder` | score cached candidates | `GET /api/products/finder` | **pass** | - | 89 rows under `evaluated` |
| `golden-goose` | evaluate candidate | `POST /api/v1/foundation/golden-goose/evaluate` | **pass** | - | decision + resale score |
| `listings` | read listing health | `GET /api/v1/noncreative/listings/health` | **pass** | - | 2 rows under `items` |
| `keyword-tracker` | read local keywords | `GET /api/v1/noncreative/keywords` | **pass** | - | 10 rows under `items` |
| `competitor-monitor` | read competitor observations | `GET /api/v1/noncreative/competitor/observations` | **empty_payload** | - | zero rows; source table `costco_source_products` does not exist |
| `listingforge` | save listing record | `POST /api/design-studio/listing-records` | **pass** | **yes** | record listed by id |
| `adpilot` | list imported ad files | `GET /api/design-studio/amazon-files` | **empty_payload** | - | no imported files; ad copy is a paid external action |
| `socialpulse` | - | - | **no_primary_action** | - | registry records no actions |
| `profitability` | read economics contract | `GET /api/v1/foundation/economics/contract` | **pass** | - | formula version + metrics |

### Pass evidence (real values, not status codes)

- `hub` — 6 measured fields: total 470, pass 245, fail 20, review 205, plus rates.
- `ledger` — balance 5000 / allotment 5000 / consumed 0 / class compute / plan foundation.
- `prospector`, `goldengoose`, `thewatch`, `rankledger`, `rivalboard` — 89 scanner products each.
- `auctioneer`, `profitability` — 9 and 10 measured fields (`formula_version`, readiness, explanation, metrics).
- `autothink` — 98 fields; local model `bojo`, cloud live **not** armed.
- `account` — tier free, 1000 jobs/month, seat limit 10, export disabled.
- `foundation` — 2 provider rows (`ollama`, and the second provider).
- `jobs` — created `immediate_success` job; `GET /jobs-durable/{id}` returned the same id.
- `keywords` — submitted the fixture import; `GET /jobs-durable/{job_id}` returned the job.
- `design-studio` — uploaded a text asset; `GET /assets` listed the returned id.
- `product-finder` — 89 `evaluated` rows with `asin`, `name`, `amazon_price`, filter verdicts.
- `golden-goose` — decision `BLOCKED_ECONOMICS` with 10 mandatory-gate states and a resale score.
- `listings` — 2 listing-health rows; `keyword-tracker` — 10 keyword rows.
- `listingforge` — created a listing record; `GET /listing-records` listed the returned id.

### What still fails, and why it is not fixed here

1. **`offerchisel`, `towncrier`** — their only actions are paid model calls.
   Proving them needs an operator credit approval. The contract does not spend.
2. **`beta-signup`** — the endpoint is mounted and correctly refuses without a
   valid invite (403 `signup_denied`). Persistence cannot be shown while no
   invite exists; issuing one is an owner action, not a contract probe.
3. **`beta-ops`** — `GET /admin/dashboard` requires `PERM_PLATFORM_ADMIN`; the
   dev-loopback operator identity is not a platform admin. The route exists and
   refuses, which is the honest result.
4. **`competitor-monitor`** — returns an honest zero: `costco_source_products`
   has not been created in this deployment. Endpoint works; there is no data.
5. **`adpilot`** — no imported ad files and no harvested terms; its remaining
   action is a paid ad-copy call. Data gap + paid gate.
6. **`beta`, `beta-support`, `socialpulse`** — the registry records no actions,
   so there is nothing to call. These are gaps, not passes.

## Scorecard: `contract` dimension

Weights now (total **1.00**):

| dimension | before | after |
|---|---|---|
| works | 0.28 | **0.23** |
| usable | 0.12 | **0.07** |
| contract | — | **0.10** |
| correct / complete / measured / seller | 0.25 / 0.12 / 0.10 / 0.13 | unchanged |

The 0.10 is taken 0.05 from `works` and 0.05 from `usable`, exactly as
instructed. `tools/scorecards.py` reads `state/contracts/service_contracts.json`:
100 on `pass`, 0 with the named reason otherwise. A missing artefact scores 0
and says "run python tools/contract_check.py" — it cannot silently pass.

**At-bar count: 0 of 29 before, 0 of 29 after.** No service was at the bar
before the reweight, so none dropped. Scores are unchanged for every service
whose contract passes; the only decreases are the nine contract failures:

| service | before | after | contract |
|---|---|---|---|
| `design-studio` | 65.9 | **65.9** | 100 (asset upload persisted) |
| `hub` | 88.5 | **88.5** | 100 (summary, 6 fields) |
| `prospector` | 88.5 | **88.5** | 100 (89 scanner rows) |
| `product-finder` | 55.0 | **55.0** | 100 (89 finder rows) |
| `beta` | 74.7 | 63.2 | 0 (no primary action) |
| `beta-support` | 74.7 | 63.2 | 0 (no primary action) |
| `beta-signup` | 74.7 | 63.2 | 0 (403 invite-gated) |
| `beta-ops` | 74.7 | 63.2 | 0 (403 platform-admin) |
| `competitor-monitor` | 74.7 | 63.2 | 0 (empty feed) |
| `offerchisel` | 67.0 | 57.0 | 0 (paid external only) |
| `towncrier` | 55.0 | 45.0 | 0 (paid external only) |
| `adpilot` | 55.0 | 45.0 | 0 (no ad files) |
| `socialpulse` | 67.0 | 57.0 | 0 (no primary action) |

The three named services keep their holes: `design-studio` is weakest on
`measured`, `hub` and `prospector` on `measured` — the contract did not paper
over them.

## ProductFinder: the page now calls the endpoint

Before: `ProductFinder.jsx` named `/api/products/finder` only in comments
(lines 18–21, 124) and staged `UNKNOWN`s in local state. `fetch` appeared
nowhere.

Now:

- `northstar-os-ui/src/lib/productFinderApi.js` is the single transport:
  `GET /api/products/finder?limit=100`, bff envelope handled, refusal mapped to
  an `Error` with `.code`/`.status`, `candidateToRow` keeps every field the
  backend did not observe as `UNKNOWN`.
- An ASIN add (and the `?asin=` deep link) issues the request, replaces the row
  with the real candidate, and says so: `pf-lookup-note`.
- A backend refusal renders `pf-lookup-error` with the code and message and
  stages **no row**.
- A valid ASIN the cache does not hold renders `pf-lookup-missing`, a row whose
  title is "No cached observation" and status "Not in cache" — no invented
  metrics.
- The page also lost three fabricated artefacts: "observed 2h ago", the
  hardcoded provenance timeline, and the "no live market data" notice now says
  "cached observations, never a live market call".

**The endpoint is GET-only** (`main.py:2875`), so "ASIN add → POST" is
implemented as the request that route actually serves: a GET. Adding a POST
would require editing `main.py`, which is outside this task's write scope, and
would invent a write the product does not have. The contract check asserts the
real call; the Playwright spec watches the real network request.

## Tests

```
python -m pytest Northstar_backend/test_contract_check.py Northstar_backend/test_product_finder_api.py -q
...............                                                          [100%]
15 passed, 1 warning in 35.68s
```

The warning is the pre-existing `APlusPackIn.copy` Pydantic shadow warning.

`test_contract_check.py` (12 tests) pins: external actions are never selected;
the highest provable action wins; no-action services are gaps; stub payloads
fail; a full in-process run over 29 services proves the four writable services
persist and the refusals stay refusals. `test_product_finder_api.py` (3 tests)
pins the finder response shape the page maps, the exact-ASIN lookup and honest
miss, and ASIN dedupe.

```
npx playwright test tests/e2e/product_finder_contract.spec.ts
Running 3 tests using 1 worker
[1/3] adding an ASIN calls the finder and renders the real cached row
[2/3] a backend refusal is shown honestly and stages no row
[3/3] an uncached ASIN is reported as absent, never invented
  3 passed (4.2s)
```

The shared `:8000` backend and `:8101` UI server were used read-only and never
started or stopped. Because the running `:8101` Vite server belongs to the main
worktree, the Playwright run pointed at an ephemeral Vite server for this
worktree on `127.0.0.1:8102`, started and torn down by Playwright's `webServer`
(localhost-only, per the AGENTS.md exception).

## Notes and limits

- The live run writes four small, labelled probe records: an
  `immediate_success` job, one keyword import job, one text asset, one listing
  record. All are additive and named `contract-probe*`.
- `state/` is gitignored; `state/contracts/service_contracts.json` is force-added
  so the scorecard has its evidence on a fresh checkout.
- The registry is **not** edited. `product-finder`'s empty `actions[]` and the
  `registry_gaps.json` gap list still need the registry owner to reconcile them;
  this task records the truth in the contract artefact instead.
- A read-only service proves "returns real data", not "persists". Persistence is
  claimed only for the four writes whose value was read back.
