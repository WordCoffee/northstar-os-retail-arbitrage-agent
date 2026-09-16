"""Shared fixtures/factories for Golden Goose Finder tests.

Mock BreakdownEconomics objects are built from the data models defined in
breakdown_economics.py (the shared dataclass shapes the scorer, orchestrator
and report modules all consume). Factories introspect the active dataclass
fields so they keep working whether the full shared model or a slim local
fallback is on the import path.
"""

from typing import Any, Dict

import dataclasses

import pytest

from ..breakdown_economics import BreakdownEconomics, IndividualListing, WholesalePack

_WS_SUPPORTED = {f.name for f in dataclasses.fields(WholesalePack)}
_IND_SUPPORTED = {f.name for f in dataclasses.fields(IndividualListing)}
_ECON_SUPPORTED = {f.name for f in dataclasses.fields(BreakdownEconomics)}


def make_individual(**overrides: Any) -> IndividualListing:
    data: Dict[str, Any] = dict(
        asin="B09GOLDDEMO1",
        title="Kirkland Signature Laundry Detergent Pods (152 ct)",
        brand="Kirkland Signature",
        category_slug="health-household",
        amazon_price=29.99,
        bsr=3500,
        review_rating=4.7,
        review_count=1200,
        fba_sellers=1,
        monthly_sales_estimate=3000.0,
    )
    data.update(overrides)
    return IndividualListing(**{k: v for k, v in data.items() if k in _IND_SUPPORTED})


def make_wholesale(**overrides: Any) -> WholesalePack:
    data: Dict[str, Any] = dict(
        source_store="Costco",
        product_title="Kirkland Signature Laundry Detergent Pods 152 ct",
        brand="Kirkland Signature",
        category_slug="health-household",
        pack_count=152,
        wholesale_price=24.99,
    )
    data.update(overrides)
    # Older consumers used wholesale_pack_title; the shared model prefers
    # product_title. Normalize so either spelling works.
    if "wholesale_pack_title" in data:
        data.setdefault("product_title", data["wholesale_pack_title"])
    return WholesalePack(**{k: v for k, v in data.items() if k in _WS_SUPPORTED})


_IND_FIELDS = {
    "asin", "title", "brand", "category_slug", "amazon_price", "bsr",
    "review_rating", "review_count", "fba_sellers", "monthly_sales_estimate",
}
_WS_FIELDS = {
    "source_store", "product_title", "wholesale_pack_title",
    "wholesale_price", "pack_count", "brand", "category_slug",
}


def make_economics(**overrides: Any) -> BreakdownEconomics:
    """BreakdownEconomics with HIGH-scoring defaults.

    Nested overrides use dotted keys: "individual.fba_sellers",
    "wholesale.source_store". Plain field names route automatically to
    the correct sub-model or the economics object itself.
    """
    ind_data: Dict[str, Any] = {}
    ws_data: Dict[str, Any] = {}
    econ_data: Dict[str, Any] = {}
    for key, value in overrides.items():
        if key.startswith("individual."):
            ind_data[key.split(".", 1)[1]] = value
        elif key.startswith("wholesale."):
            ws_data[key.split(".", 1)[1]] = value
        elif key in _IND_FIELDS:
            ind_data[key] = value
        elif key in _WS_FIELDS:
            ws_data[key] = value
        else:
            econ_data[key] = value

    # total_costs_per_unit == breakeven, derived as price - net when both are
    # known (keeps every tiered fixture internally consistent).
    price = ind_data.get("amazon_price", 29.99)
    net = econ_data.get("net_profit_per_unit", 12.50)
    if (
        isinstance(price, (int, float)) and not isinstance(price, bool)
        and isinstance(net, (int, float)) and not isinstance(net, bool)
    ):
        default_total = round(float(price) - float(net), 2)
    else:
        default_total = None

    econ: Dict[str, Any] = dict(
        unit_cogs=0.24,
        repackaging_cost_per_unit=0.75,
        referral_fee=1.20,
        fulfillment_fee=4.75,
        inbound_cost=0.35,
        prep_cost=0.25,
        packaging_cost=0.25,
        return_reserve=0.55,
        total_amazon_fees=6.50,
        total_costs_per_unit=default_total,
        net_profit_per_unit=12.50,
        net_profit_per_costco_pack=1900.00,
        roi_per_unit=125.0,
        roi_per_costco_pack=152.0,
        profit_margin_pct=45.0,
        breakeven_amazon_price=default_total,
        economics_confidence="estimated",
        economics_notes=["Fee stack estimated from the FBA fee preview."],
    )
    econ.update(econ_data)
    econ = {k: v for k, v in econ.items() if k in _ECON_SUPPORTED}
    return BreakdownEconomics(
        wholesale=make_wholesale(**ws_data),
        individual=make_individual(**ind_data),
        **econ,
    )


# --- Opportunity profile fixtures (one per tier plus an unknown-data case) ---

_HIGH = make_economics()

_MEDIUM = make_economics(
    asin="B09MEDIUM001",
    title="Member's Mark Paper Towels (12 pk)",
    amazon_price=18.99,
    bsr=12000,
    review_rating=4.2,
    review_count=300,
    fba_sellers=3,
    monthly_sales_estimate=700.0,
    **{"wholesale.brand": "Member's Mark",
       "wholesale.category_slug": "toys-games",
       "wholesale.source_store": "Sam's Club",
       "wholesale.wholesale_pack_title": "Member's Mark Paper Towels 12 pk"},
    net_profit_per_unit=11.00,
    net_profit_per_costco_pack=88.00,
    roi_per_unit=60.0,
    roi_per_costco_pack=89.0,
    profit_margin_pct=30.0,
    total_amazon_fees=3.20,
    unit_cogs=2.10,
)

_LOW = make_economics(
    asin="B09LOWX00001",
    title="Everyday Essentials Trash Bags (200 ct)",
    amazon_price=19.99,
    bsr=65000,
    review_rating=4.0,
    review_count=90,
    fba_sellers=6,
    monthly_sales_estimate=300.0,
    **{"wholesale.brand": "Everyday Essentials",
       "wholesale.category_slug": "home-kitchen",
       "wholesale.source_store": "Costco",
       "wholesale.wholesale_pack_title": "Everyday Essentials Trash Bags 200 ct"},
    net_profit_per_unit=10.20,
    net_profit_per_costco_pack=510.00,
    roi_per_unit=72.0,
    roi_per_costco_pack=118.0,
    profit_margin_pct=20.0,
    total_amazon_fees=5.10,
    unit_cogs=1.80,
)

_REJECT = make_economics(
    asin="B09REJECT01",
    title="Budget Brand Paperback (24 ct)",
    amazon_price=9.99,
    bsr=220000,
    review_rating=3.9,
    review_count=500,
    fba_sellers=8,
    monthly_sales_estimate=25.0,
    **{"wholesale.brand": "Budget Brand",
       "wholesale.category_slug": "books",
       "wholesale.source_store": "Costco",
       "wholesale.wholesale_pack_title": "Budget Brand Paperback 24 ct"},
    net_profit_per_unit=-0.61,
    net_profit_per_costco_pack=-91.50,
    roi_per_unit=-8.0,
    roi_per_costco_pack=-7.0,
    profit_margin_pct=-6.0,
    total_amazon_fees=4.10,
    unit_cogs=6.50,
)

_UNKNOWN_DATA = make_economics(
    asin="B0UNKNOWN001",
    title="Mystery Wholesale Pack",
    amazon_price=None,
    bsr=None,
    review_rating=None,
    review_count=None,
    fba_sellers=None,
    monthly_sales_estimate=None,
    **{"wholesale.brand": "Unknown Brand",
       "wholesale.category_slug": None,
       "wholesale.source_store": None,
       "wholesale.wholesale_pack_title": None},
    unit_cogs=1.50,
    net_profit_per_unit=None,
    net_profit_per_costco_pack=None,
    roi_per_unit=None,
    roi_per_costco_pack=None,
    profit_margin_pct=None,
    total_amazon_fees=None,
    economics_confidence="unavailable",
    economics_notes=["No fee estimate available."],
)


@pytest.fixture
def ec() -> Any:
    """Factory fixture: ec(individual.fba_sellers=0, ...) -> BreakdownEconomics."""
    return make_economics


@pytest.fixture
def high() -> BreakdownEconomics:
    return _HIGH


@pytest.fixture
def medium() -> BreakdownEconomics:
    return _MEDIUM


@pytest.fixture
def low() -> BreakdownEconomics:
    return _LOW


@pytest.fixture
def reject() -> BreakdownEconomics:
    return _REJECT


@pytest.fixture
def unknown_data() -> BreakdownEconomics:
    return _UNKNOWN_DATA