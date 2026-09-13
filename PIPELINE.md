# Northstar OS Retail Arbitrage Agent — End-to-End Pipeline (v2026-09-13)

This document describes the complete, production data pipeline from Kirkland product discovery through buying decisions. Every stage is implemented as bounded, resumable, crash-safe CLI tools with zero live calls without explicit approval.

---

## 1. Discovery (Costco catalog → ASIN list)

**Input:** `data/costco-items.csv` (curated, 516 rows as of 2026-09-13)
**Tool:** `costco_api_client.py` + `costco_live_runner.py`
- **Sources:** OpenWebNinja realtime Costco search (10 credits/page, key SET, gate `COSTCO_CATALOG_SOURCE=OPENWEBNINJA`)
- **Outputs:**
  - Layer 1 (discovery): `data/costco-discovery-catalog.json` (append-only, 799 records)
  - Layer 2 (detail): `data/costco-product-detail.json` (per-item prices, 0→516 via 65 targeted queries)
  - Layer 3 (invoice): `data/costco-invoice-confirmed.json` (empty — scaffolded for Business Center imports)
- **CSV export:** `data/costco-items.csv` — merges new rows, updates prices, **never deletes** your 180 curated rows
- **Run report:** `data/costco-catalog-run-report.json` (audit trail per refresh)

---

## 2. Amazon Discovery (Kirkland ASINs, quantity-validated)

**Tool:** `bright_data_client.py` (Web Unlocker, 1 credit/request, 5,000 free/mo)
**Compliance gate:** `sourcescout_compliant_manifest.json` — **245 PASS only** (FAIL=20, REVIEW=205 excluded by quantity-match)
**Output:** `brightdata_enrich_compliant.py` bounded runner
- **Result:** 245/245 complete, committed `brightdata-compliant-20260913T050631Z-30e2`
- **Fields:** buy_box_price, title, category, breadcrumb, weight, rating, monthly_sales_estimate
- **Gaps:** `total_sellers`/`fba_sellers` always None (page-level parse only)

---

## 3. Seller Depth (per-ASIN roster)

**Tool:** `easyparser_seller_enrich.py` (Easyparser OFFER, ~1 credit/ASIN)
**Inputs:** 58 needs-fee ASINs (from margin shortlist)
**Runner features:**
- Targeted `--asin-file` / `--only-asins` filtering (manifest order kept)
- Truthful credit accounting via provider **balance-delta** (fixed cumulative-counter bug)
- Crash-safe: streaming `ledger.jsonl`, `summary.json` in finally block, stdout tee with UTF-8 fallback
- Resume on existing run dir (skips finished ASINs, replays ledger truthfully)
**Result:** 58/58 complete, 40 available / 18 partial, balance 99→41, committed `easyparser-seller-20260913T055735Z-c414`
**Fields per ASIN:** seller names/IDs/ratings, `buybox_winner`, `is_fba`/`is_fbm`, Prime, condition, shipping

---

## 4. Margin Shortlist (zero network, operator-defined economics)

**Tool:** `margin_shortlist.py`
**Formula (your definition):** `profit = buy_box − COGS − FBA_fee` (no referral/fuel/inbound)
**Gates:**
- COGS trusted only on `exact` / `high_confidence` CSV matches
- FBA fee = enriched, else weight-estimated; missing → `needs-fee` bucket (never assumed)
- Price outliers filtered (`$1.00–$500.00` default)
**Outputs:** `shortlist.csv/json`, `ceilings.csv` (max COGS to clear $9), `below_cut` (complete data, under threshold)
**Current (2026-09-13):**
- 1 ranked: `B07GDWR1BX` profit $10.55 (USDA Multivitamin 80ct, $29.69 COGS)
- 5 below-cut (incl. 3 sharing one $19.79 COGS row — collision flag)
- 171 needs-cost, 58 needs-fee, 10 price-flagged

---

## 5. COGS Fill (Costco prices → trusted margins)

**Two tracks, both now live:**
- **OpenWebNinja targeted refreshes** (65 queries, ~650 credits, CSV 181→516): each `--query` + `--max-pages 1` merges into CSV automatically; 65 queries ran, 1 new ranked ASIN added
- **Archive mining (zero network):** `archive_candidates_v2.json` → `review_queue.json` (83 gap ASINs with scored Costco options, ceiling-prioritized, deduped) + `auto_mined_strong.json` (36 ≥0.8-score pairs for 20 ASINs)

**Verification step (operator):** review `review_queue.json` — confirm pack parity, reply with ASIN + verified price → I append to CSV → free shortlist re-run

---

## 6. Fee Gap (FBA fees for 58 ASINs)

**Options (need live approval):**
- **Unwrangle amazon_detail** (1 credit/ASIN, key SET) — parked on typed failure (diagnostic re-probe needed)
- **Chocodata /amazon/product** (5 credits/ASIN, key SET) — weight→FBA fee, 1-ASIN probe first
- **Bright Data dataset** (async, different API) — may carry fee, needs probe

**Current:** 0/58 filled; `needs-fee` bucket unchanged

---

## 7. Buying Report (merged decision layer)

**Tool:** offline merge (`buying-report/20260913T073500Z.json`)
**Layers merged:**
1. Bright Data base (price, title, category, weight)
2. EasyParser roster (sellers, FBA/FBM, buybox winner, fulfillment)
3. COGS (from CSV, match_quality tagged)
4. Profit/ROI (your formula)
**Current:** 1 actionable ASIN (`B07GDWR1BX`); others pending COGS/fee verification

---

## 8. RapidAPI (future seller breadth)

**Status:** Key + 6 host pool synced to backend `.env`; client code speaks only `amazon-product-data4` shape; per-host adapters + 1-ASIN probes needed before trust.

---

## Runner Contract (every live tool)

| Property | Enforcement |
|---|---|
| **Hard gates** | `SCANNER_LIVE_ALLOWED=1` + provider key + `--live` + `--max-requests` + `--max-credits` (all required) |
| **Credit accounting** | Pre-request worst-case reserve + post-call balance-delta truth; provider balance `== 0` stops next call |
| **No retries** | One call per ASIN; 24h cache serves repeats free |
| **Crash safety** | Streaming ledger, finally-block summary, stdout tee to `run.log` |
| **Resume** | `--resume-from RUN_ID` skips finished, replays ledger honestly |
| **Scope lock** | **245 PASS only** — 470 pool / FAIL / REVIEW never touched |

---

## Files You Interact With

| File | Purpose | You Edit? |
|---|---|---|
| `data/costco-items.csv` | Trusted COGS (item_name, costco_cost) | **Yes** — verify prices, append rows |
| `Northstar_backend/.env` | All API keys + gates | **Yes** — keys only; gates are `1`/`0` |
| `Northstar_backend/data/enrich/costco-cogs-fill/review_queue.json` | Operator verification queue | **Review only** — reply with ASIN + price |
| `Northstar_backend/data/enrich/margin-shortlist/<stamp>/shortlist.csv` | Ranked buy list | Read only |
| `Northstar_backend/data/enrich/buying-report/<stamp>.json` | Final merged decision data | Read only |

---

## Next Live Approvals You Can Give

1. **Verify top 20 review-queue entries** → I append to CSV → free shortlist re-run
2. **Unwrangle diagnostic re-probe** (1 credit) → confirms failure class
3. **Chocodata 1-ASIN probe** (5 credits) → tests weight→fee
4. **Targeted OpenWebNinja 1-page** for highest remaining ceiling cluster
5. **Easyparser batch on top 3 ranked + 10 competitors** (fits in 41 balance)
6. **RapidAPI host probe** (1 ASIN, 1 of 6 pooled hosts)

All tools are bounded, resumable, and will stop before any cap is exceeded.