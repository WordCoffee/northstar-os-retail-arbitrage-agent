# Bounded public observations: Amazon search result pages for target spices.
# Respectful fetches (small number). Public pages only.
import re, json, os, urllib.request, time

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"
QUERIES = {
  "organic ceylon cinnamon powder": "https://www.amazon.com/s?k=organic+ceylon+cinnamon+powder",
  "organic garlic powder": "https://www.amazon.com/s?k=organic+garlic+powder",
  "organic turmeric powder": "https://www.amazon.com/s?k=organic+turmeric+powder",
}
os.makedirs("docs/mogra-organics-research-2026-10-02/_raw", exist_ok=True)
allobs = {}
for q,u in QUERIES.items():
    try:
        req = urllib.request.Request(u, headers={"User-Agent": UA, "Accept-Language":"en-US,en;q=0.9"})
        html = urllib.request.urlopen(req, timeout=30).read().decode("utf-8","replace")
    except Exception as e:
        print("ERR", q, e); continue
    if re.search(r'captcha|Robot Check|automated access', html):
        print("BLOCKED", q); continue
    items = []
    # split on data-asin blocks
    blocks = re.split(r'data-asin="([A-Z0-9]{10})"', html)
    for i in range(1, len(blocks)-1, 2):
        asin = blocks[i]; b = blocks[i+1]
        mt = re.search(r'<h2[^>]*>.*?<span[^>]*>(.*?)</span>', b, re.S) or re.search(r'aria-label="([^"]{15,180})"', b)
        title = re.sub(r'<[^>]+>','',mt.group(1)).strip() if mt else ""
        mp = re.search(r'a-price-whole">([0-9,]+)', b)
        mf = re.search(r'a-price-fraction">([0-9]{2})', b)
        price = (mp.group(1).replace(",","") + "." + (mf.group(1) if mf else "00")) if mp else ""
        mr = re.search(r'([0-9.]+) out of 5 stars', b)
        mc = re.search(r'aria-label="([0-9,]+) ratings?"', b) or re.search(r's-underline-text">([0-9,]+)<', b)
        brand = title.split(",")[0].strip() if title else ""
        if title and len(title) > 12:
            items.append({"asin":asin,"title":title[:170],"brand_guess":brand[:50],
                          "price_usd":price,"rating":mr.group(1) if mr else "",
                          "ratings":mc.group(1).replace(",","") if mc else ""})
    allobs[q] = items[:24]
    print(f"{q}: {len(items)} items")
    time.sleep(2)

json.dump(allobs, open("docs/mogra-organics-research-2026-10-02/_raw/amazon_search_obs.json","w",encoding="utf-8"), indent=1)
for q,items in allobs.items():
    print("\n===", q, "===")
    for o in items[:12]:
        print(f'  ${o["price_usd"]:<7} {o["rating"]:<4} {o["ratings"]:<7} {o["title"][:88]}')
