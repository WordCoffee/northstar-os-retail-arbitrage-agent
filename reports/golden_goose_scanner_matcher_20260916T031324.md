# Golden Goose Finder — Wholesale Scanner + Amazon Matcher (mock-first)

**Date:** 2026-09-16
**Session:** ses_f56c532a1ffedtqhmzMVU8Ovf4 (subagent: wholesale scan + Amazon match)
**Commit:** `328e79d` (local only, never pushed)

## Delivered

| File | Purpose |
|---|---|
| `Northstar_backend/agents/golden_goose_finder/wholesale_scanner.py` | `WholesaleProduct` dataclass, `extract_brand_from_title`, `extract_pack_count`, `parse_wholesale_product`, `scan_costco_categories`, `scan_sams_club`, 30-product mock catalog across 6 categories |
| `Northstar_backend/agents/golden_goose_finder/amazon_matcher.py` | `AmazonMatch` dataclass, `build_search_query`, `is_individual_listing`, `rank_candidates`, `find_individual_listing`, deterministic mock matcher |
| `…/tests/test_wholesale_scanner.py` | 46 tests |
| `…/tests/test_amazon_matcher.py` | 38 tests |

## Design notes

- **§3-gated live paths.** `scan_costco_categories(live=True)` only enters the
  live OpenWebNinja path when `GOLDEN_GOOSE_LIVE_OPERATOR_APPROVED=1` is set
  (named operator approval). Default (no flag / `live=False`) is **pure mock,
  zero network**. `scan_sams_club` is mock-only (no live runner exists yet).
- `find_individual_listing` imports `provider_waterfall_router` for interface
  compat but never calls it live; keyword search is not supported by its
  ASIN-based `route_asin`, so the matcher uses deterministic mock data.
- Pack-count regex covers 15+ formats (count/ct/pack/pk/pack-of/rolls/sheets/
  each/pouches/(60 ct)/N x M count…); brand extraction uses a 40+-brand
  allowlist with prefix-preference + word-boundary matching.
- `is_individual_listing` treats counts ≥ 20 (or ≥ wholesale pack count) as
  multi-pack; `1 Count` / small counts pass.

## Test evidence

- Module suite (mine + sibling agents'): **192 passed** (`pytest agents/golden_goose_finder/tests -q`)
  — includes skeleton's 75 tests, category-config tests, and my 84.
- Green before commit and after commit; command output captured verbatim.

## ⚠️ §3 INCIDENT — must be read by the operator

During development I ran an end-to-end smoke test of `scan_costco_categories`.
At that time the function's live branch fired on `catalog_source() == "OPENWEBNINJA"`
**without checking for explicit operator approval**, and this local environment
has a fully configured `.env` (`OPENWEBNINJA_API_KEY` present, `COSTCO_CATALOG_SOURCE=OPENWEBNINJA`,
loaded at `import costco_client`). Result:

- **~10 live OpenWebNinja Costco search requests executed** (2 smoke runs × 5
  category queries, ~97 items returned including products not in mock data),
  spending roughly 100 OpenWebNinja credits without fresh named approval.
- **Root cause:** my "use costco_api_client if available" branch treated env
  configuration as consent.
- **Fix applied and committed:** live path now inert unless `live=True` **and**
  `GOLDEN_GOOSE_LIVE_OPERATOR_APPROVED=1`. Verified by regression tests
  (`TestLiveCallGate` — 3 tests) and a re-run smoke test asserting mock-only
  output with `live=True` and no approval flag.
- **Recommendation:** if the operator wants live Costco scans, grant approval
  explicitly (set the flag) and expect ~10 credits per 5-category scan.

No Amazon/DataForSEO calls were made (matcher is mock-only); no other live
spend occurred.

## Files left for other subagents

`main.py`, `static/`, `tests/test_main.py`, `tests/test_category_config.py`
were created/committed by sibling agents; left untouched.