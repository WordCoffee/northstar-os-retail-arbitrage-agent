"""Fixture data for the Costco Non-Kirkland manual-export workflow tests.

ALL FIXTURES ARE LOCAL / NON-LIVE. Clearly labeled as mock/fixture. No real
account data, secrets, cookies, tokens, or live provider exports.
"""
from __future__ import annotations

import csv
import io
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def minutes_ago(n):
    return (datetime.now(timezone.utc) - timedelta(minutes=n)).isoformat()


def hours_ago(n):
    return (datetime.now(timezone.utc) - timedelta(hours=n)).isoformat()


# ---------------------------------------------------------------------------
# SellerAmp CSV fixture
# ---------------------------------------------------------------------------

SELLERAMP_CSV_HEADER = [
    "asin", "title", "brand", "upc", "estimated monthly sales",
    "buy box price", "seller count", "fba sellers", "mfn sellers",
    "amazon retail", "brand owner", "bsr", "bsr category",
    "shipping weight", "referral fee rate", "fba fee", "sellability",
]

SELLERAMP_CSV_ROWS = [
    {
        "asin": "B0AMPM0101",
        "title": "WETFLY Ionic Convertible Fly & Spin Combo",
        "brand": "Wetfly",
        "upc": "799488777777",
        "estimated monthly sales": "6400",
        "buy box price": "179.99",
        "seller count": "5",
        "fba sellers": "0",
        "mfn sellers": "4",
        "amazon retail": "No",
        "brand owner": "No",
        "bsr": "#901 in Sports",
        "bsr category": "Sports",
        "shipping weight": "2.1",
        "referral fee rate": "0.15",
        "fba fee": "6.90",
        "sellability": "Eligible",
    },
    {
        "asin": "B0AMPM0102",
        "title": "SafeRacks Golf Bag and Equipment Storage Rack",
        "brand": "SafeRacks",
        "upc": "799488888888",
        "estimated monthly sales": "900",
        "buy box price": "151.79",
        "seller count": "3",
        "fba sellers": "2",
        "mfn sellers": "1",
        "amazon retail": "No",
        "brand owner": "No",
        "bsr": "#3100 in Sports",
        "bsr category": "Sports",
        "shipping weight": "18.0",
        "referral fee rate": "0.15",
        "fba fee": "12.10",
        "sellability": "Eligible",
    },
]

SELLERAMP_CSV = "\n".join(
    [",".join(SELLERAMP_CSV_HEADER)] +
    [",".join(str(row[h]) for h in SELLERAMP_CSV_HEADER) for row in SELLERAMP_CSV_ROWS]
)


def write_selleramp_csv(path):
    with open(path, "w", encoding="utf-8", newline="") as fh:
        fh.write(SELLERAMP_CSV)


# ---------------------------------------------------------------------------
# SellerAmp JSON fixture
# ---------------------------------------------------------------------------

SELLERAMP_JSON = {
    "schema": "selleramp-export",
    "generated_at": now_iso(),
    "records": [
        {
            "asin": "B0AMPM0101",
            "title": "WETFLY Ionic Convertible Fly & Spin Combo",
            "brand": "Wetfly",
            "upc": "799488777777",
            "estimated_monthly_sales": 6400,
            "buy_box_price": 179.99,
            "active_seller_count": 5,
            "active_fba_seller_count": 0,
            "active_mfn_seller_count": 4,
            "amazon_retail_active": False,
            "brand_owner_seller_active": False,
            "bsr": 901,
            "bsr_category": "Sports",
            "shipping_weight_lb": 2.1,
            "referral_fee_rate": 0.15,
            "fba_fulfillment_fee": 6.90,
            "asin_sellability_status": "Eligible",
        },
        {
            "asin": "B0AMPM0102",
            "title": "SafeRacks Golf Bag and Equipment Storage Rack",
            "brand": "SafeRacks",
            "upc": "799488888888",
            "estimated_monthly_sales": 900,
            "buy_box_price": 151.79,
            "active_seller_count": 3,
            "active_fba_seller_count": 2,
            "active_mfn_seller_count": 1,
            "amazon_retail_active": False,
            "brand_owner_seller_active": False,
            "bsr": 3100,
            "bsr_category": "Sports",
            "shipping_weight_lb": 18.0,
            "referral_fee_rate": 0.15,
            "fba_fulfillment_fee": 12.10,
            "asin_sellability_status": "Eligible",
        },
    ],
}


def write_selleramp_json(path):
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(SELLERAMP_JSON, fh)


# ---------------------------------------------------------------------------
# Source product fixture (canonical costco_source_product)
# ---------------------------------------------------------------------------

def source_fixture(**kw):
    src = {
        "id": "csp_fixture_1",
        "source_name": "costco_discovery_catalog",
        "source_record_id": "2700048",
        "source_file_or_dataset": "fixture.json",
        "source_url": "https://www.costco.com/fixture.html",
        "costco_item_number": "2700048",
        "title_raw": "Dream Plush Adjustable Wedge Pillow with Cooling Cover",
        "title_normalized": "dream plush adjustable wedge pillow with cooling cover",
        "brand_raw": "Dream Plush",
        "brand_normalized": "dream plush",
        "upc": "799488123456",
        "ean": None,
        "gtin": None,
        "manufacturer_part_number": "DP-100",
        "costco_price": 24.99,
        "currency": "USD",
        "costco_pack_raw": "1 ct",
        "normalized_unit_count": 1,
        "normalized_unit_kind": "ct",
        "size_or_weight_raw": None,
        "availability_status": "in_stock",
        "warehouse_or_location": None,
        "observed_at": minutes_ago(30),
        "imported_at": now_iso(),
        "freshness_status": "fresh",
        "evidence_class": "cached_source_snapshot",
        "identity_status": "unresolved",
        "exclusion_reason": None,
        "manual_review_required": False,
        "eligible_for_costco_non_kirkland_workflow": True,
        "disallowed_classes": [],
    }
    src.update(kw)
    return src


def write_provider_manifest_csv(path, asins, **extra):
    with open(path, "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["asin", "source_sku", "title", "brand"])
        w.writeheader()
        for a in asins:
            w.writerow({"asin": a, "source_sku": "2700048", "title": extra.get("title", "Fixture"),
                        "brand": extra.get("brand", "Fixture")})


# ===========================================================================
# Legacy fixtures preserved for the existing discovery/exclusion tests
# ===========================================================================

KIRKLAND_BRAND = {
    "brand_raw": "Kirkland Signature",
    "item_name": "Kirkland Signature Paper Towels, 2-Ply, 160 Sheets, 12 Individually Wrapped Rolls",
    "costco_item_id": "512599",
    "regular_price": 23.99,
    "pack_size": "12 Pack(s)",
    "source_url": "https://www.costco.com/.product.512599.html",
}

KIRKLAND_TITLE_ONLY = {
    "brand_raw": "Costco Wholesale",
    "item_name": "Kirkland Signature Dishwasher Detergent Pacs 115 Count",
    "regular_price": 13.99,
}

NON_KIRKLAND = {
    "brand_raw": "Dream Plush",
    "item_name": "Dream Plush Adjustable Wedge Pillow with Cooling Cover",
    "regular_price": 39.99,
    "source_url": "https://www.costco.com/dream-plush-adjustable-wedge-pillow.html",
}

NON_KIRKLAND_WITH_UPC = {
    "brand_raw": "SwissGear",
    "item_name": "SWISSGEAR 8097 2-piece Set 20\"/24\" Softside Spinner",
    "regular_price": 199.99,
    "upc_or_ean": "799488123456",
    "manufacturer_part_number": "8097",
    "pack_size": "2 piece set",
}

MISSING_BRAND_KIRKLAND_HINT = {
    "brand_raw": None,
    "item_name": "Kirkland Signature Organic Olive Oil, 2 L",
    "regular_price": 18.99,
}

MISSING_BRAND_NO_HINT = {
    "brand_raw": None,
    "item_name": "Adjustable Wedge Pillow with Cooling Cover",
    "regular_price": 39.99,
}

KIRKLAND_IN_URL = {
    "brand_raw": "Some Brand",
    "item_name": "Premium Vitamin Pack",
    "source_url": "https://www.costco.com/kirkland-signature-premium-vitamin-pack.html",
    "regular_price": 24.99,
}

KIRKLAND_IN_NOTES = {
    "brand_raw": "Some Brand",
    "item_name": "Premium Vitamin Pack",
    "notes": "Comparable to Kirkland Signature premium packs.",
    "regular_price": 24.99,
}


def write_csv_fixture(records, path):
    with open(path, "w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=["item_name", "costco_cost"])
        writer.writeheader()
        for r in records:
            writer.writerow({"item_name": r.get("item_name", r.get("title_raw", "")),
                             "costco_cost": r.get("regular_price", r.get("costco_price", ""))})


def write_discovery_catalog_fixture(records, path):
    payload = {
        "catalog": "costco-discovery-catalog",
        "updated_at": "2026-09-13T00:00:00Z",
        "record_count": len(records),
        "records": records,
    }
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh)


def make_tmp_data_dir():
    import tempfile
    return Path(tempfile.mkdtemp(prefix="northstar-cnk-"))


def amazon_fixture(asin="B0TEST1234", brand="Dream Plush",
                   title="Dream Plush Adjustable Wedge Pillow with Cooling Cover",
                   upc=None, mpn=None, pack_count=1, unit_size=None, **kw):
    from costco_non_kirkland.matching import AmazonAttributes
    return AmazonAttributes(
        asin=asin, title=title, brand=brand, upc=upc,
        manufacturer_part_number=mpn, pack_count=pack_count, unit_size=unit_size, **kw)