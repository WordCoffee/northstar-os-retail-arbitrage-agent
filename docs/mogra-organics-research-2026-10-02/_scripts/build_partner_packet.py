# Partner decision packet + dated launch schedule + decision gates.
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

# ============================================================ PARTNER DECISION PACKET
PP_H=["provider_id","company","country","contact_public","contact_source","products_forms",
      "capability","evidence_summary","unresolved_documentation","moq","price_status","packaging",
      "setup_cost","freight","lead_time","customer_supplied_ingredients","our_labels_applied",
      "finished_unit_fba_prep","outreach_priority","outreach_reason"]
def p(*a): return list(a)
PP=[
 p("PP-01","Pearl Group Corporation","Vietnam","info@pearlflavor.com · +84 3727 2426 · vietnampepper.vn","vietnampepper.vn (public site)",
   "Black/white pepper; cinnamon/cassia; turmeric (fresh + dried sliced verified; powder claimed); coriander, cumin, cardamom, fennel, mustard; dried herbs",
   "Turnkey candidate (supply + private-label/ODM/OEM claimed). Also supply-only.",
   "USDA-NOP VERIFIED in USDA OID (Control Union, CROPS+HANDLING) 2026-10-02; private-label/OEM/ODM claimed on site",
   "Certificate number + expiry; exact certified facility; exporter-of-record match; organic status of PACKING; turmeric POWDER coverage; lot COA",
   "QUOTE REQUIRED","QUOTE REQUIRED","QUOTE REQUIRED","QUOTE REQUIRED","QUOTE REQUIRED","QUOTE REQUIRED",
   "QUOTE REQUIRED","QUOTE REQUIRED (private label claimed)","FBA-prep: QUOTE REQUIRED",
   "1 - HIGH","Only supplier with independently verified organic status; broad certified range; potential single-source turnkey. Verified organic is a gate, not a nice-to-have."),
 p("PP-02","JAPC (Jaqon Lanka)","Sri Lanka","sales@japc.lk · +9476 800 0902 · japc.lk","japc.lk/certifications (public page)",
   "True Ceylon cinnamon; black/white pepper; turmeric; ginger; cardamom; cloves; nutmeg; herbs",
   "Turnkey candidate (organic spices, private label low MOQ claimed); supply-only also implied",
   "Names Control Union as certifier (PROVISIONAL - no cert number); curcumin >=4%, mesh, moisture, steam sterilization published",
   "Certificate number + scope + expiry; USDA OID confirmation; packing-facility organic status; lot COA",
   "QUOTE REQUIRED (low MOQ claimed for private label)","QUOTE REQUIRED","QUOTE REQUIRED","QUOTE REQUIRED","QUOTE REQUIRED","QUOTE REQUIRED","QUOTE REQUIRED",
   "QUOTE REQUIRED","QUOTE REQUIRED",
   "2 - HIGH","Certifier named (independently checkable, same certifier as Pearl). Ceylon origin is the priority cinnamon origin."),
 p("PP-03","Spices Inc.","USA (Lowell, MA)","spicesinc.com (public site, contact via site)","spicesinc.com / private-and-white-labeling",
   "Spice ingredients, custom blends, salt and smoked/flavoured salt blends",
   "PACKING-ONLY and TURNKEY (manages sourcing, storage, blending, then co-packs)",
   "Claims organic capability; no certifier named",
   "USDA-NOP handler certification (distinct from any SQF/GMP); certifier name + number; whether customer-supplied organic ingredient is accepted",
   "QUOTE REQUIRED","QUOTE REQUIRED","QUOTE REQUIRED","QUOTE REQUIRED","QUOTE REQUIRED","QUOTE REQUIRED","QUOTE REQUIRED",
   "QUOTE REQUIRED - must ask","QUOTE REQUIRED",
   "3 - HIGH","Best documented turnkey operational fit found; handles blending + co-pack + salt blends in one place."),
 p("PP-04","Specialty Food Co-Packers","USA","800-225-3826 · 915-769-0097","specialtyfoodcopackers.com (public site)",
   "Spices (powder filling), seasonings",
   "PACKING-ONLY and TURNKEY",
   "Claims USDA Organic + SQF + GMP facility, Kosher, dedicated gluten-free",
   "NOP organic handler certification specifically (SQF/GMP are NOT organic certs); certifier + number; customer-supplied ingredient policy",
   "QUOTE REQUIRED","QUOTE REQUIRED","QUOTE REQUIRED","QUOTE REQUIRED","QUOTE REQUIRED","QUOTE REQUIRED","QUOTE REQUIRED",
   "QUOTE REQUIRED - must ask","QUOTE REQUIRED",
   "4 - HIGH","Dedicated powder-filling + gluten-free segregation claimed; relevant if Mogra needs allergen-safe packing."),
 p("PP-05","Organic Spices Inc.","USA (McKinney, TX)","organicspices.com (public site)","organicspices.com",
   "Bulk/wholesale organic spices; contract manufacturing + private label",
   "PACKING-ONLY and TURNKEY; also importer",
   "Claims 'comprehensive certified organic'; contract manufacturing + private label",
   "NOP handler certification; importer certification; certifier + number; customer-supplied ingredient policy",
   "QUOTE REQUIRED","QUOTE REQUIRED","QUOTE REQUIRED","QUOTE REQUIRED","QUOTE REQUIRED","QUOTE REQUIRED","QUOTE REQUIRED",
   "QUOTE REQUIRED - must ask","QUOTE REQUIRED",
   "5 - MEDIUM","McKinney TX organic-spice cluster; contract manufacturing + import capability in one firm."),
 p("PP-06","Spicy Organic","USA (McKinney, TX)","spicyorganic.com (public site)","spicyorganic.com/pages/wholesale-customers",
   "40+ USDA organic spices and herbs",
   "SUPPLY-ONLY (importer-wholesaler). Packing not evidenced.",
   "Only published quantity ladder found (5 lb to 44 lb)",
   "Organic certifier + number; finished-unit capability; customer-supplied ingredient policy",
   "5 lb (published)","QUOTE REQUIRED","QUOTE REQUIRED","QUOTE REQUIRED","QUOTE REQUIRED","QUOTE REQUIRED","QUOTE REQUIRED",
   "Not evidenced","QUOTE REQUIRED",
   "6 - MEDIUM","Lowest published entry quantity (5 lb) - useful for ingredient pilots under the $1,500-2,500 budget."),
 p("PP-07","Bata Food LLC / B.V.","Turkey / Netherlands / USA","batafood.com (public site); US office New Jersey","batafood.com/product/organic-black-pepper-whole",
   "Organic black pepper whole; bulk organic food ingredients",
   "SUPPLY-ONLY (importer-distributor with customs-cleared Rotterdam stock)",
   "Claims BRC/EU/USDA/TR organic/Kosher; only published MOQ (800 kg)",
   "Organic certification; handler scope if any; customer-supplied ingredient policy not applicable",
   "800 kg (published) - likely above a $1,500-2,500 pilot","QUOTE REQUIRED","QUOTE REQUIRED","QUOTE REQUIRED","QUOTE REQUIRED","QUOTE REQUIRED","QUOTE REQUIRED",
   "N/A - supply only","QUOTE REQUIRED",
   "7 - LOW for launch","800 kg MOQ is likely to exceed the stated product budget; hold as a scale-up option, not a pilot."),
 p("PP-08","Rocky Mountain Spice Company","USA","303-308-8066","rockymountainspice.com/co-packing/",
   "Custom blends; bags, pouches, plastic bottles; labelling + case assembly",
   "PACKING-ONLY and TURNKEY (blending)",
   "USDA Organic badge on site; Kosher/gluten-free options",
   "NOP certifier + number; customer-supplied ingredient policy; label-application capability",
   "QUOTE REQUIRED","QUOTE REQUIRED","QUOTE REQUIRED","QUOTE REQUIRED","QUOTE REQUIRED","QUOTE REQUIRED","QUOTE REQUIRED",
   "QUOTE REQUIRED - must ask","QUOTE REQUIRED",
   "8 - MEDIUM","Publishes labelling + case assembly explicitly; relevant to the provider-applied vs own-application label question."),
]
w("partner_decision_packet.csv",PP_H,PP)

# ============================================================ DATED LAUNCH SCHEDULE
LS_H=["seq","workstream","milestone","est_completion_date","responsible_role","dependencies",
      "evidence_required","status","consequence_of_delay","backup_action"]
def s(*a): return list(a)
LS=[
 s("1","Owner/scope","Confirm legal entity spelling (T2Holdings LLC)","2026-10-06","owner","-",
   "Business record showing exact registered name","planning allowance","All outreach blocked","Use a documented placeholder only; do not sign"),
 s("2","Supplier/samples","Final SKU decision (2-4, contingent on MOQ/economics)","2026-10-07","owner","1",
   "Signed-off SKU list","planning allowance","Cannot scope quotes or packaging","Launch 2 SKUs only"),
 s("3","Supplier/samples","Send partner RFQs (6 prepared)","2026-10-07","partner","1,2",
   "Sent RFQ records","planning allowance","No supplier responses; timeline slips","Send fewer, higher-priority RFQs"),
 s("4","Compliance/label","Commission customs-broker review","2026-10-08","partner","2",
   "Written broker position on HTS + AD/CVD","planning allowance","Landed cost invalid","Domestic-only routes"),
 s("5","Packaging/label","Provider-applied vs own-label decision (artwork supplied by us)","2026-10-09","owner","2,3",
   "Decision record + label spec","planning allowance","Packer quotes not comparable","Default to provider-applied for speed"),
 s("6","Supplier/samples","Supplier lead-time + MOQ responses received","2026-10-13","supplier","3",
   "Written quotes with lead times","planning allowance","Target becomes unsupportable","Reduce assortment / switch provider"),
 s("7","Supplier/samples","Sample requests issued","2026-10-13","partner","3,6",
   "Sample order confirmations","planning allowance","Sample approval slips","Expedite a single priority sample"),
 s("8","Packaging/label","Packer selection (same-company vs bulk+separate packer)","2026-10-14","partner","5,6",
   "Signed packer quote (packing-only or turnkey)","planning allowance","No production slot","Route A via Pearl only"),
 s("9","Compliance/label","Confirm packer NOP handler certification (not SQF/GMP)","2026-10-15","packer","8",
   "Certificate number + scope covering repacking","planning allowance","Organic claim unsafe","Drop organic claim; re-scope"),
 s("10","Supplier/samples","Sample evaluation + acceptance","2026-10-20","owner/partner","7",
   "Sample evaluation record + lot COA (heavy metals for cinnamon)","planning allowance","Cannot commit to production","Re-sample or switch supplier"),
 s("11","Packaging/label","Label artwork finalised to packer spec","2026-10-21","owner","5,8",
   "Final artwork files + packer confirmation of format","planning allowance","Printing delayed","Use plain/unbranded pilot units"),
 s("12","Packaging/label","Organic/label review (owner-reported approval; scope NOT audited)","2026-10-22","owner","11",
   "Owner confirmation of label approval","planning allowance","Claim risk on listing","Remove organic claim from label"),
 s("13","Compliance/label","Amazon category/grocery eligibility + FBA prep requirements confirmed","2026-10-22","partner","2",
   "Amazon guidance screenshots/notes","planning allowance","Listing blocked","Merchant-fulfilled fallback"),
 s("14","Supplier/samples","Production slot booked with packer/supplier","2026-10-23","packer","8,9,12",
   "Booking confirmation","planning allowance","Miss production window","Reduce volume / smaller run"),
 s("15","Supplier/samples","PRODUCTION COMPLETE (units built)","2026-10-31","packer","14",
   "Production completion report + lot records","planning allowance","Slips all downstream dates","Partial shipment of finished units"),
 s("16","Amazon/launch","Listing build (title, bullets, images, keywords)","2026-11-02","owner","11,13",
   "Listing content + image assets","planning allowance","Cannot go live at receipt","Draft listing ready in advance"),
 s("17","Amazon/launch","SHIPMENT DISPATCHED (leaves origin/packer)","2026-11-04","supplier/packer","15",
   "Bill of lading / carrier tracking","planning allowance","Arrival risk","Expedited freight"),
 s("18","Amazon/launch","DELIVERED TO AMAZON (arrives at fulfilment centre)","2026-11-12","Amazon/carrier","17",
   "Carrier delivery confirmation","planning allowance","Late receiving","Ship remainder later"),
 s("19","Amazon/launch","RECEIVED / AVAILABLE INVENTORY (check-in complete)","2026-11-22","Amazon","18",
   "FBA receiving/check-in confirmation","planning allowance","Not buyable by target","Merchant-fulfilled availability"),
 s("20","Amazon/launch","BUYABLE LISTING LIVE","2026-11-25","Amazon","19,16",
   "Live ASIN with active offer","planning allowance","Miss target; use latest 2026-12-01","Plan B merchant fulfilment"),
 s("21","Amazon/launch","Advertising activation (separate budget)","2026-11-25","owner","20",
   "Campaign structure + budget line","planning allowance","No traffic","Organic-only start"),
 s("22","Amazon/launch","Week-1 review: conversion + unit economics","2026-12-02","owner","21",
   "Metric snapshot","planning allowance","Blind scaling","Hold spend flat"),
 s("23","Amazon/launch","December decision: scale / adjust / reorder","2026-12-05","owner","22",
   "Decision record + actual costs","planning allowance","Stockout or waste","Conservative reorder"),
]
w("launch_schedule.csv",LS_H,LS)

# ============================================================ DECISION GATES
DG_H=["gate_id","trigger","decision_required","options","evidence_needed"]
def g(*a): return list(a)
DG=[
 g("G1","A priority supplier returns lead time > 3 weeks OR no response by 2026-10-13",
   "Reduce assortment / change provider","(a) cut to 1-2 SKUs (b) switch to US packer (c) shift target to 2026-12-01",
   "Written lead times from at least 2 providers"),
 g("G2","Packer cannot confirm NOP handler certification by 2026-10-15",
   "Change packer OR drop organic claim","(a) alternate packer (b) non-organic launch (c) defer organic SKUs",
   "Certificate number + scope covering repacking"),
 g("G3","Ceylon cinnamon lot COA shows heavy metals above the level Mogra will stand behind",
   "Change supplier OR change SKU","(a) alternate Ceylon supplier (b) swap to black pepper only","Lot-specific COA for the supplied lot"),
 g("G4","Quoted MOQ for a chosen SKU exceeds the $1,500-$2,500 product budget",
   "Reduce scope or SKU","(a) drop that SKU (b) find lower-MOQ provider (c) shrink pack size","Quotes with MOQ and unit cost"),
 g("G5","FBA receiving not confirmed by 2026-11-22",
   "Change fulfilment plan","(a) merchant-fulfilled availability (b) revise target to 2026-12-01","FBA receiving status"),
 g("G6","Landed cost (incl. duty/AD-CVD) makes contribution negative before advertising",
   "Change route or SKU","(a) domestic route (b) different SKU (c) different price point","Broker position + supplier quotes + FBA fee"),
 g("G7","Label approval scope is unclear or artwork misses packer spec by 2026-10-22",
   "Do not print / re-review","(a) plain pilot units (b) hold launch until approved","Owner confirmation + packer spec match"),
]
w("decision_gates.csv",DG_H,DG)

print("PARTNER PACKET BUILT")
