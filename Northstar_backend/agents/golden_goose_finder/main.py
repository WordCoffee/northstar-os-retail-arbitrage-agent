"""Golden Goose Finder — retail-arbitrage opportunity scanner.

Discovers SMALL, LIGHT, high-value national-brand products at Costco /
Sam's Club (singles AND multi-packs) that can be resold on Amazon for
$10+ net profit per unit after all fees.

Usage:
  CLI:  python -m agents.golden_goose_finder.main [options]
  API:  POST /api/golden-goose/scan
  Mock: POST /api/golden-goose/scan-mock

Pipeline phases:
  1. DISCOVERY  — Scan wholesale catalogs for small/light products
  2. MATCHING   — Find individual / small-pack Amazon listings
  3. ECONOMICS  — Calculate full economics per unit
  4. SCORING    — Score, tier, and rank all opportunities
  5. REPORTING  — Generate reports and export data
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import traceback
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request

# ---------------------------------------------------------------------------
# Sibling module imports (graceful degradation when modules are stubs).
# Try package-relative first (the sibling modules live in this package),
# then top-level legacy paths, then built-in fallbacks.
# ---------------------------------------------------------------------------

try:
    from .category_config import get_all_categories, is_brand_allowed, parse_pack_quantity
except ImportError:
    try:
        from category_config import get_all_categories, is_brand_allowed
        parse_pack_quantity = None  # type: ignore[assignment]
    except ImportError:
        get_all_categories = None  # type: ignore[assignment]
        is_brand_allowed = lambda _name: True  # type: ignore[assignment]
        parse_pack_quantity = None  # type: ignore[assignment]

try:
    from .wholesale_scanner import (
        WholesaleProduct,
        get_mock_wholesale_data,
        scan_costco_categories,
        scan_sams_club,
    )
except ImportError:
    try:
        from wholesale_scanner import WholesaleProduct, get_mock_wholesale_data
        scan_costco_categories = None  # type: ignore[assignment]
        scan_sams_club = None  # type: ignore[assignment]
    except ImportError:
        WholesaleProduct = None  # type: ignore[assignment,misc]
        get_mock_wholesale_data = lambda **kw: []  # type: ignore[assignment]
        scan_costco_categories = None  # type: ignore[assignment]
        scan_sams_club = None  # type: ignore[assignment]

try:
    from .amazon_matcher import AmazonMatch, find_individual_listing, get_mock_amazon_matches, is_individual_listing
except ImportError:
    try:
        from amazon_matcher import AmazonMatch, find_individual_listing, get_mock_amazon_matches
        is_individual_listing = None  # type: ignore[assignment]
    except ImportError:
        AmazonMatch = None  # type: ignore[assignment,misc]
        find_individual_listing = None  # type: ignore[assignment]
        get_mock_amazon_matches = lambda _wp: []  # type: ignore[assignment]
        is_individual_listing = None  # type: ignore[assignment]

try:
    from .breakdown_economics import BreakdownEconomics, WholesalePack, calculate_breakdown_economics
except ImportError:
    try:
        from breakdown_economics import BreakdownEconomics, calculate_breakdown_economics
    except ImportError:
        BreakdownEconomics = None  # type: ignore[assignment,misc]
        calculate_breakdown_economics = lambda *a, **kw: None  # type: ignore[assignment]

try:
    from .opportunity_scorer import ScoredOpportunity, score_batch
except ImportError:
    try:
        from opportunity_scorer import ScoredOpportunity, score_batch
    except ImportError:
        ScoredOpportunity = None  # type: ignore[assignment,misc]
        score_batch = lambda *a, **kw: []  # type: ignore[assignment]

try:
    from .goose_report import (
        generate_json_report,
        save_report,
        generate_console_display,
        export_to_scout_panel,
    )
except ImportError:
    try:
        from goose_report import (
            generate_json_report,
            save_report,
            generate_console_display,
            export_to_scout_panel,
        )
    except ImportError:
        generate_json_report = lambda *a, **kw: {}  # type: ignore[assignment]
        save_report = lambda *a, **kw: ""  # type: ignore[assignment]
        generate_console_display = lambda *a: ""  # type: ignore[assignment]
        export_to_scout_panel = lambda *a: []  # type: ignore[assignment]

# ---------------------------------------------------------------------------
# Category slug bridge — category_config, wholesale_scanner, and the API use
# slightly different slug conventions. The orchestrator normalizes so a
# canonical slug (e.g. "vitamins_supplements") resolves scanner data that
# uses its own convention (e.g. "vitamins").
# ---------------------------------------------------------------------------

_SLUG_ALIASES = {
    "nicotine_cessation": "nicotine-cessation",
    "otc_health": "otc-health",
    "vitamins_supplements": "vitamins",
    "household_cleaning": "household",
    "personal_care": "personal-care",
    "snacks_bars": "snacks-bars",
    "baby_child": "baby-child",
}


def _normalize_slug(slug: str) -> str:
    """Normalize a category slug (underscores → hyphens, lowercase)."""
    if not slug:
        return ""
    return str(slug).strip().lower().replace("_", "-")


def _slug_candidates(slug: str) -> list[str]:
    """Return every known variant of a category slug, most-specific first."""
    if not slug:
        return []
    raw = str(slug)
    norm = _normalize_slug(raw)
    candidates = [raw, norm]
    alias = _SLUG_ALIASES.get(raw) or _SLUG_ALIASES.get(norm)
    if alias:
        candidates.append(alias)
    # de-duplicate, preserve order
    return list(dict.fromkeys(candidates))


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent
BACKEND_DIR = BASE_DIR.parent.parent
REPORT_DIR = BACKEND_DIR / "data" / "golden-goose-reports"

# ---------------------------------------------------------------------------
# Lightweight built-in mock data (used when sibling modules are not yet wired)
# ---------------------------------------------------------------------------

_BUILTIN_CATEGORIES = {
    "vitamins-supplements": {
        "name": "Vitamins & Supplements",
        "brand_blocklist": [],
        "pack_patterns": [r"(\d+)\s*-?\s*(?:ct|count|pack|pk|tab|capsule|softgel|gummy)s?"],
    },
    "personal-care": {
        "name": "Personal Care",
        "brand_blocklist": [],
        "pack_patterns": [r"(\d+)\s*-?\s*(?:ct|count|pack|pk|oz)s?"],
    },
    "household": {
        "name": "Household",
        "brand_blocklist": [],
        "pack_patterns": [r"(\d+)\s*-?\s*(?:ct|count|pack|pk)s?"],
    },
    "food-beverage": {
        "name": "Food & Beverage",
        "brand_blocklist": [],
        "pack_patterns": [r"(\d+)\s*-?\s*(?:ct|count|pack|pk|bag)s?"],
    },
    "electronics": {
        "name": "Electronics & Accessories",
        "brand_blocklist": [],
        "pack_patterns": [r"(\d+)\s*-?\s*(?:ct|count|pack|pk)s?"],
    },
}


@dataclass
class _MockWholesaleProduct:
    source_store: str = "Costco"
    product_title: str = ""
    brand: str = ""
    category_slug: str = ""
    pack_count: int | None = None
    wholesale_price: float = 0.0


@dataclass
class _MockAmazonMatch:
    asin: str = ""
    title: str = ""
    brand: str = ""
    amazon_price: float = 0.0
    bsr: int | None = None
    review_rating: float | None = None
    review_count: int | None = None
    fba_sellers: int | None = None
    is_prime: bool = True
    monthly_sales_estimate: int | None = None


@dataclass
class _MockBreakdownEconomics:
    wholesale_title: str = ""
    amazon_asin: str = ""
    amazon_title: str = ""
    brand: str = ""
    source_store: str = ""
    category_slug: str = ""
    pack_count: int = 1
    wholesale_price: float = 0.0
    unit_cogs: float = 0.0
    amazon_price: float = 0.0
    total_amazon_fees: float = 0.0
    net_profit_per_unit: float = 0.0
    roi_per_unit: float = 0.0
    profit_margin_pct: float = 0.0
    economics_confidence: str = "mock"
    monthly_sales_estimate: int | None = None
    fba_sellers: int | None = None


@dataclass
class _MockScoredOpportunity:
    rank: int = 0
    economics: _MockBreakdownEconomics | None = None
    composite_score: float = 0.0
    tier: str = "REJECT"
    passes_all_filters: bool = False
    scoring_notes: list[str] = field(default_factory=list)
    opportunity_tags: list[str] = field(default_factory=list)
    # New scoring fields (defaults for builtin fallback path)
    profit_score: float = 0.0
    demand_score: float = 0.0
    competition_score: float = 0.0
    listing_health_score: float = 0.0
    price_gap_score: float = 0.0
    ad_feasibility_score: float = 0.0
    ad_feasibility_breakdown: dict = field(default_factory=dict)


# Built-in mock data — realistic multi-pack breakdown scenarios
_BUILTIN_MOCK_PRODUCTS: list[_MockWholesaleProduct] = [
    _MockWholesaleProduct("Costco", "Kirkland Signature Minoxidil 5% Foam 6-Month Supply (6ct)", "Kirkland", "personal-care", 6, 34.99),
    _MockWholesaleProduct("Costco", "Nature Made Multi Complete Vitamins 500ct", "Nature Made", "vitamins-supplements", 1, 18.99),
    _MockWholesaleProduct("Sam's Club", "Member's Mark Hand Sanitizer 8-pack (16.9oz each)", "Members Mark", "household", 8, 21.47),
    _MockWholesaleProduct("Costco", "Kirkland Signature Organic K-Cups Variety Pack (120ct)", "Kirkland", "food-beverage", 120, 34.99),
    _MockWholesaleProduct("Costco", "Kirkland Signature Extra Strength Pain Reliever 500ct", "Kirkland", "vitamins-supplements", 1, 12.99),
    _MockWholesaleProduct("Sam's Club", "Equate Daily Multivitamin Gummies 250ct (4-pack)", "Equate", "vitamins-supplements", 4, 24.98),
    _MockWholesaleProduct("Costco", "Kirkland Signature Crest Pro-Health Toothpaste 8-pack", "Kirkland", "personal-care", 8, 15.99),
    _MockWholesaleProduct("Costco", "Kirkland Signature Aller-Tec Cetirizine 10mg 365ct", "Kirkland", "vitamins-supplements", 1, 14.99),
    _MockWholesaleProduct("Sam's Club", "Flonase Allergy Relief 240 Spray (2-pack)", "Flonase", "personal-care", 2, 32.98),
    _MockWholesaleProduct("Costco", "Kirkland Signature Vitamin D3 50mcg (600 softgels)", "Kirkland", "vitamins-supplements", 1, 9.99),
]

_BUILTIN_MOCK_MATCHES: list[_MockAmazonMatch] = [
    _MockAmazonMatch("B0CP6LXPLK", "Kirkland Signature Minoxidil 5% Topical Aerosol 6-Month Supply", "Kirkland", 79.99, 1820, 4.6, 12450, 8, True, 3200),
    _MockAmazonMatch("B005DK1FOI", "Nature Made Multi Complete with Iron 130 Tablets", "Nature Made", 15.87, 4521, 4.7, 8920, 12, True, 5800),
    _MockAmazonMatch("B08R68VXFR", "Member's Mark Hand Sanitizer 8 oz (Pack of 8)", "Members Mark", 29.47, 8740, 4.5, 3200, 5, True, 2100),
    _MockAmazonMatch("B0B1J8MFHV", "Kirkland Signature K-Cups Medium Roast Coffee (120ct)", "Kirkland", 44.99, 2341, 4.4, 7600, 10, True, 4200),
    _MockAmazonMatch("B004W1RY72", "Kirkland Signature Extra Strength Acetaminophen 500mg", "Kirkland", 18.49, 3210, 4.7, 5430, 7, True, 2800),
    _MockAmazonMatch("B07QDPMMGV", "Equate Adult Daily Multivitamin Gummies 250ct", "Equate", 13.24, 6800, 4.5, 4100, 9, True, 1900),
    _MockAmazonMatch("B00SG6RH2C", "Kirkland Signature Daily Care Toothpaste Fresh Mint 8-Pack", "Kirkland", 22.99, 9450, 4.3, 2800, 4, True, 1400),
    _MockAmazonMatch("B00U9Z7D4E", "Kirkland Signature Aller-Tec Cetirizine 10mg Tablets 365ct", "Kirkland", 22.99, 2100, 4.6, 9800, 6, True, 3600),
    _MockAmazonMatch("B00E9FGOGI", "Flonase Allergy Relief Nasal Spray 120 Sprays", "Flonase", 25.49, 1540, 4.7, 15600, 11, True, 8200),
    _MockAmazonMatch("B004GIPJB2", "Kirkland Signature Vitamin D3 2000 IU 600 Softgels", "Kirkland", 14.49, 3800, 4.8, 18200, 5, True, 9500),
]


def _builtin_calculate_economics(
    wholesale: _MockWholesaleProduct,
    match: _MockAmazonMatch,
) -> _MockBreakdownEconomics:
    """Calculate breakdown economics for a wholesale→Amazon pair."""
    pack_count = wholesale.pack_count or 1
    unit_cogs = wholesale.wholesale_price / pack_count

    # Amazon fee estimation (~15% referral + ~$4 FBA small/standard)
    referral_fee = match.amazon_price * 0.15
    fba_fee = 4.50 if match.amazon_price < 25 else 6.50
    total_fees = round(referral_fee + fba_fee, 2)

    net_profit = round(match.amazon_price - unit_cogs - total_fees, 2)
    roi = round((net_profit / unit_cogs * 100), 1) if unit_cogs > 0 else 0.0
    margin = round((net_profit / match.amazon_price * 100), 1) if match.amazon_price > 0 else 0.0

    return _MockBreakdownEconomics(
        wholesale_title=wholesale.product_title,
        amazon_asin=match.asin,
        amazon_title=match.title,
        brand=wholesale.brand,
        source_store=wholesale.source_store,
        category_slug=wholesale.category_slug,
        pack_count=pack_count,
        wholesale_price=wholesale.wholesale_price,
        unit_cogs=round(unit_cogs, 2),
        amazon_price=match.amazon_price,
        total_amazon_fees=total_fees,
        net_profit_per_unit=net_profit,
        roi_per_unit=roi,
        profit_margin_pct=margin,
        economics_confidence="mock",
        monthly_sales_estimate=match.monthly_sales_estimate,
        fba_sellers=match.fba_sellers,
    )


def _builtin_score_opportunity(
    econ: _MockBreakdownEconomics,
    idx: int,
    roi_floor: float = 10.0,
    min_monthly_sales: int = 1000,
) -> _MockScoredOpportunity:
    """Score a breakdown opportunity."""
    notes: list[str] = []
    tags: list[str] = []

    # Composite score components (0-100 scale)
    profit_score = min(100, max(0, econ.net_profit_per_unit * 4))  # $25 = 100
    roi_score = min(100, max(0, econ.roi_per_unit))  # 100% = 100
    pack_count = getattr(econ, "pack_count", None) or (getattr(getattr(econ, "wholesale", None), "pack_count", None) or 1)
    pack_bonus = min(30, (pack_count - 1) * 5)  # up to 30 for large packs
    confidence_bonus = 20 if econ.economics_confidence == "estimated" else 10

    composite = round((profit_score * 0.35 + roi_score * 0.30 + pack_bonus + confidence_bonus), 1)
    composite = min(100, composite)

    # Tier assignment
    if econ.net_profit_per_unit >= 10 and econ.roi_per_unit >= roi_floor:
        tier = "HIGH"
        notes.append(f"${econ.net_profit_per_unit:.2f} profit/unit exceeds ${roi_floor} floor")
        tags.append("profitable")
    elif econ.net_profit_per_unit >= 5:
        tier = "MEDIUM"
        notes.append(f"Moderate profit ${econ.net_profit_per_unit:.2f}/unit")
        tags.append("moderate")
    elif econ.net_profit_per_unit > 0:
        tier = "LOW"
        notes.append(f"Low profit ${econ.net_profit_per_unit:.2f}/unit")
    else:
        tier = "REJECT"
        notes.append("Negative profit — not viable")
        tags.append("loss-leader")

    if pack_count and pack_count >= 6:
        tags.append("high-breakdown")
    if econ.roi_per_unit >= 100:
        tags.append("triple-digit-roi")

    passes = tier in ("HIGH", "MEDIUM")

    return _MockScoredOpportunity(
        rank=idx + 1,
        economics=econ,
        composite_score=composite,
        tier=tier,
        passes_all_filters=passes,
        scoring_notes=notes,
        opportunity_tags=tags,
    )


def _builtin_score_batch(
    economics: list[_MockBreakdownEconomics],
    roi_floor: float = 10.0,
    min_monthly_sales: int = 1000,
) -> list[_MockScoredOpportunity]:
    """Score all opportunities and sort by composite score descending."""
    scored = []
    for i, econ in enumerate(economics):
        scored.append(_builtin_score_opportunity(econ, i, roi_floor, min_monthly_sales))
    scored.sort(key=lambda s: s.composite_score, reverse=True)
    for i, s in enumerate(scored):
        s.rank = i + 1
    return scored


async def _live_scan(
    categories: list[str] | None = None,
    roi_floor: float = 10.0,
    min_monthly_sales: int = 1000,
    max_results: int = 100,
) -> list:
    """Run the full live scan pipeline using real API data.

    Uses scan_costco_categories(live=True) for discovery and
    find_individual_listing(live_armed=True) for Amazon matching.
    All other phases (economics, scoring, reporting) are identical to mock.

    §3 gate: this function only executes when
    GOLDEN_GOOSE_LIVE_OPERATOR_APPROVED=1.  The gate is checked by the
    caller (run_pipeline); this function trusts that check.
    """
    # Phase 1: Discovery — scan Costco via OpenWebNinja
    # Use keyword search for better coverage; category slugs don't map well to OpenWebNinja queries
    search_keywords = categories or ["kirkland"]  # default to broad Kirkland search
    wholesale_products = await scan_costco_categories(
        keywords=search_keywords,
        live=True,
    )

    if not wholesale_products:
        return []

    # Phase 2: Matching — find Amazon individual listings via Chocodata + EasyParser
    match_pairs: list[tuple[Any, Any]] = []
    for wp in wholesale_products:
        try:
            matches = await find_individual_listing(wp, max_candidates=3, live_armed=True)
            if matches:
                match_pairs.append((wp, matches[0]))  # best match
        except Exception:
            continue

    if not match_pairs:
        return []

    # Phase 3: Economics — calculate breakdown economics
    economics: list = []
    for wp, m in match_pairs:
        try:
            # Convert WholesaleProduct → WholesalePack (different dataclasses)
            ws_pack = WholesalePack(
                source_store=wp.source_store,
                product_title=wp.product_title,
                brand=wp.brand,
                category_slug=wp.category_slug,
                pack_count=wp.pack_count or 1,
                wholesale_price=wp.wholesale_price,
            )
            econ = calculate_breakdown_economics(ws_pack, m)
            if econ is not None:
                # Propagate seller verification timestamp from match to economics
                if hasattr(m, "seller_verified_at") and m.seller_verified_at:
                    econ.individual.seller_verified_at = m.seller_verified_at
                economics.append(econ)
        except Exception:
            continue

    if not economics:
        return []

    # Phase 4: Scoring — score all opportunities
    scored = score_batch(
        economics,
        roi_floor=roi_floor,
        min_monthly_sales=min_monthly_sales,
    )

    return scored


def _mock_scan(
    categories: list[str] | None = None,
    roi_floor: float = 10.0,
    min_monthly_sales: int = 1000,
    max_results: int = 100,
) -> list:
    """Run a full mock scan pipeline.

    Uses sibling modules when available; falls back to built-in mock data.
    """
    # Phase 1: Discovery — get wholesale products
    wholesale_products = _get_mock_wholesale_products(categories)

    if not wholesale_products:
        return []

    # Phase 2: Matching — find Amazon listings for each wholesale product
    match_pairs: list[tuple[Any, Any]] = []
    try:
        if not _is_noop(get_mock_amazon_matches):
            for wp in wholesale_products:
                try:
                    matches = get_mock_amazon_matches(wp)
                except TypeError:
                    matches = get_mock_amazon_matches()
                if not matches and not _is_noop(get_mock_amazon_matches):
                    # typed fallback: last-resort built-in match by index
                    idx = min(len(match_pairs), len(_BUILTIN_MOCK_MATCHES) - 1)
                    if idx >= 0:
                        matches = [_BUILTIN_MOCK_MATCHES[idx]]
                for m in matches[:1]:  # take best match
                    match_pairs.append((wp, m))
        else:
            for i, wp in enumerate(wholesale_products):
                if i < len(_BUILTIN_MOCK_MATCHES):
                    match_pairs.append((wp, _BUILTIN_MOCK_MATCHES[i]))
    except Exception:
        for i, wp in enumerate(wholesale_products):
            if i < len(_BUILTIN_MOCK_MATCHES):
                match_pairs.append((wp, _BUILTIN_MOCK_MATCHES[i]))

    if not match_pairs:
        return []

    # Phase 3: Economics — calculate breakdown economics
    economics: list = []
    try:
        if not _is_noop(calculate_breakdown_economics):
            for wp, m in match_pairs:
                econ = calculate_breakdown_economics(wp, m)
                if econ is not None:
                    economics.append(econ)
        else:
            for wp, m in match_pairs:
                econ = _builtin_calculate_economics(wp, m)
                economics.append(econ)
    except Exception:
        for wp, m in match_pairs:
            econ = _builtin_calculate_economics(wp, m)
            economics.append(econ)

    if not economics:
        return []

    # Phase 4: Scoring — score all opportunities
    try:
        if not _is_noop(score_batch):
            scored = score_batch(economics, roi_floor=roi_floor, min_monthly_sales=min_monthly_sales)
        else:
            scored = _builtin_score_batch(economics, roi_floor, min_monthly_sales)
    except Exception:
        scored = _builtin_score_batch(economics, roi_floor, min_monthly_sales)

    # Apply max_results limit
    return scored[:max_results]


def _get_mock_wholesale_products(categories: list[str] | None = None) -> list:
    """Resolve mock wholesale products via sibling module or builtin data.

    ``get_mock_wholesale_data`` accepts a single category slug and filters
    by the wholesale_scanner slug convention; a category filter is applied
    by collecting per-category results, then a final slug containment pass.
    """
    if not _is_noop(get_mock_wholesale_data):
        try:
            if not categories:
                return list(get_mock_wholesale_data())
            products: list = []
            for cat in categories:
                for cand in _slug_candidates(cat):
                    try:
                        got = list(get_mock_wholesale_data(cand))
                    except (TypeError, KeyError):
                        got = []
                    if got:
                        products.extend(got)
                        break
            if not products:
                # Category slugs may differ from scanner slugs — fetch all
                # and filter by any known variant of the wanted slugs.
                all_p = list(get_mock_wholesale_data())
                wanted = {
                    _normalize_slug(c)
                    for cat in categories
                    for c in _slug_candidates(cat)
                    if c
                }
                products = [
                    p for p in all_p
                    if _normalize_slug(getattr(p, "category_slug", "") or "") in wanted
                ]
            return products
        except Exception:
            pass

    # Builtin fallback
    products = list(_BUILTIN_MOCK_PRODUCTS)
    if categories:
        wanted = {
            _normalize_slug(c)
            for cat in categories
            for c in _slug_candidates(cat)
            if c
        }
        products = [
            p for p in products
            if _normalize_slug(getattr(p, "category_slug", "") or "") in wanted
        ]
    return products


# ---------------------------------------------------------------------------
# Pipeline — core orchestrator logic
# ---------------------------------------------------------------------------


# Default scan timeout budget (seconds)
DEFAULT_SCAN_TIMEOUT = 300  # 5 minutes

# FIXES_50 #49: dry-run estimate constants (credit-ledger/v1 §3, no spend).
CC_SEARCH_PER_CATEGORY = 10   # goose.scan.live estimate (one search per category)
CC_ENRICH_PER_OPP = 1         # sourcescout.enrich estimate (per opportunity)
EST_SECONDS_PER_SEARCH = 2.0
EST_SECONDS_PER_OPP = 0.05
EST_OPP_CAP = 1000            # hard ceiling for the projected count


def _manifest_env_flags() -> dict[str, bool]:
    """Presence-only flags for the scan manifest — never values (B7 no-leak)."""
    import os as _os
    names = (
        "GOLDEN_GOOSE_LIVE_OPERATOR_APPROVED",
        "GOLDEN_GOOSE_LIVE_AUTH_PHRASE",
        "SCANNER_LIVE_ALLOWED",
        "COSTCO_CATALOG_DETAIL_ENABLED",
        "BRIGHTDATA_COSTCO_DETAIL_ENABLED",
        "FIRECRAWL_COSTCO_DETAIL_ENABLED",
    )
    return {n: bool(str(_os.getenv(n, "") or "").strip()) for n in names}


def _git_sha() -> str | None:
    """Best-effort HEAD sha for the scan manifest (never a live operation)."""
    import subprocess
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True, text=True, timeout=5,
        )
        if out.returncode == 0 and out.stdout.strip():
            return out.stdout.strip()[:12]
    except Exception:
        return None
    return None


def build_scan_manifest(*, categories, stores, roi_floor, min_monthly_sales,
                        max_results, use_mock, dry_run) -> dict[str, Any]:
    """FIXES_50 #23: scan manifest (inputs / provider versions / env flags /
    git SHA). No secrets, no provider values — presence-only flags."""
    return {
        "manifest_kind": "goose.scan",
        "inputs": {
            "categories": categories or "all",
            "stores": stores or None,
            "roi_floor": roi_floor,
            "min_monthly_sales": min_monthly_sales,
            "max_results": max_results,
            "use_mock": use_mock,
            "dry_run": dry_run,
        },
        "provider_versions": {"pipeline_version": "0.1.0"},
        "env_flags": _manifest_env_flags(),
        "git_sha": _git_sha(),
        "session_tool": "northstar-os-alpha",
    }


def _dry_run_estimate(categories: list[str] | None, max_results: int) -> dict[str, Any]:
    """FIXES_50 #49: credit/time/volume projection with ZERO provider calls.

    Uses the SAFE offline mock discovery routine only for a projected count;
    no economics/scoring are run and nothing is written to disk."""
    n_categories = 1 if not categories else max(1, len(categories))
    projected_opps = min(EST_OPP_CAP, max_results)
    credits = (n_categories * CC_SEARCH_PER_CATEGORY) + (projected_opps * CC_ENRICH_PER_OPP)
    seconds = round((n_categories * EST_SECONDS_PER_SEARCH) + (projected_opps * EST_SECONDS_PER_OPP), 1)
    return {
        "dry_run": True,
        "would_run_live": False,
        "estimated_credits": credits,
        "estimated_time_seconds": seconds,
        "estimated_opportunities": projected_opps,
        "categories_scanned": categories or "all",
        "note": "Estimate only — no provider call was made and no report was written.",
    }


async def run_pipeline(
    use_mock: bool = True,
    categories: list[str] | None = None,
    stores: list[str] | None = None,
    roi_floor: float = 10.0,
    min_monthly_sales: int = 1000,
    max_results: int = 100,
    scan_timeout: float = DEFAULT_SCAN_TIMEOUT,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Execute the full Golden Goose pipeline.

    Phase 1: DISCOVERY — Scan wholesale catalogs for small/light products
    Phase 2: MATCHING  — Find individual / small-pack Amazon listings
    Phase 3: ECONOMICS — Calculate full economics per unit
    Phase 4: SCORING   — Score, tier, and rank all opportunities
    Phase 5: REPORTING — Generate reports and export data

    ``dry_run=True`` (FIXES_50 #49) makes ZERO provider calls and writes NO
    report: it returns a credit/time/volume projection instead.

    Returns the full report dict.
    """
    start = time.time()

    # FIXES_50 #49: dry-run never touches a provider, never writes a report,
    # and never requires the live gate (there is no call to authorize).
    if dry_run:
        estimate = _dry_run_estimate(categories, max_results)
        report = {
            "meta": {
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "pipeline_version": "0.1.0",
                "mode": "dry-run",
                "elapsed_seconds": round(time.time() - start, 3),
                "scan_complete": True,
                "scan_timeout_seconds": scan_timeout,
                "categories_scanned": categories or "all",
                "stores_scanned": stores or ["Costco", "Sam's Club"],
                "filters": {
                    "roi_floor": roi_floor,
                    "min_monthly_sales": min_monthly_sales,
                    "max_results": max_results,
                },
                "dry_run": estimate,
                "scan_manifest": build_scan_manifest(
                    categories=categories, stores=stores, roi_floor=roi_floor,
                    min_monthly_sales=min_monthly_sales, max_results=max_results,
                    use_mock=use_mock, dry_run=True,
                ),
            },
            "summary": {"total_opportunities": 0, "high_tier_count": 0,
                        "medium_tier_count": 0, "low_tier_count": 0,
                        "reject_count": 0, "estimated_monthly_profit": 0.0,
                        "average_roi_pct": 0.0},
            "opportunities": [],
        }
        return report

    scan_deadline = start + scan_timeout

    if use_mock:
        scored = _mock_scan(
            categories=categories,
            roi_floor=roi_floor,
            min_monthly_sales=min_monthly_sales,
            max_results=max_results,
        )
    else:
        # Live path — requires §3 named operator approval
        import os as _os
        if _os.getenv("GOLDEN_GOOSE_LIVE_OPERATOR_APPROVED", "").strip() != "1":
            raise HTTPException(
                status_code=403,
                detail="Live scanning requires operator approval per §3 of the Operating Constitution.",
            )
        scored = await _live_scan(
            categories=categories,
            roi_floor=roi_floor,
            min_monthly_sales=min_monthly_sales,
            max_results=max_results,
        )

    # Build opportunity list for export
    opportunities = _scored_to_dicts(scored)

    # Check scan timeout
    scan_complete = True
    if time.time() >= scan_deadline:
        scan_complete = False
        logger.warning("[GoldenGoose] Scan timeout reached (%.1fs), returning partial results", scan_timeout)

    # Assign ranks (sorted by composite_score descending)
    opportunities.sort(key=lambda o: o.get("composite_score", 0), reverse=True)
    for i, o in enumerate(opportunities):
        o["rank"] = i + 1

    # Filter by store if specified
    if stores:
        opportunities = [
            o for o in opportunities
            if o.get("source_store", "") in stores
        ]

    # Phase 5: Reporting
    elapsed = round(time.time() - start, 3)
    high_count = sum(1 for o in opportunities if o.get("tier") == "HIGH")
    medium_count = sum(1 for o in opportunities if o.get("tier") == "MEDIUM")
    low_count = sum(1 for o in opportunities if o.get("tier") == "LOW")
    reject_count = sum(1 for o in opportunities if o.get("tier") == "REJECT")
    total_monthly_profit = sum(
        o.get("net_profit_per_unit", 0) * (o.get("monthly_sales_estimate") or 0)
        for o in opportunities
        if o.get("tier") in ("HIGH", "MEDIUM")
    )
    # Average ROI over viable (non-rejected) tiers only — REJECT rows carry
    # noise-level negative margins that would distort the headline signal.
    viable_rois = [
        o.get("roi_per_unit", 0)
        for o in opportunities
        if o.get("tier") != "REJECT" and o.get("roi_per_unit") is not None
    ]
    avg_roi = round(sum(viable_rois) / len(viable_rois), 1) if viable_rois else 0

    report = {
        "meta": {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "pipeline_version": "0.1.0",
            "mode": "mock" if use_mock else "live",
            "elapsed_seconds": elapsed,
            "scan_complete": scan_complete,
            "scan_timeout_seconds": scan_timeout,
            "categories_scanned": categories or "all",
            "stores_scanned": stores or ["Costco", "Sam's Club"],
            "filters": {
                "roi_floor": roi_floor,
                "min_monthly_sales": min_monthly_sales,
                "max_results": max_results,
            },
            "scan_manifest": build_scan_manifest(
                categories=categories, stores=stores, roi_floor=roi_floor,
                min_monthly_sales=min_monthly_sales, max_results=max_results,
                use_mock=use_mock, dry_run=False,
            ),
        },
        "summary": {
            "total_opportunities": len(opportunities),
            "high_tier_count": high_count,
            "medium_tier_count": medium_count,
            "low_tier_count": low_count,
            "reject_count": reject_count,
            "estimated_monthly_profit": round(total_monthly_profit, 2),
            "average_roi_pct": avg_roi,
        },
        "opportunities": opportunities,
    }

    # Save report to disk (atomic write) + scan manifest (FIXES_50 #23)
    try:
        REPORT_DIR.mkdir(parents=True, exist_ok=True)
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        report_path = REPORT_DIR / f"goose_scan_{ts}.json"
        # Atomic write: write to temp file then rename
        temp_path = report_path.with_suffix(".tmp")
        with open(temp_path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, default=str)
        temp_path.replace(report_path)
        report["meta"]["report_path"] = str(report_path)

        manifest_path = REPORT_DIR / f"scan_manifest_{ts}.json"
        mtmp = manifest_path.with_suffix(".tmp")
        with open(mtmp, "w", encoding="utf-8") as f:
            json.dump(report["meta"]["scan_manifest"], f, indent=2, default=str)
        mtmp.replace(manifest_path)
        report["meta"]["scan_manifest_path"] = str(manifest_path)
    except Exception as exc:
        logger.warning("[GoldenGoose] Report save failed: %s", exc)

    return report


def _scored_to_dicts(scored: list) -> list[dict[str, Any]]:
    """Convert scored opportunities to flat dicts for JSON serialization.

    Accepts both the built-in flat ``_MockBreakdownEconomics`` shape and the
    sibling ``BreakdownEconomics`` shape (nested ``wholesale``/``individual``
    objects, per the module contract).
    """
    results = []
    for s in scored:
        econ = getattr(s, "economics", None)
        if econ is None and isinstance(s, dict):
            results.append(s)
            continue
        if econ is None:
            continue

        # Nested wholesale/individual objects (sibling BreakdownEconomics)
        wholesale = getattr(econ, "wholesale", None)
        individual = getattr(econ, "individual", None)

        def _get(obj, *names, default=None):
            for name in names:
                if obj is not None and hasattr(obj, name):
                    return getattr(obj, name)
            return default

        d = {
            "rank": getattr(s, "rank", 0),
            "composite_score": getattr(s, "composite_score", 0),
            "tier": getattr(s, "tier", "REJECT"),
            "passes_all_filters": getattr(s, "passes_all_filters", False),
            "scoring_notes": getattr(s, "scoring_notes", []),
            "opportunity_tags": getattr(s, "opportunity_tags", []),
            # New scoring fields
            "profit_score": getattr(s, "profit_score", 0),
            "demand_score": getattr(s, "demand_score", 0),
            "competition_score": getattr(s, "competition_score", 0),
            "listing_health_score": getattr(s, "listing_health_score", 0),
            "price_gap_score": getattr(s, "price_gap_score", 0),
            "ad_feasibility_score": getattr(s, "ad_feasibility_score", 0),
            "ad_feasibility_breakdown": getattr(s, "ad_feasibility_breakdown", {}),
            # Economics fields (flat)
            "wholesale_title": _get(econ, "wholesale_title") or _get(wholesale, "product_title", "title", default=""),
            "product_title": _get(econ, "wholesale_title") or _get(wholesale, "product_title", "title", default=""),
            "amazon_asin": _get(econ, "amazon_asin") or _get(individual, "asin", default=""),
            "amazon_title": _get(econ, "amazon_title") or _get(individual, "title", default=""),
            "brand": _get(econ, "brand") or _get(wholesale, "brand", default=""),
            "source_store": _get(econ, "source_store") or _get(wholesale, "source_store", default=""),
            "category_slug": _get(econ, "category_slug") or _get(wholesale, "category_slug", default=""),
            "pack_count": _get(econ, "pack_count") or _get(wholesale, "pack_count", default=1) or 1,
            "wholesale_price": _get(econ, "wholesale_price") or _get(wholesale, "wholesale_price", default=0) or 0,
            "unit_cogs": _get(econ, "unit_cogs", default=0) or 0,
            "amazon_price": _get(econ, "amazon_price") or _get(individual, "amazon_price", default=0) or 0,
            "total_amazon_fees": _get(econ, "total_amazon_fees", default=0) or 0,
            "net_profit_per_unit": _get(econ, "net_profit_per_unit", default=0) or 0,
            "roi_per_unit": _get(econ, "roi_per_unit", default=0) or 0,
            "profit_margin_pct": _get(econ, "profit_margin_pct", default=0) or 0,
            "economics_confidence": _get(econ, "economics_confidence", default="mock") or "mock",
            "monthly_sales_estimate": _get(econ, "monthly_sales_estimate") or _get(individual, "monthly_sales_estimate"),
            "fba_sellers": _get(econ, "fba_sellers") or _get(individual, "fba_sellers"),
            # Seller identity fields (for audit)
            "seller_name": _get(individual, "seller_name"),
            "is_brand_seller": _get(individual, "is_brand_seller"),
            "is_amazon_seller": _get(individual, "is_amazon_seller"),
            "seller_verified_at": _get(individual, "seller_verified_at"),
            # Price gap fields
            "buy_box_price": _get(econ, "buy_box_price"),
            "undercut_headroom": _get(econ, "undercut_headroom"),
            "max_undercut_price": _get(econ, "max_undercut_price"),
            # Per-unit cost (MOQ)
            "per_unit_cost": _get(wholesale, "per_unit_cost"),
        }
        results.append(d)
    return results


# ---------------------------------------------------------------------------
# FastAPI Router
# ---------------------------------------------------------------------------

router = APIRouter(prefix="/api/golden-goose", tags=["golden-goose"])


# ---------------------------------------------------------------------------
# bff/v1 envelope + entitlement helpers for this router (B1/B7 contracts).
# ---------------------------------------------------------------------------
import secrets as _secrets
from .gg_entitlements import gg_entitlements_for_plan  # noqa: E402
from .job_model import DONE, GooseJob, new_job_id  # noqa: E402


def _bff(envelope_status: str, data=None, error=None, http_status: int = 200):
    """Uniform bff/v1 JSON response (no provider names, IDs, or paths leak)."""
    from fastapi.responses import JSONResponse
    return JSONResponse(
        {
            "contract": "bff/v1",
            "request_id": "req_" + _secrets.token_hex(16),
            "status": envelope_status,
            "data": data,
            "error": error,
            "meta": {"service": "golden_goose", "version": "v1"},
        },
        status_code=http_status,
    )


def _bff_ok(data):
    return _bff("ok", data=data)


def _bff_empty(data=None):
    return _bff("empty", data=data or {})


def _bff_err(code: str, message: str, http_status: int):
    return _bff(
        "error",
        error={"code": code, "message": message,
               "retryable": code in ("provider_unavailable", "rate_limited"),
               "details": None},
        http_status=http_status,
    )


def _strip_internal(meta: dict) -> dict:
    """Remove internal filesystem paths before serving a report's meta."""
    out = dict(meta or {})
    out.pop("report_path", None)
    out.pop("scan_manifest_path", None)
    return out


def _caller_plan(request) -> str:
    """Resolve the caller's plan from a bearer token; demo = foundation."""
    hdr = request.headers.get("authorization", "") if request else ""
    if hdr.lower().startswith("bearer "):
        try:
            import auth as _auth
            payload = _auth.decode_token(hdr[7:].strip())
            plan = payload.get("plan", "foundation")
            gg_entitlements_for_plan(plan)   # unknown plan ids raise -> fall to demo
            return plan
        except Exception:
            return "foundation"
    return "foundation"


def _category_denied_response(request, category: str):
    """Return a 403 envelope response when the plan does not entitle a GG
    category, else None (allowed)."""
    plan = _caller_plan(request)
    try:
        ent = gg_entitlements_for_plan(plan)
    except Exception:
        ent = {"categories": [], "exports": []}
    if category not in ent["categories"]:
        return _bff_err(
            "entitlement_required",
            "This plan does not entitle Golden Goose category %r." % category,
            403,
        )
    return None


def _done_job_view() -> dict:
    """An opaque, finished job view for a served report (B7 job model)."""
    from .job_model import DONE, RUNNING, GooseJob, new_job_id
    job = GooseJob(job_id=new_job_id())
    job.transition(RUNNING)
    job.transition(DONE)
    return job.public_view()


@router.post("/scan-mock")
async def scan_mock(
    categories: list[str] | None = Query(None),
    roi_floor: float = Query(10.0),
    min_monthly_sales: int = Query(1000),
    max_results: int = Query(100),
):
    """Run a scan using mock data (no live API calls). Safe for testing.

    Returns the bff/v1 envelope; internal report/scan_manifest paths are
    stripped (no-leak, B1 §6)."""
    report = await run_pipeline(
        use_mock=True,
        categories=categories,
        roi_floor=roi_floor,
        min_monthly_sales=min_monthly_sales,
        max_results=max_results,
    )
    return _bff_ok({
        "summary": report["summary"],
        "opportunities": report["opportunities"],
        "meta": _strip_internal(report["meta"]),
    })


@router.post("/scan")
async def scan_live(
    categories: list[str] | None = Query(None),
    stores: list[str] | None = Query(None),
    roi_floor: float = Query(10.0),
    min_monthly_sales: int = Query(1000),
    max_results: int = Query(100),
):
    """Run a live scan (requires §3 operator approval for each API call).

    Checks GOLDEN_GOOSE_LIVE_OPERATOR_APPROVED env var.
    """
    import os
    gate = os.environ.get("GOLDEN_GOOSE_LIVE_OPERATOR_APPROVED", "0")
    if gate != "1":
        raise HTTPException(
            status_code=403,
            detail=(
                "Live scanning requires operator approval per §3 of the Operating "
                "Constitution. Set GOLDEN_GOOSE_LIVE_OPERATOR_APPROVED=1 and restart "
                "the server. Use /scan-mock for testing."
            ),
        )
    # Gate passed — run the live scan
    start_time = __import__("time").time()
    scored = await _live_scan(
        categories=categories,
        roi_floor=roi_floor,
        min_monthly_sales=min_monthly_sales,
        max_results=max_results,
    )
    opportunities = _scored_to_dicts(scored)
    opportunities.sort(key=lambda o: o.get("composite_score", 0), reverse=True)
    for i, o in enumerate(opportunities):
        o["rank"] = i + 1
    elapsed = round(__import__("time").time() - start_time, 3)
    high = sum(1 for o in opportunities if o.get("tier") == "HIGH")
    med = sum(1 for o in opportunities if o.get("tier") == "MEDIUM")
    low = sum(1 for o in opportunities if o.get("tier") == "LOW")
    return {
        "opportunities": opportunities,
        "summary": {
            "total_opportunities": len(opportunities),
            "high_tier_count": high,
            "medium_tier_count": med,
            "low_tier_count": low,
        },
        "meta": {"mode": "live", "elapsed_seconds": elapsed},
    }


@router.get("/opportunities")
async def get_opportunities(
    request: Request,
    tier: str | None = Query(None),
    category: str | None = Query(None),
    min_profit: float | None = Query(None),
):
    """Get previously scanned and scored opportunities from latest report.

    bff/v1 envelope; category filters are gated by the caller's plan
    (B7 entitlement mapping); internal report paths are stripped; the
    response carries an opaque, finished job view (B7 job model).
    """
    if category:
        denied = _category_denied_response(request, category)
        if denied is not None:
            return denied

    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    def _mtime(p):
        try:
            return p.stat().st_mtime
        except OSError:
            return 0.0

    def _is_live(p):
        try:
            with open(p, "r", encoding="utf-8") as f:
                return json.load(f).get("meta", {}).get("mode") == "live"
        except Exception:
            return False

    report_files = sorted(
        REPORT_DIR.glob("goose_scan_*.json"), key=_mtime, reverse=True
    )
    # Prefer any live scan report over the newest mock report.
    live_reports = [p for p in report_files if _is_live(p)]
    if live_reports:
        report_files = live_reports

    if not report_files:
        return _bff_empty({
            "reason": "no_reports_yet",
            "message": "No scan reports found. Run a scan first via POST /api/golden-goose/scan-mock.",
            "next": "/api/golden-goose/scan-mock",
        })

    with open(report_files[0], "r", encoding="utf-8") as f:
        report = json.load(f)

    opps = report.get("opportunities", [])

    # Apply filters
    if tier:
        opps = [o for o in opps if o.get("tier") == tier.upper()]
    if category:
        opps = [o for o in opps if o.get("category_slug") == category]
    if min_profit is not None:
        opps = [o for o in opps if (o.get("net_profit_per_unit") or 0) >= min_profit]

    return _bff_ok({
        "items": opps,
        "summary": report.get("summary", {}),
        "report_meta": _strip_internal(report.get("meta", {})),
        "job": _done_job_view(),
    })


@router.get("/categories")
async def list_categories():
    """List all target categories with their configuration (bff/v1 envelope)."""
    try:
        if get_all_categories is not None:
            cats = get_all_categories()
            return _bff_ok({"categories": cats})
    except Exception:
        pass

    return _bff_ok({"categories": _BUILTIN_CATEGORIES})


@router.get("/dry-run")
async def dry_run_scan(
    categories: list[str] | None = Query(None),
    roi_floor: float = Query(10.0),
    min_monthly_sales: int = Query(1000),
    max_results: int = Query(100),
):
    """FIXES_50 #49: dry-run projection. Zero provider calls, no report write."""
    report = await run_pipeline(
        use_mock=True, categories=categories,
        roi_floor=roi_floor, min_monthly_sales=min_monthly_sales,
        max_results=max_results, dry_run=True,
    )
    return _bff_ok({
        "meta": _strip_internal(report["meta"]),
        "estimate": report["meta"]["dry_run"],
    })


@router.get("/entitlements")
async def gg_entitlements_route(request: Request):
    """The caller's plan -> GG categories/exports (B7 mapping, envelope-wrapped)."""
    plan = _caller_plan(request)
    try:
        ent = gg_entitlements_for_plan(plan)
    except Exception:
        ent = {"plan": plan, "categories": [], "exports": []}
    return _bff_ok(ent)


@router.get("/health")
async def health_check():
    """Health check for the Golden Goose Finder service (bff/v1 envelope)."""
    return _bff_ok({
        "status": "ok",
        "service": "golden-goose-finder",
        "version": "0.1.0",
        "modules_loaded": {
            "category_config": get_all_categories is not None,
            "wholesale_scanner": WholesaleProduct is not None,
            "amazon_matcher": AmazonMatch is not None,
            "breakdown_economics": BreakdownEconomics is not None,
            "opportunity_scorer": ScoredOpportunity is not None,
            "goose_report": generate_json_report is not None and not _is_noop(generate_json_report),
        },
        "mock_data_source": "builtin" if WholesaleProduct is None else "sibling_module",
    })


def _is_noop(fn) -> bool:
    """Check if a function is the no-op lambda fallback."""
    try:
        return fn.__name__ == "<lambda>"
    except AttributeError:
        return False


# ---------------------------------------------------------------------------
# CLI Entry Point
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="golden-goose-finder",
        description="Golden Goose Finder — Multi-pack breakdown arbitrage scanner",
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--mock", action="store_true", default=True, help="Use mock data (default)")
    mode.add_argument("--live", action="store_true", help="Live scan (requires §3 approval)")

    parser.add_argument("--categories", nargs="*", default=None, help="Filter by category slugs")
    parser.add_argument("--stores", nargs="*", default=None, help="Filter by store names")
    parser.add_argument("--roi-floor", type=float, default=10.0, help="$ minimum net profit per unit (default: $10)")
    parser.add_argument("--min-sales", type=int, default=1000, help="Minimum monthly sales (default: 1000)")
    parser.add_argument("--max-results", type=int, default=100, help="Maximum results (default: 100)")
    parser.add_argument("--output-dir", type=str, default=None, help="Report output directory")
    parser.add_argument("--json", action="store_true", help="Output raw JSON instead of table")
    parser.add_argument("--verbose", action="store_true", help="Show all candidates including REJECT tier")
    parser.add_argument("--dry-run", action="store_true",
                        help="FIXES_50 #49: estimate credits/time/volume; NO provider calls, NO report write")

    return parser


def _print_table(opportunities: list[dict], verbose: bool = False):
    """Print a formatted table of opportunities to stdout."""
    if not verbose:
        opportunities = [o for o in opportunities if o.get("tier") != "REJECT"]

    if not opportunities:
        print("\n  No opportunities found.\n")
        return

    # Header
    print(f"\n{'Rank':<5} {'ASIN':<12} {'Brand':<16} {'Product':<40} {'Source':<10} {'Pack':<5} {'COGS':<8} {'Amazon':<8} {'Profit':<8} {'ROI%':<7} {'Score':<7} {'Tier':<8}")
    print("-" * 145)

    for o in opportunities:
        title = (o.get("wholesale_title") or "")[:38]
        brand = (o.get("brand") or "")[:14]
        print(
            f"{o.get('rank', ''):<5} "
            f"{o.get('amazon_asin', ''):<12} "
            f"{brand:<16} "
            f"{title:<40} "
            f"{o.get('source_store', ''):<10} "
            f"{o.get('pack_count', ''):<5} "
            f"${o.get('unit_cogs', 0):<7.2f} "
            f"${o.get('amazon_price', 0):<7.2f} "
            f"${o.get('net_profit_per_unit', 0):<7.2f} "
            f"{o.get('roi_per_unit', 0):<6.1f}% "
            f"{o.get('composite_score', 0):<7.1f} "
            f"{o.get('tier', ''):<8}"
        )

    print()


def _safe_stdout():
    """Reconfigure stdout so emoji/UTF-8 output never crashes legacy consoles."""
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def main():
    """CLI entry point."""
    parser = _build_parser()
    args = parser.parse_args()

    if args.live:
        import os as _os
        gate = _os.getenv("GOLDEN_GOOSE_LIVE_OPERATOR_APPROVED", "").strip()
        if gate != "1":
            print("ERROR: Live scanning requires §3 operator approval.")
            print("       Set GOLDEN_GOOSE_LIVE_OPERATOR_APPROVED=1 and re-run.")
            print("       Use --mock for testing.")
            sys.exit(1)

    output_dir = Path(args.output_dir) if args.output_dir else None
    if output_dir:
        global REPORT_DIR
        REPORT_DIR = output_dir

    _safe_stdout()
    print("\n🦢 Golden Goose Finder v0.1.0")
    print("=" * 50)
    print(f"  Mode:       {'Mock (safe)' if not args.live else 'LIVE'}")
    print(f"  Categories: {', '.join(args.categories) if args.categories else 'all'}")
    print(f"  Stores:     {', '.join(args.stores) if args.stores else 'all'}")
    print(f"  Min Net/Unit: ${args.roi_floor:.2f}")
    print(f"  Min Sales:  {args.min_sales}")
    print(f"  Max:        {args.max_results}")
    print()

    import asyncio

    report = asyncio.run(
        run_pipeline(
            use_mock=not args.live,
            categories=args.categories,
            stores=args.stores,
            roi_floor=args.roi_floor,
            min_monthly_sales=args.min_sales,
            max_results=args.max_results,
            dry_run=args.dry_run,
        )
    )

    if args.json:
        print(json.dumps(report, indent=2, default=str))
    else:
        summary = report["summary"]
        if args.dry_run:
            est = report["meta"].get("dry_run", {})
            print("  DRY-RUN      (no provider call, no report written)")
            print(f"  Est Credits: {est.get('estimated_credits', 0)}")
            print(f"  Est Time:    {est.get('estimated_time_seconds', 0)}s")
            print(f"  Est Opps:    {est.get('estimated_opportunities', 0)}")
            print(f"  Categories:  {est.get('categories_scanned', 'all')}")
            print(f"  Note:        {est.get('note', '')}")
            sys.exit(0)
        print(f"  Results:    {summary['total_opportunities']} opportunities")
        print(f"  HIGH:       {summary['high_tier_count']}")
        print(f"  MEDIUM:     {summary['medium_tier_count']}")
        print(f"  LOW:        {summary['low_tier_count']}")
        print(f"  REJECT:     {summary['reject_count']}")
        print(f"  Est Monthly: ${summary['estimated_monthly_profit']:,.2f}")
        print(f"  Avg ROI:    {summary['average_roi_pct']}%")
        print(f"  Time:       {report['meta']['elapsed_seconds']}s")
        _print_table(report["opportunities"], verbose=args.verbose)

        if report["meta"].get("report_path"):
            print(f"  Report saved: {report['meta']['report_path']}")
        print()


if __name__ == "__main__":
    main()
