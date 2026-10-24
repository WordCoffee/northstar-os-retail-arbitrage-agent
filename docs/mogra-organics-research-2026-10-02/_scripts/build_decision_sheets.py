# Supplier / packager / shipping decision sheets + route speed ranking.
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

UR="UNKNOWN — CONFIRMATION REQUIRED"
QR="QUOTE REQUIRED"

# ============================================ SUPPLIERS (split: ingredient vs turnkey)
SD_H=["category","company","country","public_contact","products_and_exact_forms",
      "supply_only","turnkey_finished","evidence_status","documentation_gaps","moq",
      "price","stock_availability","sample_dispatch_time","production_packing_lead_time",
      "earliest_dispatch_date","est_arrival_us_packer","outreach_priority","priority_reason"]
def s(*x): return list(x)
SD=[
 # --- TURNKEY FINISHED-PRODUCT PROVIDERS ---
 s("Turnkey finished-product","Pearl Group Corporation","Vietnam","info@pearlflavor.com · +84 3727 2426 · vietnampepper.vn",
   "Black/white pepper; cinnamon/cassia; turmeric (fresh + dried sliced VERIFIED; powder CLAIMED); coriander, cumin, cardamom, fennel, mustard; dried herbs",
   "Yes (bulk possible)","Yes (private label/ODM/OEM claimed)","USDA-NOP VERIFIED 2026-10-02 (Control Union, CROPS+HANDLING)",
   "Cert number/expiry; exact certified facility; exporter-of-record match; ORGANIC STATUS OF PACKING; turmeric powder coverage; lot COA",
   QR,QR,UR,UR,UR,UR,UR,"1 — HIGH","Only independently verified organic status; broad certified range; potential single-source turnkey"),
 s("Turnkey finished-product","JAPC (Jaqon Lanka)","Sri Lanka","sales@japc.lk · +9476 800 0902 · japc.lk",
   "True Ceylon cinnamon; black/white pepper; turmeric; ginger; cardamom; cloves; nutmeg; herbs",
   "Yes","Yes (private label low MOQ claimed)","PROVISIONAL — names Control Union; no cert number",
   "Cert number/scope/expiry; USDA OID confirmation; packing-facility organic status; lot COA",QR,QR,UR,UR,UR,UR,UR,"2 — HIGH",
   "Certifier named and independently checkable; Ceylon is the priority cinnamon origin"),
 s("Turnkey finished-product","Spices Inc.","USA (Lowell MA)","spicesinc.com","Spice ingredients, custom blends, salt and smoked/flavoured salt blends",
   "No (sourcing-led)","Yes (sourcing + blending + co-pack)","Claims organic capability; no certifier named",
   "USDA-NOP handler cert (distinct from SQF/GMP); certifier + number; customer-supplied ingredient policy",QR,QR,UR,UR,UR,UR,UR,"3 — HIGH",
   "Best documented turnkey fit; blending + co-pack + salt in one firm"),
 s("Turnkey finished-product","Specialty Food Co-Packers","USA","800-225-3826 · 915-769-0097","Spices (powder filling), seasonings",
   "No","Yes","Claims USDA Organic + SQF + GMP facility, Kosher, gluten-free",
   "NOP handler cert specifically (SQF/GMP are NOT organic certs); customer-supplied ingredient policy",QR,QR,UR,UR,UR,UR,UR,"4 — HIGH",
   "Dedicated powder filling + gluten-free segregation claimed"),
 s("Turnkey finished-product","Organic Spices Inc.","USA (McKinney TX)","organicspices.com","Bulk/wholesale organic spices; contract manufacturing; private label",
   "Yes (importer)","Yes","Claims 'comprehensive certified organic'","NOP handler cert; importer cert; customer-supplied ingredient policy",
   QR,QR,UR,UR,UR,UR,UR,"5 — MEDIUM","Cluster + contract manufacturing + import capability in one firm"),
 s("Turnkey finished-product","Rocky Mountain Spice Company","USA","303-308-8066","Custom blends; bags, pouches, plastic bottles; labelling + case assembly",
   "No","Yes (blending + packing)","USDA Organic badge; no certifier named","NOP certifier + number; label-application capability",
   QR,QR,UR,UR,UR,UR,UR,"8 — MEDIUM","Publishes labelling + case assembly explicitly"),
 # --- INGREDIENT SUPPLIERS (supply-only) ---
 s("Ingredient supplier","Spicy Organic","USA (McKinney TX)","spicyorganic.com","40+ USDA organic spices and herbs (powder/whole)",
   "Yes","Not evidenced","Only published quantity ladder (5 lb – 44 lb)","Organic certifier + number; finished-unit capability",
   "5 lb (published)",QR,UR,QR,UR,UR,UR,"6 — MEDIUM","Lowest published entry quantity — fits a small pilot budget"),
 s("Ingredient supplier","Bata Food LLC / B.V.","Turkey / Netherlands / USA","batafood.com; US office New Jersey","Organic black pepper whole; bulk organic ingredients",
   "Yes","No","Claims BRC/EU/USDA/TR organic/Kosher","Organic certification; handler scope","800 kg (published)",QR,UR,UR,UR,UR,UR,"7 — LOW for launch",
   "800 kg MOQ likely exceeds the $1,500–2,500 budget; scale-up option, not a pilot"),
 s("Ingredient supplier","Prime Food Products (Pvt) Ltd","Sri Lanka","primefoodproducts.com","Black pepper whole/cut/powdered; retail pouches 100g–1kg",
   "Yes","Partial (private label claimed)","Claims USDA organic with piperine/density specs","Certificate number; packing organic status; price",
   QR,QR,UR,QR,UR,UR,UR,"9 — MEDIUM","Claims USDA organic on pepper with public specs"),
]
w("supplier_decision_sheets.csv",SD_H,SD)

# ============================================ PACKAGERS
PK_H=["provider_class","company","location","public_contact","customer_supplied_ingredients",
      "whole_spice_capability","powder_capability","stock_jars_pouches","filling","sealing",
      "lot_date_coding","label_application","organic_handling_capability_and_evidence",
      "minimum_run","setup_charges","receiving_storage_charges","earliest_production_slot",
      "finished_goods_ready_date","fba_prep_and_carrier_pickup","distance_to_us",
      "outreach_priority","notes"]
def p(*x): return list(x)
PK=[
 p("Food co-packer / filler","Specialty Food Co-Packers","USA (TX per public contact)","800-225-3826 · 915-769-0097",
   "UNKNOWN — CONFIRMATION REQUIRED","Claimed spice range (whole not separately evidenced)","YES — powder filling is the stated capability",
   "UNKNOWN","Claimed","Claimed","UNKNOWN","UNKNOWN","USDA Organic + SQF + GMP CLAIMED; NOP handler cert NOT confirmed",
   QR,QR,QR,UR,UR,"UNKNOWN — confirm","OWNER_INPUT_REQUIRED — no pickup/delivery ZIP provided","4 — HIGH",
   "Gluten-free segregation claimed"),
 p("Food co-packer / filler","Spices Inc.","Lowell, MA","spicesinc.com",
   "UNKNOWN — CONFIRMATION REQUIRED","YES (sourcing-led)","YES — blending + co-pack",
   "UNKNOWN","Claimed","Claimed","UNKNOWN","Claimed (private/white label)","Organic claimed; no certifier named",
   QR,QR,QR,UR,UR,"UNKNOWN - confirm","OWNER_INPUT_REQUIRED","3 - HIGH","Salt blend capability adds optionality"),
 p("Turnkey ingredient + packing","Organic Spices Inc.","McKinney, TX","organicspices.com",
   "UNKNOWN — CONFIRMATION REQUIRED","YES","YES","UNKNOWN","Claimed (contract manufacturing)","Claimed","UNKNOWN","Claimed",
   "Certified-organic range claimed; NOP handler cert NOT confirmed",QR,QR,QR,UR,UR,"UNKNOWN - confirm","OWNER_INPUT_REQUIRED","5 - MEDIUM",
   "Importer + co-packer in one firm"),
 p("Turnkey ingredient + packing","Rocky Mountain Spice Company","USA (303-308-8066 public)","303-308-8066",
   "UNKNOWN — CONFIRMATION REQUIRED","Claimed","Claimed (custom blending)","Bags, pouches, plastic bottles stated",
   "Claimed","Claimed","Claimed","YES — labelling + case assembly explicitly stated","USDA Organic badge; NOP certifier NOT named",
   QR,QR,QR,UR,UR,"UNKNOWN — confirm","OWNER_INPUT_REQUIRED","8 — MEDIUM",
   "Strongest published evidence of label application capability"),
 p("Turnkey ingredient + packing","Pearl Group Corporation","Ho Chi Minh City, Vietnam","info@pearlflavor.com",
   "N/A — supplies own ingredient","Claimed","Claimed","Bulk bags, pouches, jars, retail-ready stated",
   "Claimed","Claimed","UNKNOWN","Claimed (private label/ODM/OEM)","Ingredient organic VERIFIED; PACKING organic status UNCONFIRMED",
   QR,QR,QR,UR,UR,"UNKNOWN — confirm","N/A — international","1 — HIGH",
   "Packing organic scope is the open question, not capability"),
 p("Sealed-unit label / FBA-prep (NOT a food repacker)","(Amazon FBA prep centres generally)","Varies by programme",
   "Via Amazon Seller Central","N/A","N/A — NOT established","N/A — NOT established","N/A",
   "N/A","N/A","N/A","FNSKU labelling / poly-bagging only",
   "CAUTION: an FBA prep centre is NOT established as authorised to open, reseal or repack food",
   "N/A","N/A",QR,"N/A","N/A","Standard prep + carrier partner pickup","N/A","DO NOT ASSUME",
   "Use only for label application and poly-bagging of already-sealed units. Food repacking requires a qualified food packer."),
]
w("packager_decision_sheets.csv",PK_H,PK)

# ============================================ SHIPPING OPTIONS
SO_H=["option","company_or_service","official_contact_or_quote_link","origin_pickup_coverage","transport_mode",
      "door_to_door_vs_terminal","customs_brokerage","food_organic_acceptance_questions","required_shipment_info",
      "published_transit_indication","actual_delivery_estimate","cost_coverage","suitability_small_initial_order",
      "recommended_next_quote_request","notes"]
def o(*x): return list(x)
SO=[
 o("B — Buyer-arranged international express","DHL Express Worldwide","https://www.mydhl.com · quote via DHL Express MyDHL / account manager",
   "Supplier-arranged pickup to DHL origin facility (must be booked)","Air express",
   "Door-to-door","Customs clearance via DHL Express / DHL Global Forwarding; confirm whether duty/tax is prepaid or collect",
   "Ask: perishable/food acceptance, temperature not required for dry spices, organic paperwork acceptance, country-specific food import rules",
   "Commercial invoice, packing list, HS code, Incoterm + named place, declared value, organic/transaction certificate, phytosanitary if required",
   "DHL states international express typically 1–3 business days transit; customs clearance usually on arrival but can add several days if flagged",
   "QUOTE REQUIRED","Origin pickup/export charges + main transport + insurance + clearance + destination handling + delivery — itemise each",
   "Reasonable for a small, high-value, time-critical parcel","Quote door-to-door delivered cost incl. duties for the exact origin and destination ZIP",
   "Do not treat airport transit as the delivered date"),
 o("B — Buyer-arranged international express","FedEx International Priority","https://www.fedex.com/en-us/shipping/international-1-5-day.html · quote/rate calculator",
   "Supplier-arranged pickup to FedEx origin","Air express","Door-to-door, customs-cleared",
   "FedEx International Priority is customs-cleared; confirm duty/tax payment terms",
   "Ask: food/agri acceptance, dry-spice commodity, organic documents, any restricted-food rules by destination",
   "Commercial invoice, packing list, HS code, Incoterm + named place, declared value, organic certificate",
   "FedEx states International Priority delivers in 1–3 business days to many destinations",
   "QUOTE REQUIRED","Same itemisation as above — origin pickup, transport, insurance, clearance, destination handling, delivery",
   "Reasonable for small urgent parcel","Quote delivered cost for exact origin + destination ZIP, and confirm duties prepaid vs collect",
   "Express transit is door-to-door and customs-cleared, but clearance delays can still apply"),
 o("B — Buyer-arranged international express","UPS Worldwide Expedited / Saver","https://www.ups.com/us/en/support/international-tools-resources/international-shipping-services",
   "Supplier-arranged pickup to UPS origin","Air express","Door-to-door; day-definite (Expedited)",
   "UPS customs brokerage available; confirm duty/tax terms",
   "Ask: food/agri acceptance, dry commodity, organic paperwork, import restrictions",
   "Commercial invoice, packing list, HS code, Incoterm + named place, declared value, organic certificate",
   "UPS states Worldwide Expedited delivers in 2–5 business days; Saver typically 1–3 business days",
   "QUOTE REQUIRED","Same itemisation","Reasonable for small urgent parcel","Quote delivered cost for exact lanes",
   "Expedited is day-definite; Saver is typically faster/cheaper — confirm which service is quoted"),
 o("C — Independent air-freight forwarding","DHL Global Forwarding (air)","https://www.mhl-dgf.com · request an international freight quote",
   "Forwarder arranges origin pickup","Air freight (consolidated or direct)",
   "Can be door-to-door or airport-to-airport — CONFIRM","Forwarder-managed clearance can be quoted; confirm inclusions",
   "Ask: food/dry-commodity acceptance, organic docs, DG-free status for dry powder",
   "Cargo details: cartons, weight, dimensions, commodity description, HS code, origin/destination, declared value, Incoterm",
   "DHL states it provides immediate air-freight quotation for general cargo up to ~2,000 kg per shipment; transit QUOTE REQUIRED",
   "QUOTE REQUIRED","Origin handling + freight + clearance + destination + delivery — itemise; watch minimum charges and airport terminal fees",
   "Possible for consolidation; overhead may exceed value on a small order","Request a delivered quote and ask explicitly what is excluded",
   "Airport-to-airport pricing must not be compared with a delivered quote without adding remaining charges"),
 o("D — Ocean LCL (only if size/timeline justify)","DHL Global Forwarding (ocean LCL)","https://www.mhl-dgf.com · LCL product page",
   "Consolidation required — not viable for one small parcel","Ocean LCL",
   "Terminal-to-terminal more common; door delivery an extra service","Forwarder-managed; confirm","Ask: dry-commodity acceptance, food import requirements",
   "Cargo + cartons + weight/volume + HS code + ports + Incoterm","DHL cites 2,800+ weekly LCL services; transit QUOTE REQUIRED",
   "NOT SUITABLE for a small time-critical launch order — LONGER-TERM OPTION",
   "Origin CFS + ocean + destination CFS + clearance + delivery + demurrage risk — itemise",
   "POOR for this launch","Do not request for the first shipment; revisit at scale",
   "LCL consolidation and demurrage make this unsuitable for a small launch order"),
 o("A — Factory/supplier-arranged shipping","Supplier's own forwarder / EXW or FCA terms","Supplier contact (per supplier sheet)",
   "Supplier arranges everything","Supplier's choice — often sea or air",
   "Depends on Incoterm","Supplier's broker or buyer's — depends on terms","Ask the supplier who arranges and who holds documents",
   "Supplier handles; buyer must still receive documents for import","Supplier-stated only — UNCONFIRMED",
   "UNRANKED — CONFIRMATION REQUIRED","Often quoted FOB/CIF only — does NOT include destination charges",
   "Poor unless supplier holds a strong delivered rate","Ask each supplier for a delivered (DAP/DDP) quote to the US packer ZIP",
   "FOB/CIF quotes exclude destination charges — do not compare with delivered quotes"),
 o("E — Domestic parcel or LTL, supplier → packer","US carriers (UPS / FedEx / DHL domestic)","Carrier sites",
   "n/a (domestic leg)","Parcel or LTL","Door-to-door","Domestic — no customs","n/a",
   "Packing list + weight/dims + labels","Carrier published transit (1–5 business days typical)","QUOTE REQUIRED",
   "Pickup + linehaul + residential/commercial delivery","GOOD — likely the simplest completed route",
   "Quote domestic leg only, separately","Cheapest when the first shipment is domestic"),
 o("F — Domestic packer → Amazon","Packer-arranged to FBA, or Amazon Partner Carrier","Via packer, or Amazon Partner Carrier options where eligible",
   "n/a","Parcel or LTL (less often air)","To Amazon fulfilment centre","n/a","n/a",
   "FNSKU labels, carton labels, weights/dims","QUOTE REQUIRED","QUOTE REQUIRED",
   "Inbound transportation + placement fees are SEPARATE Amazon charges","GOOD","Confirm FBA destination before quoting",
   "Domestic packer-to-Amazon leg; quote after FBA destination is fixed"),
 o("G — Amazon Partner Carrier","Amazon Partner Carrier Options","Via Seller Central (where eligible)","n/a",
   "Parcel / LTL","To Amazon fulfilment centre","n/a","n/a","FNSKU + carton labels","QUOTE REQUIRED","QUOTE REQUIRED",
   "Partner-carrier pricing plus Amazon inbound placement fees","Depends on eligibility and shipment size","Confirm eligibility in Seller Central before relying on it",
   "Partner-carrier pricing is separate from Amazon inbound placement fees"),
 o("Comparison platform (NOT a carrier)","Freightos / similar marketplaces","https://www.freightos.com",
   "Aggregates quotes from carriers/forwarders","Depends on selected carrier","Depends on selected carrier",
   "Varies by quote","Varies","Varies","Marketplace — QUOTE REQUIRED","QUOTE REQUIRED",
   "Use to COMPARE quotes; the actual performing carrier must be identified per quote","Useful for benchmarking only",
   "Use to compare; then confirm the performing carrier and what the price includes","Do not treat the platform as the carrier performing pickup"),
]
w("shipping_options_comparison.csv",SO_H,SO)

# ============================================ SHIPPING INPUT CHECKLIST
SI_H=["id","input_required","why_needed","owner","status","blocks_comparison"]
def i(*x): return list(x)
SI=[
 i("SI-01","Exact origin pickup address","Determines origin charges and availability","owner","OWNER_INPUT_REQUIRED","All international quotes"),
 i("SI-02","Delivery ZIP / address (US packer)","Determines destination charges and transit","owner","OWNER_INPUT_REQUIRED","All international + domestic quotes"),
 i("SI-03","Commodity and exact product form","Drives acceptance rules and HS classification","partner","OWNER_INPUT_REQUIRED","Carrier acceptance"),
 i("SI-04","Origin country","Drives customs entry and import rules","partner","PARTIALLY KNOWN (per provider)","Customs quote"),
 i("SI-05","Carton count and dimensions","Air freight chargeable weight; parcel limits","partner","UNKNOWN","Freight quote"),
 i("SI-06","Gross weight","Chargeable weight (actual vs volumetric)","partner","UNKNOWN","Freight quote"),
 i("SI-07","Pallet information where applicable","LTL / FBA pallet dimensions","partner","UNKNOWN","LTL quote"),
 i("SI-08","Declared value","Insurance and customs valuation","owner","UNKNOWN","Insurance + customs"),
 i("SI-09","Ready-for-pickup date","Anchors transit and buffer","partner","UNKNOWN","Delivery estimate"),
 i("SI-10","Import documents available","Invoice, packing list, HS code, organic certificate, phytosanitary if required","partner","PARTIALLY KNOWN","Customs clearance"),
 i("SI-11","Incoterm and named place","Determines who pays which legs","owner","NOT AGREED","Cost split"),
 i("SI-12","Pickup/delivery ZIP for 'nearby' screening","Distance claims require our actual ZIP","owner","OWNER_INPUT_REQUIRED","Packager proximity"),
 i("SI-13","Amazon FBA destination","Final leg destination","owner","UNKNOWN","Amazon leg quote"),
 i("SI-14","Amazon inbound placement fee schedule","Separate charge from transport","partner","UNKNOWN","Landed cost"),
]
w("shipping_input_checklist.csv",SI_H,SI)

# ============================================ ROUTE SPEED RANKING
RS_H=["route_id","route_description","product_order_size_fit","documentation_readiness",
      "earliest_credible_finished_unit","route_label","critical_unresolved","source_confirmed_vs_planning","notes"]
def r(*x): return list(x)
RS=[
 r("R1","US turnkey (US packer sources + packs, e.g. McKinney TX cluster)","Best fit for a 2–4 SKU pilot at $1,500–2,500",
   "Organic certifier names still unconfirmed","UNKNOWN — depends on packer lead time, not yet quoted",
   "POTENTIALLY FEASIBLE","No import; packer organic handler cert unconfirmed; no quotes","PLANNING ALLOWANCE ONLY",
   "Fewest legs and lowest customs risk, but no supplier has confirmed a lead time"),
 r("R2","Overseas turnkey finished units (Pearl / JAPC)","Only route where one supplier covers ingredient AND packing",
   "Pearl ingredient organic VERIFIED; PACKING organic status UNCONFIRMED","UNKNOWN — production + export readiness unconfirmed",
   "TIMING RISK","Export documentation readiness, packing organic scope, production slot, ocean/air cut-off","PLANNING ALLOWANCE ONLY",
   "Do not rank overseas as fast merely because air freight exists — production readiness and export docs gate it"),
 r("R3","Overseas bulk + US co-packer","Ingredient verified for Pearl; co-packer unverified",
   "Bulk organic verified (Pearl); co-packer NOP handler cert unconfirmed","UNKNOWN — depends on origin production AND US packer slot",
   "TIMING RISK","Two contracts; import customs release; organic-importer obligation; two lead times in series","PLANNING ALLOWANCE ONLY",
   "Most control, most coordination, most dependent on two separate lead times"),
 r("R4","US ingredients + US packer (domestic only)","Avoids all import legs","No import documentation required",
   "UNKNOWN — depends on packer slot","LONGER-TERM OPTION","Higher ingredient cost unproven; thin supplier evidence",
   "PLANNING ALLOWANCE ONLY","Simplest customs-wise; cost hypothesis not proven"),
 r("R5","Any route where supplier lead time is unknown","Cannot be ranked at all","n/a",
   "UNRANKED — CONFIRMATION REQUIRED","UNRANKED / CONFIRMATION REQUIRED",
   "No supplier has provided a production or packing lead time","n/a",
   "Per instruction: where timing is unknown, do not silently assign a favourable estimate"),
]
w("route_speed_ranking.csv",RS_H,RS)

print("DECISION SHEETS BUILT")
