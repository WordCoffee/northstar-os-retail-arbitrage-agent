"""Northstar OS — Demo Data Seeder

Seeds the database with demo/fixture data for development and testing.
Reads the embedded demo fixtures from ``static/northstar-os/js/demo-data.js``
and populates products, keywords, campaigns, listings, and memory entries.

All seeded data is tagged as demo (``data_kind='demo'``) so the UI can
distinguish it from live data.

Usage:
    python scripts/seed_demo_data.py
    python scripts/seed_demo_data.py --reset      Drop demo data first, then re-seed
    python scripts/seed_demo_data.py --status     Show current demo data counts
    python scripts/seed_demo_data.py --quiet      Suppress verbose output

Requires: data_layer.py (Northstar_backend/)
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------

_BACKEND_DIR = Path(__file__).resolve().parent.parent
_REPO_ROOT = _BACKEND_DIR.parent

sys.path.insert(0, str(_BACKEND_DIR))
from data_layer import DataLayer, get_db, ProductsDB, KeywordsDB  # noqa: E402

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("seed_demo_data")


# ---------------------------------------------------------------------------
# Demo fixture data (embedded — no file I/O required)

# Products derived from the SourceScout demo rows in demo-data.js
# ---------------------------------------------------------------------------

DEMO_PRODUCTS: List[Dict[str, Any]] = [
    {
        "asin": "B0CP6LXPLK",
        "title": "Kirkland Signature Hair Regrowth Treatment Extra Strength for Men, "
                 "5% Minoxidil Topical Solution, 2 fl oz, 6-pack",
        "brand": "Kirkland Signature",
        "category": "Health & Wellness",
        "marketplace": "US",
        "amazon_price": 42.00,
        "costco_cost": 17.99,
        "fba_fee_estimate": 8.43,
        "net_profit": 11.53,
        "roi_pct": 64.1,
        "bsr_rank": 8432,
        "monthly_sales_estimate": 110,
        "review_count": 4821,
        "rating": 4.5,
        "seller_count": 8,
        "risk_score": 25,
        "authorization_status": "approved",
        "last_enriched_at": datetime.now(timezone.utc).isoformat(),
        "data_sources": json.dumps(["demo_fixture", "seller_offer_cache", "costco_csv"]),
        "cost_basis_source": "costco_csv",
    },
    {
        "asin": "B08B5GZXHN",
        "title": "Signature Organic Extra Virgin Olive Oil 2L (2QT 3.6 fl. oz), Set of 2",
        "brand": "Kirkland Signature",
        "category": "Food & Beverage",
        "marketplace": "US",
        "amazon_price": 27.03,
        "costco_cost": 8.99,
        "fba_fee_estimate": 6.10,
        "net_profit": 7.86,
        "roi_pct": 87.4,
        "bsr_rank": 15203,
        "monthly_sales_estimate": 40,
        "review_count": 499,
        "rating": 4.6,
        "seller_count": 3,
        "risk_score": 15,
        "authorization_status": "approved",
        "last_enriched_at": datetime.now(timezone.utc).isoformat(),
        "data_sources": json.dumps(["demo_fixture", "scored_snapshot"]),
        "cost_basis_source": "costco_csv",
    },
    {
        "asin": "B095MLHJ97",
        "title": "Kirkland Facial Towelettes 180ct",
        "brand": "Kirkland Signature",
        "category": "Health & Wellness",
        "marketplace": "US",
        "amazon_price": 14.71,
        "costco_cost": 6.99,
        "fba_fee_estimate": 4.62,
        "net_profit": 2.01,
        "roi_pct": 28.8,
        "bsr_rank": 4200,
        "monthly_sales_estimate": 220,
        "review_count": 1200,
        "rating": 4.3,
        "seller_count": 12,
        "risk_score": 45,
        "authorization_status": "needs_review",
        "last_enriched_at": datetime.now(timezone.utc).isoformat(),
        "data_sources": json.dumps(["demo_fixture"]),
        "cost_basis_source": "costco_csv",
    },
    {
        "asin": "B00MG4X4LK",
        "title": "Kirkland Ultra Clean Laundry Detergent",
        "brand": "Kirkland Signature",
        "category": "Household",
        "marketplace": "US",
        "amazon_price": 21.19,
        "costco_cost": None,
        "fba_fee_estimate": 7.02,
        "net_profit": None,
        "roi_pct": None,
        "bsr_rank": 28500,
        "monthly_sales_estimate": 95,
        "review_count": 870,
        "rating": 4.4,
        "seller_count": 5,
        "risk_score": 50,
        "authorization_status": "needs_fee_verification",
        "last_enriched_at": datetime.now(timezone.utc).isoformat(),
        "data_sources": json.dumps(["demo_fixture"]),
    },
    {
        "asin": "B0F87RXTVC",
        "title": "Word Coffee Daily Affirmation Cards for Moms — 53 Hand-Crafted Cards",
        "brand": "Word Coffee",
        "category": "Books & Stationery",
        "marketplace": "US",
        "amazon_price": 19.99,
        "costco_cost": 6.10,
        "fba_fee_estimate": 4.01,
        "net_profit": 7.52,
        "roi_pct": 45.2,
        "bsr_rank": 18500,
        "monthly_sales_estimate": 300,
        "review_count": 342,
        "rating": 4.7,
        "seller_count": 2,
        "risk_score": 10,
        "authorization_status": "approved",
        "last_enriched_at": datetime.now(timezone.utc).isoformat(),
        "data_sources": json.dumps(["demo_fixture"]),
        "cost_basis_source": "supplier",
    },
    # Additional products for broader demo coverage
    {
        "asin": "B01KHC9D6C",
        "title": "Kirkland Signature Hair Regrowth Treatment Extra Strength for Men, "
                 "5% Minoxidil Topical Solution, 2 fl oz, 6-pack",
        "brand": "Kirkland Signature",
        "category": "Health & Wellness",
        "marketplace": "US",
        "amazon_price": 39.97,
        "costco_cost": 19.79,
        "fba_fee_estimate": 8.10,
        "net_profit": 6.08,
        "roi_pct": 30.7,
        "bsr_rank": 11200,
        "monthly_sales_estimate": 85,
        "review_count": 3200,
        "rating": 4.4,
        "seller_count": 6,
        "risk_score": 30,
        "authorization_status": "approved",
        "data_sources": json.dumps(["demo_fixture", "costco_amazon_mapping"]),
    },
    {
        "asin": "B003FGTTUI",
        "title": "Kirkland Signature, Organic Extra Virgin Olive Oil, 2 L",
        "brand": "Kirkland Signature",
        "category": "Food & Beverage",
        "marketplace": "US",
        "amazon_price": 23.09,
        "costco_cost": 23.09,
        "fba_fee_estimate": 5.80,
        "net_profit": -6.45,
        "roi_pct": -27.9,
        "bsr_rank": 8900,
        "monthly_sales_estimate": 120,
        "review_count": 2100,
        "rating": 4.5,
        "seller_count": 4,
        "risk_score": 60,
        "authorization_status": "declined",
        "data_sources": json.dumps(["demo_fixture", "costco_amazon_mapping"]),
    },
    {
        "asin": "B01CZ637O2",
        "title": "Kirkland Signature Glucosamine with MSM, 375 Tablets",
        "brand": "Kirkland Signature",
        "category": "Health & Wellness",
        "marketplace": "US",
        "amazon_price": 18.49,
        "costco_cost": 9.99,
        "fba_fee_estimate": 5.20,
        "net_profit": 0.52,
        "roi_pct": 5.2,
        "bsr_rank": 22400,
        "monthly_sales_estimate": 65,
        "review_count": 780,
        "rating": 4.6,
        "seller_count": 7,
        "risk_score": 40,
        "authorization_status": "approved",
        "data_sources": json.dumps(["demo_fixture", "costco_amazon_mapping"]),
    },
]

# Keywords derived from the AdPilot demo data in demo-data.js
DEMO_KEYWORDS: List[Dict[str, Any]] = [
    {
        "keyword": "affirmation cards for women",
        "search_volume": 45200,
        "relevance_score": 0.95,
        "trend_direction": "rising",
        "competition_level": "high",
        "associated_asins": ["B0F87RXTVC"],
        "source": "demo_fixture",
    },
    {
        "keyword": "gift cards for women",
        "search_volume": 89300,
        "relevance_score": 0.88,
        "trend_direction": "stable",
        "competition_level": "high",
        "associated_asins": ["B0F87RXTVC"],
        "source": "demo_fixture",
    },
    {
        "keyword": "mom affirmation cards",
        "search_volume": 12400,
        "relevance_score": 0.92,
        "trend_direction": "rising",
        "competition_level": "medium",
        "associated_asins": ["B0F87RXTVC"],
        "source": "demo_fixture",
    },
    {
        "keyword": "kirkland minoxidil",
        "search_volume": 33100,
        "relevance_score": 0.98,
        "trend_direction": "stable",
        "competition_level": "medium",
        "associated_asins": ["B0CP6LXPLK", "B01KHC9D6C"],
        "source": "demo_fixture",
    },
    {
        "keyword": "hair regrowth treatment men",
        "search_volume": 67800,
        "relevance_score": 0.90,
        "trend_direction": "stable",
        "competition_level": "high",
        "associated_asins": ["B0CP6LXPLK", "B01KHC9D6C"],
        "source": "demo_fixture",
    },
    {
        "keyword": "organic olive oil 2l",
        "search_volume": 18900,
        "relevance_score": 0.85,
        "trend_direction": "stable",
        "competition_level": "low",
        "associated_asins": ["B08B5GZXHN", "B003FGTTUI"],
        "source": "demo_fixture",
    },
    {
        "keyword": "kirkland olive oil",
        "search_volume": 28400,
        "relevance_score": 0.93,
        "trend_direction": "stable",
        "competition_level": "medium",
        "associated_asins": ["B08B5GZXHN", "B003FGTTUI"],
        "source": "demo_fixture",
    },
    {
        "keyword": "glucosamine supplements",
        "search_volume": 52000,
        "relevance_score": 0.80,
        "trend_direction": "stable",
        "competition_level": "high",
        "associated_asins": ["B01CZ637O2"],
        "source": "demo_fixture",
    },
    {
        "keyword": "coffee beans",
        "search_volume": 245000,
        "relevance_score": 0.05,
        "trend_direction": "stable",
        "competition_level": "high",
        "associated_asins": [],
        "source": "demo_fixture",
    },
    {
        "keyword": "free printable affirmation cards",
        "search_volume": 8200,
        "relevance_score": 0.10,
        "trend_direction": "stable",
        "competition_level": "low",
        "associated_asins": [],
        "source": "demo_fixture",
    },
]

# Keyword performance records (historical tracking per keyword per ASIN)
DEMO_KEYWORD_PERFORMANCE: List[Dict[str, Any]] = [
    # affirmation cards for women — B0F87RXTVC
    {
        "keyword_text": "affirmation cards for women",
        "asin": "B0F87RXTVC",
        "organic_rank": 3,
        "sponsored_rank": 1,
        "impressions": 11333,
        "clicks": 640,
        "orders": 99,
        "spend": 412.0,
        "revenue": 1979.01,
        "acos": 27.1,
        "tier": "winners_exact",
        "movement": "promoted",
        "days_in_tier": 14,
    },
    # gift cards for women — B0F87RXTVC
    {
        "keyword_text": "gift cards for women",
        "asin": "B0F87RXTVC",
        "organic_rank": 8,
        "sponsored_rank": 2,
        "impressions": 2090,
        "clicks": 118,
        "orders": 33,
        "spend": 180.0,
        "revenue": 659.67,
        "acos": 12.4,
        "tier": "winners_exact",
        "movement": "promoted",
        "days_in_tier": 21,
    },
    # mom affirmation cards — B0F87RXTVC
    {
        "keyword_text": "mom affirmation cards",
        "asin": "B0F87RXTVC",
        "organic_rank": 12,
        "sponsored_rank": 5,
        "impressions": 1440,
        "clicks": 82,
        "orders": 7,
        "spend": 99.0,
        "revenue": 139.93,
        "acos": 41.2,
        "tier": "almost_winners",
        "movement": "no_change",
        "days_in_tier": 7,
    },
    # kirkland minoxidil — B0CP6LXPLK
    {
        "keyword_text": "kirkland minoxidil",
        "asin": "B0CP6LXPLK",
        "organic_rank": 2,
        "sponsored_rank": None,
        "impressions": 8900,
        "clicks": 520,
        "orders": 78,
        "spend": 0.0,
        "revenue": 3276.0,
        "acos": 0.0,
        "tier": "organic_hero",
        "movement": "stable",
        "days_in_tier": 45,
    },
]

# Campaigns derived from AdPilot demo data
DEMO_CAMPAIGNS: List[Dict[str, Any]] = [
    {
        "asin": "B0F87RXTVC",
        "campaign_type": "SP",
        "campaign_name": "WCF-BenchAuto",
        "status": "enabled",
        "daily_budget": 10.0,
        "targeting_type": "auto",
        "impressions": 15200,
        "clicks": 380,
        "spend": 95.0,
        "orders": 8,
        "revenue": 159.92,
        "acos": 37.5,
        "roas": 1.68,
        "bid_strategy": "dynamic_down_only",
    },
    {
        "asin": "B0F87RXTVC",
        "campaign_type": "SP",
        "campaign_name": "WCF-ScaleBroad",
        "status": "enabled",
        "daily_budget": 15.0,
        "targeting_type": "broad",
        "impressions": 8400,
        "clicks": 420,
        "spend": 126.0,
        "orders": 35,
        "revenue": 699.65,
        "acos": 18.0,
        "roas": 5.55,
        "bid_strategy": "dynamic_down_only",
    },
    {
        "asin": "B0F87RXTVC",
        "campaign_type": "SP",
        "campaign_name": "WCF-AlmostWinners",
        "status": "enabled",
        "daily_budget": 25.0,
        "targeting_type": "phrase",
        "impressions": 5600,
        "clicks": 310,
        "spend": 155.0,
        "orders": 42,
        "revenue": 839.58,
        "acos": 18.5,
        "roas": 5.42,
        "bid_strategy": "dynamic_down_only",
    },
    {
        "asin": "B0F87RXTVC",
        "campaign_type": "SP",
        "campaign_name": "WCF-WinnersExact",
        "status": "enabled",
        "daily_budget": 40.0,
        "targeting_type": "exact",
        "impressions": 13423,
        "clicks": 758,
        "spend": 592.0,
        "orders": 132,
        "revenue": 2638.68,
        "acos": 22.4,
        "roas": 4.46,
        "bid_strategy": "dynamic_down_only",
    },
]

# Listings derived from ListingForge demo data
DEMO_LISTINGS: List[Dict[str, Any]] = [
    {
        "asin": "B0F87RXTVC",
        "version": 1,
        "title": "Word Coffee Daily Affirmation Cards for Moms — 53 Hand-Crafted Cards",
        "bullet_points": json.dumps([
            "53 unique, research-backed daily affirmations designed to help moms "
            "refocus in 30 seconds",
            "Premium 350GSM soft-touch matte stock — a gift-ready, high-end "
            "tactile experience",
            "Pocket-sized 2.36 x 3.54 inches — morning ritual, purse, nightstand, "
            "or desk",
            "Analog wellness: screen-free mental reset for clarity, courage, and purpose",
            "Thoughtful gift for Mother's Day, new moms, and the overwhelm of "
            "everyday life",
        ]),
        "backend_terms": json.dumps([
            "daily affirmations for women",
            "mom affirmation cards",
            "self care gifts for moms",
            "gift for mom",
            "mental health support",
            "morning ritual",
        ]),
        "seo_score": 30.0,
        "conversion_score": 25.0,
        "compliance_score": 20.0,
        "visual_score": 10.0,
        "rufus_score": 15.0,
        "overall_score": 79.6,
        "status": "published",
    },
    {
        "asin": "B0F87JDPD4",
        "version": 1,
        "title": "Word Coffee Affirmation Cards for Women — 53 Daily Mental Wellness Cards",
        "bullet_points": json.dumps([
            "A daily jolt of inspiration — for your mind, not your mug",
            "53 hand-crafted affirmations grounded in positive psychology and "
            "neuroplasticity",
            "Premium soft-touch matte finish, gift-ready premium box",
            "Niche gift angles: career woman, chef, host, and the self-improver "
            "on your list",
        ]),
        "backend_terms": json.dumps([
            "affirmation cards for women",
            "gift cards for women",
            "career woman gift",
            "yoga gifts for women",
            "daily affirmations",
        ]),
        "seo_score": 30.0,
        "conversion_score": 25.0,
        "compliance_score": 20.0,
        "visual_score": 10.0,
        "rufus_score": 15.0,
        "overall_score": 80.1,
        "status": "published",
    },
]

# Memory entries for demo account
DEMO_MEMORIES: List[Dict[str, Any]] = [
    {
        "account_id": "t2-holdings-tyrone-johnson",
        "entry_type": "preference",
        "content": (
            "User prefers Kirkland Signature products for retail arbitrage. "
            "Focus on Health & Wellness and Household categories with "
            "net profit >= $6 and ROI >= 20%."
        ),
        "source": "demo_seed",
        "confidence": 0.95,
        "tags": json.dumps(["sourcing", "preference", "kirkland"]),
    },
    {
        "account_id": "t2-holdings-tyrone-johnson",
        "entry_type": "experience",
        "content": (
            "Kirkland Minoxidil (B0CP6LXPLK) is the highest-margin product in the "
            "portfolio at $11.53 net / 64.1% ROI. Monthly velocity ~110 units. "
            "Buy box is competitive but stable."
        ),
        "source": "demo_seed",
        "confidence": 0.92,
        "tags": json.dumps(["product", "minoxidil", "high_performer"]),
    },
    {
        "account_id": "t2-holdings-tyrone-johnson",
        "entry_type": "lesson",
        "content": (
            "Olive oil products (B08B5GZXHN, B003FGTTUI) have thin margins. "
            "The 2L organic at $8.99 cost is profitable, but the $23.09 cost "
            "variant is breakeven or negative. Always verify Costco cost before "
            "committing to an olive oil ASIN."
        ),
        "source": "demo_seed",
        "confidence": 0.88,
        "tags": json.dumps(["lesson", "olive_oil", "cost_verification"]),
    },
    {
        "account_id": "t2-holdings-tyrone-johnson",
        "entry_type": "preference",
        "content": (
            "Word Coffee affirmation cards (B0F87RXTVC) brand voice: bold, clear, "
            "premium, emotionally honest, practical, non-cheesy. "
            "Taglines: 'Fuel Your Focus', 'Grab Word Coffee, not a cup.'"
        ),
        "source": "demo_seed",
        "confidence": 0.90,
        "tags": json.dumps(["brand_voice", "word_coffee", "listing"]),
    },
    {
        "account_id": "t2-holdings-tyrone-johnson",
        "entry_type": "experience",
        "content": (
            "AdPilot tier system: Tier 1 Bench Auto ($10/day) for discovery, "
            "Tier 2 Scale Broad ($15/day), Tier 3 Almost Winners ($25/day) "
            "for 1-14 sales, Tier 4 Winners Exact ($40/day) for 15+ sales. "
            "Negative keywords: coffee beans, free printable affirmation cards."
        ),
        "source": "demo_seed",
        "confidence": 0.93,
        "tags": json.dumps(["adpilot", "tiers", "campaign_strategy"]),
    },
]


# ---------------------------------------------------------------------------
# Seed logic
# ---------------------------------------------------------------------------

class DemoDataSeeder:
    """Seeds the database with demo fixtures.

    Attributes:
        db: Database layer.
        quiet: Suppress verbose output.
    """

    def __init__(self, db: Optional[DataLayer] = None, quiet: bool = False):
        self.db = db or get_db()
        self.quiet = quiet
        self._products_db = ProductsDB(self.db)
        self._keywords_db = KeywordsDB(self.db)

    def seed_all(self) -> Dict[str, int]:
        """Seed all demo data. Returns counts per table."""
        counts: Dict[str, int] = {}
        counts["products"] = self._seed_products()
        counts["keywords"] = self._seed_keywords()
        counts["keyword_performance"] = self._seed_keyword_performance()
        counts["campaigns"] = self._seed_campaigns()
        counts["listings"] = self._seed_listings()
        counts["memories"] = self._seed_memories()

        # Log to audit
        try:
            from data_layer import AuditDB
            AuditDB(self.db).log(
                action="demo_data_seeded",
                entity_type="system",
                details=counts,
            )
        except Exception:
            pass

        return counts

    def remove_demo_data(self) -> Dict[str, int]:
        """Remove all data tagged as demo fixtures."""
        counts: Dict[str, int] = {}

        # Products with demo_fixture in data_sources
        cur = self.db.execute(
            "SELECT COUNT(*) as cnt FROM products "
            "WHERE data_sources LIKE '%demo_fixture%'"
        )
        counts["products_removed"] = cur.fetchone()["cnt"]
        self.db.execute(
            "DELETE FROM products WHERE data_sources LIKE '%demo_fixture%'"
        )

        # Keywords from demo
        cur = self.db.execute(
            "SELECT COUNT(*) as cnt FROM keywords WHERE source = 'demo_fixture'"
        )
        counts["keywords_removed"] = cur.fetchone()["cnt"]
        self.db.execute("DELETE FROM keywords WHERE source = 'demo_fixture'")

        # Keyword performance linked to demo keywords
        self.db.execute(
            """DELETE FROM keyword_performance
               WHERE keyword_id IN (
                   SELECT id FROM keywords WHERE source = 'demo_fixture'
               )"""
        )

        # Campaigns for demo ASINs (with demo-specific names)
        demo_asins = [p["asin"] for p in DEMO_PRODUCTS]
        for asin in demo_asins:
            self.db.execute("DELETE FROM campaigns WHERE asin = ?", (asin,))
        counts["campaigns_removed"] = len(demo_asins)

        # Listings for demo ASINs
        for asin in demo_asins:
            self.db.execute("DELETE FROM listings WHERE asin = ?", (asin,))
        counts["listings_removed"] = len(demo_asins)

        # Memory entries for demo account
        cur = self.db.execute(
            "SELECT COUNT(*) as cnt FROM memory_entries "
            "WHERE source = 'demo_seed'"
        )
        counts["memories_removed"] = cur.fetchone()["cnt"]
        self.db.execute(
            "DELETE FROM memory_entries WHERE source = 'demo_seed'"
        )

        self.db.commit()
        return counts

    def get_status(self) -> Dict[str, int]:
        """Get current demo data counts."""
        status: Dict[str, int] = {}

        cur = self.db.execute(
            "SELECT COUNT(*) as cnt FROM products "
            "WHERE data_sources LIKE '%demo_fixture%'"
        )
        status["demo_products"] = cur.fetchone()["cnt"]

        cur = self.db.execute(
            "SELECT COUNT(*) as cnt FROM keywords WHERE source = 'demo_fixture'"
        )
        status["demo_keywords"] = cur.fetchone()["cnt"]

        cur = self.db.execute(
            "SELECT COUNT(*) as cnt FROM memory_entries WHERE source = 'demo_seed'"
        )
        status["demo_memories"] = cur.fetchone()["cnt"]

        # Total counts
        for table in ("products", "keywords", "listings", "campaigns",
                       "memory_entries", "keyword_performance"):
            cur = self.db.execute(f"SELECT COUNT(*) as cnt FROM {table}")
            status[f"total_{table}"] = cur.fetchone()["cnt"]

        return status

    # --- Private seed methods ---

    def _seed_products(self) -> int:
        """Seed demo products into the products table."""
        count = 0
        for product in DEMO_PRODUCTS:
            try:
                data = dict(product)
                data.setdefault("created_at", datetime.now(timezone.utc).isoformat())
                data["updated_at"] = datetime.now(timezone.utc).isoformat()
                self._products_db.upsert(data)
                count += 1
                if not self.quiet:
                    log.info(f"  Seeded product: {data['asin']} - {data['title'][:50]}...")
            except Exception as exc:
                log.error(f"  Failed to seed product {product.get('asin')}: {exc}")
        return count

    def _seed_keywords(self) -> int:
        """Seed demo keywords."""
        count = 0
        for kw in DEMO_KEYWORDS:
            try:
                self._keywords_db.upsert(dict(kw))
                count += 1
                if not self.quiet:
                    log.info(f"  Seeded keyword: '{kw['keyword']}' (sv={kw.get('search_volume')})")
            except Exception as exc:
                log.error(f"  Failed to seed keyword '{kw['keyword']}': {exc}")
        return count

    def _seed_keyword_performance(self) -> int:
        """Seed keyword performance records (historical tracking)."""
        count = 0
        now = datetime.now(timezone.utc).isoformat()

        for perf in DEMO_KEYWORD_PERFORMANCE:
            try:
                # Look up the keyword_id
                kw_text = perf["keyword_text"]
                asin = perf["asin"]

                cur = self.db.execute(
                    "SELECT id FROM keywords WHERE keyword = ?", (kw_text,)
                )
                row = cur.fetchone()
                if not row:
                    log.warning(f"  Keyword not found for perf record: '{kw_text}'")
                    continue

                keyword_id = row["id"]
                perf_id = str(uuid.uuid4())

                self.db.execute(
                    """INSERT OR REPLACE INTO keyword_performance
                       (id, keyword_id, asin, organic_rank, sponsored_rank,
                        impressions, clicks, orders, spend, revenue, acos,
                        tier, movement, days_in_tier, recorded_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        perf_id,
                        keyword_id,
                        asin,
                        perf.get("organic_rank"),
                        perf.get("sponsored_rank"),
                        perf.get("impressions", 0),
                        perf.get("clicks", 0),
                        perf.get("orders", 0),
                        perf.get("spend", 0.0),
                        perf.get("revenue", 0.0),
                        perf.get("acos"),
                        perf.get("tier", "bench"),
                        perf.get("movement", "no_change"),
                        perf.get("days_in_tier", 0),
                        now,
                    ),
                )
                count += 1
                if not self.quiet:
                    log.info(
                        f"  Seeded keyword_perf: '{kw_text}' / {asin} "
                        f"(organic={perf.get('organic_rank')})"
                    )
            except Exception as exc:
                log.error(f"  Failed to seed keyword_perf: {exc}")

        self.db.commit()
        return count

    def _seed_campaigns(self) -> int:
        """Seed demo campaigns."""
        count = 0
        for campaign in DEMO_CAMPAIGNS:
            try:
                data = dict(campaign)
                cid = str(uuid.uuid4())
                data["id"] = cid
                now = datetime.now(timezone.utc).isoformat()
                data["created_at"] = now
                data["updated_at"] = now

                columns = list(data.keys())
                placeholders = ", ".join(["?"] * len(columns))
                col_names = ", ".join(columns)

                self.db.execute(
                    f"INSERT OR REPLACE INTO campaigns ({col_names}) "
                    f"VALUES ({placeholders})",
                    tuple(data.values()),
                )
                count += 1
                if not self.quiet:
                    log.info(
                        f"  Seeded campaign: {data['campaign_name']} "
                        f"(asin={data['asin']}, acos={data.get('acos')})"
                    )
            except Exception as exc:
                log.error(f"  Failed to seed campaign: {exc}")

        self.db.commit()
        return count

    def _seed_listings(self) -> int:
        """Seed demo listings."""
        count = 0
        for listing in DEMO_LISTINGS:
            try:
                data = dict(listing)
                lid = str(uuid.uuid4())
                data["id"] = lid
                now = datetime.now(timezone.utc).isoformat()
                data["created_at"] = now
                data["updated_at"] = now

                columns = list(data.keys())
                placeholders = ", ".join(["?"] * len(columns))
                col_names = ", ".join(columns)

                self.db.execute(
                    f"INSERT OR REPLACE INTO listings ({col_names}) "
                    f"VALUES ({placeholders})",
                    tuple(data.values()),
                )
                count += 1
                if not self.quiet:
                    log.info(
                        f"  Seeded listing: v{data['version']} for {data['asin']} "
                        f"(score={data.get('overall_score')})"
                    )
            except Exception as exc:
                log.error(f"  Failed to seed listing: {exc}")

        self.db.commit()
        return count

    def _seed_memories(self) -> int:
        """Seed demo memory entries."""
        count = 0
        for memory in DEMO_MEMORIES:
            try:
                data = dict(memory)
                eid = str(uuid.uuid4())
                data["id"] = eid
                now = datetime.now(timezone.utc).isoformat()
                data["created_at"] = now
                data["updated_at"] = now

                columns = list(data.keys())
                placeholders = ", ".join(["?"] * len(columns))
                col_names = ", ".join(columns)

                self.db.execute(
                    f"INSERT OR REPLACE INTO memory_entries ({col_names}) "
                    f"VALUES ({placeholders})",
                    tuple(data.values()),
                )
                count += 1
                if not self.quiet:
                    log.info(
                        f"  Seeded memory: {data['entry_type']} - "
                        f"{data['content'][:60]}..."
                    )
            except Exception as exc:
                log.error(f"  Failed to seed memory: {exc}")

        self.db.commit()
        return count


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    """CLI entry point for demo data seeding."""
    parser = argparse.ArgumentParser(
        description="Northstar OS — Demo Data Seeder",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/seed_demo_data.py              Seed demo data (idempotent)
  python scripts/seed_demo_data.py --reset      Remove old demo data, then re-seed
  python scripts/seed_demo_data.py --status     Show demo data counts
  python scripts/seed_demo_data.py --quiet      Suppress verbose output
        """,
    )

    parser.add_argument(
        "--reset", action="store_true",
        help="Remove existing demo data before seeding",
    )
    parser.add_argument(
        "--status", action="store_true",
        help="Show current demo data counts",
    )
    parser.add_argument(
        "--quiet", "-q", action="store_true",
        help="Suppress verbose output",
    )

    args = parser.parse_args()

    if args.quiet:
        logging.getLogger().setLevel(logging.WARNING)

    seeder = DemoDataSeeder(quiet=args.quiet)

    if args.status:
        status = seeder.get_status()
        print("\n" + "=" * 50)
        print("DEMO DATA STATUS")
        print("=" * 50)
        for key, value in status.items():
            print(f"  {key:30s} {value}")
        print("=" * 50)
        return

    if args.reset:
        log.info("Removing existing demo data...")
        removed = seeder.remove_demo_data()
        log.info(f"Removed: {removed}")

    log.info("Seeding demo data...")
    counts = seeder.seed_all()

    print("\n" + "=" * 50)
    print("DEMO DATA SEEDED")
    print("=" * 50)
    total = 0
    for table, count in counts.items():
        print(f"  {table:30s} {count}")
        total += count
    print(f"  {'TOTAL':30s} {total}")
    print("=" * 50)


if __name__ == "__main__":
    main()
