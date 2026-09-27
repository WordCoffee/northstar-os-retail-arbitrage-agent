"""Provider export field schemas and canonical market-snapshot mapping.

PURE / OFFLINE. Defines the canonical provider market-snapshot contract and the
per-provider column/field mappings (SellerAmp). Every mapped field
is normalized into a canonical name with provenance metadata. Unavailable fields
remain `unknown` / `not_reported` — never zero or negative.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# Canonical provider market-snapshot field set (Phase 3)
# ---------------------------------------------------------------------------

CANONICAL_FIELDS: Dict[str, str] = {
    # identity
    "asin": "identity", "parent_asin": "identity", "title": "identity",
    "brand": "identity", "manufacturer": "identity", "upc": "identity",
    "ean": "identity", "mpn": "identity", "model": "identity",
    "product_type": "identity", "variation_theme": "identity",
    "selected_variation": "identity", "item_count": "identity",
    "pack_count": "identity", "unit_count": "identity", "unit_measure": "identity",
    # marketplace
    "buy_box_price": "marketplace", "lowest_price": "marketplace",
    "lowest_fba_price": "marketplace", "lowest_mfn_price": "marketplace",
    "buy_box_seller_name": "marketplace", "buy_box_fulfillment": "marketplace",
    "active_seller_count": "marketplace", "active_fba_seller_count": "marketplace",
    "active_mfn_seller_count": "marketplace", "amazon_retail_active": "marketplace",
    "amazon_retail_seller_name": "marketplace", "brand_owner_seller_active": "marketplace",
    "brand_owner_seller_name": "marketplace", "offer_count_observed_at": "marketplace",
    "price_stability": "marketplace",
    # demand
    "bsr": "demand", "bsr_category": "demand", "bsr_timestamp": "demand",
    "estimated_monthly_sales": "demand", "estimated_monthly_revenue": "demand",
    "demand_confidence": "demand",
    # fees and size
    "referral_fee_rate": "fees", "referral_fee_amount": "fees",
    "fba_fulfillment_fee": "fees", "storage_fee_estimate": "fees",
    "shipping_weight_lb": "size", "package_dimensions": "size",
    "fba_size_tier": "size", "standard_size_status": "size",
    # risk and eligibility
    "asin_sellability_status": "risk", "category_restriction_status": "risk",
    "brand_restriction_status": "risk", "product_restriction_status": "risk",
    "hazmat_status": "risk", "dangerous_goods_status": "risk",
    "meltable_status": "risk", "expiration_risk_status": "risk",
    "compliance_risk": "risk", "provider_risk_notes": "risk",
}

# Values used when a field is not available in the export.
NOT_AVAILABLE = "not_available_in_export"
NOT_REPORTED = "not_reported"
UNKNOWN = "unknown"
REQUIRES_MANUAL_REVIEW = "requires_manual_review"


# ---------------------------------------------------------------------------
# SellerAmp / Seller Assistant column mapping
# ---------------------------------------------------------------------------

SELLERAMP_CSV_COLUMNS = {
    "asin": "asin",
    "parent asin": "parent_asin",
    "title": "title",
    "product title": "title",
    "brand": "brand",
    "manufacturer": "manufacturer",
    "upc": "upc",
    "ean": "ean",
    "mpn": "mpn",
    "model": "model",
    "item count": "item_count",
    "pack count": "pack_count",
    "unit count": "unit_count",
    "unit measure": "unit_measure",
    "buy box price": "buy_box_price",
    "price": "buy_box_price",
    "buy box": "buy_box_price",
    "lowest price": "lowest_price",
    "lowest fba price": "lowest_fba_price",
    "lowest mfn price": "lowest_mfn_price",
    "buy box seller": "buy_box_seller_name",
    "buy box fulfillment": "buy_box_fulfillment",
    "total sellers": "active_seller_count",
    "seller count": "active_seller_count",
    "fba sellers": "active_fba_seller_count",
    "mfn sellers": "active_mfn_seller_count",
    "amazon retail": "amazon_retail_active",
    "amazon seller": "amazon_retail_seller_name",
    "brand owner": "brand_owner_seller_active",
    "brand owner seller": "brand_owner_seller_name",
    "estimated monthly sales": "estimated_monthly_sales",
    "est sales": "estimated_monthly_sales",
    "estimated monthly revenue": "estimated_monthly_revenue",
    "bsr": "bsr",
    "sales rank": "bsr",
    "bsr category": "bsr_category",
    "review count": "review_count",
    "reviews": "review_count",
    "rating": "rating",
    "shipping weight": "shipping_weight_lb",
    "weight": "shipping_weight_lb",
    "package dimensions": "package_dimensions",
    "fba size tier": "fba_size_tier",
    "referral fee rate": "referral_fee_rate",
    "referral fee": "referral_fee_amount",
    "fba fee": "fba_fulfillment_fee",
    "storage fee": "storage_fee_estimate",
    "sellability": "asin_sellability_status",
    "category restriction": "category_restriction_status",
    "brand restriction": "brand_restriction_status",
    "product restriction": "product_restriction_status",
    "hazmat": "hazmat_status",
    "dangerous goods": "dangerous_goods_status",
    "meltable": "meltable_status",
    "expiration risk": "expiration_risk_status",
    "compliance": "compliance_risk",
}

SELLERAMP_JSON_KEYS = {
    "asin": "asin",
    "parent_asin": "parent_asin",
    "title": "title",
    "brand": "brand",
    "manufacturer": "manufacturer",
    "upc": "upc",
    "ean": "ean",
    "mpn": "mpn",
    "model": "model",
    "item_count": "item_count",
    "pack_count": "pack_count",
    "unit_count": "unit_count",
    "unit_measure": "unit_measure",
    "buy_box_price": "buy_box_price",
    "price": "buy_box_price",
    "lowest_price": "lowest_price",
    "lowest_fba_price": "lowest_fba_price",
    "lowest_mfn_price": "lowest_mfn_price",
    "buy_box_seller_name": "buy_box_seller_name",
    "buy_box_fulfillment": "buy_box_fulfillment",
    "active_seller_count": "active_seller_count",
    "seller_count": "active_seller_count",
    "active_fba_seller_count": "active_fba_seller_count",
    "active_mfn_seller_count": "active_mfn_seller_count",
    "amazon_retail_active": "amazon_retail_active",
    "amazon_retail_seller_name": "amazon_retail_seller_name",
    "brand_owner_seller_active": "brand_owner_seller_active",
    "brand_owner_seller_name": "brand_owner_seller_name",
    "estimated_monthly_sales": "estimated_monthly_sales",
    "estimated_monthly_revenue": "estimated_monthly_revenue",
    "bsr": "bsr",
    "bsr_category": "bsr_category",
    "review_count": "review_count",
    "rating": "rating",
    "shipping_weight_lb": "shipping_weight_lb",
    "package_dimensions": "package_dimensions",
    "fba_size_tier": "fba_size_tier",
    "referral_fee_rate": "referral_fee_rate",
    "referral_fee_amount": "referral_fee_amount",
    "fba_fulfillment_fee": "fba_fulfillment_fee",
    "storage_fee_estimate": "storage_fee_estimate",
    "asin_sellability_status": "asin_sellability_status",
    "category_restriction_status": "category_restriction_status",
    "brand_restriction_status": "brand_restriction_status",
    "product_restriction_status": "product_restriction_status",
    "hazmat_status": "hazmat_status",
    "dangerous_goods_status": "dangerous_goods_status",
    "meltable_status": "meltable_status",
    "expiration_risk_status": "expiration_risk_status",
    "compliance_risk": "compliance_risk",
    "provider_risk_notes": "provider_risk_notes",
}

PROVIDER_SCHEMAS = {
    "selleramp": {"csv": SELLERAMP_CSV_COLUMNS, "json": SELLERAMP_JSON_KEYS},
}


def schema_version_for(provider: str, kind: str) -> str:
    return f"{provider}-{kind}-1"


def resolve_mapping(provider: str, kind: str, raw_key: str) -> Optional[str]:
    """Map a raw column/key to a canonical field name (case-insensitive)."""
    schemas = PROVIDER_SCHEMAS.get(provider)
    if not schemas:
        return None
    mapping = schemas.get(kind, {})
    key = str(raw_key).strip().lower()
    return mapping.get(key)