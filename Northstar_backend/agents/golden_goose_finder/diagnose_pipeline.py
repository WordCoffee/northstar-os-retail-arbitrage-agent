"""Diagnostic script to check API keys and pipeline stages."""
import os
import sys
from pathlib import Path

# Add the Northstar_backend root to path (parent of agents/)
backend = Path(__file__).resolve().parent.parent.parent
if str(backend) not in sys.path:
    sys.path.insert(0, str(backend))

# Load env
from dotenv import load_dotenv
load_dotenv()

# Stage 1: Check keys
print("=" * 60)
print("STAGE 1: API Key Check")
print("=" * 60)

keys = {
    "OPENWEBNinja_API_KEY": os.getenv("OPENWEBNinja_API_KEY"),
    "OPENWEBNINJA_API_KEY": os.getenv("OPENWEBNINJA_API_KEY"),
    "CHOCODATA_API_KEY": os.getenv("CHOCODATA_API_KEY"),
    "EASYPARSER_API_KEY": os.getenv("EASYPARSER_API_KEY"),
    "BRIGHT_DATA_KEY": os.getenv("BRIGHT_DATA_KEY"),
    "SCRAPINGDOG_API_KEY": os.getenv("SCRAPINGDOG_API_KEY"),
    "SCRAPINGBEE_API_KEY": os.getenv("SCRAPINGBEE_API_KEY"),
    "SCRAPEBADGER_API_KEY": os.getenv("SCRAPEBADGER_API_KEY"),
    "AMAZONSCRAPERAPI_KEY": os.getenv("AMAZONSCRAPERAPI_KEY"),
    "APICLAW_API_KEY": os.getenv("APICLAW_API_KEY"),
    "FIRECRAWL_API_KEY": os.getenv("FIRECRAWL_API_KEY"),
    "SCRAPE_DO_TOKEN": os.getenv("SCRAPE_DO_TOKEN"),
}

for name, val in keys.items():
    if val:
        print(f"  {name}: SET (len={len(val)})")
    else:
        print(f"  {name}: MISSING")

# Stage 2: Try Costco search
print("\n" + "=" * 60)
print("STAGE 2: Costco Search Test")
print("=" * 60)

try:
    from costco_api_client import search_page
    result = search_page("vitamins", 1)
    print(f"  success: {result.get('success')}")
    print(f"  items: {len(result.get('items', []))}")
    if result.get("error"):
        print(f"  error: {result['error']}")
    if result.get("data_gaps"):
        print(f"  data_gaps: {result['data_gaps']}")
    if result.get("items"):
        item = result["items"][0]
        print(f"  first item: {item.get('item_name', '?')[:60]}")
except Exception as e:
    print(f"  Exception: {type(e).__name__}: {e}")

# Stage 3: Try Chocodata Amazon search
print("\n" + "=" * 60)
print("STAGE 3: Chocodata Amazon Search Test")
print("=" * 60)

try:
    from agents.golden_goose_finder.amazon_adapters import ChocodataBrandAgnosticSearch
    adapter = ChocodataBrandAgnosticSearch()
    print(f"  Adapter initialized: {adapter}")
    print(f"  Has API key: {adapter._api_key is not None}")
except Exception as e:
    print(f"  Exception: {type(e).__name__}: {e}")

# Stage 4: Try EasyParser
print("\n" + "=" * 60)
print("STAGE 4: EasyParser Test")
print("=" * 60)

try:
    from agents.golden_goose_finder.amazon_adapters import EasyParserSellerRoster
    adapter = EasyParserSellerRoster()
    print(f"  Adapter initialized: {adapter}")
    print(f"  Has API key: {adapter._api_key is not None}")
except Exception as e:
    print(f"  Exception: {type(e).__name__}: {e}")

# Stage 5: Check whitelist
print("\n" + "=" * 60)
print("STAGE 5: Category Config Check")
print("=" * 60)

try:
    from agents.golden_goose_finder.category_config import (
        ALLOWED_BRANDS,
        BLOCKED_SELLERS,
        CATEGORY_WHITELIST,
    )
    print(f"  Allowed brands: {len(ALLOWED_BRANDS)}")
    print(f"  Blocked sellers: {len(BLOCKED_SELLERS)}")
    print(f"  Category whitelist: {CATEGORY_WHITELIST}")
except Exception as e:
    print(f"  Exception: {type(e).__name__}: {e}")

print("\n" + "=" * 60)
print("DIAGNOSTIC COMPLETE")
print("=" * 60)
