# ASIN Market Data Completeness Plan

**Status:** PLAN ONLY — implementation-ready, NOT yet approved for live execution.
**Date:** 2026-08-17
**Scope:** Complete, honest ASIN-level market intelligence (20 business fields) for
the Northstar retail arbitrage shortlist workflow.
**Hard rule:** No live provider call may run until a human decision approves a
provider, a budget, and a source of truth (Section 8). All artifacts in this plan
are offline-safe; GET routes stay cache-only (`SCANNER_LIVE_ALLOWED` gate intact,
proven by `test_live_containment.py`).

---

## 1. Executive Summary

The scanner today produces row-level economics from cache-only data: Amazon price
from a search snapshot, Costco COGS from the three-layer catalog, fee estimates
from the versioned fee engine. What it cannot produce honestly is **per-ASIN
market intelligence**: who actually holds the Buy Box, how many sellers compete,
whether the roster is complete, what demand really is, and which of those facts
are observed vs. estimated vs. unknown.

This plan delivers the decision-ready target: a **normalized per-ASIN market
snapshot** (20 business fields), an **ASIN Data Completeness Score (0-100)** with
a **status taxonomy** that decides *ready for test buy* vs. every blocking gap,
and a **controlled 20-ASIN enrichment workflow** whose every live step is gated
behind a human-approved preflight.

Delivered in this plan already (Phase 7, offline-only):
- `intel_schema.py` — validates the normalized snapshot contract (zero-for-unknown
  rejection, per-field provenance, honest coverage metadata).
- `completeness_score.py` — the 0-100 score, 6 weighted categories, status ladder,
  purchase-authorization rules mirroring `product_analysis`.
- `enrichment_preflight.py` — dry-run planner: batch cap <= 20, fresh-cache skip,
  credit estimates, budget stop, human-confirmation flag. Zero network, zero writes.
- `test_asin_intel_plan.py` — 28 tests, all passing offline.

**What is explicitly NOT done here:** no provider selected, no budget approved, no
live call issued, no server route modified, no UI changed. Those are Human
Decisions (Section 8).

---

## 2. Current-State Field Matrix (Phase 1 audit)

Existence today, per record. Legend: **Y** = populated; **O** = only offline
cache/estimation; **N** = never supplied by the current pipeline.

| # | Business field | Scan row (cache-only) | Offline snapshot store | Providers capable today | Notes |
|---|---|---|---|---|---|
| 1 | ASIN | Y | Y | Y | URL-only rows lack it |
| 2 | Product title | Y | Y | Y | |
| 3 | Amazon price | Y (`amazon_price`) | Y | Y | |
| 4 | Buy Box price | O (scan `buy_box_price`) | Y | Easyparser Y; Web Unlocker = price alias; dataset pass-through | winner never inferred from lowest |
| 5 | Buy Box winner identity | N | Y (`buy_box.seller_name/id`) | Easyparser only | Web Unlocker hardcodes `"unknown"` (bright_data_client.py:383-384) |
| 6 | Buy Box fulfillment (FBA/FBM) | N | Y (`buy_box.fulfillment`) | Easyparser only | |
| 7 | Total sellers | O (scan `total_sellers`) | Y (`seller_counts.observed_total`) | Easyparser roster; Web Unlocker aggregate parse; dataset pass-through | claimed vs observed stay distinct |
| 8 | FBA sellers | O (scan `fba_sellers`) | Y (`seller_counts.fba_observed`) | Easyparser only | Web Unlocker returns None by contract |
| 9 | FBM sellers | N | Y (`seller_counts.fbm_observed`) | Easyparser only | dataset computes but never outputs (brightdata_client.py:89) |
| 10 | Per-seller offers | N (detail panel only, on-demand) | Y (`offers[]`) | Easyparser OFFER only | aggregate-only providers → coverage partial |
| 11 | Shipping amount per offer | N | O (text/free-flag only) | none numeric | Easyparser extracts `shipping_text`/`shipping_is_free`, never the number (easyparser_client.py:44-45) |
| 12 | Monthly sales estimate | O (scan, from search text) | Y (`demand.estimated_monthly_sales`) | Web Unlocker/dataset pass-through; Easyparser none | demand_estimator bands +-15/30/50/70% |
| 13 | Sales rank / BSR | O (scan `sales_rank`) | Y (store key) | Web Unlocker parse | |
| 14 | FBA fee | O (fee engine, weight-derived) | Y (`fees.fba_fee` + status) | Web Unlocker estimate; dataset pass-through; Easyparser none | verified/estimated/provisional tiers |
| 15 | Referral fee | O (fee engine) | Y (`fees.referral_fee`) | fee engine only | category resolver: browse node → verified |
| 16 | Costco COGS | Y (3-layer catalog) | Y (`cost.costco_cost`) | n/a (Costco side) | invoice_confirmed > product_detail > CSV |
| 17 | Pack/variant equivalence | O (`pack_match`) | Y (`identity.pack_match`) | n/a | exact/invoice gate for purchase |
| 18 | UPC/EAN/GTIN | N (except catalog rows) | Y (`identity.upc_or_ean`) | easyparser: always null | missing → Unknown, never invented |
| 19 | Net weight / dimensions | N (fee engine weight sometimes) | Y (`identity.net_weight_lbs`) | Web Unlocker; Easyparser none | null-by-contract in Easyparser |
| 20 | Amazon category / browse node | O (browse node → verified) | Y | Web Unlocker; Easyparser none | category resolver versioned |

### Existing support files (read-only references)
- `market_snapshot_store.py` — `data/amazon-market-snapshots.json` (env
  `SCANNER_MARKET_SNAPSHOT_PATH`), `schema_version=1`, per-ASIN `buy_box`,
  `seller_counts{observed_total,claimed_total,fba_observed,...}`,
  `offers/offers_returned/offers_complete`, `stages` (detail/offers/sales),
  freshness (offers +7d, sales +30d, identity +90d), `missing_fields` catalog
  (market_snapshot_store.py:95-108).
- `demand_estimator.py` — `estimate_demand(...)` → `estimated_monthly_sales`,
  `sales_estimate_low/high`, `sales_estimation_method/source/confidence`.
- `costco_api_client.py` — 3-layer catalog (`discovery_only`/`invoice_confirmed`/
  `detail_only`), `resolve_costco_cost` priority.
- `portfolio_analytics.py` — readiness ladder `blocked_mismatch → ... →
  complete_opportunity`; `opportunity_analytics.py` row-level
  `data_completeness_score` (10x10 dims) stays untouched; the new score is the
  per-ASIN shortlist decision gate, additive, not a replacement.
- Scanner GET routes stay cache-only — `main.py` `/api/kirkland/scanner`
  (main.py:459), `/api/kirkland/live` (main.py:212); summary carries
  `live_allowed`/`scanner_mode`/`enrichment_source`.

---

## 3. Data Gaps and Decision Log (Phase 1)

| # | Gap | Impact | Decision needed |
|---|---|---|---|
| G1 | No per-ASIN roster unless user clicks Load seller details (Easyparser ~5 cr/ASIN) | shortlist cannot rank competition | D1 provider, D2 budget |
| G2 | Buy Box winner identity only via Easyparser | other providers must render "Unknown", never inferred | D1 |
| G3 | Numeric shipping per offer never extracted (Easyparser) | landed-price math stays approximate; keep `shipping_text` + flag | none (documented limitation) |
| G4 | Easyparser never supplies UPC/EAN/GTIN/weight/dims/brand/category/fee/rank/sales | fields 18/19 stay Unknown for Easyparser rows | D1 provider mix |
| G5 | Monthly sales needs Web Unlocker/dataset detail calls | demand category uses internal estimate or stays null | D1 |
| G6 | Costco online discovery costs are not invoice costs | purchase authorization requires invoice_confirmed; shortlist rows may need `invoices import` | D3 source of truth |
| G7 | No completeness score/status displayed anywhere in the UI | operators cannot triage the 20-ASIN batch | D5 UI scope |
| G8 | No preflight planner existed | risk of accidental batch runs | delivered here (Phase 7) |

**Decision log entries:** this plan itself. No provider/budget decision made. All
live-capable additions remain behind the `SCANNER_LIVE_ALLOWED` gate with
`POST /api/kirkland/refresh` as the only live entry point.

---

## 4. Normalized ASIN Market Snapshot Schema (Phase 2)

File: `data/asin-market-snapshots.json` (new; env `ASIN_MARKET_SNAPSHOT_PATH`,
project-root relative). Per-ASIN records, per-ASIN atomic tmp+replace writes
(reuse the `market_snapshot_store` write pattern).

```json
{
  "schema_version": 1,
  "asin": "B0PLACEH01",
  "ingested_at": "2026-08-17T12:00:00+00:00",
  "sources": {
    "easyparser_offer": { "request_zip_code": "75201", "credits_used": 5,
      "raw_response": {} }
  },
  "facts": {
    "identity": { "name": null, "pack_match": null, "upc_or_ean": null,
      "net_weight_lbs": null },
    "cost": { "costco_cost": null, "cost_status": "unavailable",
      "source": null, "paid_cost_invoice": null },
    "fees": { "referral_fee": null, "referral_fee_confidence": "unavailable",
      "fba_fee": null, "fba_fee_status": "unavailable",
      "prep_cost_per_unit": 0.0, "inbound_cost_per_unit": 0.0,
      "packaging_cost_per_unit": 0.0, "return_reserve_rate": 0.0 },
    "demand": { "estimated_monthly_sales": null,
      "sales_estimation_method": "unknown",
      "sales_estimation_confidence": "unknown" },
    "market": {
      "amazon_price": null,
      "buy_box": { "available": false, "price": null, "seller_name": null,
        "seller_id": null, "fulfillment": null, "source": null,
        "observed_at": null },
      "seller_counts": { "total_observed": null, "fba_observed": null,
        "fbm_observed": null, "amazon_observed": null, "claimed_total": null },
      "coverage": { "offer_list_available": false,
        "offers_complete_status": "unknown",
        "coverage_reason": "no provider roster requested" },
      "offers": []
    },
    "economics": { "net_profit": null, "roi_pct": null,
      "economics_confidence": "unavailable",
      "economics_status": "missing_market_or_cost_inputs" },
    "provenance": {
      "market.amazon_price": { "source": "easyparser",
        "fetched_at": "2026-08-17T12:00:00+00:00" }
    }
  }
}
```

Contract invariants (enforced by `intel_schema.validate_snapshot`):
1. Unknown numbers are `null`; **0 is never a substitute** (explicit configured
   0.00 costs excepted: prep/inbound/packaging/reserve).
2. Raw provider responses live in `sources`; normalized facts in `facts`;
   derived economics in `facts.economics` — never mixed.
3. Every populated value field carries provenance (`source`, `fetched_at`).
4. Coverage metadata is mandatory and honest: `offer_list_available` bool +
   `offers_complete_status` (`full|partial|unknown`) + `coverage_reason`
   whenever not full.
5. Seller counts keep `observed_*` (from returned offer rows) separate from
   `claimed_total` (provider headline); a claimed number with zero observed
   rows stays `partial` coverage, never `full`.
6. `buy_box` winner is recorded only when the provider explicitly reports it
   (Easyparser `buybox_winner`); never inferred from lowest price.
7. Missing values never cascade: no sales → demand null; no fees → economics
   `unavailable`; no COGS → `cost_status: unavailable`.

---

## 5. Completeness Score and Status Taxonomy (Phase 3)

Implemented in `completeness_score.py` (pure, offline). **Score = prioritization
signal; Status = decision gate.**

### 5.1 Categories (weights sum to 100)

| Category | Max | How points accrue |
|---|---|---|
| identity_mapping | 15 | name 5; pack_match exact/invoice-confirmed 10, candidate 3, mismatch/unknown 0 |
| source_cost | 15 | COGS present 10; basis invoice +5, online discovery +3, estimated +2 |
| market_coverage | 20 | amazon_price 4, buy box available+price 4, observed offer list 4, coverage full 4, observed seller counts 4 — **partial coverage caps the category at 10** |
| fees_economics | 20 | referral fee 4, FBA fee 6 (verified 6 / estimated 4 / provisional 2), economics estimated 6 / provisional 3 / unavailable 0, net+ROI present 4 — **provisional fees cap at 8** |
| demand | 15 | estimate present 9; provider_verified +6, internal_estimate +3, unknown method +0 |
| invoice_readiness | 15 | invoice-confirmed cost 15; online discovery 5; estimated 2; none 0 |

### 5.2 Status ladder (first unmet need wins)

`discovery_only` → `blocked` → `needs_mapping` → `needs_market_data` →
`needs_fee_verification` → `needs_demand_data` → `needs_invoice_confirmation`
→ `ready_for_test_buy`.

- `discovery_only`: scan row only (no identity, market, or cost facts).
- `blocked`: pack mismatch proven; **or** all data gates pass but
  `account_review_approved=False` (reason `requires_account_review`); **or**
  economics not `estimated` tier.
- `ready_for_test_buy`: pack exact/invoice **and** amazon price + offer roster
  **and** fees verified/estimated **and** demand present **and**
  invoice-confirmed COGS **and** explicit account/sourcing review approval.
- `purchase_authorized` (separate boolean): invoice-confirmed cost **and**
  exact pack fingerprint **and** amazon price **and** economics `estimated` —
  mirrors `product_analysis` rules, never weakened.

### 5.3 Anti-misleading rules (tested)

- Missing demand/sellers/cost score 0 — never fabricated, never estimated from
  price/title/seller counts.
- Partial rosters cap the market category; provisional fees cap the fee
  category.
- Zero-for-unknown is rejected at schema validation AND scores 0.
- Score is monotone in added data.

---

## 6. Controlled Enrichment Workflow (Phase 4)

Operator-run CLI (`enrichment_preflight.py` + a thin runner, future) — **never
inside a scan or GET route**.

### 6.1 Sequence (every live step gated)

1. **Select** candidate ASINs from the scanner (cache-only) — selection rules
   in Section 10.
2. **Preflight (dry-run)** — `plan_enrichment(asins, cache_statuses, provider,
   max_credits)`:
   - ASIN validation (10-char alphanumeric);
   - hard batch cap **<= 20** (`MAX_ENRICHMENT_BATCH_SIZE`, default 20, clamped);
   - fresh-cache ASINs skipped at zero cost (TTL rules from
     `market_snapshot_store` freshness);
   - credit estimate per provider (documented estimates: Easyparser ~5/ASIN,
     Chocodata 5, Web Unlocker 1, Unwrangle 1; Scavio unknown → `None`, never a
     guess);
   - `max_credits` budget stop truncates the plan; over-budget ASINs listed as
     deferred, never silently dropped;
   - returns `dry_run: true`, `requires_human_confirmation: true`.
3. **Human approval** — D1 provider + D2 budget + shortlist confirmation.
4. **Run** — the only live step, with the approved plan as input; per-ASIN
   results stored to the normalized snapshot store; per-ASIN atomic writes;
   run report (attempts, successes, per-ASIN credits, failures).
5. **Review** — scores/statuses recomputed; rows needing `invoices import`
   flagged; economics recomputed only via the existing backend pipeline
   (fee_engine/product_analysis, untouched).

### 6.2 Guardrails (mirror AGENTS.md contract)

- Never during scan/render/filter/sort/page load.
- Cached per-ASIN (offer cache keyspace separate from scanner cache).
- Provider errors/unavailable results are never cached.
- Live calls only when `SCANNER_LIVE_ALLOWED=1`; default off.

---

## 7. Provider Capability Matrix (Phase 5)

Audited against source (line numbers from the actual clients).

| Capability | Scavio (search) | Easyparser (OFFER) | BrightData Web Unlocker | BrightData dataset |
|---|---|---|---|---|
| ASIN | Y (scavio_client.py:75) | Y (:62,:158) | Y (:269,:372) | Y (:116) |
| Title | Y (:76) | Y (:63,:159) | Y (:270,:373-374) | Y (:117) |
| Amazon price | Y (:77) | no direct key | Y (:271,:375) | Y (:118) |
| Buy Box price | N | Y (:66,:213) | Y but = price alias (:376) | pass-through (:119) |
| Buy Box winner identity | N | Y (:68-69,:215-216) | N (hardcoded `"unknown"` :383-384) | pass-through (:130) |
| Total sellers | N | provider `offer_count` (:64,:160) | Y aggregate parse (:377) | pass-through (:120-121) |
| FBA sellers | N | observed count (:74,:191) | None by contract (:379-380) | pass-through (:122) |
| FBM sellers | N | observed count (:75,:192) | no key | computed, not output (:89) |
| Per-seller offers | N | Y `offers[]` (:29-49) | N (aggregates only) | pass-through `sellers` (:66-80,:123) |
| Per-offer Buy Box flag | N | Y `buybox_winner` (:31) | N | N |
| Shipping numeric | N | text/free-flag only (:44-45) | N | N |
| Monthly sales est. | N | N | Y (:275,:385) | pass-through (:133) |
| FBA fee | N | N | Y weight-derived (:387) | pass-through (:132) |
| Category/browse node | N | N | Y (:390-396) | pass-through |
| Cost / request | not documented | response `credits_used` (:145-146); ~5 est. | 1 credit (docstring) | not stated in file |

**Failure semantics (audited):** Scavio `LAST_SEARCH_ERROR` global, per-keyword
continue, partial results returned; Easyparser never raises — base shape +
`data_gaps` appends, partial data kept (zip/observed_at/credits); Web Unlocker
`LAST_ERROR` + in-memory 15-min cache, `{}` on invalid ASIN; dataset client
returns None on failure with one partial path (completed-but-empty → all-null
shape). **Import-time network: none in any client** (load_dotenv only) — scan
rows and GET routes stay offline-safe as proven by `test_live_containment.py`.

**Implication:** only **Easyparser OFFER** satisfies the honesty bar for the
market block (fields 4-10: roster, winner identity, observed FBA/FBM counts).
Web Unlocker adds sales/rank/category (fields 12-13, 20). Neither supplies
UPC/EAN/GTIN (18). Decision D1 chooses the mix; until then market facts stay
Unknown/null and the score reflects it.

---

## 8. Human Decisions Required

`NEEDS HUMAN DECISION:`

1. **D1 — Provider mix:** Easyparser OFFER only (honest roster, ~5 cr/ASIN, no
   sales/rank/category/UPC) vs. Easyparser + Web Unlocker detail calls (~1
   cr/ASIN extra) vs. dataset-based (no roster honesty) vs. keep OFF.
2. **D2 — Budget:** per-run credit cap (e.g., 20 ASINs x 5 cr = ~100 cr) and
   monthly cap; deposited credits vs. free tier; budget-stop behavior
   (defer vs. abort).
3. **D3 — Source of truth for COGS:** require `invoices import` confirmation
   (Business Center invoice) for any purchase-authorized row vs. accept
   online-discovery costs for research only (existing rule: discovery costs
   never authorize a buy — confirm unchanged).
4. **D4 — 20-ASIN shortlist basis:** score desc vs. status-first vs. mix;
   include `discovery_only` rows?
5. **D5 — UI scope for Phase 6:** new table columns (Score, Status, Coverage)
   + completeness panel vs. report-only (CSV/CLI) first.
6. **D6 — Sales/demand tier:** accept internal `demand_estimator` estimates as
   "estimated" for the demand category, or require provider-verified numbers
   (Web Unlocker) before Ready for Test Buy.

No default is applied for any of the above; the scaffolding works with OFF.

---

## 9. UI Implementation Plan (Phase 6)

NOT implemented. Design, mapped to the existing Scout UI audit:

1. **Table:** add `Score` (0-100 badge) and `Status` (taxonomy label) columns
   after `Tier`/`Status`; the Status filter joins the persisted
   `t2.kirklandScout.filters.v2` set, and new columns register in
   `COLUMNS_KEY` defaults with bounds (score 70-140, status 90-220 px) and
   resizable handles per the existing implementation.
2. **Unknown rendering:** Score renders `—` (never 0-meaning-unknown; a true 0
   score is labeled `0 (discovery only)`), Status `Unknown`, Coverage
   `Full/Partial/Unknown` with a reason tooltip — via the existing
   `renderUnknown` pattern; no invented numbers.
3. **Detail row:** extend the sheet's `market` segment with the snapshot block:
   observed counts (Total/FBA/FBM), Buy Box winner (source-tagged, `Unknown`
   until loaded), coverage disclosure, provenance (`fetched_at`/`source`), and
   the existing "Load seller details" button (on-demand
   `GET /api/products/{asin}/offers`, Easyparser) — no auto-refresh.
4. **Preflight UI (later phase):** dry-run plan preview (requests, credits,
   budget stop) rendered before any live run; disabled unless gate on.
5. **Zero provider calls on load:** any new fetch must go through the same
   cache-only routes; a new snapshot read endpoint returns store data only.

---

## 10. 20-ASIN Shortlist Selection Rules

1. From the latest scored snapshot (cache-only), filter: valid ASIN present,
   economics tier estimated or provisional (never `unavailable`), pack_match
   exact or candidate (mismatch excluded).
2. Rank by completeness score desc; cap at 20 (`MAX_ENRICHMENT_BATCH_SIZE`);
   over-budget rows deferred, never dropped.
3. Skip ASINs already fresh in the snapshot store (zero cost).
4. Include at least 1 invoice-confirmed Costco row when available (fields
   16/17 gates).
5. Report the plan (`enrichment_preflight.plan_enrichment`) before any live
   step; execution requires human approval of D1/D2.

---

## 11. Offline Test Plan and Results (Phase 7)

### 11.1 New scaffolding (delivered, NOT wired into the server)

- `intel_schema.py` — `validate_snapshot()`, fixtures, zero-for-unknown and
  provenance rules.
- `completeness_score.py` — `compute_completeness(snapshot,
  account_review_approved)`: 0-100 score, category scores + reasons, status
  ladder, `purchase_authorized`.
- `enrichment_preflight.py` — `plan_enrichment()`: batch cap, fresh skip,
  credit estimates, budget stop, dry-run + human-confirmation flags;
  `missing_field_groups()`.
- `test_asin_intel_plan.py` — 28 tests in 4 classes (schema, score, preflight,
  scanner-gate re-assert).

### 11.2 Test results

- `python -m unittest test_asin_intel_plan` → **28 OK**.
- Full offline Python suite (all 29 test modules, `test_scavio*` excluded):
  same file set without the new tests = **714 OK (skipped=3)**; with them =
  **742 OK (skipped=3)** — the +28 delta is exactly this plan's tests. (The
  previously documented explicit subset was 687 OK (skipped=3); the 27-test
  difference is other modules in the full set.)
- UI harness `node test_ui_display.cjs` → **756 PASS** (unchanged; no UI
  touched).

### 11.3 Zero-provider-call proofs in the new suite

- `EnrichmentPreflightTests.test_provider_modules_never_imported_by_planner` —
  the planner imports no provider client.
- `ScannerGateReassertTests` — `GET /api/kirkland/scanner` and
  `/api/kirkland/live` run with every outbound client patched to raise; the
  scanner still returns `live_allowed: false`, `scanner_mode: cache_only`,
  `enrichment_source: OFF` (cache-only re-assert).

### 11.4 Phase 6 UI tests

Deferred honestly: the UI does not yet render Score/Status/Coverage states, so
no UI fixture tests exist for them. Once Phase 6 is implemented, harness tests
must cover unknown-score/status rendering, filter integration, resizable column
registration, and zero-fetch-on-load — mirroring the existing
`test_ui_display.cjs` patterns.

---

## 12. Final Report (Phase 8) — First Live Run Checklist

Before any live enrichment run (each item is a human action):

1. [ ] D1: provider mix decided and recorded here.
2. [ ] D2: per-run and monthly credit budgets set in `.env` (documented, no
       secrets printed).
3. [ ] D3: source-of-truth rule confirmed (invoice confirmation required for
       purchase authorization — recommended).
4. [ ] D4/D5: shortlist basis and UI scope decided.
5. [ ] `SCANNER_LIVE_ALLOWED=1` set by the operator only for the run window,
       then reverted to off.
6. [ ] `plan_enrichment` output reviewed and saved as the run plan (batch
       <= 20, credits <= budget).
7. [ ] Snapshot store path backed up (read-only copy) before the run.
8. [ ] Run executed via the controlled CLI only (never via GET routes or the
       UI).
9. [ ] Run report reviewed: successes, per-ASIN credits, failures,
       `data_gaps`, coverage statuses.
10. [ ] `POST /api/kirkland/refresh` not used for enrichment (it is the scan
        entry point only).
11. [ ] Test suite re-run after the run to confirm the containment proofs
        still pass.

**Files changed by this plan task (offline-only):**
- `docs/asin-market-data-completeness-plan.md` (this document)
- `intel_schema.py`, `completeness_score.py`, `enrichment_preflight.py`
- `test_asin_intel_plan.py`

**No live API calls were made during this task. No server route, cache,
catalog, or data file was modified.**