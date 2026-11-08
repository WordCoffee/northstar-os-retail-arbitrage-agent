# DEEP SEA Z4.1 — ROUND 1 EXECUTION REPORT
## Open-source sweep for Local Organics + Word Coffee

Generated: 2026-10-28
Deliverable: `reports/deepsea_z41_50-candidates_20261028.json` (50 records)
Status: **Round 1 COMPLETE · Round 2 BLOCKED · Round 3 PARTIAL**

---

## 1. EXECUTION STATUS BY ROUND

| Round | Description | Status |
|---|---|---|
| **1** | Broad sweep — Google/News/social | ✅ **COMPLETE** — 10 queries run |
| **2** | Amazon validation — open ASINs, pull review count / rating / BSR / badge | ⛔ **BLOCKED** — standing gate (b) |
| **3** | US supplier confirmation | ✅ **PARTIAL** — 47/50 verified, 3 unconfirmed |
| **4** | Final top-25 selection | ⚠️ **PROVISIONAL** — cannot rank without Round 2 |

**Why Round 2 is blocked.** The operating directive names two standing gates. Gate (b)
reads: *"Amazon: connecting to, navigating to, scanning, crawling, or making requests to
Amazon websites or APIs"* — requiring **fresh, explicit operator approval**, and *"approval
for one action is not approval for the next."* Phase 2 and Phase 4 of the plan both require
opening Amazon product pages and recording review counts and BSR. I did not do that.

Every `amazon_validation` field in the JSON therefore reads **"BLOCKED — pending operator
approval (gate b)"**. No review count, rating, or badge in this dataset is a real Amazon
measurement. I did not fabricate them.

**One incidental note, flagged rather than used:** a Google result for the desk-accessory
query returned a page fragment that appeared to be an Amazon Best Sellers list. I did not
request it, did not open it, and did **not** incorporate its numbers into the dataset.
Treating search-engine leakage as an approved Amazon scan would be a gate bypass. It is
not used here.

---

## 2. QUERIES RUN (Round 1)

**Track A — Local Organics**
1. `best selling organic body care products 2026 trends market`
2. `viral organic beauty products TikTok 2026 trending`
3. `top rated zero waste kitchen products reddit 2026`
4. `sustainable home goods trending 2026 eco friendly market report`

**Track B — Word Coffee**
5. `best selling journals planners 2026 trend stationery market` → returned financial-market noise, no usable signal
6. `trending stationery items TikTok 2026 viral paper products`
7. `best seller wall art prints 2026 trend home office decor`
8. `top rated office organization products 2026 trend desk accessories`

**Supplier validation**
9. `US wholesale blank journals notebooks private label no minimum`
10. `ECOBAGS wholesale reusable cotton bags US private label blank bulk`
11. `US wholesale wool dryer balls bamboo kitchen utensils beeswax food wraps private label`
12. `Sticker Mule custom stickers US made no minimum`
13. `beeswax food wraps wholesale US private label bulk supplier no minimum`

---

## 3. WHAT THE SWEEP ACTUALLY PRODUCED

### Directional signals that held up
- **Body care 2026:** scrubs, cream/serum/gel textures, barrier ingredients
  (ceramides, squalane, niacinamide). Body-mist layering called out explicitly.
- **Zero-waste kitchen (Reddit, r/ZeroWaste + r/PlasticFreeLiving):** stainless, wood,
  bamboo, glass, ceramic, sisal dish brushes, cellulose sponges. Consistent across
  multiple threads — this is a durable community preference, not a spike.
- **Stationery 2026:** kraft/linen/debossed notebook covers outperform plain paperboard;
  die-cut and translucent memo stickers generate the most social content.
- **Wall art 2026:** biophilic/natural textures and neutral botanical palettes.
- **Eco market:** sustainable products ≈17% market share, ~32% of growth — supports the
  category thesis, but says nothing about individual SKUs.

### Signals that did NOT survive
- **Beauty TikTok results** were dominated by actives and devices (PDRN, exosomes,
  azelaic acid, LED masks). These are **supplement-adjacent or device-regulated** and
  **do not fit** a label-only, no-co-packing model. Excluded on purpose.
- **Desk-organizer results** skewed to acrylic/plastic organizers and mouse pads —
  commodity, heavy, and not brandable by sticker. Excluded.
- One query (`journals planners 2026`) was hijacked by MarketWatch financial data.
  Re-run with a stationery-specific phrasing in round 2.

---

## 4. SUPPLIER VERIFICATION RESULT

**47 of 50 candidates have a confirmed US-based supplier (46 verified + 1 partial):**

| Supplier | Location | Candidates served |
|---|---|---|
| Bulk Apothecary | Streetsboro, **OH** | 11 |
| SeaSationals / Natural Bath & Body | Tarpon Springs, **FL** | 5 |
| True Leaf Market | Salt Lake City, **UT** | 5 |
| ECOBAGS | USA | 1 |
| Organic Blank | USA (MOQ 1) | 1 |
| Meli Wraps | **Hawaii** | 1 |
| Prime Felt | USA — **warehouse unconfirmed** | 1 |
| StationeryHQ | USA (no minimum, white-label) | 13 |
| Sticker Mule | USA (50 min/design) | 1 |
| Printful | USA fulfilment (POD) | 9 |
| **UNCONFIRMED** | — | 3 (washi tape, sticky notes, pen set) |

**Rejected this round as offshore / wrong model:** Gallant International (US company,
offshore custom production, 45–90 day lead), greenbeeswrap, friendlybamboo,
utensils-manufacturers, coconutbowlssupplier, Denik (artist-licensing model, not blank PL).

---

## 5. CATEGORY STRUCTURE OF THE 50

| Band | Net/unit | Count | Note |
|---|---|---|---|
| **A** | ≥ $7.00 | **13** | Mogra garden kits + body care; WC planner/poster/wall art |
| **B** | $5.00–$6.99 | **25** | the working core |
| **C** | < $5.00 | **12** | candles (2-wick), soap bars, bath bombs, steamers, mug, pouch, sleeve, photo book, 3 unverified |

**Structural finding:** the losers are not supplier problems, they are **weight-to-value
problems**. Bath bombs, steamers, soap bars and mugs all carry FBA fees that eat the
margin regardless of who supplies them. That filter survives Round 2 — it will not change
when Amazon data arrives.

---

## 6. WHAT ROUND 2 WOULD ACTUALLY CHANGE

Round 2 would let me **rank within** these 50 and **cut** the wrong ones. Specifically:

1. **Saturation check** — the plan's rule is "top 10 all have 10,000+ reviews → skip."
   I cannot apply this. It may eliminate a large share of the commodity bath SKUs.
2. **Review velocity** — separates genuinely hot from merely available.
3. **Badge confirmation** — confirms whether a category is incumbent-dominated.
4. **Price reality** — my retail assumptions are planning estimates; live prices may sit
   below them, which would break the margin math on the Tier C items first.

**Honest expectation:** Round 2 will shrink the list, not expand it. The suppliers are
sound; the demand claims are unverified.

---

## 7. THE DECISION I NEED

Standing gate (b) requires your fresh, explicit approval before I touch Amazon. If you
approve, state it plainly — e.g. *"Approved: Amazon read-only scan for the 50 candidates
in reports/deepsea_z41_50-candidates_20261028.json"* — and I will run Round 2 as a
read-only pass (no purchase, no listing, no account change).

Without that approval I can still:
- run Round 1 deeper on non-Amazon sources (Etsy bestseller pages, Reddit threads,
  TikTok Creative Center, Google Trends)
- complete supplier verification on the 3 unconfirmed items
- request firm quotes on the 10 Tier-A products

**Recommended:** approve the read-only Amazon pass, because every remaining decision in
this plan depends on it, and it is the cheapest possible use of that gate.
