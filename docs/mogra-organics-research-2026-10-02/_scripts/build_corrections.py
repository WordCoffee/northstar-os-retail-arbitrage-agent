# Correction pass tables: exact competitor observations, finalist comparison, hypothetical economics.
import csv, os
ROOT=os.path.join("docs","mogra-organics-research-2026-10-02")
def w(name,header,rows):
    n=len(header); bad=0; fx=[]
    for i,r in enumerate(rows,1):
        if len(r)!=n: bad+=1; print(f"  !! {name} r{i}: {len(r)} exp {n}"); r=(list(r)+[""]*n)[:n]
        fx.append(r)
    with open(os.path.join(ROOT,name),"w",newline="",encoding="utf-8") as f:
        cw=csv.writer(f,quoting=csv.QUOTE_MINIMAL); cw.writerow(header)
        for r in fx: cw.writerow(r)
    print(f"{name}: {len(fx)} rows, {bad} mismatches")

# ============================================================ COMPETITOR OBSERVATIONS (corrected)
CO_H=["obs_id","marketplace","asin","brand","product","form","net_qty","pack_count","price_usd",
      "price_per_oz_usd","rating","ratings_count","ratings_context","category_or_list","rank_note",
      "comparable_class","observation_date","source","limitations"]
def c(*a): return list(a)
CO=[
 c("CO-01","Amazon US","B00ZK8YIXW","Simply Organic","Ground Ceylon Cinnamon","ground","2.08 oz","1","7.29","3.50","4.8","34526",
   "VARIATION-FAMILY count (same 34,526 appears on B0GVVQV4S7 and B07BRPCK32) - NOT this child ASIN's own reviews","Herbs, Spices & Seasonings BSR","BSR #1 overall",
   "PREMIUM Ceylon (directly comparable)","2026-10-02","Amazon Best Sellers + search (public)","Single observation; price/size may vary; review count is variation-family, not child-ASIN velocity"),
 c("CO-02","Amazon US","B0GVVQV4S7","Simply Organic","Ceylon Ground Cinnamon 2.08 oz","ground","2.08 oz","1","14.58","7.01","4.8","34526",
   "VARIATION-FAMILY (same 34,526) - price differs across variants for same nominal size","Herbs, Spices & Seasonings","","PREMIUM Ceylon","2026-10-02","Amazon search (public)","Price variation across siblings is unexplained; verify before benchmarking"),
 c("CO-03","Amazon US","B081R5PX1D","True Organic","Pure Ceylon Cinnamon Powder","ground","1 lb","1","14.95","0.93","4.7","9184",
   "listing-level (as displayed)","organic ceylon cinnamon powder search","","PREMIUM Ceylon","2026-10-02","Amazon search (public)",""),
 c("CO-04","Amazon US","B075LXXCVC","Anthony's","Organic Ceylon Cinnamon Powder","ground","1 lb","1","17.19","1.07","4.7","10604",
   "listing-level (as displayed)","organic ceylon cinnamon powder search","","PREMIUM Ceylon","2026-10-02","Amazon search (public)",""),
 c("CO-05","Amazon US","B0FGF3F9H4","Micro Ingredients","Organic Ceylon Cinnamon Powder","ground","8 oz","1","9.99","1.25","4.5","4639",
   "VARIATION-FAMILY (same 4,639 on 1 lb and 2 lb sizes)","organic ceylon cinnamon powder search","","PREMIUM Ceylon","2026-10-02","Amazon search (public)",""),
 c("CO-06","Amazon US","B07MHX96HW","FGO","Organic Ceylon Cinnamon Powder","ground","16 oz","1","24.99","1.56","4.6","11138",
   "listing-level","organic ceylon cinnamon powder search","","PREMIUM Ceylon","2026-10-02","Amazon search (public)","Higher $/oz than True Organic/Anthony's"),
 c("CO-07","Amazon US","B00416T8Q6","Frontier Co-op","Organic Ceylon Cinnamon, Ground, Bulk Bag","ground","16 oz","1","22.50","1.41","4.6","3934",
   "listing-level","organic ceylon cinnamon powder search","","PREMIUM Ceylon","2026-10-02","Amazon search (public)","Frontier owns the Simply Organic brand"),
 c("CO-08","Amazon US","B0BTMWK123","One Farm by WAAYB","Organic Ceylon Cinnamon, Single Estate","ground","","1","12.99","","4.7","1713",
   "listing-level","organic ceylon cinnamon powder search","","PREMIUM Ceylon (single-estate angle)","2026-10-02","Amazon search (public)","Net qty not captured"),
 c("CO-09","Amazon US","B0DJQRZLBT","Jiva Organics","Organic Cinnamon Sticks Bulk Bag","sticks","1.75 lb","1","17.99","0.64","3.6","53",
   "listing-level","organic ceylon cinnamon sticks search","","PREMIUM Ceylon sticks","2026-10-02","Amazon search (public)","Low rating (3.6) - quality risk signal for sticks"),
 c("CO-10","Amazon US","B081R6TDNX","True Organic","Ceylon Cinnamon Sticks","sticks","8 oz","1","18.15","2.27","4.6","1182",
   "listing-level","organic ceylon cinnamon sticks search","","PREMIUM Ceylon sticks","2026-10-02","Amazon search (public)",""),
 c("CO-11","Amazon US","B0DJX2V82K","(premium sticks listing)","Premium Organic Ceylon Cinnamon Sticks","sticks","1 lb","1","27.45","1.72","4.4","561",
   "listing-level","organic ceylon cinnamon sticks search","","PREMIUM Ceylon sticks","2026-10-02","Amazon search (public)","Highest $/lb for sticks observed"),
 c("CO-12","Amazon US","B078N4QVMD","(premium nutmeg listing)","Organic Whole Nutmeg","whole","3.5 oz","1","9.99","2.85","4.8","2738",
   "listing-level","organic whole nutmeg search","","PREMIUM whole nutmeg","2026-10-02","Amazon search (public)",""),
 c("CO-13","Amazon US","B081R8NVP4","True Organic","Ceylon Nutmeg Whole","whole","","1","7.95","","4.7","264",
   "listing-level","organic whole nutmeg search","","PREMIUM whole nutmeg","2026-10-02","Amazon search (public)","Net qty not captured"),
 c("CO-14","Amazon US","B0005YW28O","McCormick Gourmet","Nutmeg, Whole, Organic","whole","","1","5.67","","4.8","3986",
   "listing-level","organic whole nutmeg search","","PREMIUM whole nutmeg","2026-10-02","Amazon search (public)","Major brand"),
 c("CO-15","Amazon US","B07QW1GKR1","Amazon Grocery","Garlic Powder, 24 oz","powder","24 oz","1","7.22","0.30","4.8","32169",
   "variation context not confirmed","organic garlic powder search","","COMMODITY (not comparable to premium)","2026-10-02","Amazon search (public)","PRIVATE LABEL - excluded from premium comparison"),
 c("CO-16","Amazon US","B074ZK8MQS","McCormick","Garlic Powder (non-organic)","powder","","1","7.57","","4.8","25885",
   "listing-level","organic garlic powder search","","COMMODITY (not comparable)","2026-10-02","Amazon search (public)","Conventional; huge incumbent scale"),
 c("CO-17","Amazon US","B08HYBN4DJ","OSR","Organic Turmeric Powder with Curcumin","ground","16 oz","1","9.49","0.59","4.7","12402",
   "listing-level","organic turmeric powder search","","COMMODITY-like (near-cost organic)","2026-10-02","Amazon search (public)","Price-war evidence"),
 c("CO-18","Amazon US","B00H3QRW6E","Jiva Organics","Organic Turmeric Powder","ground","1 lb","1","9.98","0.62","4.6","11052",
   "listing-level","organic turmeric powder search","","COMMODITY-like (near-cost organic)","2026-10-02","Amazon search (public)","Price-war evidence"),
 c("CO-19","Amazon US","","Amazon Grocery / Happy Belly","Paprika 2.75 oz; Onion Powder; Ground Cinnamon; Sea Salt","various","","1","1.25","0.45","4.8","",
   "not captured","Herbs, Spices & Seasonings BSR top-30","top-30","COMMODITY private label","2026-10-02","Amazon Best Sellers (public)","Private-label floor evidence; ASINs not captured"),
 c("CO-20","Amazon US","","(unbranded listing)","Tellicherry Black Pepper Whole Peppercorn","whole","","1","9.60","","4.8","",
   "not captured","Herbs, Spices & Seasonings BSR","top-15","PREMIUM whole pepper (format-comparable)","2026-10-02","Amazon Best Sellers (public)","ASIN and net qty not captured in this pass"),
]
w("competitor_observations.csv",CO_H,CO)

# ============================================================ FINALIST DECISION COMPARISON
FD_H=["candidate","classification","demand_evidence","seasonal_timing_evidence","new_brand_accessibility",
      "comparable_competitor_observations","price_pack_opportunity","differentiation","supply_timing_evidence",
      "confidence","missing_evidence","decision","why_this_vs_alternatives"]
def f(*a): return list(a)
FD=[
 f("Ground Ceylon cinnamon","RECOMMENDED (provisional) - primary",
   "Category BSR #1 is a Ceylon cinnamon product; multiple premium Ceylon listings with 1k-11k ratings; deep competitive field proves sustained demand",
   "Cinnamon is a documented winter-holiday spice; baking peaks Nov-Dec; also year-round baking demand",
   "Better than commodity: premium price band ($0.93-$1.56/oz) rewards a differentiated offer; still crowded",
   "B081R5PX1D $0.93/oz; B075LXXCVC $1.07/oz; B0FGF3F9H4 $1.25/oz; B00416T8Q6 $1.41/oz; B07MHX96HW $1.56/oz; B00ZK8YIXW (2.08 oz) $3.50/oz",
   "2-4 oz $8-$14; larger 1 lb refill $15-$25. Premium band supports a 2-4 oz launch SKU",
   "Proposed: species-verified Ceylon (not cassia) + LOT-tested heavy metals. Both require substantiation before any claim",
   "UNKNOWN - no supplier lead time provided by Pearl or JAPC",
   "MEDIUM-HIGH (demand and price evidence strong; supply timing unproven)",
   "Supplier lead time; lot COA with heavy-metal results; whether Pearl packs finished units organically",
   "LAUNCH CANDIDATE",
   "Wins over turmeric/garlic because the premium band (not the commodity floor) is where a new brand can compete on quality rather than price"),
 f("Whole black pepper","RECOMMENDED (provisional) - primary",
   "Premium whole-pepper listing in category top-15 at $9.60; whole/grinder-refill is a recognised premium format",
   "Everyday demand; no strong holiday peak - so it is not a seasonal bet",
   "Moderate: format differentiation (whole/refill) survives commodity pressure better than ground",
   "CO-20 (top-15, $9.60, whole); exact ASIN/net qty not captured - gap",
   "2-3 oz refill $8-$13; grinder format higher",
   "Proposed: verified-organic whole peppercorn + refill format",
   "Pearl whole pepper VERIFIED organic (USDA OID 2026-10-02); lead time UNKNOWN",
   "MEDIUM (organic supply verified; competitor observation incomplete)",
   "Exact competitor ASIN/net qty; Pearl MOQ, price, lead time",
   "LAUNCH CANDIDATE",
   "Wins over ground pepper because the whole/refill format escapes the Amazon-private-label commodity floor"),
 f("Ceylon cinnamon sticks","PROVISIONAL - secondary",
   "Several premium stick listings; B081R6TDNX 1,182 ratings; B0DJX2V82K $1.72/oz",
   "Giftable + holiday; strong Nov-Dec gifting potential",
   "Moderate-high: sticks are a premium/gift format less contested than powder",
   "B081R6TDNX $2.27/oz; B0DJX2V82K $1.72/oz; B0DJQRZLBT $0.64/oz but rating only 3.6",
   "4 oz $12-$20 giftable",
   "Proposed: true Ceylon quills, gift-ready pack. Requires quill grading",
   "UNKNOWN - quill-grade supply and packing not confirmed",
   "MEDIUM (demand real; supply and grading unproven)",
   "Quill-grade supplier; grading spec; packing format; lead time",
   "SECONDARY - evaluate only if first two are on track",
   "Deferred because it needs quill-grading expertise and a separate packing format, adding timeline risk"),
 f("Whole nutmeg","PROVISIONAL - alternative",
   "Dedicated Amazon Nutmeg BSR subcategory exists; B078N4QVMD 2,738 ratings; McCormick Gourmet 3,986",
   "Strong holiday association (egg nog, baking); cultural peak",
   "Moderate: smaller category; premium whole-nutmeg niche exists",
   "B078N4QVMD $2.85/oz; B081R8NVP4 $7.95; B0005YW28O $5.67; B07DTL42KB $5.99",
   "3.5 oz jar $8-$12",
   "Proposed: whole nutmeg for fresh grating",
   "UNKNOWN - Pearl nutmeg coverage not observed in the truncated OID capture",
   "LOW-MEDIUM (smaller category; supply unconfirmed)",
   "Nutmeg organic coverage at candidate suppliers; lead time",
   "NOT in first launch - keep as candidate 4",
   "Ranks below cinnamon/pepper because the category is smaller and organic supply is unconfirmed"),
 f("Cloves (whole)","PROVISIONAL - alternative",
   "Amazon Grocery whole cloves $2.29/2 oz in top-30; organic Ceylon cloves observed at $6.95",
   "Strong holiday association",
   "Low-moderate: private label owns entry price",
   "CO from BSR top-30; organic Ceylon cloves observed but ASIN not captured",
   "2-3 oz $6-$9",
   "Proposed: whole cloves premium",
   "UNKNOWN - clove coverage not observed in truncated OID capture",
   "LOW-MEDIUM",
   "Clove organic coverage; competitor ASIN; lead time",
   "NOT in first launch",
   "Modest category size and unconfirmed supply"),
 f("Baking-spice set (cinnamon, nutmeg, cloves, allspice)","PROVISIONAL - defer",
   "Holiday spice-set occasion documented; set listings exist",
   "Strongly seasonal",
   "Moderate, but set economics multiply complexity",
   "not itemised - set competitor observation not captured",
   "MSRP $18-$30 per set",
   "Proposed: curated holiday baking set",
   "UNKNOWN - requires multiple ingredients and multi-SKU packing",
   "LOW",
   "Set competitor observation; multi-item supply; packing cost",
   "DEFER - not a first launch",
   "Multiplies packing, labelling and MSRP complexity - incompatible with the timeline"),
]
w("finalist_decision_comparison.csv",FD_H,FD)

# ============================================================ HYPOTHETICAL ECONOMICS
HE_H=["sku","line","formula","value","unit","value_type","assumption_note","source_or_limitation"]
def h(*a): return list(a)
HE=[
 h("Ceylon cinnamon ground 2 oz","Proposed selling price - scenario LOW","owner input","9.99","per unit","PROPOSED","Illustrative price point only","Not an owner-approved price"),
 h("Ceylon cinnamon ground 2 oz","Proposed selling price - scenario MID","owner input","12.99","per unit","PROPOSED","Illustrative price point only","Not an owner-approved price"),
 h("Ceylon cinnamon ground 2 oz","Proposed selling price - scenario HIGH","owner input","15.99","per unit","PROPOSED","Illustrative price point only","Not an owner-approved price"),
 h("Ceylon cinnamon ground 2 oz","Amazon referral fee","price x 0.15","","per unit","ASSUMED_STANDARD","Grocery referral commonly 15%","MUST confirm category rate"),
 h("Ceylon cinnamon ground 2 oz","Amazon FBA fulfilment fee","UNKNOWN - requires unit weight/dims","","per unit","UNKNOWN","Cannot compute without packaging spec","No FBA fee table used"),
 h("Ceylon cinnamon ground 2 oz","Ingredient (organic Ceylon cinnamon)","UNKNOWN - quote required","","per unit","UNKNOWN","No supplier quote exists","Retail references are NOT wholesale"),
 h("Ceylon cinnamon ground 2 oz","Packaging (pouch/jar + label)","UNKNOWN - quote required","","per unit","UNKNOWN","No co-packer quote exists",""),
 h("Ceylon cinnamon ground 2 oz","Packing labour + setup","UNKNOWN - quote required","","per unit + one-time","UNKNOWN","No co-packer quote exists",""),
 h("Ceylon cinnamon ground 2 oz","Lot testing (heavy metals, micro)","UNKNOWN - lab quote required","","per lot","UNKNOWN","Required for the differentiation claim",""),
 h("Ceylon cinnamon ground 2 oz","Maximum acceptable finished-unit cost","price - referral - FBA - target_contribution","","per unit","FORMULA_ONLY","Cannot evaluate without FBA + target","Formula shown; no validated number"),
 h("Ceylon cinnamon ground 2 oz","Contribution before advertising","price - referral - FBA_fee - landed_unit_cost","","per unit","FORMULA_ONLY","Cannot evaluate without FBA + landed cost","Formula shown; no validated number"),
 h("Ceylon cinnamon ground 2 oz","Break-even ACOS","contribution_before_ads / price","","percent","FORMULA_ONLY","Depends entirely on contribution","Formula shown; no validated number"),
 h("Ceylon cinnamon ground 2 oz","HYPOTHETICAL illustration","12.99 - (12.99x0.15) - 3.50 - 4.00 = 3.54","3.54","per unit","HYPOTHETICAL","ALL inputs assumed: price $12.99; referral 15%; FBA $3.50 assumed; landed cost $4.00 assumed","Illustration only - NOT a forecast and NOT validated"),
 h("Ceylon cinnamon ground 2 oz","HYPOTHETICAL break-even ACOS","3.54 / 12.99","27.3","percent","HYPOTHETICAL","Derived from the illustration above","Illustration only - NOT a benchmark"),
 h("Ceylon cinnamon ground 2 oz","Initial inventory (illustrative)","500 units","500","units","PROPOSED","Illustrative pilot size only","NOT an owner-approved quantity"),
 h("Ceylon cinnamon ground 2 oz","Cash exposure (illustrative)","500 x landed_unit_cost","","USD","FORMULA_ONLY","Cannot compute without landed cost","Null preserved"),
 h("Whole black pepper 3 oz","Proposed selling price - scenario MID","owner input","11.99","per unit","PROPOSED","Illustrative price point only","Not an owner-approved price"),
 h("Whole black pepper 3 oz","Contribution before advertising","price - referral - FBA_fee - landed_unit_cost","","per unit","FORMULA_ONLY","Ingredient cost UNKNOWN (Pearl verified organic, no price)","Formula shown; no validated number"),
 h("Whole black pepper 3 oz","Maximum acceptable finished-unit cost","price - referral - FBA - target_contribution","","per unit","FORMULA_ONLY","Cannot evaluate without FBA + target","Formula shown; no validated number"),
 h("Whole black pepper 3 oz","HYPOTHETICAL illustration","11.99 - 1.80 - 3.50 - 3.50 = 3.19","3.19","per unit","HYPOTHETICAL","ALL inputs assumed; referral treated as ~15%","Illustration only - NOT a forecast"),
 h("Whole black pepper 3 oz","Break-even ACOS","3.19 / 11.99","26.6","percent","HYPOTHETICAL","Derived from illustration","Illustration only - NOT a benchmark"),
 h("Cross-SKU","Holiday peak FBA surcharge window","Oct 15 2026 - Jan 14 2027","","","VERIFIED","Amazon policy summary","Applies during the launch window"),
 h("Cross-SKU","Customs duty + AD/CVD","UNKNOWN - broker review required","","per shipment","UNKNOWN","No HTS-confirmed rate","Never inferred as zero"),
 h("Cross-SKU","Mogra organic certification (if applicable)","UNKNOWN - certifier opinion required","","per year","UNKNOWN","Depends on chosen role",""),
 h("Cross-SKU","PPC / CPC assumptions","NOT COLLECTED","","","UNKNOWN","No CPC data authorised","No CPC invented"),
 h("Cross-SKU","Sales forecast","NOT PROVIDED","","","UNKNOWN","No operating history exists","No forecast invented"),
]
w("hypothetical_economics.csv",HE_H,HE)

print("CORRECTION TABLES BUILT")
