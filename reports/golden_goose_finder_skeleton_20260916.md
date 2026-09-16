# Golden Goose Finder — Skeleton + Category Config (Build Report)

**Date:** 2026-09-16
**Session:** subagent (ses_f56c532aaffeOsc6EDRu0gBnxH)
**Scope:** project skeleton + brand/category registry module + tests. Code only; no live calls.

## Files created

- `Northstar_backend/agents/__init__.py` (empty package marker)
- `Northstar_backend/agents/golden_goose_finder/__init__.py` — `__version__ = "0.1.0"`
- `Northstar_backend/agents/golden_goose_finder/category_config.py` — registry module
- `Northstar_backend/agents/golden_goose_finder/tests/__init__.py` (empty)
- `Northstar_backend/agents/golden_goose_finder/tests/test_category_config.py` — pytest suite

## Module contents (category_config.py)

- **BRAND_ALLOWLIST** — 76 national brands → 8 categories (nicotine_cessation, otc_health,
  vitamins_supplements, household_cleaning, personal_care, pet, snacks_bars, baby_child).
  Store brands excluded: Equate (flagged in the spec as skip), Kirkland Signature, Member's Mark,
  Great Value, and generic `store brand` / `private label` keywords — none appear in the allowlist.
- **CATEGORY_CONFIG** — all 8 slugs with the full 12-field schema per category
  (display_name, amazon_browse_nodes, amazon_category_name, referral_fee_rate,
  typical_pack_sizes, typical_wholesale_range, typical_individual_range,
  size_filter_max_weight_oz, size_filter_max_dimensions_in, min_monthly_sales, min_rating, priority).
- **amazon_category_name matches the repo fee engine** (`amazon_us_fee_rules_2026.py`):
  Health & Personal Care (price_switch), Home & Kitchen (flat 15%), Pet Supplies (flat 15%),
  Grocery & Gourmet Food (price_switch), Baby Products (price_switch).
- **referral_fee_rate** — 0.15 default; 0.08 where the typical individual unit falls in the
  price-switch low tier (otc_health, snacks_bars). Documented as a planning estimate; the fee
  engine still applies the exact switch schedule.
- **SIZE_FILTER** — `DEFAULT_SIZE_FILTER` (48.0 oz / [12, 8, 4] in, repackaging description).
- **ROI_FLOOR** — `DEFAULT_ROI_FLOOR_PER_UNIT = 10.00` with explicit "overridable per profile,
  NOT a master brain default" documentation.
- **BRAND_EXCLUSION_LIST** — Kirkland Signature, Member's Mark, Great Value, Equate,
  store brand, private label (extensible).
- **Helpers** — get_category_config (raises KeyError w/ valid slugs), get_all_categories,
  get_brand_list (all or per-category), is_brand_allowed (case-insensitive; exclusions always
  win), get_amazon_browse_nodes.
- **parse_pack_quantity(title, category_slug=None)** — layered regex resolution:
  1) number + primary count unit (leftmost wins: "200 Count", "250 Softgels", "81 Count (4 Pack)" → 81),
  2) number + container unit ("30 Pack", "24 Pack of 2 oz tubes" → 24),
  3) "N x M" multi-pack ("24 x 10.2 oz cans" → 24),
  4) parenthesized bare number,
  5) last-resort any number > 1 that isn't a dose/measure/price/glued-to-letter
     ("Rubber Gloves - 200" → 200; "Vitamin D3 5000 IU" → None). `category_slug` reserved for
     future category-specific heuristics.

## Test results

```
python -m pytest agents/golden_goose_finder/tests/test_category_config.py -v
75 passed in 0.08s
```

Coverage: all category slugs resolve, per-category brand spot-checks, exclusion-list catches
Kirkland/Member's Mark/Equate/Great Value, 22 parse_pack_quantity known formats + 7 negative
cases, is_brand_allowed matrix (17 cases), complete config schema/type checks, fee-engine
category name alignment, unique dense priorities 1-8, no store brands in any category.

## Notes for parent session

- "Rite Aid" (listed in the spec's nicotine_cessation section) was NOT allowlisted — it is a
  pharmacy store brand, consistent with the NO-store-brands rule; Equate was likewise skipped.
  Add back explicitly if a national-brand carve-out is wanted.
- Browse nodes mix high-confidence numeric IDs (3760901, 3777871, 11055981, 165796011,
  2619533011, 16310101, 1055398 — first-node set cross-checked against the repo's
  REFERRAL_BROWSE_NODE_MAP) with human-readable node paths, since IDs drift over time.
- Master-brain profile resolution and 00_STATE.json batch wiring are left to the parent session
  (no profile identity was resolved here; this is pre-integration code only).