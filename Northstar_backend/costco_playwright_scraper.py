"""Playwright-based Costco.com product detail extraction."""
import asyncio
import json
import os
from typing import Dict, List
from playwright.async_api import async_playwright

async def fetch_costco_product_details(item_ids: List[str]) -> Dict[str, Dict]:
    """Fetch product details from Costco.com for given item IDs using Playwright."""
    results = {}
    
    async with async_playwright() as p:
        # Launch browser (headless=False for debugging, headless=True for production)
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = await context.new_page()
        
        for item_id in item_ids:
            url = f"https://www.costco.com/.product.{item_id}.html"
            print(f"\nFetching {url}...")
            
            try:
                await page.goto(url, wait_until="networkidle", timeout=30000)
                
                # Wait for content to load
                await page.wait_for_timeout(3000)
                
                # Extract product details
                data = await page.evaluate("""() => {
                    const result = {};
                    
                    // Product title
                    const titleEl = document.querySelector('h1[itemprop="name"], h1.product-name, .product-title h1');
                    result.title = titleEl ? titleEl.innerText.trim() : null;
                    
                    // Price
                    const priceEl = document.querySelector('[itemprop="price"], .price-amount, .product-price .value');
                    result.price = priceEl ? priceEl.innerText.trim() : null;
                    
                    // Sale/regular price
                    const saleEl = document.querySelector('.sale-price, .promo-price');
                    result.sale_price = saleEl ? saleEl.innerText.trim() : null;
                    
                    // Description/specs
                    const descEl = document.querySelector('[itemprop="description"], .product-description, .product-details');
                    result.description = descEl ? descEl.innerText.trim() : null;
                    
                    // All text content for pack size extraction
                    const bodyText = document.body.innerText;
                    result.body_text = bodyText.substring(0, 5000);  // First 5000 chars
                    
                    // Images
                    const imgEl = document.querySelector('[itemprop="image"], .product-image img');
                    result.image_url = imgEl ? imgEl.src : null;
                    
                    return result;
                }""")
                
                results[item_id] = {
                    "url": url,
                    "data": data,
                    "status": "success"
                }
                print(f"  Success: {data.get('title', 'N/A')[:80]}")
                print(f"  Price: {data.get('price', 'N/A')}")
                
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
        if data['status'] == 'success':
            title = data['data'].get('title', 'N/A')
            price = data['data'].get('price', 'N/A')
            print(f"{item_id}: {title[:80]} | ${price}")
        else:
            print(f"{item_id}: ERROR - {data.get('error', 'Unknown')}")

if __name__ == "__main__":
    asyncio.run(main())