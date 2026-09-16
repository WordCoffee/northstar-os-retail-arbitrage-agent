# Golden Goose Finder — Complete Build Report

**Date:** 2026-09-16
**Committed:** `7423251` (+ 6 agent commits; local only, no push)
**Status:** COMPLETE — mock-first build, full pipeline functional, live calls §3-gated

---

## What Was Built

The complete **Golden Goose Finder** module at `Northstar_backend/agents/golden_goose_finder/` — a brand-agnostic multi-pack breakdown arbitrage scanner that replaces the dead-end Kirkland-only pipeline.

### Architecture (8 modules)

| Module | Purpose | Tests |
|---|---|---|
| `category_config.py` | 76 national brands / 8 categories / pack-parse regex / brand exclusions | 75 |
| `wholesale_scanner.py` | Costco + Sam's Club discovery (mock-first, §3-gated live path) | 84* |
| `amazon_matcher.py` | Individual-pack ASIN finder + relative pack-size filter | 84* |
| `breakdown_economics.py` | Full fee-stack economics (referral, FBA, repackaging, reserve, breakeven) | 41 |
| `opportunity_scorer.py` | Weighted composite scoring, hard filters, HIGH/MED/LOW/REJECT, tags | 46* |
| `goose_report.py` | JSON v1.0 reports, console table, Scout-panel export | 46* |
| `main.py` | FastAPI router + CLI + `/scan-mock` (safe) + `/scan` (403 hard-stop) | 33 |
| `runtime_agent.py` | **NEW — the 5-helper sub-agent orchestrator** | 23 |

**Full package: 303 tests passing.** Backend suite: 1835 passing.

### The Runtime Agent (your 5-helper requirement)

`runtime_agent.py` defines the five helper sub-agents the Golden Goose Finder controls:

| # | Helper | Web Surface | Output |
|---|---|---|---|
| 1 | Costco Catalog Scanner | costco.com search | multi-pack products (title/brand/count/price) |
| 2 | Sam's Club Catalog Scanner | samsclub.com search | multi-pack products |
| 3 | Amazon Product Finder | amazon.com search | individual/small-pack ASINs |
| 4 | Amazon Seller Analyzer | offer listing pages | FBA/FBM seller depth, Buy Box |
| 5 | Price/BSR History Tracker | Keepa-class history / snapshots | BSR + price history signals |

- `build_helper_payloads()` → ready-to-paste prompts per helper
- `collect_helper_results()` → parses STRICT-JSON sub-agent replies, validates required fields
- `amazon_matches_from_helper_results()` → merges finder + seller + history into `AmazonMatch`
- `MockHelperDispatcher` → deterministic offline end-to-end harness (all 5 helpers, no live calls)
- `require_live_approval()` → §3 hard gate; live mode raises `LiveArmedError` without named operator approval

### How the brain runs it (live, with approval)

1. `build_helper_payloads(categories=[...])`
2. Spawn 5 OpenCode sub-agents with the generated prompts (each scans its web surface)
3. `collect_helper_results(raw_outputs)` → validate JSON
4. Convert to `WholesaleProduct` / `AmazonMatch` → `calculate_breakdown_economics` → `score_batch` → `generate_json_report`
5. UI: `Northstar_backend/agents/golden_goose_finder/static/golden-goose-panel.html` + FastAPI endpoints

### Demo output (mock run)

Top finds from the offline harness:
- **Nicorette Nicotine Gum 2mg** — 200ct @ $89.99 Costco → 60ct packs @ $67.49 Amazon → **$54.22 profit/pack**, HIGH
- **Blue Buffalo Dog Food** — $49.99 club → $124.98 Amazon → **$52.39 profit**, HIGH
- **Colgate 6-pack** → **$64.45 profit**, HIGH
- 23 HIGH / 5 MEDIUM / 2 LOW across 30 opportunities

---

## Fixes Made (beyond delegated builds)

1. **Mock Amazon economics were broken** — individual listings were priced as `per-unit-COGS × 2.5` ("1 Count" @ $0.13 for Advil). Rewrote `get_mock_amazon_matches()` with a realistic small-pack model (`_small_pack_count()` + per-unit premium pricing). Demo now shows sane $7-67 price points.
2. **Pack-size filter was wrong** — absolute `count ≥ 20 = multi-pack` rejected legitimate individual packs (a 60ct vitamin bottle is an individual listing vs club 500ct). Rewrote `is_individual_listing()`: literal multi-pack phrases always reject; otherwise relative to wholesale pack (must be ≤ half the club pack).
3. **Harness report path** — `save_report()` now fed via `generate_json_report()` (dicts, not dataclasses).

## Incidents Disclosed

- The wholesale-scanner agent accidentally fired ~10 live OpenWebNinja requests (~100 credits) during a smoke test before its §3 gate landed. **Fixed**: live path now inert unless `GOLDEN_GOOSE_LIVE_OPERATOR_APPROVED=1`. See `reports/golden_goose_scanner_matcher_20260916T031324.md`.
- Pre-existing untracked test artifacts (tmp-probe snapshots, dryrun files) were swept into the commit — harmless, but flagged.

## 100 Improvements Roadmap

Delivered at `reports/golden_goose_improvements_100_20260916.md` — 25 each across **data finding, consolidation, presentation, filters**, prioritized P0/P1/P2. Recommended first wave: P0 items 1-5 (Keepa, SP-API ungating, Sam's Club catalog, flyer parser) + 26-30 (unified ID registry, source confidence) + 51-55 (score tooltips, sparklines) + 76-80 (per-category ROI floors, dual gates).

## $10/unit ROI Floor — Profile-Level per Your Direction

`DEFAULT_ROI_FLOOR_PER_UNIT = 10.00` in `category_config.py`, documented as **overridable per user profile, NOT a master-brain default**. The scorer takes `roi_floor` as a parameter — no global hardcode.

## Next Steps (require your named approval — §3)

1. **Live mock→real transition**: arm `GOLDEN_GOOSE_LIVE_OPERATOR_APPROVED` and run the 5-helper agent against real Costco.com + samsclub.com + amazon.com
2. **Keepa API key** (~$17-20/mo) → real historical BSR/seller data
3. **Amazon SP-API credentials** → real-time ungating + FBA fee verification
4. P0 improvements wave from the roadmap