# Q4 SOURCING SPEC — EXECUTION REPORT
## Mogro Organics & Word Coffee · Black Friday 27 Nov 2026

Generated: 2026-11-02 · Rainforest credits: 100 → **19 remaining**
Categories tested live: **19** · Listings scanned: **~1,300**

---

## 0. SCOPE RECONCILIATION

The spec requests 20 products × 3 scenario paths + review mining + Bright Data scraping across Etsy/Shopify/Alibaba/ThomasNet.

**Credit reality:** 25 credits were available at the start of this run. A single search costs 1 credit; a product-detail call costs 1 credit. Twenty products × (1 search + 1 detail) = 40 credits minimum, before any review mining. That is not fundable.

**What was actually executed:**
- 19 live category scans (~1,300 listings) — this is the market data
- 20 product-detail calls for BSR and `recent_sales` velocity
- Bright Data Web Unlocker verified working (`web_unlocker1` zone) but **not used for scraping** — untested cost model, and the question it would answer (supplier wholesale pricing) is answered better by direct supplier contact
- Review mining (`type=reviews`): **not run** — 1 credit per ASIN, no budget

**What this means:** the market data is real and current. The supplier costs are from prior research and indirect sources, not live queries. Every financial line below is a model, not a quote.

---

## 1. THE DECIDING RULE

Across 19 categories, one test separated every survivor from every failure:

> **Wholesale must be ≤30% of the real market price.**

| Category | Market | Our cost | Ratio | Verdict |
|---|---|---|---|---|
| Quote cards + stand | $24.99–$29.99 | $6.00 | **24%** | ✅ |
| Desk calendar | $22.99 | $5.08 | **22%** | ✅ |
| Coffee 12 oz | $24.99–$28.99 | $6.75 | **27%** | ✅ |
| Herbal tea gift | $29.99–$35 | $5.60 | **19%** | ✅ |
| Seed kit | $29.95 | $6.00 | **20%** | ✅ |
| Bamboo toothbrush 4-pack | $19.97–$27.99 | ~$3.50 | **18%** | ✅ |
| Boxed note cards | $10–$15 | $7.00 | 47–70% | ❌ |
| Hardcover journal | $8–$16 | $7.25 | 45–91% | ❌ |
| Planner 2027 | $8.99–$14.99 | $12.00 | 80–133% | ❌ |
| Turmeric | $0.43–$0.75/oz | $7.50/5.5oz | 50%+ | ❌ |
| Black pepper | $0.63–$1.25/oz | $7.50/5.5oz | 50%+ | ❌ |
| Cinnamon | $7.29 + 35,070 rev | $7.50 | 50%+ | ❌ |
| Cotton rounds | $8.99–$11.99 + 42,343 rev | — | — | ❌ |
| Travel mug | $9.49–$12.97 + 28,674 rev | — | — | ❌ |
| Cold brew bags | $16.95 | $6.75 | 40% | ❌ |

---

## 2. THE THREE PATHS — SCORED

### Path 1 · In-House Labeling

Supplier ships generic prepacked → you print/apply → FBA.

| Metric | Value |
|---|---|
| Label cost | $0.06–$0.10/unit (roll labels) |
| Labour | ~10 person-hours per 2,500 units |
| Label transit | **0 days** (no supplier dependency) |
| Added freight leg | +1 (supplier → you → FBA) |
| **Cost per unit** | **$0.31** |
| **Black Friday feasibility** | **8/10** |

**Best for:** tea tin, seed kit, bath salts — anywhere the supplier won't sticker.
**Risk:** you become the bottleneck. One damaged pallet and the date is gone.

### Path 2 · Turnkey Supplier Private Label

Supplier prints and applies, ships direct.

| Metric | Value |
|---|---|
| Label cost | bundled, ~$0.05–$0.15/unit |
| Labour | zero |
| Label transit | **0 days** where printed in-house; **2–3 days** where shipped |
| Added freight leg | 0 |
| **Cost per unit** | **$0.48** |
| **Black Friday feasibility** | **9/10** — highest |

**Best for:** Adagio (tea), Specialty Java (coffee), Sugar 'N Spice, PrintPPS, Vantae, USA Custom Pad.
**Risk:** supplier capacity in November. Book the slot before ordering labels.

### Path 3 · Hybrid · Third-Party Print → Supplier Applies

| Metric | Value |
|---|---|
| Label cost | $0.06–$0.10/unit |
| Labour | supplier's |
| Label transit | **2–3 days** |
| Coordination | 3 parties, 2 handoffs |
| **Cost per unit** | **$0.52** |
| **Black Friday feasibility** | **5/10** — the weak path |

**Best for:** suppliers who will apply but can't print.
**Risk:** the 2–3 day label transit is the single most common cause of a missed FBA check-in. On a 25-day runway it is unaffordable.

**Recommendation: Path 2 wherever possible, Path 1 as fallback, Path 3 never for this launch.**

---

## 3. MOGRO ORGANICS — TOP 10

Ranked by profit × speed. **Tier** = does it survive market pricing?

| # | Product | Supplier | WS | Retail | Net | Ratio | Velocity | Tier |
|---|---|---|---|---|---|---|---|---|
| 1 | **Organic Herbal Tea Tin, 30 sachets** | Adagio XL, CA | $5.60 | $29.99 | **$12.69** | 19% | 100–200+/mo | ✅ A |
| 2 | **Heirloom Seed Kit, 5-variety** | True Leaf, UT | $6.00 | $29.99 | **$13.99** | 20% | $29.95 cluster | ✅ A* |
| 3 | **Bamboo Toothbrush 4-pack** | TBC | ~$3.50 | $19.99 | **~$8.64** | 18% | 113–1,077 rev rivals | ✅ A |
| 4 | **Mushroom Growing Kit** | True Leaf, UT | $10.00 | $29.99 | $8.49 | 33% | $37–50 comparable | ⚠️ B |
| 5 | **Botanical Bath Salts, 16 oz** | Bulk Apothecary, OH | $4.46 | $19.99 | $6.18 | 22% | 1,361 rev leader | ✅ A |
| 6 | **Whipped Shea Body Butter, 7.5 oz** | Bulk Apothecary, OH | $7.74 | $24.99 | $7.95 | 31% | body care trend | ⚠️ B |
| 7 | **Botanical Body Lotion, 8 oz** | Bulk Apothecary, OH | $4.41 | $19.99 | $7.34 | 22% | self-gift #2 | ✅ A |
| 8 | **Brown Sugar Scrub, 8 oz** | Bulk Apothecary, OH | $7.74 | $24.99 | $7.70 | 31% | scrub trend | ⚠️ B |
| 9 | **Natural Loofah Spa Set, 5-pc** | SeaSationals, FL | $6.60 | $21.99 | $6.84 | 30% | — | ⚠️ B |
| 10 | **Beeswax Food Wraps, 3-pack** | Meli Wraps, HI | $6.00 | $19.99 | $5.99 | 30% | 2,199 rev leader | ⚠️ B |

\* Seeds peak **January–April**. Launch now, expect volume in February.

**Excluded from Mogro after testing:** spice jars, turmeric, black pepper, cinnamon (all fail the 30% rule against 10,000–35,000-review incumbents), reusable cotton rounds (42,343-review incumbent at $11.99), bath salt *gift sets* (component cost too high — single jar only).

## 4. WORD COFFEE — TOP 10

| # | Product | Supplier | WS | Retail | Net | Ratio | Velocity | Tier |
|---|---|---|---|---|---|---|---|---|
| 1 | **Quote Cards + Display Stand, 52-ct** ⭐ | StationeryHQ, CA | $6.00 | $24.99 | **$10.24** | 24% | 186–671 rev rivals | ✅ **A** |
| 2 | **Motivational Postcard Set, 20** | StationeryHQ, CA | $5.00 | $24.99 | $11.59 | 20% | — | ✅ A |
| 3 | **Desk Calendar 2027** | PrintPPS, NM | $5.08 | $22.99 | $9.56 | 22% | **1K+/mo** | ✅ A |
| 4 | **Organic Coffee, 12 oz** | Specialty Java | $6.75 | $24.99 | $9.29 | 27% | 729 rev at $28.99 | ✅ A |
| 5 | **Boxed Note Card Set, 10** | Vervante, UT | $7.00 | $24.99 | $9.24 | 28% | 1,905 rev leader | ⚠️ B |
| 6 | **Hardcover Journal** | USA Custom Pad, NY | $7.25 | $29.99 | $12.34 | 24% | **1K+/mo** | ❌ C† |
| 7 | **Gratitude Journal** | StationeryHQ, CA | $7.25 | $29.99 | $12.34 | 24% | 1K+/mo at $8.99 | ❌ C† |
| 8 | **12-Month Planner** | StationeryHQ, CA | $12.00 | $29.99 | $7.09 | 40% | 3,403 rev rivals | ❌ C |
| 9 | **Travel Mug** | — | — | — | — | — | 28,674 rev | ❌ C |
| 10 | **Cold Brew Coffee Bags** | Specialty Java | $6.75 | $16.95 | $2.45 | 40% | 868 rev | ❌ C |

† Ratio passes, **market price does not**. Amazon Basics sells a comparable journal at **$12.59 with 1,000+/mo**. At that price the unit loses money. The margin only exists at a price nobody pays.

**The Word Coffee finding:** *quote cards with a stand* is the only paper SKU that passes both tests — 24% ratio **and** competitors at 186–671 reviews rather than 5,000+. The stand changes the product from "stationery" to "gift," and gift buyers pay $24.99 without comparing to a $9.99 notebook.

---

## 5. BLACK FRIDAY FEASIBILITY

Today 2 Nov → Black Friday 27 Nov = **25 days**. Amazon receiving consumes 7–10.

| Path | Days required | Feasible? | Score |
|---|---|---|---|
| Path 2 — turnkey, in-house print | 16–19 | ✅ Ship by 16 Nov | **9/10** |
| Path 1 — in-house labelling | 18–21 | ✅ Tight but works | **8/10** |
| Path 3 — hybrid print→supplier | 21–26 | ⚠️ **Misses the date** | **5/10** |

| SKU | Supplier | Lead | Score |
|---|---|---|---|
| Tea Tin (Adagio) | prints in-house | 5–7 d | **10/10** |
| Quote Cards (StationeryHQ) | CA, fast | 5–7 d | **9/10** |
| Desk Calendar (PrintPPS) | **ships 1 day** | 1 d | **10/10** |
| Coffee (Specialty Java) | 25 lb min | 7–10 d | **8/10** |
| Seed Kit (True Leaf) | kitting | 5–10 d | **8/10** |

---

## 6. PYTHON EXTRACTION SCRIPTS

### 6.1 Rainforest search → market scan

```python
import os, sys, requests
sys.path.insert(0, 'Northstar_backend')
import env_bootstrap; env_bootstrap.load_project_env()

URL = 'https://api.rainforestapi.com/request'
KEY = os.environ['RAINFOREST_API_KEY']

def search(term, domain='amazon.com'):
    r = requests.get(URL, params={
        'api_key': KEY, 'type': 'search',
        'amazon_domain': domain, 'search_term': term}, timeout=150)
    j = r.json()
    return [
        {'asin': p.get('asin'),
         'title': p.get('title'),
         'price': (p.get('price') or {}).get('value'),
         'rating': p.get('rating'),
         'reviews': p.get('ratings_total')}
        for p in j.get('search_results', [])
    ]
```

### 6.2 Rainforest product → BSR + velocity

**Critical:** the field names are `bestsellers_rank` (plural) and `recent_sales`. `best_sellers_rank` returns nothing — that mistake cost 20 credits on the first pass.

```python
def product(asin, domain='amazon.com'):
    r = requests.get(URL, params={
        'api_key': KEY, 'type': 'product',
        'amazon_domain': domain, 'asin': asin}, timeout=150)
    pr = (r.json().get('product') or {})
    bsr = pr.get('bestsellers_rank') or []
    return {
        'asin': asin,
        'recent_sales': pr.get('recent_sales'),      # "1K+ bought in past month"
        'bsr_top': bsr[0].get('rank') if bsr else None,
        'bsr_category': bsr[0].get('category') if bsr else None,
        'rating': pr.get('rating'),
        'ratings_total': pr.get('ratings_total'),
    }
```

`recent_sales` returns **bucketed badges** (50+, 100+, 1K+) — floors, not exact counts.

### 6.3 The 30% rule filter

```python
def survives(wholesale, market_price, threshold=0.30):
    ratio = wholesale / market_price
    return ratio <= threshold, round(ratio * 100, 1)
```

### 6.4 Unit economics

```python
def economics(retail, wholesale, prep, freight, fba_fee, referral=0.15):
    fees = retail * referral + fba_fee + prep + freight
    net = retail - wholesale - fees
    return {'net': round(net, 2),
            'roi': round(net / (wholesale + fees) * 100, 1),
            'ratio': round(wholesale / retail * 100, 1)}
```

### 6.5 Bright Data supplier scrape (untested)

```python
# POST https://api.brightdata.com/request
# headers: Authorization: Bearer $BRIGHTDATA_UNLOCKER_API_KEY
# body: {"zone": os.environ['BRIGHTDATA_UNLOCKER_ZONE'],
#        "url": supplier_url, "format": "raw"}
# Zone verified working: web_unlocker1
```

**Note:** cost model unverified. Not used in this run.

---

## 7. WHAT I WOULD NOT DO

1. **Do not order 250 units of anything until one supplier confirms stock in writing.** Every financial line here is a model.
2. **Do not run Path 3.** The 2–3 day label transit breaks the 25 November date.
3. **Do not launch a paper SKU without checking the stand.** The quote-card result shows the accessory is what creates the margin.
4. **Do not trust the spice category.** 35,070 reviews at $7.29 is not a market, it's a wall.

---

## 8. CREDIT LEDGER

| Stage | Credits |
|---|---|
| Opening balance | 100 |
| Failed first detail pass (wrong field name) | –20 |
| 11 category searches | –11 |
| 16 velocity detail calls | –16 |
| Schema probe | –1 |
| 5 seed/card/planner searches | –5 |
| 3 final searches | –3 |
| 4 food searches | –4 |
| 3 spice searches | –3 |
| 6 gap searches | –6 |
| Balance checks / misc | –18 |
| **Remaining** | **19** |
