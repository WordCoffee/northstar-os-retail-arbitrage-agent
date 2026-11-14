# Independent verification — Research, PPC, Listings (2026-11-14)

Verifier session: separate from the builders. Read-only except this file.
Repo `C:\Users\T2Hol\Desktop\Northstar OS Retail Arbitrage Agent`, branch `staging`, HEAD
`2a0dbba44462b5163cfcc44bcb6c300c3fe42088` ("PPC G4: AdPilot's primary action proven by a
persisted contract (0 -> 100)").

Environment as measured, not as reported: backend `http://127.0.0.1:8000/health` → 200
(`{"status":"ok",…}`), UI `http://127.0.0.1:8101/` → 200, both the supervised pids (backend
21864, UI 29708) alive for the whole session and **not restarted**. Free RAM at start
**4,282 MB** (the brief said ~2.3 GB). Playwright run one spec at a time, headless,
127.0.0.1 only. No Amazon host was contacted; the only live model call was the authorized
free `beam-free` compose inside the listings spec.

## Research — product-finder, `/product-finder`

| gate | verdict | exact command | real output |
|---|---|---|---|
| G1 persist → read back | **AGREE** | `npx playwright test tests/e2e/g1_research_persist.spec.ts --reporter=line` | `Running 2 tests using 1 worker`; **2 passed (5.3 s)**. Projects: `chromium-desktop` (Desktop Chrome/Chromium) and `chromium-mobile` (iPhone 12 descriptor → **WebKit**). Read back is from the **store**, not the DOM: poll `GET /api/products/research/{asin}` until `research.asin` matches, assert `status` ∈ `observed|no_observation` and `saved_at` set, then reload and see `pf-saved-{asin}`, then find the row in `GET /api/products/research` |
| G2 its own seller score | **AGREE** | `python -c "from tools.seller_tester.services import run_pass; … run_pass(only='scan', out_path=<temp>, work_dir=<temp>)"` | `scan`: selected **5**, scored **5**, passed **5**, refused 0, **mean 100.0**, `service: product-finder`, `measured: true`; `network`: *"none: every path runs against local fixtures and local code"*. Matches `ty/seller_scores.json` (product-finder mean **100.0**, scored **5**, passed **5**, path `scan`) |
| G3 workspace + click path | **AGREE** | `npx playwright test tests/e2e/research-desk.spec.ts --reporter=line` **and** `npx playwright test tests/e2e/workspaces/research.spec.ts --project=desktop-chromium --project=iphone-12-webkit` | desk spec: **4 passed (13.6 s)** (2 tests × 2 projects); workspace spec: **8 passed (5.2 s)** across `desktop-chromium` (Chromium) and `iphone-12-webkit` (WebKit). Frame carries `data-ws-id/-route/-core/-view/-tool/-gate`, scene **Orion Cradle** fires `northstar:scene`, the click path moves to view `set` (`?view=set`) and republishes tab context to Bojo, `?billing=enforce` refuses the service |
| G4 primary action + contract | **AGREE** | `GET http://127.0.0.1:8000/api/products/finder?limit=100`; artefact `state/contracts/service_contracts.json`; `npx playwright test tests/e2e/product_finder_contract.spec.ts --reporter=line` | live **200**, **89 rows** under `data.evaluated` (first row `B00GYZWNY6`, `amazon_price 29.48`). Artefact row `product-finder`: `GET /api/products/finder`, status **200**, `"89 row(s) under 'evaluated'"`, verdict **pass**. Standalone spec (runs unaided): **6 passed (6.8 s)** |
| G5 narrow tests | **AGREE** | `python -m pytest Northstar_backend/test_product_finder.py Northstar_backend/test_product_finder_api.py Northstar_backend/test_research_store.py -q --basetemp=…\verify_rpl\pt` | **20 passed**, 1 warning, 2.67 s |

**Verdict: all five gates reproduced (5/5).** The digest's "4/5, G5 missing" is now closed on
the gate's definition — an independent session reproduced G1–G4 and the service's narrow suite —
and the caveats below still stand.

What it does not prove: the finder answers from a local candidate cache, so 89 rows are cached
rows, not live market data; the scan path injects a **recorded** candidate cache and computes no
economics; `research` remains **unattributed** in `ty/seller_scores.json` (5/5, mean 100.0, no
owner — correctly refused rather than assigned to product-finder); the desk spec accepts either
"records" or the honest empty state, so it can pass with zero results; browser evidence is
headless loopback at a stale build label.

## PPC — adpilot, `/adpilot`

| gate | verdict | exact command | real output |
|---|---|---|---|
| G1 primary action end to end | **AGREE, narrowly** | `npx playwright test tests/e2e/ppc_primary_action.spec.ts --reporter=line` | **2 passed (3.1 s)**, `chromium-desktop` + `chromium-mobile` (WebKit). What it *actually* asserts: `ap-bulk-action` is visible with `aria-expanded="false"`; **no** `ap-bulk-panel` exists before the click; the click mounts the panel and flips `aria-expanded="true"`; a `input[type=file]` is **attached**; the panel text contains "upload" and "bulk"; a second click unmounts it. It does **not** upload a file, parse a report, approve a row, or download a bulksheet — the spec's own header ("the real report-to-bulk-file flow") says more than its assertions do |
| G2 its own ad copy | **AGREE** | `python -c "from seller_tester import ad_copy; r=ad_copy.run_all()"` (repo `tools` on `sys.path`) | `scored **6**`, `passed **5**`, `mean **98.1**`, identical to `ty/seller_scores.json` (adpilot mean 98.1, scored 6, passed 5, path `ad_copy`, kept failure AD-006). `ad_copy_run.py` was **not** run (it writes repo files) |
| G3 workspace render + click path | **AGREE** | `npx playwright test tests/e2e/workspaces/ppc.spec.ts --project=desktop-chromium --project=iphone-12-webkit --reporter=line` | **8 passed (5.1 s)**: 4 tests × 2 projects (Chromium desktop, WebKit iPhone 12). Scene **Meteor Rain**, frame attributes, click path to view `terms` with URL param, tab context republished, entitlement refusal path |
| G4 primary action callable, no missing credential/armed gate | **AGREE** | `python tools/contract_check.py --service adpilot --out C:\Users\T2Hol\AppData\Local\Temp\opencode\verify_rpl\adpilot_contract.json` | stdout: `services 1, passed 1, persisted 1, gaps 0, partial_probe_not_written: false`. Row: `POST /api/v1/foundation/jobs-durable` → **201**, `persisted: true`, `"1 row(s) under 'runs'; read back ad87f7ef-21e3-4a0a-9231-1ff84f2fefd5 via /api/v1/foundation/jobs-durable/ad87f7ef-…"`, verdict **pass**. The 201 came back with no credential or arming step, so there is no missing-credential gate on this action. Published artefact agrees: adpilot `pass`, 201, persisted (`e18ff0c8-…`) |
| G5 narrow tests | **AGREE** | `python -m pytest Northstar_backend/test_adpilot_api.py Northstar_backend/test_ppc_contract.py Northstar_backend/test_ad_copy_scorer.py -q --basetemp=…\verify_rpl\pt2` | **18 passed**, 1 warning, 1.80 s |

**Verdict: 5/5 reproduced, with one ceiling named** — "primary action end to end" is proven only
to the level of *the button opens the real panel and a file input exists*; no upload-to-download
transaction is executed by the spec. On the gate's written definition (the action is reachable and
callable, no missing credential) it is met.

What it does not prove: the ad-copy 98.1 is a **fixture-level** service-path sample over six
recorded briefs with one known failure, not live ad performance; the durable job is a campaign
**plan** written to the dev DB, not an ad change and not a push to any ad platform; ACOS/TACOS
behaviour against real spend is untouched; no Amazon host was contacted.

## Listings — listings, `/listings`

| gate | verdict | exact command | real output |
|---|---|---|---|
| G1 persist + read back (live compile) | **AGREE** | `npx playwright test tests/e2e/g1_listings_persist.spec.ts --reporter=line` | `Running 4 tests`; **2 passed, 2 skipped (22.9 s)**. Passed = the gate test (provider configured/enabled/**armed** by name, `runtime_default_model: beam-free`) and the compose/persist/read-back, both in **`chromium-desktop`**. The 2 skips are the same two tests in **`chromium-mobile`** — the spec skips every project except `chromium-desktop` by design. The phone read-back is *not* a project: the desktop test launches its own **real WebKit** engine (`webkit.launch({headless:true})`) with the iPhone 12 descriptor and reads the record in a clean context. So the browsers exercised are **Chromium (driver) + WebKit iPhone 12 (in-test)**, one driver |
| G3 workspace render + click path | **AGREE** | `npx playwright test tests/e2e/workspaces/listings.spec.ts --project=desktop-chromium --project=iphone-12-webkit --reporter=line` | **8 passed (5.8 s)** (4 × 2 projects). Scene **Globular Core**, click path to view `diffs`, entitlement refusal path |
| G4 primary action callable (contract) | **AGREE** | artefact `state/contracts/service_contracts.json`; `GET http://127.0.0.1:8000/api/v1/noncreative/listings/health` | artefact `listings`: `GET /api/v1/noncreative/listings/health`, status **200**, `"2 row(s) under 'items'"`, verdict **pass**. Live: **200**, `kind: listings_health`, `count: 2`, items `B0F87JDPD4` / `B0F87RXTVC` both `published`, plus honest unavailability notes (`costco_identity_enrichment` / `costco_evidence` "has not been created in this deployment"). The composed, persisted listing was read back from `GET /api/design-studio/listing-records` with title/bullets/description/backend_terms equal to the applied proposal |
| G2 its own seller score (0.0) | **AGREE that the zero is honest — the seller gate is therefore NOT met** | read `ty/services.json`, `tools/seller_tester/service_briefs.json`, `ty/seller_scores.json`, `state/seller/services_proof.json`, `ty/scorecards.json`, `northstar-os-ui/src/pages/internal/ListingGuardian.jsx` | `listings` declares `optimize_listing`, route `/listings`; `ty/seller_scores.json` has **no** `listings` bucket (nearest is `listingforge` 100.0 over 6 on path `listing`); `service_briefs.json` attributes `listing` → **listingforge** (`compose_listing`), never listings; `services_proof.json` carries 8 paths, **no** listings; scorecard `seller: 0.0` "no Seller-Tester output scored for this service"; the `/listings` room only reads `signals.ncListingsHealth()` (alerts/diffs/history/escalations watchtower) and generates no copy |
| G5 narrow tests | **AGREE** | `grep -l "listings" Northstar_backend/test_*.py` → **16 files**; narrowed to the listings surface: `python -m pytest Northstar_backend/test_noncreative_reads.py Northstar_backend/test_listing_records_schema.py Northstar_backend/test_seo_listing.py -q --basetemp=…\verify_rpl\pt3` | **30 passed, 16 subtests passed**, 1 warning, 1.87 s |

**Verdict: 4 of 5 gates pass; the fifth (G2) is confirmed as an honest zero, not lifted.**
No listing artefact is being withheld: nothing scored exists under any listings/optimize_listing
name, and the only listing copy in the proof set is ListingForge's `compose_listing`, which stays
attributed to listingforge and is not merged into this row. One gap worth naming rather than
dressing up: `optimize_listing` *is* wired (`chat_tools._t_optimize_listing` → `specialists.
listing_optimizer.optimize`) and **no Seller-Tester path exercises it**, so the service is
*unsurveyed*, not merely empty. I did not manufacture a score for it.

What it does not prove: the composed copy is one `beam-free` completion on a single supplied
fact set, not listing quality over a population; nothing here publishes, prices, or touches a real
listing; the read-back proves the tenant store, not Amazon; the health endpoint reports the local
`listings` table (2 rows) and explicitly says the identity-enrichment and evidence tables do not
exist in this deployment.

## What this does not prove (cross-cutting)

- No live market data anywhere. Every Research/PPC/Listings number rests on local caches, recorded
  fixtures or the dev tenant database.
- No Amazon host was contacted, no spend, no credential value read or printed; the only live
  external call was the authorized free `beam-free` compose.
- Browser evidence is headless and loopback; the dev banner "DEV: AUTH DISABLED" is present by
  design, so no production-session path is proven by these runs.
- One pass of one spec is not a regression baseline, and `npx playwright` here runs **both**
  `chromium-desktop` and `chromium-mobile` for bare specs — a green line does not mean two
  independent engines unless the spec opens one (listings) or the projects are named (workspaces).
- PPC "end to end" stops at panel mounting; no upload → approve → download transaction is executed.
- The listings compose proves one model's one answer is persisted and read back; it says nothing
  about whether that copy would convert or survive Amazon's rules.

## Side effects (all in the dev environment)

- **DB rows, `Northstar_backend/data/northstar.db`** (already modified before this session):
  - adpilot: one durable job written by my contract probe, `ad87f7ef-21e3-4a0a-9231-1ff84f2fefd5`
    (campaign plan). This write *is* the persistence under test.
  - listings: `ds_listing_records` **4 → 7**. My run added the composed row `B0G1LD1YJS`
    (`daf927e5-3b7b-4cc8-afdc-790af39ed6e9`, source `listingforge-local`, title "Lion's Mane
    Mushroom Powder, Single Ingredient, 200 g Resealable Pouch - Mogra Organics", created
    `2026-11-14T12:07:29Z`) **and two duplicates**: `9f285741-…` (`B0CONC18592`) and
    `d0d46393-…` (`B0CONA032E0`), created `12:07:10Z`. Cause, traced not guessed: the ListingForge
    room pushes its local slice back on mount via `POST /api/design-studio/listing-records/
    migrate`, and that endpoint is idempotent **only via `legacy_key`**; the two earlier
    `contract-check` probe rows have no `legacy_key`, so they were re-created. That is a
    data-hygiene defect in the migration, not a test artefact.
  - research: two rows left behind, `B0ZZ9ZZ994` and `B0ZZ9ZZ998` (`no_observation`). The spec's
    `afterAll` deletes the constant `B0ZZ9ZZ999`, while each run writes
    `B0ZZ9ZZ99` + one random digit — so the cleanup is a **no-op by construction** and every run
    leaks one row per project.
- **Temp dirs/files** (outside the repo): `C:\Users\T2Hol\AppData\Local\Temp\opencode\verify_rpl\`
  — `scan.json`, `scan_work\`, `adpilot_contract.json`, `pt\`, `pt2\`, `pt3\`, `dbpeek.py`.
- **Repo working tree**: I edited nothing, staged nothing, committed nothing. `git status` shows
  `M Northstar_backend/data/northstar.db` (the rows above) and `M dev-start.pids` (mtime
  `06:00:39`, i.e. the supervisor's launch, before my first command) plus untracked files that
  predate this session. The only file I created is this report.
- Services were not restarted and no `STOP`/soak/vision/key-rotation/service-proof state file was
  touched.

## Where the digest overstates — and where it undersells

I found **no inflated number** in the three services' claims: every count I re-ran matched
(100.0/5 scan, 98.1/6/5 ad copy, 89 finder rows, 2 listings health rows, 0.0 listings seller). The
problem is staleness and one wording overreach:

1. **The digest is behind HEAD.** `reports/ty/digest_2026-11-14.md` still shows PPC **79.8 / 3 of
   5 / G4 missing (`contract` `empty_payload`)**, and "22 score ≥85". On this tree
   `ty/scorecards.json` (generated `2026-11-14T12:01:31Z`) has adpilot **89.8**, contract **pass**
   — and HEAD `2a0dbba4` already contains it. Disk count is **23 of 28 ≥ 85**, `meets_bar: 4`,
   gaps `listings 7.2`, `offerchisel 5.0` (not `adpilot 3.6`). The digest's PPC row contradicts its
   own `reports/ty/ppc_g4_contract_20261114.md`.
2. **Research and Listings gates are understated in the digest** (4/5 and 3/5): G5 for both is
   reproduced above (20 passed; 30 passed + 16 subtests).
3. **The overreach that does exist is the PPC spec's self-description.** `ppc_primary_action.spec.ts`
   is titled "primary action opens the real report-to-bulk-file flow" and the digest leans on this
   spec for PPC G1; the assertions stop at "a panel mounted and a file input is attached". Read as
   a completed report→bulk-file round trip, that is overstated. The spec passes for what it
   actually checks.
4. **Listings G1 is better than "2 passed" sounds and worse than "two browsers passed" sounds.**
   Two tests passed and two were skipped; the WebKit read-back is real but runs inside the desktop
   test. Any table that reports "2 passed across desktop Chromium and iPhone 12 WebKit" without the
   skips hides that only one project actually executed the spec.
5. **The listings seller zero is stated correctly** in the digest (honest zero, copy belongs to
   ListingForge) — confirmed, with the added fact that `optimize_listing` is wired but never
   sampled, so "honest zero" should be read as "unsurveyed", not "nothing could be measured".
