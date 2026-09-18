"""Test the live matching pipeline with a single product."""
import asyncio
import os
import sys
from pathlib import Path

# Set the gate BEFORE any imports
os.environ["GOLDEN_GOOSE_LIVE_OPERATOR_APPROVED"] = "1"

backend = Path(__file__).resolve().parent.parent.parent
if str(backend) not in sys.path:
    sys.path.insert(0, str(backend))

from dotenv import load_dotenv
load_dotenv()

async def test_match():
    # Step 1: Get a Costco product
    print("Step 1: Fetching Costco products...")
    from costco_api_client import search_page
    result = search_page("vitamins", 1)
    items = result.get("items", [])
    print(f"  Got {len(items)} items")
    
    if not items:
        print("  No items found. Aborting.")
        return
    
    # Step 2: Parse it
    print("\nStep 2: Parsing wholesale product...")
    from agents.golden_goose_finder.wholesale_scanner import parse_wholesale_product
    wp = parse_wholesale_product(items[0], source_store="Costco", category_slug="vitamins_supplements")
    print(f"  Title: {wp.product_title[:60]}")
    print(f"  Brand: {wp.brand}")
    print(f"  Price: ${wp.wholesale_price}")
    print(f"  Pack: {wp.pack_count}")
    print(f"  Category: {wp.category_slug}")
    print(f"  Weight: {wp.weight_lbs}")
    
    # Step 3: Try Amazon matching (live)
    print("\nStep 3: Amazon matching (live_armed=True)...")
    listing = None
    try:
        from agents.golden_goose_finder.amazon_matcher import find_individual_listing
        result = await find_individual_listing(wp, live_armed=True)
        if isinstance(result, list):
            print(f"  Got list of {len(result)} results")
            if result:
                listing = result[0]
        elif result:
            listing = result
        
        if listing:
            print(f"  Found: ASIN={listing.asin}, price=${listing.amazon_price}")
            print(f"  BSR={listing.bsr}, reviews={listing.review_count}, sellers={listing.fba_sellers}")
        else:
            print("  No listing found")
    except Exception as e:
        print(f"  Exception: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
    
    # Step 4: Try economics
    if listing and hasattr(listing, 'asin'):
        print("\nStep 4: Economics breakdown...")
        try:
            from agents.golden_goose_finder.breakdown_economics import calculate_breakdown_economics
            econ = calculate_breakdown_economics(wp, listing)
            print(f"  Net profit: ${econ.net_profit_per_unit}")
            print(f"  ROI: {econ.roi_per_unit}%")
            print(f"  Buy box: ${econ.buy_box_price}")
            print(f"  Undercut: ${econ.undercut_headroom}")
        except Exception as e:
            print(f"  Exception: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
    elif listing:
        print(f"\nStep 4: Listing is a {type(listing)} — {listing}")

asyncio.run(test_match())
