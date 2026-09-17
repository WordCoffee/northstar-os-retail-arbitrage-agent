# Golden Goose Finder — Brand-Agnostic Pivot + Free-Tier Stack
**Date:** 2026-09-16  
**Commit:** `3360449` — `pivot: brand-agnostic Golden Goose Finder + free-tier provider stack`  
**Status:** ✅ 362 tests green, all modules import clean, zero regressions

---

## What Changed

### Strategy Pivot
Replaced the Kirkland-only pipeline with a brand-agnostic retail arbitrage system targeting **ANY small, light, high-value national-brand product** at Costco/Sam's Club that yields ≥$10 net profit per unit on Amazon.

### New Hard Filters (all fail-closed on missing data)
| Filter | Rule | Unknown behavior |
|---|---|---|
| **Seller identity** | Brand-owner or Amazon.com as seller → HARD BLOCK | Fails closed |
| **Size** | Weight ≤ 5 lbs (2 lbs preferred) | Fails closed |
| **Competition** | 0 FBA = gold; 1-2 only if undercut clears profit floor; 3+ rejected | Fails closed |
| **Demand** | 1,000+ monthly sales floor | Fails closed |
| **Brand exclusion** | Kirkland, Member's Mark, Great Value, Equate + all store brands | N/A |

### Constants Updated
- `DEFAULT_MIN_MONTHLY_SALES`: 500 → **1000**
- `COMPETITION_CEILING`: 3 → **2** (1-2 FBA only with undercut escape)
- `PREFERRED_MAX_WEIGHT_OZ`: 32.0 (2 lbs) / `ABS_MAX_WEIGHT_OZ`: 80.0 (5 lbs)
- `DEMAND_ANCHORS`: baseline 500 → **1000**

### New Modules
- **`free_tier_registry.py`** — 17 zero-cost data providers, JSON credit ledger with monthly resets
- **`free_tier_router.py`** — Waterfall dispatch with audit trail, credit accounting, §3 live gate

### Modified Files (16 source + 6 test)
| File | Changes |
|---|---|
| `category_config.py` | Pet brands (KONG/Chuckit/Furminator/etc.), size constants, seller block helpers |
| `breakdown_economics.py` | `IndividualListing` gains `seller_name`, `is_brand_seller`, `is_amazon_seller`, `weight_oz` |
| `amazon_matcher.py` | `AmazonMatch` gains seller fields, `seller_identity_blocked()` helper, weighted mock data |
| `opportunity_scorer.py` | Two new hard filters (seller identity, size), competition logic rewritten |
| `goose_report.py` | Report entries carry `seller_identity` + `size_profile`; panel has `seller`, `weightOz` |
| `runtime_agent.py` | Seller analyzer role returns identity; pet mock data (KONG, Furminator, etc.) |
| `wholesale_scanner.py` | Mock catalog refreshed (pet toys/grooming, weights), brand allowlist updated |
| `main.py` | Defaults 1000, docstrings retail-arbitrage, CLI help text |
| `free_tier_registry.py` | NEW — provider registry + credit ledger |
| `free_tier_router.py` | NEW — waterfall router + audit trail |

### Test Updates
- **conftest.py**: `make_individual` gains `weight_oz=12.0`, seller identity defaults
- **MEDIUM fixture**: `fba_sellers` 3→2, `monthly_sales` 700→1200
- **New tests**: seller identity blocks (4), size filter (4), undercut rules rewritten, free-tier registry (33), free-tier router (15)
- **Removed**: Purina brand tests (no longer in allowlist)

### Mock Data Refresh
- Pet section: dog food bags → KONG toys, Furminator tools, Chuckit balls, Hartz brushes, PetSafe harnesses
- All products carry `weight_lbs` (Costco mock) and `weight_oz` (Amazon mock)
- Amazon mock V3 sometimes triggers brand-seller / Amazon-seller blocks for realistic REJECTs

---

## What's Next (Priority Order)
1. **User signups** — Scrapingdog, ScrapingBee, ScrapeBadger, FlyByAPIs, AmazonScraperApi, Apiclaw, Apify, Outscraper
2. **Sam's Club live path** — Wire Apify actor for Sam's Club catalog scanning
3. **§3 named operator approval** — Required before any live outbound calls
4. **P0 roadmap** — Price/BSR history re-scan (weekly), per-category ROI floors, score tooltips in SourceScout panel
