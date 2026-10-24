# Build the new canonical tables for the Mogra review packet.
import csv, os

ROOT = os.path.join("docs", "mogra-organics-research-2026-10-02")
os.makedirs(ROOT, exist_ok=True)

def w(name, header, rows):
    p = os.path.join(ROOT, name)
    n = len(header); bad = 0; fixed = []
    for i, r in enumerate(rows, 1):
        if len(r) != n:
            bad += 1
            print(f"  !! {name} row {i}: {len(r)} cols, expected {n}")
            r = (list(r) + [""] * n)[:n]
        fixed.append(r)
    with open(p, "w", newline="", encoding="utf-8") as f:
        cw = csv.writer(f, quoting=csv.QUOTE_MINIMAL)
        cw.writerow(header)
        for r in fixed:
            cw.writerow(r)
    print(f"{name}: {len(fixed)} rows, {bad} mismatches")

# ============================================================ EVIDENCE REGISTER
EV_H = ["evidence_id","claim","claim_status","supplier_ids","product","route","source_title",
        "source_url_or_path","quote_or_reference","observation_date","source_date","limitations"]
EV = [
["EV-001","PEARL GROUP CORPORATION (PEARL GROUP) holds current USDA-NOP certification","VERIFIED","pearl-group","all","A/B/C","USDA Organic Integrity Database (live search)","https://organic.ams.usda.gov/integrity/","Operation return: Program USDA-NOP; Certifier [CUC] Control Union Certifications B.V.; Status Certified; Country Viet Nam; Scope CROPS + HANDLING","2026-10-02","live","Product list capture was truncated at ~5000 chars; certificate number and expiry not captured; street address blank so strict name+address match not performed"],
["EV-002","Pearl certified product list includes Organic Whole Black Pepper and Organic Ground Black Pepper","VERIFIED","pearl-group","black pepper","A/B","USDA Organic Integrity Database","https://organic.ams.usda.gov/integrity/","OID strings: 'Spices (Organic Whole Black Pepper)', 'Spices (Organic Ground Black Pepper)'","2026-10-02","live","Observed in a truncated capture"],
["EV-003","Pearl certified product list includes Organic Dried Sliced Turmeric and Organic Fresh Turmeric","VERIFIED","pearl-group","turmeric","A/B","USDA Organic Integrity Database","https://organic.ams.usda.gov/integrity/","OID strings: 'Spices (Organic Dried Sliced Turmeric)', 'Spices (Organic Fresh Turmeric)'","2026-10-02","live","Truncated capture; does NOT establish organic turmeric POWDER"],
["EV-004","Pearl advertises 'Organic Tumeric Powder' on its own website","SUPPLIER_CLAIMED","pearl-group","turmeric","A/B","Pearl Group website","https://vietnampepper.vn/spice-packaging","Site product menu lists 'Organic Tumeric Powder' under Organic Spices","2026-10-02","live","Marketing listing; not certification evidence. Does not upgrade powder to verified"],
["EV-005","Pearl advertises private label / ODM / OEM and bulk, pouch, jar and retail-ready packing","SUPPLIER_CLAIMED","pearl-group","all","A","Pearl Group website - Spice Packaging","https://vietnampepper.vn/spice-packaging","'The same product can be packed in multiple options, including bulk bags, pouches, jars, and retail-ready packaging, with flexible sizes and labeling.'","2026-10-02","live","Capability claim. Says nothing about the organic certification status of the packing operation"],
["EV-006","JAPC names Control Union as its organic certifier","PROVISIONAL","japc","turmeric, black pepper","A/B","JAPC Certifications page","https://japc.lk/certifications","'Control Union Certified ... audits our organic practices, from seed to export'; also claims USDA Organic (NOP), EU, JAS, Demeter, Naturland, Bio Suisse, FSSC 22000, FDA registration","2026-10-02","live","Certifier named but NO certificate number, scope or expiry found; not confirmed in USDA OID. JAPC uses Control Union, the same certifier verified for Pearl"],
["EV-007","Amazon Andes names Control Union Peru and claims an active USDA NOP/COR/EU certificate","SUPPLIER_CLAIMED","amazon-andes","turmeric","B","Amazon Andes website","https://amazon-andes.com/raw-materials/superfoods/turmeric-wholesale-organic-supplier","'We hold an active certificate issued by Control Union Peru for USDA-NOP, COR and EU Organic'","2026-10-02","live","Certificate document NOT sighted; certifier is independently checkable"],
["EV-008","Bata Food publishes an MOQ of 800 kg on organic black pepper whole","SUPPLIER_CLAIMED","bata-food","black pepper","B","Bata Food product page","https://batafood.com/product/organic-black-pepper-whole","'Minimum Order Quantity | 800 kg'","2026-10-02","live","MOQ claim only; no pricing published"],
["EV-009","Spicy Organic publishes a wholesale quantity ladder from 5 lb to 44 lb","SUPPLIER_CLAIMED","spicy-organic","all spices","C","Spicy Organic wholesale page","https://spicyorganic.com/pages/wholesale-customers","'Wholesale bulk sizes from 5 lb to 44 lb'","2026-10-02","live","Quantity ladder published; NO prices. Organic certifier not named"],
["EV-010","Cargill sea salt states it contains no anticaking or free-flowing agents","SUPPLIER_CLAIMED","cargill-sea-salts","salt","B/C","Cargill Sea Salts","https://www.cargill.com/food-beverage/na/sea-salts","'Contains no anticaking or free flowing'","2026-10-02","live","Additive-free claim; plain salt cannot be USDA organic regardless"],
["EV-011","Plain culinary salt cannot carry USDA organic certification","VERIFIED","(all salt suppliers)","salt","all","USDA NOP regulatory framework","USDA AMS National Organic Program","Mineral, not an agricultural product; no NOP certification pathway for plain salt","2026-10-02","regulatory","Regulatory position, not a supplier fact. Blends containing salt are assessed separately"],
["EV-012","AD/CVD duties are not part of the Harmonized Tariff Schedule","VERIFIED","(all import routes)","all","A/B","USITC FAQ","https://www.usitc.gov/faq/question/are_adcvd_duties_hts.htm","'Antidumping and countervailing duties (AD/CVD) are not ordinary customs tariffs and are not in the HTS'","2026-10-02","live","Supports the position that AD/CVD must be checked via orders/scope, not read from HTS"],
["EV-013","No AD/CVD order covering black pepper or turmeric from in-scope origins has been confirmed","UNKNOWN","(all import routes)","black pepper, turmeric","A/B","ITA AD/CVD search portal (identified, not queried per product)","https://access.trade.gov/adcvd/","Portal reachable (HTTP 200); supports search by HTS number. Not queried product-by-product; endpoints not reverse-engineered","2026-10-02","live","Absence of a confirmed order is NOT confirmation that no order applies. Flagged for customs-broker review"],
["EV-014","Control Union certificate verification is behind a client-portal login","VERIFIED","pearl-group, amazon-andes, japc","all","A/B","Control Union certificate listing","https://certifications.controlunion.com/en/certificate-listing","Page reachable; certificate lookup routes to ICU / CIS / CUCERT client portals requiring login","2026-10-02","live","Not publicly queryable without an account; account creation prohibited by task. Route therefore runs via supplier certificate PDF + USDA OID"],
["EV-015","USDA Organic Integrity Database is publicly searchable without login","VERIFIED","(all)","all","all","USDA Organic Integrity Database","https://organic.ams.usda.gov/integrity/","Search UI returns operation records without authentication; one query (Pearl Group) succeeded","2026-10-02","live","Automated interaction unreliable (force-click returns unfiltered results). Manual lookup recommended"],
["EV-016","Frontier Co-op and Starwest Botanicals organic handler certification was NOT independently verified","UNKNOWN","frontier-coop, starwest-botanicals","all spices","B/C","These suppliers were named as benchmark seeds in the brief","(brief-supplied)","No certificate document or OID record sighted in any session","2026-10-02","n/a","Reputation is not evidence. Recorded to prevent a supplier-wide grade implying product approval"],
["EV-017","Especias Moy states products 'passed FDA, USDA and Customs requirements'","SUPPLIER_CLAIMED","especias-moy","spices","C","Especias Moy About page","https://especiasmoy.mx/en/nosotros","'Our products have passed FDA, USDA and Customs requirements'","2026-10-02","live","Ambiguous: most likely US import/customs compliance, NOT USDA NOP organic. NOT evidence of organic certification; NOT a contradictory claim either"],
["EV-018","Vietnam was the leading pepper exporter in 2024-2025 with the US as largest market","VERIFIED","(market anchor)","black pepper","A/B","Vietnam Pepper and Spice Association via government trade portal","https://asemconnectvietnam.gov.vn/default.aspx?ID1=2&ID8=146381","2025: 247,482 t total; US took 55,082 t (22.3%); avg black pepper export price US$6,607/t","2026-10-02","2026-01","Publicly reported industry aggregate. Used as a sanity-check anchor only, NOT a supplier quote"],
["EV-019","Spice and seasoning imports generally attract low base duty in Chapter 9","PROVISIONAL","(all import routes)","all","A/B","Peacock Tariff Consulting spice import guide (industry summary)","https://www.peacocktariffconsulting.com/spice-import-tariff/","'Most spices low base duty (0-3%). Section 122 stacks.'","2026-10-02","live","Industry secondary source, not an official rate table. Exact duty must be read from current USITC HTS"],
["EV-020","JAPC claims 3,500+ organic farmer families and in-house steam sterilization","SUPPLIER_CLAIMED","japc","turmeric, pepper","A/B","JAPC website","https://japc.lk/organic-turmeric","'Sourced from over 3,500 small-scale organic farmer families'; 'In-house steam sterilization'","2026-10-02","live","Supplier marketing"],
]

w("evidence_register.csv", EV_H, EV)

# ============================================================ PRODUCT ROUTE READINESS
PR_H = ["readiness_id","product","form","route","route_label","best_supported","plausible_alternative",
        "insufficiently_evidenced","purchase_ready","requirements_met","missing_gates","principal_risk","next_closure_action"]
PR = [
["PR-01","Black pepper","whole","A","Overseas finished/private-label","YES - for investigation","","","NO","Verified organic bulk supply (Pearl); packing capability claimed","Certified finished-unit packing scope; MOQ; price; NOP Import Certificate for finished goods; label review","A finished unit may not be seal-eligible even if the ingredient is certified","Request Pearl certificate PDF + packing-scope confirmation (RFQ P2)"],
["PR-02","Black pepper","ground","A","Overseas finished/private-label","YES - for investigation","","","NO","Ground pepper verified organic at Pearl","Certified grinding/filling scope; consumer-format packing; price","Ground pepper is a distinct certified line from whole","Confirm grinding within certified HANDLING scope"],
["PR-03","Black pepper","whole","B","Overseas bulk + US co-packer","YES - parallel","","","NO","Pearl verified organic bulk","US co-packer NOP handler certification; bulk price; freight/duty; co-pack MOQ","Organic status of the US co-packer is unverified","Verify NOP handler cert for Spices Inc and Specialty Food Co-Packers (P3)"],
["PR-04","Black pepper","whole","C","US organic ingredient + US co-packer","","YES - alternative","","NO","Fully domestic; no import","US organic ingredient verification; co-packer NOP cert; ingredient price","US organic ingredient cost likely higher (unproven)","Verify Spicy Organic / Spices Inc organic evidence (P6)"],
["PR-05","Turmeric","powder","A","Overseas finished/private-label","NO - blocked on powder evidence","","YES","NO","Pearl powder is supplier-claimed only","Organic powder certification on the certificate/addendum; packing scope; price","Do NOT infer powder organic status from fresh/sliced turmeric","Obtain full OID list or certificate addendum naming turmeric powder (P1)"],
["PR-06","Turmeric","powder","B","Overseas bulk + US co-packer","YES - for investigation","","","NO","Radiance/Amazon Andes bulk turmeric candidates","Organic verification; bulk price; US co-packer NOP cert","Bulk organic turmeric not yet verified except Pearl (powder unconfirmed)","Sight Amazon Andes Control Union Peru certificate (P2)"],
["PR-07","Turmeric","powder","C","US organic ingredient + US co-packer","","","YES","NO","Fully domestic","US organic turmeric supply is thin; White Rabbit is pilot-scale","Volume capacity may not support launch scale","Confirm White Rabbit volume capacity and powder capability (P13)"],
["PR-08","Turmeric","dried sliced","A","Overseas finished/private-label","YES - for investigation","","","NO","Dried sliced turmeric VERIFIED organic at Pearl","Consumer-format packing scope; price; MOQ","Sliced form is not a typical culinary powder SKU","Clarify whether a sliced SKU is intended"],
["PR-09","Herbs (basil, thyme, rosemary, parsley, dill, mint)","dried cut & sifted","A","Overseas finished/private-label","YES - for investigation","","","NO","Pearl certified for these herbs (observed)","Packing scope; pricing; MOQ","Truncated OID capture - list not fully enumerated","Request full certified product list"],
["PR-10","Salt (plain)","grain / flake","B/C","US domestic supply","","YES","","NO","Additive-free evidence available (Cargill)","Plain salt cannot be organic - N/A; grain size; food-grade docs","Salt cannot carry the organic seal","Confirm additive declaration and grain sizes"],
["PR-11","Salt-containing seasoning blend","blend","B/C","Blend with organic components","","YES","","NO","Only route to an organic claim on a salted product","Which components are organic; co-packer NOP cert; label pathway","Blend organic percentage drives labelling path","Ask Spices Inc about organic components and blend positioning"],
["PR-12","Cinnamon (Ceylon vs cassia)","whole / ground","A","Overseas finished/private-label","YES - for investigation","","","NO","Pearl certified for cinnamon/cassia (observed)","Species identity documentation; packing scope; price","Cassia vs Ceylon are different species and different regulatory expectations","Require species identity on spec, not inferred"],
]

w("product_route_readiness.csv", PR_H, PR)

# ============================================================ COST AND QUOTE MATRIX
CQ_H = ["cost_id","product","route","supplier","cost_line","unit","basis","one_time_or_recurring",
        "value_usd","status","source","notes"]
def row(pid, prod, route, sup, line, unit, basis, onetime, val, status, src, notes):
    return [pid, prod, route, sup, line, unit, basis, onetime, val, status, src, notes]
CQ = [
 row("CQ-001","All","A/B/C","Flavoric","Ingredient (published retail/tiered range)","lb","1-10 lb listed range","recurring","12.98-111.98","PUBLISHED_RETAIL_REFERENCE","pricing_comparison.csv","RETAIL/tiered reference, NOT a wholesale quote. Cannot be used as a wholesale cost"),
 row("CQ-002","Black pepper","A/B/C","Flavoric","Ingredient (published retail/tiered range)","lb","1-10 lb listed range","recurring","49.98-369.98","PUBLISHED_RETAIL_REFERENCE","pricing_comparison.csv","RETAIL reference only, NOT wholesale"),
 row("CQ-003","Salt blend","B/C","Spices Inc","Finished salt blend (published retail)","unit","retail unit","recurring","6.55","PUBLISHED_RETAIL_REFERENCE","pricing_comparison.csv","Chipotle salt retail price. NOT wholesale"),
 row("CQ-004","Black pepper","A","Pearl","Ingredient, bulk","kg","per kg","recurring","","QUOTE_REQUIRED","route_comparison.csv","No published price"),
 row("CQ-005","Black pepper","A","Pearl","Processing / packing into finished unit","unit","per finished unit","recurring","","QUOTE_REQUIRED","route_comparison.csv","Capability unconfirmed"),
 row("CQ-006","Black pepper","A","Pearl","Packaging (jar/pouch)","unit","per unit","recurring","","QUOTE_REQUIRED","route_comparison.csv","Formats unconfirmed"),
 row("CQ-007","Black pepper","A","Pearl","One-time setup / artwork / plates","USD","one-time","one_time","","QUOTE_REQUIRED","route_comparison.csv",""),
 row("CQ-008","Black pepper","B","Pearl + US co-packer","Ingredient, bulk","kg","per kg","recurring","","QUOTE_REQUIRED","route_comparison.csv",""),
 row("CQ-009","Black pepper","B","US co-packer","Packing-only service fee","unit","per finished unit","recurring","","QUOTE_REQUIRED","route_comparison.csv",""),
 row("CQ-010","Black pepper","B","US co-packer","Co-packer setup / plate","USD","one-time","one_time","","QUOTE_REQUIRED","route_comparison.csv",""),
 row("CQ-011","Turmeric","A","Pearl","Ingredient, bulk","kg","per kg","recurring","","QUOTE_REQUIRED","route_comparison.csv","Powder form unconfirmed"),
 row("CQ-012","Turmeric","B","Amazon Andes","Ingredient, bulk","kg","per kg","recurring","","QUOTE_REQUIRED","route_comparison.csv","Certifier named; certificate not sighted"),
 row("CQ-013","All","A/B","(freight forwarder)","Ocean freight + insurance","shipment","per shipment","recurring","","QUOTE_REQUIRED","duty_and_import_review.md","Incumbent on Incoterm; not quoted"),
 row("CQ-014","All","A/B","(customs broker)","Duty + entry + broker fees","shipment","per shipment","recurring","","UNKNOWN","duty_and_import_review.md","HTS not confirmed; AD/CVD scope unresolved. BROKER REVIEW REQUIRED"),
 row("CQ-015","All","A/B/C","(lab)","Testing (COA / heavy metals / pesticides / aflatoxin)","lot","per lot","recurring","","QUOTE_REQUIRED","supplier_questions.md","Scope depends on supplier COA coverage"),
 row("CQ-016","All","A/B/C","(certifier)","Organic certification of Mogra's own handling/import activity","USD","annual","recurring","","UNKNOWN","duty_and_import_review.md","Applicability depends on Mogra's chosen role; not quoted"),
 row("CQ-017","All","A/B","(3PL)","US storage / receiving","pallet/month","recurring","recurring","","UNKNOWN","(owner input)","Depends on volumes"),
 row("CQ-018","All","A/B/C","(Amazon)","Amazon referral + FBA fulfilment fees","unit","per unit","recurring","","UNKNOWN","(channel data not available)","No Amazon fee or sales data collected; MARKET_DATA_INCOMPLETE"),
]
w("cost_and_quote_matrix.csv", CQ_H, CQ)

# ============================================================ ASSUMPTIONS REGISTER
AS_H = ["assumption_id","scenario","assumption","value","unit","basis","why_this_scenario_exists",
        "isolated_from_observed_facts","sensitivity","status"]
AS = [
["AS-01","Illustrative pilot","Pilot finished-unit quantity","500","units","Illustrative only - NOT owner-approved demand","No owner volume supplied; a pilot needs SOME number to size packaging and MOQ conversations","YES - no observed fact depends on this","High: drives packaging setup amortisation","PROPOSED"],
["AS-02","Illustrative pilot","Retail pack net weight","2","oz","Illustrative","Common culinary spice pack size; not an owner decision","YES","Medium: drives units per lb of ingredient","PROPOSED"],
["AS-03","Illustrative","Ingredient yield loss in grinding/packing","2","%","Industry-typical placeholder","Applied so cost model is not implicitly zero-loss","YES","Low-Medium","PROPOSED"],
["AS-04","Illustrative","Organic premium on bulk ingredient vs conventional","20","%","Placeholder","Organic bulk typically prices above conventional; magnitude unverified","YES","High on ingredient line","PROPOSED"],
["AS-05","All","Supplier lead time","","days","EXPLICITLY UNKNOWN","Avoids inventing calendar dates","n/a - left blank","Critical path if long","UNKNOWN"],
["AS-06","All","Freight, duty, AD/CVD, broker cost","","USD","EXPLICITLY UNKNOWN","No confirmed HTS or AD/CVD position","n/a - left blank","Very high on landed cost","UNKNOWN"],
["AS-07","All","Amazon fees and demand","","USD/units","EXPLICITLY UNKNOWN","No authorised Amazon data collected","n/a - left blank","Determines channel viability","UNKNOWN"],
["AS-08","All","Mogra's own certification obligation","","USD/yr","Likely required; amount unknown","An organic input does not make a Mogra pack seal-eligible","n/a","Material fixed cost if applicable","UNKNOWN"],
]
w("assumptions_register.csv", AS_H, AS)

# ============================================================ RISK REGISTER
RK_H = ["risk_id","category","description","likelihood","impact","mitigation","owner_or_action","status"]
RK = [
["RK-01","Certification","Supplier-wide organic grade is mistaken for product/process approval","Medium","High","Keep evidence at product-form level; verify scope per activity","Do not treat A-grade supplier as blanket approval","OPEN - policy in place"],
["RK-02","Certification","A certified input is mistaken for an approved finished pack","High","High","Explicit label-pathway analysis per product","Certifier/label review required before claiming the seal","OPEN"],
["RK-03","Certification","No-seal pathway assumed to remove certification obligations","Medium","High","State separately that obligations can persist without the seal","Confirm arrangement with certifier","OPEN"],
["RK-04","Certification","SQF/GMP mistaken for NOP organic certification","High","Medium","Separate food-safety certs from organic certs in every table","Ask for the specific NOP certifier","OPEN"],
["RK-05","Import","AD/CVD order applies but is unverified, producing material unbudgeted duty","Low-Medium","Very High","Broker review of HTS + AD/CVD scope before any import","Commission broker review packet","OPEN"],
["RK-06","Import","Origin-specific additional tariffs change after quoting","Medium","High","Confirm at time of each import; do not carry stale assumptions","Re-check per shipment","OPEN"],
["RK-07","Quality","Turmeric adulteration (lead chromate / colourants) not detected","Medium","High","Require lot-specific adulteration screening from supplier","Add to RFQ quality section","OPEN"],
["RK-08","Quality","Published retail prices used as wholesale cost","Medium","Medium","Keep retail references flagged; never convert to wholesale","Cost model labels retail explicitly","CONTROLLED"],
["RK-09","Commercial","Missing costs treated as zero, producing false favourable economics","Medium","High","Nulls remain null; no total from incomplete inputs","Scenario register separates assumptions","CONTROLLED"],
["RK-10","Commercial","Single verified supplier creates concentration risk","Medium","Medium","Route B/C provide alternatives","Do not rely on Pearl alone","OPEN"],
["RK-11","Data","Truncated/product-list capture treated as proof of absence","Medium","Medium","Correction logged; absence not asserted from partial capture","Re-request full list","CONTROLLED"],
["RK-12","Legal/label","'Mogra Organics' packaging used without certifier label review","Medium","Medium","Flag for certifier label review before printing","Do not assert compliance","OPEN"],
["RK-13","Scope","Research scope drifts into mushrooms/topicals/supplements not documented","Low","Medium","Keep future interests in a separate section","No new workstreams opened","CONTROLLED"],
]

w("risk_register.csv", RK_H, RK)

# ============================================================ DECISION REGISTER
DC_H = ["decision_id","decision","why_it_matters","options","evidence_backed_tradeoff","recommendation",
        "consequence_of_deferral","needed_by_stage","owner_input_required"]
DC = [
["DC-01","Exact legal contracting entity name","All supplier documents, contracts and customs entries name a legal entity","Confirm T2Holdings LLC exact registered spelling, OR another entity","Cannot be researched publicly - owner records only","Confirm from owner business records before any outreach","RFQs remain unsendable; customs entry cannot be filed","Before outreach","YES - exact spelling"],
["DC-02","Initial products and forms","Determines supplier shortlist, certification needs, packaging","Pepper (whole/ground); turmeric (powder); both; add herbs; add salt blend","Pearl covers pepper+herbs in one verified operation; turmeric powder needs extra confirmation","Start with black pepper (whole+ground) - strongest verified chain","Research continues but quotes stay generic","Before outreach","YES"],
["DC-03","Organic claim / labelling pathway","Drives certification cost, label design and supplier requirements","100% organic / organic / made with organic / ingredient-only / no organic claim","Only 'made with organic' or partial claims may fit multi-ingredient blends; single-ingredient spices can be 'organic' if certified","Decide per SKU, not brand-wide","Label design blocked; certifier review cannot start","Before label design","YES"],
["DC-04","Package format and net quantity","Drives co-packer MOQ, packaging cost, Amazon listing","Jar / pouch / sachet; 1 oz / 2 oz / 4 oz / other","Jars cost more and add breakage; pouches cheaper and lighter for FBA","Pouch for pilot; re-evaluate for premium tier","Co-packer quotes cannot be compared","Before samples","YES"],
["DC-05","Initial target volumes","Turns tier pricing into real economics; sizes MOQ","Pilot 500 / small commercial / scale","No owner volume supplied","Define a pilot quantity explicitly","Quotes remain MOQ-only; no unit economics","Before quotes","YES"],
["DC-06","Budget / cash exposure","Sample, pilot and certification costs commit cash","Amount available for samples/pilot/certification","Unknown","Set a pilot budget ceiling","Sampling cannot be approved","Before samples","YES"],
["DC-07","Preferred sourcing route","A (overseas finished) vs B (bulk + US co-pack) vs C (US turnkey)","A / B / C / test two in parallel","A gives convenience but concentration risk; B balances control and cost; C simplest but likely higher ingredient cost","Investigate A and B in parallel; keep C for fallback","No quotes worth collecting at scale","Before quotes","YES"],
["DC-08","Importer and FSVP posture","Determines duty liability, FSVP and organic importer obligations","Mogra imports directly vs buys from US distributor","Direct import adds organic-importer + FSVP obligations and cost but improves control","Confirm before route B/A import","Import cost model invalid","Before importing","YES"],
["DC-09","Applicable certification arrangement","Determines whether Mogra must certify its own handling/import","Certify as importer / handler / repacker; or avoid by buying finished from a certified packer","An organic input does not certify the Mogra pack","Get a certifier opinion before committing to route B","Route B economics and timeline invalid","Before production","YES"],
["DC-10","Intended sales channels","Drives packaging, labelling and compliance","Amazon US / DTC / retail / foodservice","Amazon requires FBA-ready packaging and compliance docs","Confirm Amazon US is primary","Channel readiness cannot be assessed","Before launch","YES"],
]

w("decision_register.csv", DC_H, DC)

print("ALL NEW TABLES BUILT")
