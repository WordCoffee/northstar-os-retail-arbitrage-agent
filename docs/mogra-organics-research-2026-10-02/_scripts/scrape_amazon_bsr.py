# Bounded public observation: parse Amazon Best Sellers (Herbs, Spices & Seasonings).
# Respectful single fetch. Public page. No login, no bypass.
import re, json, os, urllib.request, csv

URL = "https://www.amazon.com/Best-Sellers-Herbs-Spices-Seasonings/zgbs/grocery/16310281"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"

req = urllib.request.Request(URL, headers={"User-Agent": UA, "Accept-Language": "en-US,en;q=0.9"})
html = urllib.request.urlopen(req, timeout=30).read().decode("utf-8", "replace")
print("fetched bytes:", len(html))

# split into rank cards
blocks = re.split(r'id="p13n-asin-index-\d+"', html)
out = []
for b in blocks[1:]:
    # rank
    mrank = re.search(r'zg-bdg-text[^>]*>\s*#?(\d+)', b)
    # title: anchor text inside the card
    mt = re.search(r'<div[^>]*class="[^"]*_cDEzb_p13n-sc-css-line-clamp[^"]*"[^>]*>(.*?)</div>', b, re.S)
    if not mt:
        mt = re.search(r'alt="([^"]{8,180})"', b)
    title = re.sub(r'<[^>]+>', '', mt.group(1)).strip() if mt else ""
    mp = re.search(r'_cDEzb_p13n-sc-price[^"]*"[^>]*>\s*\$([0-9,]+\.[0-9]{2})', b)
    price = mp.group(1).replace(",", "") if mp else ""
    mr = re.search(r'([0-9.]+)\s*out of 5 stars', b)
    rating = mr.group(1) if mr else ""
    mc = re.search(r'>([0-9,]+)</span>\s*</a>\s*</div>\s*</div>\s*</div>', b)
    reviews = mc.group(1).replace(",", "") if mc else ""
    if title:
        out.append({"rank": mrank.group(1) if mrank else "", "title": title[:160],
                    "price_usd": price, "rating": rating, "reviews": reviews})

print("parsed items:", len(out))
for o in out[:30]:
    print(f'  #{o["rank"]:<3} ${o["price_usd"]:<7} {o["rating"]:<4} {o["reviews"]:<7} {o["title"][:95]}')

os.makedirs("docs/mogra-organics-research-2026-10-02/_raw", exist_ok=True)
json.dump(out, open("docs/mogra-organics-research-2026-10-02/_raw/amazon_bsr_spices.json","w",encoding="utf-8"), indent=1)
print("saved raw observations")
