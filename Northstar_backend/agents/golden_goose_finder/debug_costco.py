"""Debug raw Costco data to see what fields are available."""
import os, sys, json
from pathlib import Path

os.environ["GOLDEN_GOOSE_LIVE_OPERATOR_APPROVED"] = "1"
backend = Path(__file__).resolve().parent.parent.parent
if str(backend) not in sys.path:
    sys.path.insert(0, str(backend))

from dotenv import load_dotenv
load_dotenv()

from costco_api_client import search_page
result = search_page("vitamins", 1)
items = result.get("items", [])
print(f"Got {len(items)} items")
if items:
    print("\nFirst item raw data:")
    print(json.dumps(items[0], indent=2, default=str))
    
    # Check what parse_wholesale_product expects
    from agents.golden_goose_finder.wholesale_scanner import parse_wholesale_product
    wp = parse_wholesale_product(items[0], source_store="Costco", category_slug="vitamins_supplements")
    print(f"\nParsed result: {wp}")
    
    # Try with all items to see which ones parse
    print("\nParsing all items:")
    for i, item in enumerate(items[:5]):
        wp = parse_wholesale_product(item, source_store="Costco", category_slug="vitamins_supplements")
        if wp:
            print(f"  [{i}] OK: {wp.product_title[:50]} | ${wp.wholesale_price} | pack={wp.pack_count} | brand={wp.brand}")
        else:
            print(f"  [{i}] FAILED: {item.get('item_name', '?')[:50]}")
