# Costco Non-Kirkland Product Research Pipeline

**OFFLINE-FIRST.** Identifies potentially attractive **non-Kirkland** Costco
products from data that already exists locally, resolves them to Amazon ASIN
candidates, and persists evidence-backed records into the canonical Northstar
database for Product Finder / Golden Goose use.

> **Costco discovery is NOT sourcing authorization.** Retail or online Costco
> pricing is discovery-only unless separately verified, legitimate,
> invoice-backed sourcing documentation exists. Retail receipts are not assumed
> sufficient for Amazon authenticity disputes.

## Safety model (non-negotiable)

- **No crawling / no live Costco requests.** All input is local (CSV/JSON/cache/db).
- **No scraping** SellerAmp SAS; no automated logins
  to `https://sas.selleramp.com/`.
- **No browser automation, stealth, proxy rotation, cookie/session reuse, or
  anti-bot evasion** anywhere in this pipeline.
- **Providers disabled by default** (`NORTHSTAR_SELLERAMP_ENABLED` must be
  explicit `1`/`true`). SellerSprite was retired 2026-09-27 (trial expired) and
  is not a supported provider.
- **No live provider calls from GET routes, UI loads, searches, views, or
  automatic jobs.** Enrichment runs only through an explicit, approval-gated
  manifest + `--approved` + `NORTHSTAR_ENRICHMENT_APPROVED=1`.
- **No secrets** are read, printed, or stored. The only env flags used are
  non-secret approval gates.
- `offline_only = true` is the default for the whole package.

## Local Costco data sources (discovered, not fetched)

The pipeline reads these already-present repo files:

| Source | Records (approx) | Content |
|---|---|---|
| `data/costco-items.csv` | 531 | `item_name`, `costco_cost` |
| `data/costco-discovery-catalog.json` | 800 | brand, pack, price, URL, item_id |
| `data/costco-product-detail.json` | 76 | detail-level (UPC, pack_count) |
| `data/costco-api-catalog.json` | 1 + held + stale | discovery-only |
| `data/costco-amazon-mapping.json` | 29 (ASIN→title) | offline ASIN ledger |

Discovery: `python -m costco_non_kirkland.discover_costco_sources --dry-run`

## Kirkland exclusion

Deterministic, marks-not-deletes. Inspects brand (raw + normalized), title (raw +
normalized), description, manufacturer, URL, and notes for `kirkland`,
`kirkland signature`, and the configurable alias list in
`kirkland_exclusion.KIRKLAND_ALIASES`.

- Excluded records keep `exclusion_reason = "kirkland_signature_out_of_scope"`
  and `eligible_for_costco_non_kirkland_workflow = false`. Source + timestamps
  preserved.
- **Missing brand is never presumed non-Kirkland.** If the title hints Kirkland
  → excluded AND `manual_review_required`. If the brand is simply absent → not
  excluded but `manual_review_required` (ambiguous).
- `audit_exclusion()` produces: total, excluded, eligible, missing-brand,
  ambiguous-brand, manual-review, and per-reason counts.

## Disallowed product classes

In addition to Kirkland, records are excluded (marks-not-deletes) when their
product class is disallowed (`disallowed.py`): hazardous, meltable, fragile,
expiry/perishable, oversized, gated/restricted, regulated medical/drug, alcohol,
tobacco, weapons, animal products. Classification is conservative keyword/size
heuristics — any positive hint excludes.

- Excluded records get `exclusion_reason = "disallowed_product_class"` and
  `eligible_for_costco_non_kirkland_workflow = false`. The detected classes are
  stored in `disallowed_classes` (e.g. `meltable,expiry_risk`).
- **Kirkland reason takes precedence**: a Kirkland record that is also disallowed
  keeps `kirkland_signature_out_of_scope` as its primary reason; the disallowed
  classes are still captured for audit.
- `audit_disallowed()` reports excluded counts and per-class breakdown.

## Sign-in gate (between provider sign-ins)

The pipeline PROMPTS the operator to sign in between provider steps. It never
automates logins, never extracts cookies, and never reuses sessions
programmatically.

```bash
# Check whether a sign-in is required (exit 1 = required)
python -m costco_non_kirkland.signin --service selleramp --check

# Operator confirms they signed in to the research browser (TTL 6h)
python -m costco_non_kirkland.signin --service selleramp --done
```

- `require_signin(service)` returns a `SignInPrompt`; enrichment and planning
  surface it and fail closed until confirmed.
- Confirmations persist in the canonical DB (`costco_confirmations`).
- Services: `costco`, `selleramp`. Retired services (`sellersprite`) fail closed
  by name.

## No direct Amazon.com scanning

This pipeline **never** opens Amazon product pages, scrapes Amazon search or
offer pages, uses Amazon browser automation, or calls undocumented Amazon
endpoints (`amazon_guard.py`). Amazon-market information comes ONLY from
approved SellerAmp snapshots or approved exports.

- `assert_no_amazon_direct_scan()` raises `AmazonDirectScanProhibited` if an
  Amazon.com URL is ever supplied to the pipeline.
- `verify_market_provenance()` fails closed for any Amazon-market field whose
  source is not an approved provider/export.

## Amazon matching

Offline match queue (`matching.py`). Priority:
1. Exact UPC/EAN/GTIN.
2. Exact manufacturer part number + brand.
3. Brand + normalized title + exact pack/count/size.
4. Title/brand candidate → **manual review only**.

Identity statuses: `unresolved`, `upc_exact_candidate`,
`manufacturer_part_exact_candidate`, `title_pack_candidate`,
`verified_exact_pack_match`, `pack_mismatch`, `size_mismatch`,
`variation_ambiguous`, `identity_conflict`, `manual_review_required`.

Never treated as verified when: pack count differs, unit size differs, case-pack
vs retail unit, uncertain child variation, UPC conflict, or brand differs. **No
ROI is computed for identity-conflicted or pack-mismatched records.**

## SellerAmp approval model

`providers.py`. The provider:
- returns `provider_not_configured` unless a **sanctioned** mechanism exists
  (official API, approved export file, sanctioned repo adapter, or explicitly
  approved live enrichment);
- exposes `deep_link(asin)` for **user-initiated** navigation only (never implies
  fetched data);
- never calls the provider automatically during browsing/search/UI.

Sales/revenue from SellerAmp are **provider estimates**, never verified Amazon
facts. Mock/fixture mode is available for tests and dry-runs. The adapter
registry is generic; adding a future provider requires a separate approved
integration pass (a future provider is neither named nor stubbed here).

## Source / freshness semantics

- Evidence classes: `user_provided_export`, `cached_source_snapshot`,
  `benchmark_reference`, `historical_reference`, `manual_entry`.
- Freshness: `fresh` (<7d), `aging` (7–30d), `stale` (>30d), `unknown`.
- Capture statuses: `captured`, `unavailable`, `provider_not_supported`,
  `parse_error`, `identity_conflict`, `not_requested`, `stale`.
- Snapshot evidence classes: `benchmark_reference`, `cached_provider_snapshot`,
  `provider_estimate`, `user_entered_assumption`, `live_verified`,
  `independently_verified_document`, `unavailable`.
- **BSR is first-class** (`bsr_raw`, `bsr_primary_rank/category`,
  `bsr_secondary_rank/category`, `bsr_capture_status`, `bsr_source`,
  `bsr_captured_at`). Unknown BSR is **never zero**.

## Economics-completeness semantics

`economics.py` wraps the canonical `foundation.economics.compute` engine
(Decimal, null-first). `economics_completeness`:
`complete | incomplete_cost | incomplete_fees | incomplete_price |
blocked_identity_mismatch | blocked_source_stale | not_calculated`.

- Missing cost/price/fee/pack-identity → those outputs stay `None` (never zero).
- If any assumption is used, `calculation_class = "hypothetical"`.
- A `hypothetical` model can never authorize a purchase.

## Golden Goose scoring

`scoring.py` — versioned (`golden-goose-costco-nonkirkland-1.0.0`), explainable,
scores only **eligible non-Kirkland + matched** candidates. Weighted composite
(demand, BSR stability, price stability, margin, ROI, competition, pack identity,
replenishment) with hard blockers (Kirkland source, identity mismatch, variation
ambiguity, stale data, missing economics, unverified pack) and penalties
(hazardous, meltable, fragile, expiry, oversized, gated, invoice-readiness,
retail-receipt-only, supply bottleneck, single-ASIN, one-source).

- `purchase_authorization_status` is **always `not_authorized`**. No automated
  path changes it.
- Recommendation statuses: `candidate | research_required | watchlist |
  high_priority_review | rejected | blocked_identity_mismatch |
  blocked_incomplete_economics | blocked_compliance_risk`.

## CLI commands

All support `--dry-run`, log counts/exclusions/source freshness, create an
auditable run manifest, never log secrets, and fail closed.

```bash
# from Northstar_backend/
python -m costco_non_kirkland.discover_costco_sources --dry-run
python -m costco_non_kirkland.import_costco_local --source costco-discovery-catalog.json --dry-run
python -m costco_non_kirkland.exclude_kirkland --run-id <run-id> --dry-run
python -m costco_non_kirkland.match_costco_to_amazon --run-id <run-id> --offline-only --dry-run
python -m costco_non_kirkland.plan_enrichment --run-id <run-id> --source selleramp --max-items 20 --dry-run
python -m costco_non_kirkland.signin --service selleramp --done
python -m costco_non_kirkland.enrich --manifest <manifest> --approved --max-items 20 --spend-cap 50 --mock
python -m costco_non_kirkland.score_golden_goose --run-id <run-id> --score-version v1 --dry-run
python -m costco_non_kirkland.export_non_kirkland_review --run-id <run-id> --format csv
```

## Persistence

`store.py` extends the canonical internal DB (`data_layer` → `northstar.db`) with
additive tables: `costco_pipeline_runs`, `costco_source_products`,
`amazon_match_candidates`, `costco_evidence`, `costco_enrichment_manifests`,
`costco_gg_scores`, `costco_confirmations`, `costco_provider_imports`,
`costco_market_snapshots`, `costco_candidate_decisions`, `costco_approvals`.
Postgres parity migration: `migrations/004_costco_non_kirkland.sql`.

## Manual-export workflow (Phases 2–9)

The operational pipeline takes eligible source products, imports manual
SellerAmp exports, validates identity + seller composition,
calculates conservative economics, ranks candidates, and produces a human
approval queue. Full details in:
- `docs/provider-export-import-guide.md` — manual exports, field mapping, dry runs.
- `docs/mfn-opportunity-filter.md` — competition rules + `mfn_opportunity_score_v1`.
- `docs/purchase-approval-workflow.md` — approval request/grant/revoke/expiry.
- `docs/costco-non-kirkland-troubleshooting.md` — troubleshooting.

Every CLI command prints `Network calls made: 0` unless a separately approved
future provider API mode is explicitly enabled.

## Tests

`costco_non_kirkland/tests/` — fixture-only, `network_guard` active (zero network
asserted). Covers: discovery, Kirkland exclusion (brand/title/URL/notes/
missing-brand), disallowed product classes (hazardous/meltable/expiry/oversize),
sign-in gate (prompt when required, satisfied after confirmation, env bypass),
Amazon direct-scan guard (blocks Amazon.com URLs, fails closed on unauthorized
sources), UPC exact, title+pack, 1-vs-2 pack mismatch, case-vs-unit mismatch,
variation ambiguity, missing cost/fee/price blocking, GG blocker & penalty
logic, provenance persistence, zero network in offline mode, no provider calls
from routes, enrichment approval+sign-in fail-closed, and no Kirkland in the
eligible GG queue.

Run: `python -m pytest costco_non_kirkland/tests -q`

## Known limitations

- CAPTCHA/MFA/bot protection require a human; never automated.
- Websites change; evidence is captured at observation time.
- Prices/fees/sales estimates are time-sensitive provider estimates.
- Marketplace/brand resale rules (gating, IP) are the operator's responsibility.
- The Costco CSV has no brand column → those rows are missing-brand and require
  review; the discovery catalog is the primary rich source.