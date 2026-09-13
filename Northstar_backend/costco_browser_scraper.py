"""Browser automation for Costco.com product detail extraction using browser-use."""
import asyncio
import json
import os
from typing import Dict, List, Optional
from browser_use import Agent, Browser
from dotenv import load_dotenv

load_dotenv()

async def fetch_costco_product_details(item_ids: List[str]) -> Dict[str, Dict]:
    """Fetch product details from Costco.com for given item IDs."""
    browser = Browser()
    results = {}
    
    for item_id in item_ids:
        url = f"https://www.costco.com/.product.{item_id}.html"
        print(f"\nFetching {url}...")
        
        agent = Agent(
            task=f"""
            Go to {url} and extract the following product details:
            1. Product title/name (exact text)
            2. Price (current price, any sale price)
            3. Pack size / quantity (e.g., "3 lbs", "400 softgels", "25 lbs", "4-pack")
            4. Unit count if mentioned (e.g., "300 tablets", "230 softgels")
            5. Weight if mentioned
            6. Any flavor/variety details
            7. Whether it's Kirkland Signature brand
            
            Return the extracted data as a JSON object.
            """,
            browser=browser,
        )
        
        try:
            result = await agent.run()
            results[item_id] = {
                "url": url,
                "extracted": result,
                "status": "success"
            }
            print(f"  Success: {result[:200]}...")
        except Exception as e:
            print(f"  Error: {e}")
            results[item_id] = {
                "url": url,
                "error": str(e),
                "status": "error"
            }
        
        # Small delay between requests
        await asyncio.sleep(2)
    
    await browser.close()
    return results

async def main():
    # Top review queue item IDs to verify
    item_ids = [
        "1292240", "1529106",  # B08PS7YJV2 - golf gloves
        "690843", "98501", "926628",  # B07CH9Y7Y8 - vitamins/fish oil
        "17767", "1217292", "4165758",  # B076ZFG1ZH - coffee
        "249375",  # B01CZ637O2 - glucosamine
        "887498",  # B07N6YF2SF - fish oil
        "52296", "1104304", "1567724",  # B07HLSQ147 - pet food
        "650377", "1140957",  # B008M2VYOE - quit gum
        "238120",  # B077LCPQ34 - B-Complex
        "71003", "692731", "1249003",  # B075D6XMYW - olive oil
        "1174112", "416076", "897980",  # B08JJV9M86 - multivitamins
        "1985100", "1905479",  # B0H9GL43LZ - pants
        "1947955", "1947952",  # B0FVWFFTYV - polos
        "1789247",  # B00U56JTPG - olive oil small
        "1992450", "1992451", "1992453",  # B0H1Z5D4LC - women's pants
        "6262016",  # B0D9B4WRQT - bath tissue
    ]
    
    print(f"Fetching details for {len(item_ids)} Costco items...")
    results = await fetch_costco_product_details(item_ids)
    
    # Save results
    os.makedirs("data/enrich/costco-cogs-fill", exist_ok=True)
    with open("data/enrich/costco-cogs-fill/browser_scrape_results.json", "w") as f:
        json.dump(results, f, indent=2)
    
    print("\n=== SUMMARY ===")
    for item_id, data in results.items():
        print(f"{item_id}: {data['status']}")

if __name__ == "__main__":
    asyncio.run(main())