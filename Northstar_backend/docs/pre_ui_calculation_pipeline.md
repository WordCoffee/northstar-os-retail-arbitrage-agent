# Pre-UI Calculation Pipeline (Northstar Scout)

Every number the Product Scout shows is computed **before** the UI
renders, by a named stage with a named owner, and carries provenance
(confidence / status / note). The UI is a **pure renderer**: it formats
and displays backend values only — no fee formulas, no category mapping,
no profit math, no ROI derivation. If a value cannot be computed
honestly it stays `null` and renders as "Unavailable" — never `0`,
`0%`, or `$0.00` (except an explicitly configured `0.00`, e.g.
packaging cost).

## Invariants

1. UI = renderer. Any new derived value must be added server-side in the
   stage that owns it, allowlisted in `main.SCANNER_ALLOWED_KEYS`, then
   rendered.
2. Every derived value ships with `confidence`, `status`, and `note`
   provenance. Confidence vocabulary is fixed per stage (below).
3. Missing input → `None`, never a fabricated number.
4. Formulas change only through a **versioned** rule module
   (`amazon_us_fee_rules_2026.py`); bump `RULES_VERSION` and the note
   when the schedule changes. Never edit rules silently.
5. No live API calls in tests; `test_network_guard` blocks real network
   in every test module.

## The complete pre-UI field catalog

| # | Field(s) | Stage / owner | Input | Output provenance |
|---|----------|---------------|-------|-------------------|
| 1 | `name`, `asin`, `product_url`, `amazon_price` (search) | `amazon_search` (BRIGHTDATA primary, ChocoData/Scavio fallback) | search keywords | `upstream_unavailable` status + `upstream_hint` on failure |
| 2 | `amazon_price` (listing), `lowest_price`, `highest_price`, `total_sellers`, `fba_sellers`, `monthly_sales_estimate/estimated`, `sales_rank`, `fba_fee` (listing), `weight_lbs` | `offer_enrichment` per-ASIN (BRIGHTDATA default, AUTO/CHOCodata/Easyparser fallbacks) | ASIN URL | `offer_data_provider`, `enrichment_status`, `enriched_at`; billed modes credit-gated to scoreable rows only (Costco cost exists AND `match_quality` ∈ exact \| invoice_confirmed); candidate/mismatch/unknown + OFF = offline placeholder at zero cost; live successes cached per-ASIN (`data/enriched-offer-cache.json`, `SCANNER_OFFER_CACHE_TTL_HOURS` default 24, `<= 0` disables) — placeholders/failures never cached |
| 3 | `costco_cost`, `costco_cost_basis`, `pack_match`, `cost_match_reason`, `cost_source`, `cost_is_purchase_authorized` | `costco_api_client.resolve_costco_cost` (wrapped as `product_analysis.get_costco_price`) across the three-layer catalog: invoice_confirmed > product_detail > CSV | item_name | basis ∈ `invoice_confirmed \| costco_online \| estimated \| candidate_match \| unavailable`; `pack_match` = exact \| invoice_confirmed \| high_confidence \| candidate \| mismatch \| unknown via `product_equivalence()` fingerprint (brand, formula/flavor, net weight, pack/count, UPC/EAN when present) + normalized-title identity (≥ `HIGH_CONFIDENCE_TITLE_RATIO` 0.85). Exact invoice → `invoice_confirmed` (only this may set `cost_is_purchase_authorized = True`); exact detail → `costco_online` (research only, `detail_only`); exact CSV → `estimated`; high-confidence (strong title identity, no known conflict) → `estimated` research cost (invoice-derived high-confidence keeps the paid cost but stays `match_quality = high_confidence`, basis `invoice_confirmed`, `cost_is_purchase_authorized = False`); anything else → `candidate_match`, never purchase-eligible. `cost_is_purchase_authorized` is `True` only for `invoice_confirmed` |
| 3b | economics downgrade (non-exact) | `product_analysis` Pack/Variant Match gate | `match_quality` | `costco_cost_basis = candidate_match`, `economics_status = mapping_verification_required`, note names the conflict; **computed price + COGS economics stay visible as `provisional` (net/ROI kept — never nulled, never hidden) so every product can be triaged**; `profit_tier` and `verdict` stay `None` (no Tier/Pass/Scale eligibility, `cost_is_purchase_authorized` stays False — verify the exact Costco item before any purchase). Rows whose fee-engine economics are already `unavailable` (e.g. missing Amazon price) keep `economics_confidence = unavailable` under the same mapping-verification status. `exact`, `invoice_confirmed`, and `high_confidence` pass the gate (only exact-invoice rows carry real paid COGS with `invoice_confirmed` and may authorize a purchase after Amazon listing checks; high-confidence rows expose the research cost and economics but never authorize a purchase) |
| 4 | `referral_fee*` | `fee_engine.calculate_referral_fee` | sale price + category/browse node | confidence ∈ `verified_category \| default_category \| unavailable`; category None → default Everything Else 15% with explicit "verify in Seller Central" note |
| 5 | `fba_fee`, `fba_base_fee`, `fba_fuel_logistics_surcharge`, `fba_size_tier`, `fba_weight_basis_lbs`, `fba_fee_status/confidence/rule/note` | `fee_engine.calculate_fba_fulfillment_fee` | package weight (+ dims) | status ∈ `available \| weight_unavailable \| dimensions_unavailable \| size_tier_unavailable \| needs_revenue_calculator_verification`; total = base + 3.5% surcharge, values equal the validated legacy table |
| 6 | `inbound_cost_per_unit`, `prep_cost_per_unit`, `packaging_cost_per_unit`, `return_reserve_rate` | `fee_engine.calculate_unit_costs` | env (`INBOUND_COST_PER_UNIT` 0.35, `PREP_COST_PER_UNIT` 0.25, `PACKAGING_COST_PER_UNIT` 0.00, `RETURN_RESERVE_RATE` 0.02) | env-driven; 0.00 only when explicitly configured |
| 7 | `net_profit`, `roi_pct`, `economics_confidence/status/note` | `fee_engine.calculate_unit_economics` | price + COGS + fees + unit costs | tier ∈ estimated (`estimated_fee_stack`) \| provisional (`needs_fee_verification`, FBA fee EXCLUDED, verify before purchase) \| unavailable (`missing_amazon_price` \| `missing_costco_cogs`); roi = net/cogs × 100 |
| 8 | `verdict` | `product_analysis._catalog_verdict_or_none` | net profit + verified monthly sales | Pass/Hold/Reject only when every input verified; else None or `Needs Fee Verification` |
| 9 | `profit_tier` (11/9/7) | `product_analysis` | net profit | **estimated rows only** — provisional/unavailable never tiered |
| 10 | gating (MIN_ROI/MIN_MARGIN) | `product_analysis` | roi + margin | applied to **estimated** rows only; provisional/unavailable rows are never dropped by thresholds they cannot truthfully satisfy. Estimated rows below the minimum are **kept visible for triage** (never silently dropped) and flagged `roi_below_minimum = true` so the UI and downstream tooling can call out the shortfall |
| 11 | dedupe by ASIN | `product_analysis._dedupe_candidates` | search results | first occurrence kept |
| 12 | sort order | `main._scanner_sort_key` + UI `SORTS` | economics group → net profit desc → ROI desc → competition asc → demand desc | group: estimated=0, provisional=1, unavailable=2 |
| 13 | Score column (`score`) | `opportunity_analytics.opportunity_fields` → UI `NS.scoutScore` | opportunity_score (economics, sales velocity, competition, match; `None` when price or COGS missing) or `data_completeness_score` fallback | every row carries a 0-100 figure for triage (label distinguishes "opp" vs "complete"); the client-side directional `computeOpportunityScores` still powers the Top Opportunities strip, labeled "directional" |
| 14 | freshness / upstream status | `costco_api_client.last_run_status` + `amazon_search.LAST_SEARCH_ERROR` | run report, last error | fresh/stale/unknown; upstream_unavailable + hint |

## Process for adding a pre-UI calculation

1. Identify the owning stage (table above). If none exists, create one
   (new module + versioned rules where applicable).
2. Compute in the backend; add fields to `product_analysis` result and
   `main.SCANNER_ALLOWED_KEYS`.
3. Carry `confidence` / `status` / `note`. Missing → `None`.
4. Render in `static/index.html` **without any fee formula**; add badges
   and expandable fee-breakdown content via `NS.feeBreakdownHtml`.
5. Tests: offline, network-guarded (`import test_network_guard`); update
   `test_product_analysis.py` / `test_scanner_endpoint.py` patches if
   the pipeline call changed; extend `test_ui_display.cjs` for
   rendering/sorting; add engine cases to `test_fee_engine.py`.
6. Run `python -m unittest discover` (all `test_*.py`) and
   `node test_ui_display.cjs`; run `npm run lint` in the project root.

## Agent handoff runbook (AI-agent presentation pipeline)

Default process: **the scanner response is the handoff**. Any agent or
human consuming the Scout reads derived values from the response and
never recomputes them. For richer presentation tasks (a report, a
recommendation deck), the consuming agent:

1. Reads `GET /api/kirkland/scanner` and consumes only
   `SCANNER_ALLOWED_KEYS`.
2. Groups by `economics_confidence` (estimated → provisional →
   unavailable), never re-derives profit/ROI.
3. Cites the `note`/`confidence` strings verbatim when a value is
   provisional or defaulted (e.g. "Default 15% — verify in Seller
   Central").
4. Never labels provisional as final, never prints `$0.00` for a
   missing value, never drops rows silently — surface the
   `economics_status` and `verdict` as-is.

File-system architecture option (no agent runtime): keep the manifest
above in `docs/` (this file), mirror it in `AGENTS.md`, and treat every
scanner response as the contract — the UI and any future presentation
layer are pure consumers.