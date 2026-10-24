# Lion's Mane existing-inventory launch: supporting tables.
import csv, os
ROOT=os.path.join("docs","mogra-organics-research-2026-10-02","lions_mane_launch")
os.makedirs(ROOT, exist_ok=True)
def w(name,header,rows):
    n=len(header); bad=0; fx=[]
    for i,r in enumerate(rows,1):
        if len(r)!=n: bad+=1; print(f"  !! {name} r{i}: {len(r)} exp {n}"); r=(list(r)+[""]*n)[:n]
        fx.append(r)
    with open(os.path.join(ROOT,name),"w",newline="",encoding="utf-8") as f:
        cw=csv.writer(f,quoting=csv.QUOTE_MINIMAL); cw.writerow(header)
        for r in fx: cw.writerow(r)
    print(f"{name}: {len(fx)} rows, {bad} mismatches")

# ==================================================== INVENTORY AUDIT TEMPLATE
IA_H=["check_id","inspection_item","what_to_verify","why_it_matters","method","evidence_required",
      "responsible","status","blocks_which_gate","owner_input_required"]
def a(*x): return list(x)
IA=[
 a("IA-01","Actual bag count","Physical count of bags on hand","500 is owner-reported; sellable count is unknown until reconciled","Physical count, photographed","Count sheet + photos","owner","NOT STARTED","G1","YES"),
 a("IA-02","Count by lot","Bags grouped by lot code / date marking","Amazon may require separate handling of different lots/date codes","Sort by printed lot code","Lot register","owner","NOT STARTED","G1","YES"),
 a("IA-03","Net quantity per bag","Bag weight in grams/oz","Defines serving size, net qty on label, shipping weight","Weigh a sample of bags","Weighing record","owner","NOT STARTED","G1, G6","YES"),
 a("IA-04","Bag material","Film type, barrier, resealable or not","Barrier affects shelf life and whether resealing is needed","Physical inspection + supplier spec","Supplier specification","owner","NOT STARTED","G6, G7","YES"),
 a("IA-05","Ingredient identity and composition","Single ingredient (mushroom powder) or carriers/other ingredients present","Determines label ingredient declaration and classification","Supplier spec + label review","Supplier specification / invoice","owner","OWNER_INPUT_REQUIRED","G1, G2, G6","YES"),
 a("IA-06","Plain powder vs extract","Whether concentrate/extract ratio applies","Extract ratios must never be inferred; affects claims","Supplier spec","Supplier specification","owner","OWNER_INPUT_REQUIRED","G6","YES"),
 a("IA-07","Fruiting body vs mycelium","Documented source part where available","Affects ingredient naming and consumer expectations","Supplier spec","Supplier specification","owner","OWNER_INPUT_REQUIRED","G6","YES"),
 a("IA-08","Supplier and manufacturing/packing entity","Who manufactured and who packed","Needed for Amazon facility documentation and traceability","Invoice / supplier docs","Supplier invoice + certificate","owner","OWNER_INPUT_REQUIRED","G1, G2, G6","YES"),
 a("IA-09","Production date","Date manufactured","Product age cannot be reset to the testing date","Invoice / date code","Invoice + lot marking","owner","OWNER_INPUT_REQUIRED","G5","YES"),
 a("IA-10","Packing date","Date packed","Affects date marking","Lot marking","Lot marking","owner","OWNER_INPUT_REQUIRED","G5","YES"),
 a("IA-11","Existing lot and date markings","What is printed on the bags today","Existing markings may be usable or may need remediation","Photograph every lot","Photo record","owner","NOT STARTED","G5, G7","YES"),
 a("IA-12","Seal integrity","Factory seal intact","Broken seals raise contamination/tamper questions","Visual + physical check","Inspection note","owner","NOT STARTED","G7","NO"),
 a("IA-13","Package damage","Crushed, punctured, moisture-exposed bags","Damaged units are not sellable","Visual inspection","Inspection note + photos","owner","NOT STARTED","G7","NO"),
 a("IA-14","Moisture exposure / deterioration","Clumping, discoloration, odor","Conditions current condition of stock","Visual + smell","Inspection note","owner","NOT STARTED","G4, G7","NO"),
 a("IA-15","Home storage conditions and duration","Temperature, humidity, light, duration","Storage history informs current-condition assessment and shelf-life argument","Owner statement","Storage log / statement","owner","NOT STARTED","G5","YES"),
 a("IA-16","Traceability to invoices","Link each lot to a purchase invoice","Traceability must exist without the bags","Invoice reconciliation","Invoices","owner","NOT STARTED","G1","YES"),
 a("IA-17","Reconciliation math","Units available before sampling, consumed by testing, retained samples, quarantined/damaged, potentially sellable","500 bags must NOT be called sellable inventory before reconciliation","Calculation from IA-01..IA-14","Inventory register","partner","NOT STARTED","G1","YES"),
]
w("inventory_audit_template.csv",IA_H,IA)

# ==================================================== TESTING & DOCUMENT CHECKLIST
TD_H=["item_id","category","item","status","what_is_known","what_is_missing","why_it_matters","closure_action","blocks_which_gate"]
def t(*x): return list(x)
TD=[
 t("TD-01","Testing","Selected laboratory","OWNER_INPUT_REQUIRED","A laboratory is selected (owner-reported)","Laboratory name, accreditation status, address","Determines report credibility and whether Amazon accepts it","Owner to supply lab identity and accreditation","G3, G4"),
 t("TD-02","Testing","Quote / reference number","OWNER_INPUT_REQUIRED","~$800 quoted (owner-reported)","Quote document, scope, reference","Confirms what $800 actually buys","Owner to supply quote","G3"),
 t("TD-03","Testing","Selected test panel","OWNER_INPUT_REQUIRED","A panel is selected (owner-reported)","Exact tests, methods, units, limits","A generic panel may not answer identity/contaminant questions","Lab-confirmation message (drafted)","G3, G4"),
 t("TD-04","Testing","Sample quantity required","OWNER_INPUT_REQUIRED","Unknown","Grams per test / per lot","Determines units consumed from inventory","Lab-confirmation message","G1, G3"),
 t("TD-05","Testing","Sampling from unopened bags","UNKNOWN","Unknown","Whether samples must come from unopened original bags","Preserves representativeness of the lot","Lab-confirmation message","G3"),
 t("TD-06","Testing","Multi-lot representation","UNKNOWN","Unknown","How lots must be sampled if more than one lot exists","Each lot may need separate representation","Lab-confirmation message","G3"),
 t("TD-07","Testing","Turnaround start point","OWNER_INPUT_REQUIRED","~2 weeks reported","Calendar vs business days; starts at receipt or order","Drives the entire dated schedule","Lab-confirmation message","G3"),
 t("TD-08","Testing","Report recipient and interpreter","UNKNOWN","Unknown","Who receives and who qualifies results","A passed report is not self-interpreting","Owner to assign a qualified reviewer","G4"),
 t("TD-09","Documentation","Supplier invoice","OWNER_INPUT_REQUIRED","None found in project files","Invoice(s) linking lots to purchase","Traceability; manufacturing entity","Owner to supply","G1"),
 t("TD-10","Documentation","Product specification","OWNER_INPUT_REQUIRED","None found","Ingredient, part, carriers, specs","Label accuracy","Owner to supply","G6"),
 t("TD-11","Documentation","Organic certificate","OWNER_INPUT_REQUIRED","Organic is owner-reported","Certificate, certifier, number, scope, product coverage, expiry","Organic claim and seal eligibility","Owner to supply","G6"),
 t("TD-12","Documentation","Existing supplier COA","UNKNOWN","Unknown","Availability and scope","May support results; may not cover this lot","Owner to supply","G4"),
 t("TD-13","Documentation","Stability / shelf-life documentation","OWNER_INPUT_REQUIRED","None found","Supplier stability data, retest data","Only basis for a multi-year shelf-life claim","Owner to supply","G5"),
 t("TD-14","Documentation","Existing label artwork","UNKNOWN","Unknown","Whether any artwork exists for this SKU","Label-gap review cannot be completed without it","Owner to supply","G6"),
 t("TD-15","Documentation","Inventory photos / storage records","UNKNOWN","Unknown","Photos of each lot, storage conditions","Supports condition assessment","Owner to supply","G1, G5"),
 t("TD-16","Documentation","Amazon account / brand documents","UNKNOWN","No listing exists","Seller account status, Brand Registry status","Gates listing creation","Owner to confirm","G9"),
 t("TD-17","Documentation","Business legal entity records","OWNER_INPUT_REQUIRED","T2 Holdings LLC (owner-reported spelling)","Exact registered name from records","Required on external submissions","Owner to verify","G9"),
 t("TD-18","Classification","Product classification decision","UNRESOLVED","Owner describes a mushroom powder","Food vs dietary supplement determination","Drives label panel, claims, and Amazon path","Qualified review of label/intended use","G2"),
 t("TD-19","Amazon compliance","Amazon-approved TIC provider verification","UNRESOLVED","Not checked","Whether the selected lab is an Amazon-approved TIC","A standalone COA does not equal Amazon approval","Verify against Amazon approved-provider list","G2, G6"),
 t("TD-20","Amazon compliance","cGMP facility documentation","UNRESOLVED","Not checked","Facility cGMP evidence for manufacturing/packing entity","Amazon 2026 supplement policy requires verified cGMP","Owner to obtain from supplier","G2, G6"),
]
w("testing_and_document_checklist.csv",TD_H,TD)

# ==================================================== LAUNCH SCHEDULE
LS_H=["task_id","workstream","task","scenario","est_completion_date","responsible","dependencies",
      "evidence_needed","status","delay_consequence","backup_action"]
def s(*x): return list(x)
LS=[
 s("LM-01","1 Inventory","Confirm inventory facts, count, lots, bag weight","all","2026-10-05","owner","-","Inventory register + photos","planning allowance","G1 blocked; sellable count unknown","Extend hold; do not sample blind"),
 s("LM-02","1 Testing","Confirm lab instructions, panel, sample plan","all","2026-10-05","owner + lab","LM-01","Lab confirmation","planning allowance","Turnaround clock cannot start","Use addendum message (drafted, unsent)"),
 s("LM-03","2 Compliance","Answer classification questions (food vs supplement)","all","2026-10-05","owner + qualified reviewer","-","Written classification rationale","planning allowance","Label and Amazon path unknown","Default to most restrictive path pending review"),
 s("LM-04","1 Testing","Sample dispatch","fast","2026-10-06","owner","LM-01, LM-02","Carrier receipt","planning allowance","Results slip day-for-day","Reship expedited"),
 s("LM-05","1 Testing","Laboratory receipt confirmed","fast","2026-10-07","lab","LM-04","Lab receipt confirmation","planning allowance","Turnaround start date unknown","Record actual date; recalculate"),
 s("LM-06","1 Testing","Laboratory receipt confirmed","base","2026-10-08","lab","LM-04","Lab receipt confirmation","planning allowance","Turnaround start slips","Recalculate results date"),
 s("LM-07","1 Testing","Results available (ILLUSTRATIVE)","fast","2026-10-21","lab","LM-05","Issued report","planning allowance","-","Assume 14 CALENDAR days from receipt; recalculate if business days or later receipt"),
 s("LM-08","1 Testing","Results available (ILLUSTRATIVE)","base","2026-10-23","lab","LM-06","Issued report","planning allowance","-","Adds ~2 days vs fast"),
 s("LM-09","3 Listing","Draft listing content, images brief, keywords","all","2026-10-12","partner","LM-03","Draft listing + shot list","planning allowance","Listing not ready at receipt","Draft in parallel with testing"),
 s("LM-10","4 Compliance","Label-gap review for this SKU","all","2026-10-14","owner + qualified reviewer","LM-03","Label gap list","planning allowance","Label cannot be finalised","Prepare artwork placeholders"),
 s("LM-11","4 Compliance","Verify organic certificate coverage","all","2026-10-14","owner","TD-11","Certificate + scope","planning allowance","Organic claim unsupported","Remove organic claim"),
 s("LM-12","4 Compliance","Check Amazon TIC / cGMP requirements if supplement","all","2026-10-16","partner","LM-03","Amazon policy determination","planning allowance","Compliance path unknown; may exceed window","Do NOT assume verification completes in this window"),
 s("LM-13","5 Shelf-life","Shelf-life and date-marking decision","fast","2026-10-23","qualified reviewer","LM-07, TD-13","Written basis for date marking","planning allowance","Launch blocker G5","Use conservative remaining life; no invented expiry"),
 s("LM-14","5 Shelf-life","Shelf-life and date-marking decision","base","2026-10-26","qualified reviewer","LM-08, TD-13","Written basis for date marking","planning allowance","Launch blocker G5","Delay scenario"),
 s("LM-15","4 Compliance","Qualified results review vs specifications","fast","2026-10-24","qualified reviewer","LM-13","Signed review note","planning allowance","Cannot release stock","Hold inventory"),
 s("LM-16","6 Packaging","Final labeling / label application","fast","2026-10-28","partner","LM-10, LM-15","Approved label","planning allowance","Packaging not ready","Receive sealed units and apply later (only if packer permits)"),
 s("LM-17","7 FBA","Pilot unit + carton inspection","fast","2026-10-30","owner","LM-16","Inspection pass record","planning allowance","Cannot dispatch","Quarantine affected units"),
 s("LM-18","7 FBA","FBA dispatch","fast","2026-10-31","partner","LM-17","Shipment record","planning allowance","Buyable date slips","Dispatch partial"),
 s("LM-19","7 FBA","Delivered to Amazon","fast","2026-11-06","Amazon/carrier","LM-18","Carrier confirmation","planning allowance","Receiving risk","Expedite"),
 s("LM-20","7 FBA","Received / available inventory","fast","2026-11-14","Amazon","LM-19","FBA check-in","planning allowance","Not buyable","Merchant-fulfilled contingency (does not bypass compliance)"),
 s("LM-21","8 Listing","Buyable listing live","fast","2026-11-18","Amazon","LM-20, LM-09","Live ASIN","planning allowance","Earlier than target if gates met","-"),
 s("LM-22","1 Testing","Results available (DELAY scenario)","delay","2026-11-05","lab","later receipt / business-day TAT","Issued report","planning allowance","Compresses everything downstream","Move target to Dec 1 or reduce assortment"),
 s("LM-23","5 Shelf-life","Shelf-life decision (delay)","delay","2026-11-09","qualified reviewer","LM-22","Written basis","planning allowance","Tight","-"),
 s("LM-24","7 FBA","FBA dispatch (delay)","delay","2026-11-16","partner","LM-23","Shipment record","planning allowance","Dec 1 target at risk","Move to Dec 1; reduce units"),
 s("LM-25","7 FBA","Buyable listing (delay)","delay","2026-12-01","Amazon","LM-24","Live ASIN","planning allowance","Latest acceptable target","Merchant-fulfilled while FBA receives"),
]
w("launch_schedule.csv",LS_H,LS)

# ==================================================== RELEASE GATES
RG_H=["gate_id","gate","pass_condition","evidence_required","status","if_failed"]
def g(*x): return list(x)
RG=[
 g("G1","Inventory identity, lots, condition, traceability established","Count by lot, weight, condition, invoice traceability, no unresolved damage","Inventory register (IA-01..IA-17)","NOT MET","Hold stock; reconcile before sampling or sale"),
 g("G2","Product classification and applicable Amazon path understood","Written determination: conventional food vs dietary supplement vs unresolved, and the Amazon compliance path that follows","Classification rationale + Amazon policy determination","NOT MET","Use most restrictive path; do not choose a category to avoid requirements"),
 g("G3","Selected testing and sampling approach confirmed","Lab identity, panel, methods, sample plan, multi-lot handling and turnaround definition confirmed","Lab confirmation response","NOT MET","Do not ship samples until confirmed; clock cannot start"),
 g("G4","Results reviewed against appropriate specifications","Report reviewed by a qualified reviewer against applicable requirements; gaps identified","Signed review note","NOT MET","Hold affected inventory; define investigation/retest path"),
 g("G5","Shelf-life / date-marking basis accepted","Defensible basis for remaining shelf life and the date marking to be printed","Supplier stability evidence + lab basis + manufacture date","NOT MET","Launch blocker; do not invent or reset an expiry date"),
 g("G6","Labeling, organic claims and applicable verification complete","Label-gap review closed; organic claim supported by certificate; Amazon-required verification completed where applicable","Approved label + certificate scope + verification records","NOT MET","Remove unsupported claims; do not dispatch"),
 g("G7","Pilot unit and carton inspection passed","Sample unit meets spec, seal and label correct, cartons correct","Inspection pass record","NOT MET","Quarantine; re-pack only under qualified supervision"),
 g("G8","Shipment released","All prior gates met; quarantine respected; not all units necessarily shipped","Release sign-off + shipment record","NOT MET","Do not dispatch"),
 g("G9","Buyable listing confirmed","ASIN live with active offer and in-stock inventory","Live listing screenshot","NOT MET","Correct listing or inventory issue"),
]
w("release_gates.csv",RG_H,RG)

# ==================================================== LAUNCH BUDGET
LB_H=["line_id","category","line","amount_usd","basis","value_type","notes"]
def b(*x): return list(x)
LB=[
 b("LB-01","Existing inventory","Acquisition cost of the ~500 bags already owned","","OWNER_INPUT_REQUIRED","UNKNOWN","Inventory already paid for is NOT economically free. Needed for view B."),
 b("LB-02","Testing","Selected laboratory test panel (owner-reported quote)","800","OWNER_REPORTED_QUOTE","OWNER_REPORTED","Confirm scope and whether it includes sample shipping"),
 b("LB-03","Testing","Preliminary testing allocation per bag","1.60","800 / 500 bags","DERIVED_PRELIMINARY","PRELIMINARY TESTING ALLOCATION ONLY - not total unit COGS. Recalculate on actual sellable count and total test cost."),
 b("LB-04","Testing","Sample shipping to laboratory","","QUOTE REQUIRED","UNKNOWN",""),
 b("LB-05","Compliance","Additional Amazon-authorised TIC verification (if supplement path)","","UNKNOWN","UNKNOWN","SEPARATE from the $800. May be required; cost not known."),
 b("LB-06","Compliance","cGMP facility documentation / review","","UNKNOWN","UNKNOWN","May be required by Amazon 2026 supplement policy"),
 b("LB-07","Compliance","Label review / regulatory review","","UNKNOWN","UNKNOWN",""),
 b("LB-08","Packaging","Labels and label application","","QUOTE REQUIRED","UNKNOWN","External labeling only vs opening/resealing is a separate qualified task"),
 b("LB-09","Packaging","Packaging remediation (if bags require resealing)","","UNKNOWN","UNKNOWN",""),
 b("LB-10","Marketing","Product photography","","UNKNOWN","UNKNOWN",""),
 b("LB-11","Marketing","Product identifiers (GTIN) if required","","UNKNOWN","UNKNOWN",""),
 b("LB-12","FBA","FBA prep (poly-bagging, FNSKU, labelling)","","UNKNOWN","UNKNOWN",""),
 b("LB-13","Logistics","Inbound shipping to Amazon","","UNKNOWN","UNKNOWN",""),
 b("LB-14","Logistics","Inbound placement / other FBA inbound charges","","UNKNOWN","UNKNOWN",""),
 b("LB-15","Selling fees","Amazon referral fee","","UNKNOWN","UNKNOWN","Rate depends on category determination"),
 b("LB-16","Selling fees","Amazon fulfilment fee","","UNKNOWN","UNKNOWN","Depends on packaged weight/dimensions"),
 b("LB-17","Advertising","Launch advertising (SEPARATE BUDGET)","","UNKNOWN","UNKNOWN","Shown separately from product costs; no CPC invented"),
 b("LB-18","Total","INCREMENTAL CASH TO LAUNCH INVENTORY ALREADY OWNED","sum(LB-02,04,05,06,07,08,09,10,11,12,13,14,15,16)","FORMULA_ONLY","UNKNOWN","View A. Cannot compute - too many unknowns. Excludes acquisition cost"),
 b("LB-19","Total","FULL PRODUCT ECONOMICS incl. acquisition cost","LB-18 + LB-01","FORMULA_ONLY","UNKNOWN","View B. Cannot compute; acquisition cost is an owner input. Inventory already paid for is NOT free"),
]
w("launch_budget.csv",LB_H,LB)

# ==================================================== SOURCE EVIDENCE REGISTER
SR_H=["source_id","title","url_or_path","source_type","observation_date","used_for","limitations"]
def r(*x): return list(x)
SR=[
 r("SRC-01","FDA - Questions and Answers on Dietary Supplements","https://www.fda.gov/food/information-consumers-using-dietary-supplements/questions-and-answers-dietary-supplements","official regulator","2026-10-02","Classification framing: supplements are defined by intended use; FDA does not pre-approve supplements","General guidance; does not classify this specific product"),
 r("SRC-02","Amazon Seller Central - Dietary supplements policy","https://sellercentral.amazon.com/gp/help/external/55N3JF2WQS7RVNE","official Amazon policy","2026-10-02","Amazon supplement compliance requirements; TIC route","Policy applies only if the supplement pathway is correct"),
 r("SRC-03","Amazon 2026 supplement compliance summary (cGMP + approved TIC provider)","https://foodlabelmaker.com/regulatory-hub/fda/dietary-supplements/amazon-supplement-update-2026/","industry summary of Amazon policy","2026-10-02","2026 requirement for verified cGMP via an Amazon-approved TIC provider","Secondary source; verify against Seller Central"),
 r("SRC-04","Amazon supplement testing policy (TIC verification)","https://sellercentral.amazon.com/seller-forums/discussions/t/c23c51e6-159c-4d01-b297-9836d7d16419","official Amazon forum announcement","2026-10-02","Third-party TIC verification requirement for supplements","Applies only to the supplement pathway"),
 r("SRC-05","Project files - Lion's Mane evidence search","docs/mogra-organics-research-2026-10-02 (full tree)","internal search","2026-10-02","Confirmed NO lab, panel, invoice, certificate, bag weight or lot data exists in the project","Absence of files is not proof the documents do not exist"),
 r("SRC-06","Owner-reported starting facts","owner prompt (this task)","owner-reported","2026-10-02","~500 bags; home storage; organic; lab selected; panel selected; ~$800; ~2 week turnaround; no listing","OWNER-REPORTED until evidence exists"),
]
w("source_evidence_register.csv",SR_H,SR)

print("LIONS MANE TABLES BUILT")
