# Build the Mogra holiday-launch deliverable tables.
import csv, os, json, re

ROOT = os.path.join("docs", "mogra-organics-research-2026-10-02")
os.makedirs(ROOT, exist_ok=True)

def w(name, header, rows):
    p = os.path.join(ROOT, name); n=len(header); bad=0; fx=[]
    for i,r in enumerate(rows,1):
        if len(r)!=n:
            bad+=1; print(f"  !! {name} r{i}: {len(r)} expected {n}"); r=(list(r)+[""]*n)[:n]
        fx.append(r)
    with open(p,"w",newline="",encoding="utf-8") as f:
        cw=csv.writer(f,quoting=csv.QUOTE_MINIMAL); cw.writerow(header)
        for r in fx: cw.writerow(r)
    print(f"{name}: {len(fx)} rows, {bad} mismatches")

# ============================================================ 1. PRODUCT UNIVERSE + RANKING
# Scoring: 1=weak .. 5=strong. Confidence separate. Unknowns do NOT raise scores.
# attainable_demand = demand reachable by a NEW listing (not category size)
PR_H = ["product","form_variants","holiday_relevance","everyday_demand","organic_demand",
        "competition_intensity","differentiation_potential","new_brand_accessibility",
        "supply_availability","speed_to_launch","margin_after_ads","packaging_simplicity",
        "cash_exposure_moq","yearround_continuation","best_product_rank","launch_by_nov_rank",
        "evidence_confidence","evidence_basis","verdict","why_it_could_work","why_it_could_fail"]
def p(*a): return list(a)
PR = [
 p("Ceylon cinnamon (true cinnamon)","ground, sticks",5,5,5,3,5,3,4,4,3,4,4,5,1,1,"MEDIUM-HIGH",
   "Amazon BSR #1 in Herbs/Spices is Simply Organic Ceylon Cinnamon; premium Ceylon sells $7-33; documented consumer heavy-metal concern","LAUNCH CANDIDATE",
   "Premium Ceylon positioning with lab-tested low-lead differentiation; strong holiday + year-round baking demand",
   "Simply Organic holds ~34k ratings; Ceylon vs cassia confusion; heavy-metal claims must be substantiated"),
 p("Black pepper (whole peppercorn)","whole, refill",3,5,4,3,3,3,4,4,3,4,4,5,2,2,"MEDIUM",
   "Tellicherry whole peppercorn in category BSR top-15 at $9.60; whole peppercorn is a grinder-refill premium format","LAUNCH CANDIDATE",
   "Whole peppercorn is a refill/grinder format where premium positioning survives; everyday demand; verified organic supply exists",
   "Commodity at ground level; Amazon private label competes hard; differentiation limited at whole level"),
 p("Cinnamon + baking spice set (cinnamon, nutmeg, cloves, allspice)","multipack/set",5,3,4,2,4,3,3,3,3,2,3,3,3,3,"MEDIUM",
   "Holiday spice association documented (cinnamon/nutmeg/ginger/cloves/allspice); set format cuts through single-SKU competition","SECONDARY - EVALUATE",
   "Holiday gifting/baking occasion; set economics can improve AOV","Set adds packing/labeling burden and MSRP math; giftable packaging hard by deadline"),
 p("Nutmeg (whole or ground)","whole, ground",5,3,3,3,4,3,3,3,3,4,4,4,5,4,"LOW-MEDIUM",
   "Amazon has a dedicated Nutmeg BSR subcategory; whole nutmeg for fresh-grating is a premium niche","SECONDARY - EVALUATE",
   "Fresh-grate whole nutmeg is a credible premium niche; holiday association","Smaller category; whole nutmeg requires import + fresh supply"),
 p("Ground ginger","ground",5,4,3,3,3,2,3,4,3,4,5,5,4,5,"LOW-MEDIUM",
   "Holiday baking staple; ground ginger is a commodity with private-label presence","MONITOR",
   "Clear holiday association","Highly commoditised; Amazon private label present; weak differentiation"),
 p("Turmeric","ground",2,5,5,5,2,2,5,4,3,4,5,5,1,6,"HIGH",
   "Organic turmeric search shows incumbents at ~$0.59-0.62/oz with 11-12k ratings each","AVOID OR DEFER",
   "Large organic category; verified organic supply exists","Price war at ~$0.60/oz against incumbents with 11k+ reviews; near-zero differentiation for a new brand"),
 p("Garlic powder","granules, powder",2,5,4,5,2,2,4,4,3,5,5,5,2,7,"HIGH",
   "Organic garlic powder: McCormick $0.78/oz, 365 $1.45/oz, Badia $0.63/oz; Amazon Saver at $0.32/oz","AVOID OR DEFER",
   "Very large everyday category","Dominated by Amazon private label and major brands at sub-$1/oz; no new-brand wedge"),
 p("Onion powder","granules, powder",2,5,4,5,2,2,4,4,3,5,5,5,2,8,"MEDIUM",
   "Happy Belly Onion Powder sits in category top-30 at $1.29","AVOID OR DEFER",
   "Everyday staple","Amazon private label owns the entry price point"),
 p("Paprika / smoked paprika","ground",3,4,4,4,3,2,4,3,3,4,4,4,1,9,"LOW-MEDIUM",
   "Amazon Grocery Paprika 2.75 oz at $1.25 in category top-30","MONITOR",
   "Smoked paprika has some premium positioning","Private label at $1.25; smoked requires specific supply"),
 p("Cumin","ground, seed",2,5,4,4,2,2,4,4,3,4,5,5,1,10,"MEDIUM",
   "Everyday commodity; strong in Indian/Mexican cooking","MONITOR",
   "Steady everyday demand","Commodity; limited differentiation"),
 p("Cloves (whole)","whole",5,3,3,3,4,3,3,3,3,4,4,4,5,11,"MEDIUM",
   "Amazon Grocery Whole Cloves $2.29/2oz in top-30; organic Ceylon cloves at $6.95","MONITOR",
   "Holiday association; whole cloves hold premium better than ground","Modest category size"),
 p("Cardamom","whole pods, ground",4,3,4,3,4,3,3,3,2,4,5,4,4,12,"LOW-MEDIUM",
   "High-value spice; premium pricing achievable","MONITOR",
   "High value per unit; premium viable","Cost per unit is high; cash exposure"),
 p("Rosemary","dried, cut",3,4,3,3,3,3,3,4,4,4,5,5,5,13,"LOW",
   "Culinary herb; holiday roast association","MONITOR","Roast/holiday use","Weak commodity; limited evidence gathered"),
 p("Thyme","dried, cut",3,4,3,3,3,3,3,4,4,4,5,5,5,14,"LOW","Holiday roast association","MONITOR","Roast/holiday use","Weak commodity"),
 p("Sage","dried, rubbed",4,3,3,3,4,3,3,4,4,4,5,5,5,15,"LOW","Strong Thanksgiving/holiday stuffing association","MONITOR","Distinct holiday association","Narrow season"),
 p("Oregano","dried, cut",2,4,3,3,3,3,3,4,4,4,5,5,5,16,"LOW","Everyday Italian/Mexican","MONITOR","Everyday use","Commodity"),
 p("Allspice","ground, whole",5,3,3,3,4,3,3,3,3,4,4,4,5,17,"LOW","Holiday baking + Caribbean cuisine","MONITOR","Holiday association","Small category"),
 p("Sea salt (plain)","fine, coarse, flake",3,5,0,4,3,3,4,4,4,4,4,4,3,18,"HIGH",
   "Salt dominates 8 of the top-30 Herbs/Spices BSR positions","SEPARATE TRACK - NOT ORGANIC",
   "Huge demand; additive-free positioning exists","Plain salt CANNOT be USDA organic; outside Mogra's organic premise unless blended"),
 p("Salt-containing seasoning blend","blend",3,4,2,3,4,3,3,3,3,4,4,4,3,19,"LOW","Blends such as Badia Complete Seasoning sit in top-30","PROPOSED - LATER",
   "Blends can carry 'made with organic'","Blend formulation + label complexity; not a simple launch SKU"),
 p("Vanilla (pods/extract)","pods, extract",4,5,4,4,4,3,2,3,2,4,5,5,3,20,"LOW",
   "10 Madagascar vanilla pods at $12.99 in category top-30","MONITOR",
   "Strong holiday baking demand; high value","Supply is expensive and volatile; not an herb/spice in scope"),
 p("Cinnamon sticks (Ceylon)","whole sticks",5,4,5,3,5,3,4,4,3,4,4,5,4,21,"MEDIUM",
   "Sticks are a giftable/premium format distinct from powder","SECONDARY - EVALUATE",
   "Premium stick format; holiday gifting","Requires quill grading knowledge; packing format matters"),
 p("Peppermint / culinary mint","dried",4,3,3,3,3,2,3,3,4,4,5,5,5,22,"LOW","Holiday association","MONITOR","Holiday scent/flavour","Weak as culinary SKU"),
 p("Fennel seed","whole",2,3,3,3,2,3,3,4,4,4,5,5,5,23,"LOW","Everyday/regional","MONITOR","Steady niche","Commodity"),
 p("Fenugreek","seed, ground",1,2,3,3,2,3,3,4,4,4,5,5,5,24,"LOW","Regional cuisine","MONITOR","Niche","Weak evidence of broad demand"),
]
w("product_opportunity_ranking.csv", PR_H, PR)

# ============================================================ 2. COMPETITOR OBSERVATIONS
CO_H = ["obs_id","marketplace","query_or_list","brand","product","form","net_qty","pack_count",
        "price_usd","price_per_oz_usd","rating","ratings_count","asin","rank_note","observation_date",
        "source","limitations"]
def c(*a): return list(a)
CO = [
 c("CO-01","Amazon US","Herbs/Spices BSR #1","Simply Organic","Ground Ceylon Cinnamon","ground","","1","7.29","","4.8","34526","","BSR #1 overall","2026-10-02","Amazon Best Sellers (public)","BSR rank is not unit sales; price as observed"),
 c("CO-02","Amazon US","Herbs/Spices BSR #2","Amazon Grocery","Garlic Powder","powder","3.9 oz","1","1.60","0.41","4.8","","","top-2","2026-10-02","Amazon Best Sellers (public)","Amazon private label; ratings not captured"),
 c("CO-03","Amazon US","Herbs/Spices BSR","Happy Belly","Ground Cinnamon","ground","","1","1.32","","4.8","","","top-10","2026-10-02","Amazon Best Sellers (public)","Amazon private label"),
 c("CO-04","Amazon US","Herbs/Spices BSR","Happy Belly","Onion Powder","powder","","1","1.29","","4.8","","","top-12","2026-10-02","Amazon Best Sellers (public)","Amazon private label"),
 c("CO-05","Amazon US","Herbs/Spices BSR","Amazon Grocery","Ground Black Pepper","ground","3 oz","1","3.22","1.07","4.8","","","top-25","2026-10-02","Amazon Best Sellers (public)",""),
 c("CO-06","Amazon US","Herbs/Spices BSR","Amazon Grocery","Paprika","ground","2.75 oz","1","1.25","0.45","4.8","","","top-26","2026-10-02","Amazon Best Sellers (public)",""),
 c("CO-07","Amazon US","Herbs/Spices BSR","Amazon Saver","Garlic Powder","powder","2.5 oz","1","0.80","0.32","4.7","","","top-28","2026-10-02","Amazon Best Sellers (public)","Amazon private label; entry-price floor"),
 c("CO-08","Amazon US","Herbs/Spices BSR","(unbranded listing)","Tellicherry Black Pepper Whole Peppercorn","whole","","1","9.60","","4.8","","","top-13","2026-10-02","Amazon Best Sellers (public)","Premium whole-pepper format"),
 c("CO-09","Amazon US","Herbs/Spices BSR","Amazon Grocery","Whole Cloves","whole","2 oz","1","2.29","1.15","4.8","","","top-19","2026-10-02","Amazon Best Sellers (public)",""),
 c("CO-10","Amazon US","organic ceylon cinnamon powder","True Organic","Pure Ceylon Cinnamon Powder","ground","1 lb","1","14.95","0.93","4.7","9184","","","2026-10-02","Amazon search (public)","Search position not rank; ratings as observed"),
 c("CO-11","Amazon US","organic ceylon cinnamon powder","Anthony's","Organic Ceylon Cinnamon Powder","ground","1 lb","1","17.19","1.07","4.7","10604","","","2026-10-02","Amazon search (public)",""),
 c("CO-12","Amazon US","organic ceylon cinnamon powder","Micro Ingredients","Organic Ceylon Cinnamon Powder","ground","8 oz","1","9.99","1.25","4.5","4639","","","2026-10-02","Amazon search (public)",""),
 c("CO-13","Amazon US","organic ceylon cinnamon powder","(multiple)","Organic Ceylon Cinnamon Powder","ground","","1","11.55","","4.5","2338","","","2026-10-02","Amazon search (public)",""),
 c("CO-14","Amazon US","organic garlic powder","McCormick","Organic Garlic Powder","powder","16.75 oz","1","13.11","0.78","4.8","3346","","","2026-10-02","Amazon search (public)",""),
 c("CO-15","Amazon US","organic garlic powder","Simply Organic","Garlic Powder","powder","3.64 oz","1","6.24","1.71","4.8","4085","","","2026-10-02","Amazon search (public)",""),
 c("CO-16","Amazon US","organic garlic powder","365 by Whole Foods","Organic Garlic Powder","powder","2.33 oz","1","3.38","1.45","4.6","3640","","","2026-10-02","Amazon search (public)",""),
 c("CO-17","Amazon US","organic garlic powder","Badia","Organic Garlic Powder","powder","3 oz","1","1.89","0.63","4.8","858","","","2026-10-02","Amazon search (public)",""),
 c("CO-18","Amazon US","organic turmeric powder","OSR","Organic Turmeric Powder with Curcumin","ground","16 oz","1","9.49","0.59","4.7","12402","","","2026-10-02","Amazon search (public)","Incumbent scale ~12k ratings"),
 c("CO-19","Amazon US","organic turmeric powder","Jiva Organics","Organic Turmeric Powder","ground","1 lb","1","9.98","0.62","4.6","11052","","","2026-10-02","Amazon search (public)","Incumbent scale ~11k ratings"),
 c("CO-20","Amazon US","Herbs/Spices BSR (salt sub-track)","multiple","Sea salt (Baja Gold, Celtic, Redmond, Maldon, Diamond Crystal)","various","","1","","","","","","8 of top-30","2026-10-02","Amazon Best Sellers (public)","Plain salt cannot be USDA organic"),
]
w("competitor_observations.csv", CO_H, CO)

# ============================================================ 3. PRODUCT-SUPPLIER MATRIX
PS_H = ["product","supplier_id","supplier_name","supplier_role","location","form_offered",
        "organic_status_verified","moq_known","price_status","launch_support_likelihood",
        "evidence","missing_confirmation"]
def q(*a): return list(a)
PS = [
 q("Ceylon cinnamon (ground)","pearl-group","Pearl Group Corporation","processor-exporter","Vietnam","cinnamon bark/split/sticks (observed); powder to confirm","VERIFIED (pepper/turmeric/observed cinnamon)","not published","QUOTE_REQUIRED","MEDIUM - organic verified but packing/lead time unconfirmed","USDA OID verified 2026-10-02","packing scope; powder-for-cinnamon; lead time; MOQ"),
 q("Ceylon cinnamon (ground)","japc","JAPC (Jaqon Lanka)","processor-exporter","Sri Lanka","True Ceylon Cinnamon; organic","PROVISIONAL (Control Union named)","low (private label)","QUOTE_REQUIRED","MEDIUM-HIGH - Ceylon origin + private label claimed","japc.lk certifications page 2026-10-02","certificate number; MOQ; lead time"),
 q("Ceylon cinnamon (ground)","micro-cinnamon-note","(see competitor Micro Ingredients / True Organic)","importer-brand","USA/Sri Lanka","Ceylon cinnamon powder","SUPPLIER_CLAIMED","unknown","PUBLISHED_RETAIL_REFERENCE","N/A - competitor reference","Amazon search 2026-10-02","not a supplier route; benchmark only"),
 q("Black pepper (whole)","pearl-group","Pearl Group Corporation","processor-exporter","Vietnam","whole + ground black pepper","VERIFIED","not published","QUOTE_REQUIRED","MEDIUM-HIGH - verified organic; packing unconfirmed","USDA OID 2026-10-02","MOQ; packing scope; lead time"),
 q("Black pepper (whole)","bata-food","Bata Food LLC / B.V.","importer-distributor","TR/NL/US","whole black pepper","SUPPLIER_CLAIMED","800 kg","QUOTE_REQUIRED","MEDIUM - only published MOQ; cleared Rotterdam stock","batafood.com 2026-10-02","organic verification; price"),
 q("Black pepper (whole)","prime-food-products","Prime Food Products (Pvt) Ltd","processor-exporter","Sri Lanka","whole/cut/powdered","SUPPLIER_CLAIMED","not published","QUOTE_REQUIRED","MEDIUM - claims USDA organic with specs","primefoodproducts.com 2026-10-02","certificate; price"),
 q("Turmeric (ground)","pearl-group","Pearl Group Corporation","processor-exporter","Vietnam","fresh + dried sliced verified; powder claimed","VERIFIED (sliced/fresh) / powder CLAIMED","not published","QUOTE_REQUIRED","MEDIUM - powder needs confirmation","USDA OID 2026-10-02","turmeric POWDER certification"),
 q("Turmeric (ground)","amazon-andes","Amazon Andes","producer-exporter","Peru","milled powder","SUPPLIER_CLAIMED (Control Union Peru named)","not published","QUOTE_REQUIRED","MEDIUM","amazon-andes.com 2026-10-02","certificate sighting"),
 q("Cinnamon sticks","japc","JAPC","processor-exporter","Sri Lanka","True Ceylon Cinnamon quills/powder","PROVISIONAL","low (private label)","QUOTE_REQUIRED","MEDIUM-HIGH","japc.lk 2026-10-02","certificate number"),
 q("Nutmeg","pearl-group","Pearl Group Corporation","processor-exporter","Vietnam","(not observed in captured list)","UNKNOWN for nutmeg","not published","QUOTE_REQUIRED","LOW-MEDIUM - nutmeg not confirmed","USDA OID (truncated) 2026-10-02","nutmeg coverage"),
 q("Cloves","pearl-group","Pearl Group Corporation","processor-exporter","Vietnam","(not observed in captured list)","UNKNOWN for cloves","not published","QUOTE_REQUIRED","LOW-MEDIUM","USDA OID (truncated) 2026-10-02","clove coverage"),
 q("Any finished SKU (Route A)","pearl-group","Pearl Group Corporation","processor-exporter + private label","Vietnam","private label / ODM / OEM claimed","VERIFIED organic (forms above)","not published","QUOTE_REQUIRED","MEDIUM - capability claimed","vietnampepper.vn 2026-10-02","packing organic scope; MOQ; price; lead time"),
 q("Any finished SKU (Route B)","spices-inc","Spices Inc.","co-packer","Lowell MA, USA","sourcing + blending + co-pack + salt blends","SUPPLIER_CLAIMED","not published","QUOTE_REQUIRED","MEDIUM - turnkey fit","spicesinc.com 2026-10-02","NOP handler certification; MOQ; setup cost"),
 q("Any finished SKU (Route B)","specialty-food-copackers","Specialty Food Co-Packers","co-packer","USA","spice powder filling + seasonings","SUPPLIER_CLAIMED","not published","QUOTE_REQUIRED","MEDIUM","specialtyfoodcopackers.com 2026-10-02","NOP certifier; MOQ; setup"),
 q("Any finished SKU (Route B)","organic-spices-inc","Organic Spices Inc.","importer + co-packer","McKinney TX, USA","organic spices + contract mfg + private label","SUPPLIER_CLAIMED","not published","QUOTE_REQUIRED","MEDIUM","organicspices.com 2026-10-02","NOP handler cert; MOQ; setup"),
 q("Any finished SKU (Route C)","spicy-organic","Spicy Organic","importer-wholesaler","McKinney TX, USA","40+ organic spices, 5-44 lb ladder","SUPPLIER_CLAIMED","5 lb","QUOTE_REQUIRED","MEDIUM-HIGH - lowest published entry quantity","spicyorganic.com 2026-10-02","organic verification; finished-unit capability"),
]
w("product_supplier_matrix.csv", PS_H, PS)

# ============================================================ 4. ECONOMICS SCENARIOS
EC_H = ["sku_scenario","cost_or_price_line","value_usd","unit","basis","value_type","source_or_basis","note"]
def e(*a): return list(a)
EC = [
 e("Scenario A: Ceylon cinnamon ground 2 oz pouch","Ingredient (organic Ceylon cinnamon)","","per lb","bulk","UNKNOWN","quote required","No supplier quote exists"),
 e("Scenario A: Ceylon cinnamon ground 2 oz pouch","Ingredient per finished unit","","per unit","2 oz","DERIVED","2 oz / yield","Cannot compute without ingredient price"),
 e("Scenario A: Ceylon cinnamon ground 2 oz pouch","Pouch + label + packing","","per unit","per unit","UNKNOWN","co-packer quote required",""),
 e("Scenario A: Ceylon cinnamon ground 2 oz pouch","Co-packer setup / artwork","","one-time","one-time","UNKNOWN","quote required","Amortised over pilot units"),
 e("Scenario A: Ceylon cinnamon ground 2 oz pouch","Testing (heavy metals, microbiology)","","per lot","per lot","UNKNOWN","lab quote required","Differentiation depends on this"),
 e("Scenario A: Ceylon cinnamon ground 2 oz pouch","Inbound freight (domestic or import)","","per shipment","per shipment","UNKNOWN","broker/forwarder quote","Import duty/AD-CVD unresolved"),
 e("Scenario A: Ceylon cinnamon ground 2 oz pouch","Amazon referral fee","15","% of price","percentage","ASSUMED_STANDARD","Amazon standard referral for grocery","Must confirm category rate"),
 e("Scenario A: Ceylon cinnamon ground 2 oz pouch","Amazon fulfilment (FBA) fee","","per unit","per unit","UNKNOWN","requires weight/dims","Holiday peak surcharge Oct 15 2026-Jan 14 2027"),
 e("Scenario A: Ceylon cinnamon ground 2 oz pouch","Retail price (target)","","per unit","2 oz","PROPOSED","benchmark: premium Ceylon $0.93-1.25/oz observed","Positioning decision pending"),
 e("Scenario A: Ceylon cinnamon ground 2 oz pouch","Advertising (PPC)","","per unit","ACOS assumption","UNKNOWN","no CPC data authorised","Break-even ACOS must be computed once costs known"),
 e("Scenario B: Black pepper whole 3 oz pouch","Ingredient (organic whole black pepper)","","per lb","bulk","UNKNOWN","quote required","Pearl verified organic; no price"),
 e("Scenario B: Black pepper whole 3 oz pouch","Retail price (target)","","per unit","3 oz","PROPOSED","benchmark: premium whole pepper listing at $9.60 observed",""),
 e("Scenario C: Ceylon cinnamon sticks 4 oz","Ingredient (organic Ceylon quills)","","per lb","bulk","UNKNOWN","quote required",""),
 e("Cross-SKU","Mogra organic certification (if applicable)","","per year","annual","UNKNOWN","certifier opinion required","May be avoidable on Route A/C"),
 e("Cross-SKU","Customs duty + AD/CVD (import routes)","","per shipment","per shipment","UNKNOWN","broker review required","No duty figure asserted anywhere"),
 e("Cross-SKU","Pilot run quantity (illustrative)","500","units","per SKU","PROPOSED","illustrative only","NOT owner-approved demand"),
 e("Cross-SKU","Holiday peak FBA fulfilment surcharge window","","","Oct 15 2026 - Jan 14 2027","VERIFIED","Amazon seller guidance 2026","Applies during the launch window"),
]
w("economics_scenarios.csv", EC_H, EC)

# ============================================================ 5. LAUNCH ACTION PLAN
LA_H = ["seq","milestone","target_date","date_type","depends_on","owner","status","evidence_to_retain"]
def l(*a): return list(a)
LA = [
 l("1","Owner product decision (final 2-4 SKUs)","2026-10-06","planning allowance","-","Owner","OPEN","Decision record"),
 l("2","Confirm legal entity spelling","2026-10-06","planning allowance","-","Owner","OPEN","Business record"),
 l("3","Supplier outreach (5 RFQs sent)","2026-10-08","planning allowance","1,2","Research/Owner","BLOCKED on D1","Sent RFQ + responses"),
 l("4","Sample requests issued","2026-10-10","planning allowance","3","Owner","OPEN","Sample order + COA"),
 l("5","Customs-broker review commissioned","2026-10-08","planning allowance","1","Owner","OPEN","Broker written position"),
 l("6","Co-packer selection + setup quote","2026-10-13","planning allowance","3","Research","OPEN","Signed quote"),
 l("7","Sample evaluation + acceptance","2026-10-17","planning allowance","4","Owner/Research","OPEN","Sample evaluation record"),
 l("8","Packaging + label artwork finalised","2026-10-20","planning allowance","7","Owner/Design","OPEN","Approved artwork"),
 l("9","Organic/label review (if claimed)","2026-10-20","planning allowance","8","Certifier","OPEN","Certifier confirmation"),
 l("10","Pilot production run","2026-10-27","planning allowance","6,8,9","Co-packer","OPEN","Pilot lot records"),
 l("11","QA + lot acceptance","2026-10-30","planning allowance","10","Owner/Research","OPEN","COA + inspection"),
 l("12","Ship to FBA / 3PL","2026-11-03","planning allowance","11","Owner","OPEN","Bill of lading / tracking"),
 l("13","Fulfilment-centre receiving + check-in","2026-11-10","planning allowance","12","Amazon","OPEN","Receiving confirmation"),
 l("14","Listing build (title, bullets, images)","2026-11-05","planning allowance","8","Owner","OPEN","Listing content"),
 l("15","Buyable inventory (FBA live)","2026-11-15","TARGET (planning, not committed)","13,14","Amazon","OPEN","Live ASIN"),
 l("16","PPC activation","2026-11-15","planning allowance","15","Owner","OPEN","Campaign structure"),
 l("17","Week-1 review: conversion + economics","2026-11-22","planning allowance","15","Owner","OPEN","Metric snapshot"),
 l("18","Week-2 decision: scale / adjust / pause","2026-11-29","planning allowance","17","Owner","OPEN","Decision record"),
 l("19","December push (ads + promo if eligible)","2026-12-01","planning allowance","18","Owner","OPEN","Campaign config"),
 l("20","Reorder evaluation","2026-12-15","planning allowance","19","Owner","OPEN","Actual costs + sales"),
 l("X","BFCM FBA inbound deadline (missed by this plan)","2026-10-14 to 2026-10-28","VERIFIED (Amazon guidance)","-","-","NOT FEASIBLE for this launch","Amazon Q4 guidance"),
]
w("launch_action_plan.csv", LA_H, LA)

# ============================================================ 6. SOURCE REGISTER
SR_H = ["source_id","title","url","source_type","observation_date","used_for","limitations"]
def s(*a): return list(a)
SR = [
 s("SRC-01","Amazon Best Sellers — Herbs, Spices & Seasonings","https://www.amazon.com/Best-Sellers-Herbs,-Spices-Seasonings/zgbs/grocery/16310281","public marketplace","2026-10-02","Category leader positions, private-label dominance, price points","BSR rank is not unit sales; single observation; may vary by session"),
 s("SRC-02","Amazon search — organic ceylon cinnamon powder","https://www.amazon.com/s?k=organic+ceylon+cinnamon+powder","public marketplace","2026-10-02","Competitor prices, ratings counts, brand concentration","Search position is not rank; sponsored results mixed in"),
 s("SRC-03","Amazon search — organic garlic powder","https://www.amazon.com/s?k=organic+garlic+powder","public marketplace","2026-10-02","Competitor prices per oz","As above"),
 s("SRC-04","Amazon search — organic turmeric powder","https://www.amazon.com/s?k=organic+turmeric+powder","public marketplace","2026-10-02","Incumbent scale (11-12k ratings) and ~$0.60/oz price war","As above"),
 s("SRC-05","Amazon Seller Central — Q4 2026 peak readiness playbook","https://sellercentral.amazon.com/help/hub/reference/external/G4QH4XCRWUXRJBLY","official Amazon guidance","2026-10-02","BFCM inbound deadlines (Oct 14 / 21 / 28); promo submission close Oct 20","Event-readiness guidance, not a universal ban on later arrivals"),
 s("SRC-06","Holiday peak FBA fulfilment fees (US)","https://amzprep.com/holiday-peak-fulfillment-fees/","industry summary of Amazon policy","2026-10-02","Holiday peak fulfilment surcharge Oct 15 2026 - Jan 14 2027","Secondary source summarising Amazon policy"),
 s("SRC-07","Seasonal spice association (cinnamon, nutmeg, ginger, cloves)","https://theconversation.com/how-cinnamon-nutmeg-and-ginger-became-the-scents-of-winter-holidays-far-from-their-tropical-origins-218329","editorial/expert commentary","2026-10-02","Holiday relevance of specific spices","Cultural association, not sales data"),
 s("SRC-08","Independent heavy-metal testing of Simply Organic Ceylon cinnamon","https://tamararubin.com/2025/12/simply-organic-ceylon-cinnamon/","independent lab blog","2026-10-02","Documented consumer heavy-metal concern in cinnamon","Third-party blog; not peer-reviewed; single product"),
 s("SRC-09","USDA Organic Integrity Database","https://organic.ams.usda.gov/integrity/","official registry","2026-10-02","Pearl Group organic verification","Interaction unreliable; truncated capture"),
 s("SRC-10","JAPC certifications page","https://japc.lk/certifications","supplier page","2026-10-02","JAPC names Control Union as certifier","No certificate number; supplier claim"),
 s("SRC-11","Amazon category sub-pages: Nutmeg BSR","https://www.amazon.com/Best-Sellers-Nutmeg/zgbs/grocery/16321731","public marketplace","2026-10-02","Existence of a Nutmeg subcategory (category interest signal)","Subcategory existence is not demand magnitude"),
 s("SRC-12","Vietnam Pepper & Spice Association trade summary","https://asemconnectvietnam.gov.vn/default.aspx?ID1=2&ID8=146381","industry/government trade portal","2026-10-02","Pepper market context (2025 exports, US share, avg price)","Aggregate market data, not supplier quote"),
]
w("source_evidence_register.csv", SR_H, SR)

print("LAUNCH TABLES BUILT")
