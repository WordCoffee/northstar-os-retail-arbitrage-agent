# PROMO-COMPLIANCE SCAN — Phase D2

**Date:** 2026-09-20 · **Baseline:** `6b4ddb2` (D1 approved) · **Method:** offline
code/documentation audit only — **no live fetches** to any retailer/wholesaler
site (would be external network traffic), no spend. ToS posture is classified
from documented, commonly-referenced platform terms; final legal determinations
are `[LEGAL REVIEW REQUIRED]` and belong to counsel at the paid-launch gate
(consistent with the D6 handoff and `docs/legal/`).

---

## 1. Sourcing surface — per-module compliance

| Module | Method | ToS posture | Status |
|---|---|---|---|
| `supplier_discovery.py` | Discovery from public catalogs; **live fetch is §3-gated + injected transport**; default = offline seed catalog | Public-catalog discovery; search-engine/Alibaba use must respect their terms | ✅ PASS (offline default; live = gated + documented) |
| `supplier_catalog_ingestion.py` | Seed/catalog ingestion (offline) | N/A (offline) | ✅ PASS |
| `costco_playwright_scraper.py`, `costco_browser_scraper.py` | Headless/Playwright fetch of Costco.com product pages | Costco.com ToS restrict automated access without permission → **scraping risk** | ⚠️ REVIEW REQUIRED |
| `costco_api_client.py` / `adapters/open_web_ninja.py` | OpenWebNinja / Unwrangle **APIs** (credentialed) | API terms apply (license-scoped) | ✅ PASS (API-keyed) |
| `firecrawl_costco.py` / `adapters/firecrawl.py`, `adapters/scrape_do.py`, `scrapedo_amazon.py` | Paid fetch APIs for Amazon/Costco HTML | Vendor API terms; HTML returned per their ToS | ✅ PASS (API-keyed) |
| `bright_data_costco.py`, `src/scrapers/amazonSearch.js`, `bright_data_client.py` | Bright Data Web Unlocker — raw HTML of Amazon search/Costco pages | Amazon.com ToS prohibit unlicensed automated scraping; Web Unlocker vendors claim permission, but **resale of scraped Amazon data has ToS risk** | ⚠️ REVIEW REQUIRED |
| `amazon_search.py`, `canopy_client.py`, `scavio_client.py`, `rapidapi_*`, `adapters/easy_parser.py` | Credentialed product-data APIs | API terms apply | ✅ PASS (API-keyed) |
| `tasks/supplier_pipeline.py` + `Northstar_backend/data/us_suppliers.csv` | Curated supplier directory (public catalog summaries) | Public data summaries; no scraping | ✅ PASS |

**Wholesaler/retailer CSV list:** `data/us_suppliers.csv` contains **public
catalog metadata** (name, website, MOQ, rating as text). It does not embed
scraped private content and is treated as marketing/directory data — no
violation found; **[LEGAL REVIEW REQUIRED]** for any future automated access to
those sites.

**Net:** API-keyed paths = PASS; HTML-scrape paths (Costco pages via Playwright/
Web Unlocker, Amazon search pages via Web Unlocker) = **REVIEW REQUIRED** — flag
for counsel + a documented retry/rate posture (delays + circuit breaker exist)
and a "authorized access only" note in runbooks.

## 2. Legal disclaimer embed — presence check

| Surface (pricing/sourcing/resale guidance) | Disclaimer present? | Slot |
|---|---|---|
| Scout v1 results view | ✅ `table-note`/`result-note`, `calc-callout`s | `scout-results` |
| SourceScout workspace (C1) | ✅ result-note "Estimates from fixture data — not a recommendation to buy." | `sourcescout` canvas |
| Margin/Profit/Risk/Cycle tools | ✅ `calc-callout` + `result-note` (each view) | per-view |
| Golden Goose workspace (B2/C5) | ✅ callout "Not a purchase authorization" + legend | `gg-workspace` |
| AdPilot V1 pipeline (C3) | ✅ mock banner + manifest `disclaimer` (no-leak) | `adpilot` + `gg-export` |
| SocialPulse (C4) | ✅ workspace status note; drafts labeled mock | `socialpulse` |
| Command Center / Commerce Ops / Creative Studio | ✅ honest empty/pending states + shell footer | `spa-footer` |
| Auth / Landing / Onboarding / Hub | ✅ footers + onboarding slot | B6 slots |
| Exports / manifests | ✅ `goose-export/v1` `disclaimer` (B7) | `gg-export` |

**Verdict:** no pricing/sourcing/resale surface is missing a disclaimer. **No
legal-copy changes required** at this time; add `[LEGAL REVIEW REQUIRED]` only
for the scrape-path authorization statement (see §4).

## 3. Credit ledger / entitlement bypass review

- **Ledger integrity:** idempotent grants/consume (no double-charge), fail-closed
  `InsufficientCredits` (no negative balance), append-only, reservation
  expiry — covered by `test_credit_ledger.py`. No bypass found.
- **Entitlement gating:** GG categories/exports gated by plan
  (`/entitlements` + category filter 403s unentitled plans — `test_golden_goose_seam.py`);
  admin route requires `admin` role + whitelist (`test_security_boundaries.py`);
  `/scan` is 403. **No bypass path found** through Phase B/C code.
- **Deferred (flagged, not a bypass):** legacy read endpoints (`/api/kirkland/*`,
  `/api/suppliers`, `/plans`) are not plan-gated — they are read-only demo
  surfaces (foundation may read); paid-tier enforcement on those surfaces is
  Phase-C debt, tracked in D6 follow-ups. No money/purchasing path exists
  anywhere (no billing wired).

## 4. Required legal-copy changes

| # | Change | Owner |
|---|---|---|
| L1 | Add a footer/runbook line on scrape-enabled surfaces (GG/SourceScout): "Data is sourced under current provider terms; automated wholesale/retail access may require permission." → **`[LEGAL REVIEW REQUIRED]`** | Counsel at launch gate |
| L2 | Keep all existing B6 slots unchanged (no contradiction). | — |

**Overall D2 verdict: PASS** with two REVIEW-REQUIRED flags (Amazon/Costco
HTML-scrape paths, per-module table) — no compliance blocker found, no
legal-copy change required immediately.