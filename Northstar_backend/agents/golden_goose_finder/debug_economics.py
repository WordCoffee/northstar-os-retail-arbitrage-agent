"""Debug economics calculation."""
import os, sys
from pathlib import Path

os.environ["GOLDEN_GOOSE_LIVE_OPERATOR_APPROVED"] = "1"
backend = Path(__file__).resolve().parent.parent.parent
if str(backend) not in sys.path:
    sys.path.insert(0, str(backend))

from dotenv import load_dotenv
load_dotenv()

# Create a simple test case
from agents.golden_goose_finder.wholesale_scanner import WholesaleProduct
from agents.golden_goose_finder.breakdown_economics import IndividualListing, WholesalePack, calculate_breakdown_economics

# Create a mock wholesale product
wp = WholesaleProduct(
    source_store="Costco",
    product_title="SmartyPants Kids Plus Multivitamin, 180 Gummies",
    brand="SmartyPants",
    category_slug="vitamins_supplements",
    pack_count=1,  # Single bottle
    wholesale_price=19.99,
)

# Create a mock individual listing
ind = IndividualListing(
    asin="B04aa84d48",
    title="SmartyPants Kids Multivitamin, 180 Count",
    brand="SmartyPants",
    category_slug="vitamins_supplements",
    amazon_price=39.98,
    bsr=3409,
    review_rating=4.6,
    review_count=1108,
    fba_sellers=0,
    monthly_sales_estimate=3000.0,
    weight_oz=None,
    seller_name="Unknown",
    is_brand_seller=False,
    is_amazon_seller=False,
)

# Wrap in WholesalePack
ws_pack = WholesalePack(
    source_store=wp.source_store,
    product_title=wp.product_title,
    brand=wp.brand,
    category_slug=wp.category_slug,
    pack_count=wp.pack_count or 1,
    wholesale_price=wp.wholesale_price,
)

econ = calculate_breakdown_economics(ws_pack, ind)
print(f"Net profit: ${econ.net_profit_per_unit}")
print(f"ROI: {econ.roi_per_unit}%")
print(f"Buy box: ${econ.buy_box_price}")
print(f"Undercut headroom: ${econ.undercut_headroom}")
print(f"Unit COGS: ${econ.unit_cogs}")
print(f"Total fees: ${econ.total_amazon_fees}")
print(f"Total costs: ${econ.total_costs_per_unit}")
print(f"Confidence: {econ.economics_confidence}")
print(f"Notes: {econ.economics_notes}")
