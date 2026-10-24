# Build the Lion's Mane launch blueprint PDF (ReportLab).
import csv, os
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.enums import TA_JUSTIFY, TA_CENTER
from reportlab.platypus import (BaseDocTemplate, PageTemplate, Frame, Paragraph, Spacer,
                                Table, TableStyle, PageBreak, HRFlowable)
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

BASE=os.path.join("docs","mogra-organics-research-2026-10-02")
ROOT=os.path.join(BASE,"lions_mane_launch")
OUT=os.path.join(BASE,"review_packet"); os.makedirs(OUT,exist_ok=True)
PDF=os.path.join(OUT,"Mogra_Organics_Lions_Mane_Launch_Blueprint_2026-10-02.pdf")
FD=r"C:\Windows\Fonts"
def reg(n,f):
    p=os.path.join(FD,f)
    if os.path.exists(p): pdfmetrics.registerFont(TTFont(n,p)); return True
    return False
HG=reg("Georg","georgia.ttf") and reg("Georg-B","georgiab.ttf") and reg("Georg-I","georgiai.ttf")
if reg("Ari","arial.ttf"): reg("Ari-B","arialbd.ttf"); reg("Ari-I","ariali.ttf"); BODY,BODY_B,BODY_I="Ari","Ari-B","Ari-I"
else: BODY,BODY_B,BODY_I="Helvetica","Helvetica-Bold","Helvetica-Oblique"
HEAD,HEAD_B,HEAD_I=("Georg","Georg-B","Georg-I") if HG else ("Times-Roman","Times-Bold","Times-Italic")

PAPER=colors.HexColor("#FBFAF7"); INK=colors.HexColor("#1E2A26"); PINE=colors.HexColor("#22463A")
SAGE=colors.HexColor("#6E8B74"); CLAY=colors.HexColor("#9A6A4F"); RULE=colors.HexColor("#D8D4CB")
MUTED=colors.HexColor("#6B6B63"); WARNBG=colors.HexColor("#F3EFE7"); OKBG=colors.HexColor("#EDF2EE")
RED=colors.HexColor("#8C3B2E")
def S(n,**k): return ParagraphStyle(n,**k)
st_title=S("t",fontName=HEAD_B,fontSize=26,leading=31,textColor=PINE)
st_h1=S("h1",fontName=HEAD_B,fontSize=16,leading=20,textColor=PINE,spaceBefore=2,spaceAfter=7)
st_h2=S("h2",fontName=HEAD_B,fontSize=11.5,leading=15,textColor=INK,spaceBefore=8,spaceAfter=4)
st_body=S("b",fontName=BODY,fontSize=9.5,leading=13.4,textColor=INK,spaceAfter=5,alignment=TA_JUSTIFY)
st_bul=S("bu",fontName=BODY,fontSize=9.5,leading=13.2,textColor=INK,leftIndent=13,bulletIndent=3,spaceAfter=2.5)
st_small=S("sm",fontName=BODY,fontSize=8.3,leading=11.3,textColor=MUTED,spaceAfter=3,alignment=TA_JUSTIFY)
st_cellh=S("ch",fontName=BODY_B,fontSize=8.1,leading=10.5,textColor=colors.white)
def P(t,s=st_body): return Paragraph(t,s)
def B(t): return Paragraph(t,st_bul,bulletText="•")
def rule(c=RULE,w=0.7,sb=2,sa=6): return HRFlowable(width="100%",thickness=w,color=c,spaceBefore=sb,spaceAfter=sa)
def tbl(header,rows,widths,fs=8.1):
    tot=float(sum(widths)); tgt=6.6*inch; widths=[w*tgt/tot for w in widths]
    cs=ParagraphStyle("cx",fontName=BODY,fontSize=fs,leading=fs+2.4,textColor=INK)
    data=[[Paragraph(h,st_cellh) for h in header]]
    for r in rows: data.append([Paragraph(str(c) if c not in (None,"") else "—",cs) for c in r])
    t=Table(data,colWidths=widths,repeatRows=1,hAlign="LEFT")
    t.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),PINE),("VALIGN",(0,0),(-1,-1),"TOP"),
        ("TOPPADDING",(0,0),(-1,-1),4),("BOTTOMPADDING",(0,0),(-1,-1),4),
        ("LEFTPADDING",(0,0),(-1,-1),5),("RIGHTPADDING",(0,0),(-1,-1),5),
        ("LINEBELOW",(0,0),(-1,-1),0.35,RULE),("ROWBACKGROUNDS",(0,1),(-1,-1),[colors.white,PAPER])]))
    return t
def callout(title,body,tone="note"):
    bg=OKBG if tone=="ok" else (WARNBG if tone=="warn" else PAPER)
    tc=RED if tone=="bad" else PINE
    inner=[[Paragraph(f"<b>{title}</b>",S("ct",fontName=HEAD_B,fontSize=10.3,leading=13,textColor=tc))],
           [Paragraph(body,S("cb2",fontName=BODY,fontSize=9.2,leading=12.6,textColor=INK))]]
    t=Table(inner,colWidths=[6.6*inch],hAlign="LEFT")
    t.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,-1),bg),("BOX",(0,0),(-1,-1),0.6,RULE),
        ("LINEBEFORE",(0,0),(0,-1),2.4,SAGE),("LEFTPADDING",(0,0),(-1,-1),9),
        ("RIGHTPADDING",(0,0),(-1,-1),9),("TOPPADDING",(0,0),(-1,-1),6),("BOTTOMPADDING",(0,0),(-1,-1),6)]))
    return t
def rows_of(fn): return list(csv.DictReader(open(os.path.join(ROOT,fn),newline="",encoding="utf-8")))
def trunc(s,n):
    s=(s or "").strip(); return s if len(s)<=n else s[:n-1]+"…"
TODAY="2026-10-02"

class Doc(BaseDocTemplate):
    def __init__(s,fn,**k):
        super().__init__(fn,**k)
        s.addPageTemplates([PageTemplate(id="v",frames=[Frame(0.95*inch,0.95*inch,6.6*inch,9.1*inch,id="m")],onPage=s.deco)])
    def deco(s,c,d):
        c.saveState(); w,h=letter
        c.setFillColor(PAPER); c.rect(0,0,w,h,stroke=0,fill=1)
        c.setFont(BODY,7.3); c.setFillColor(MUTED)
        c.drawString(0.95*inch,h-0.62*inch,"MOGRA ORGANICS — LION'S MANE EXISTING-INVENTORY LAUNCH BLUEPRINT")
        c.setFont(BODY_I,7.3); c.setFillColor(RED)
        c.drawRightString(w-0.95*inch,h-0.62*inch,"WORKING PLAN — INVENTORY NOT RELEASED UNTIL GATES ARE MET")
        c.setStrokeColor(RULE); c.setLineWidth(0.5); c.line(0.95*inch,h-0.70*inch,w-0.95*inch,h-0.70*inch)
        c.line(0.95*inch,0.78*inch,w-0.95*inch,0.78*inch)
        c.setFont(BODY,7.3); c.setFillColor(MUTED)
        c.drawString(0.95*inch,0.63*inch,f"T2 Holdings LLC (spelling unverified) · baseline {TODAY}")
        c.drawRightString(w-0.95*inch,0.63*inch,f"Page {d.page}")
        c.restoreState()

st=[]
# COVER
st += [Spacer(1,1.0*inch), Paragraph("Mogra Organics",st_title), Spacer(1,4),
 Paragraph("Lion's Mane Existing-Inventory Launch Blueprint",S("x",fontName=HEAD,fontSize=16,leading=21,textColor=INK)),
 Spacer(1,13), rule(PINE,1.4,0,11),
 Paragraph("Existing inventory → testing → release decision → listing and packaging readiness → Amazon FBA → buyable inventory.",
           S("lede",fontName=HEAD_I,fontSize=11.5,leading=16.5,textColor=MUTED)), Spacer(1,18),
 callout("WORKING PLAN — INVENTORY NOT RELEASED UNTIL GATES ARE MET",
  "The ~500 bags are owner-reported and unreconciled. They are NOT sellable inventory and have NOT been released. "
  "Testing has not been completed. No laboratory has been contacted, no sample ordered, nothing paid, no Amazon listing created or submitted.",tone="bad"),
 Spacer(1,16),
 tbl(["Field","Value"],[
  ["Baseline planning date",TODAY],
  ["Target","Buyable by 2026-11-25 (latest acceptable 2026-12-01) — not guaranteed"],
  ["Inventory","~500 bags Lion's mane mushroom powder (OWNER-REPORTED), stored at owner's home"],
  ["Testing","Laboratory and panel selected (OWNER-REPORTED); ~$800 quoted; ~2-week turnaround; NOT completed"],
  ["Amazon","No listing exists. Account, category, Brand Registry, identifiers and compliance NOT assumed"],
  ["Management","Managed separately from the herb/spice holiday launch blueprint"],
  ["Earliest realistic buyable","~18 Nov (fast) · ~23 Nov–1 Dec (base) · 1 Dec or later (delay)"]],
  [1.6*inch,5.0*inch],fs=7.8)]

# 1 EXEC
st += [PageBreak(), P("1. Executive decision brief",st_h1), rule(),
 P("<b>What we have:</b> approximately 500 bags of Lion's mane mushroom powder (owner-reported), stored at the owner's home, described as organic. No testing completed. No Amazon listing."),
 P("<b>The decision this blueprint supports:</b> whether, when and how this already-owned inventory can reach Amazon FBA and become buyable — without paying for testing that does not answer the right questions, and without releasing stock that is not ready."),
 P("<b>Three findings that change the plan:</b>")]
st += [tbl(["#","Finding","Consequence"],
 [["1","<b>No supporting documentation exists in the project.</b> A full project-tree search found no lab identity, test panel, supplier invoice, organic certificate, COA, bag weight or lot codes.","Everything is owner-reported until evidence arrives"],
  ["2","<b>A two-week test is not a shelf life.</b> Nothing substantiates a date marking today.","Product age cannot be reset to the testing date; G5 is a hard blocker"],
  ["3","<b>If this is a dietary supplement</b>, Amazon's 2026 policy requires verified cGMP via an Amazon-approved TIC provider — and a standalone COA does not equal Amazon approval.","The ~$800 test may be insufficient; extra cost and time likely"]],
 [0.3*inch,3.7*inch,2.6*inch]), Spacer(1,6),
 callout("Biggest risk to timeline and budget",
 "Whether the selected laboratory is an Amazon-approved TIC provider is UNRESOLVED. It cannot be answered until the classification question (G2) is settled.",tone="warn"),
 P("<b>Immediate blocker set:</b> classification (G2) · lab/panel confirmation (G3) · shelf-life basis (G5).")]

# 2 INVENTORY
st += [P("2. Starting inventory and unknowns",st_h1), rule(),
 P("Owner-reported: ~500 bags, home storage, organic. Everything else is unestablished. Full checklist: inventory_audit_template.csv (17 items).")]
ia=rows_of("inventory_audit_template.csv")
st += [tbl(["Item","Status"],[
 [[r["inspection_item"] for r in ia if r["check_id"]==k][0], v] for k,v in
 [("IA-01","OWNER-REPORTED (~500); unreconciled"),("IA-02","UNKNOWN"),("IA-03","UNKNOWN"),
  ("IA-05","OWNER_INPUT_REQUIRED"),("IA-06","OWNER_INPUT_REQUIRED"),("IA-07","OWNER_INPUT_REQUIRED"),
  ("IA-08","OWNER_INPUT_REQUIRED"),("IA-09","OWNER_INPUT_REQUIRED"),("IA-10","OWNER_INPUT_REQUIRED"),
  ("IA-11","NOT STARTED"),("IA-12","NOT STARTED"),("IA-13","NOT STARTED"),("IA-14","NOT STARTED"),
  ("IA-15","NOT STARTED"),("IA-16","NOT STARTED"),("IA-17","NOT STARTED")]],[3.0*inch,3.6*inch]), Spacer(1,6),
 callout("Reconciliation must precede any 'sellable' claim",
 "Units before sampling, consumed by testing, retained samples, damaged/quarantined, and potentially sellable are ALL UNKNOWN. "
 "500 bags are not sellable inventory. Stock remains on documented launch hold.",tone="bad"),
 P("Home storage is <b>not</b> automatically disqualifying — but its effect cannot be assessed until conditions, duration and current condition are documented.",st_small)]

# 3 TESTING
st += [PageBreak(), P("3. Testing plan and the ~$800 commitment",st_h1), rule(),
 P("<b>Preserved, not restarted.</b> The laboratory and panel are already selected (owner-reported).")]
st += [tbl(["Question","Status"],
 [["Laboratory identity / accreditation","OWNER_INPUT_REQUIRED"],["Quote / reference number","OWNER_INPUT_REQUIRED"],
  ["Selected tests, methods, units","OWNER_INPUT_REQUIRED"],["Sample quantity required","UNKNOWN"],
  ["Samples from unopened original bags?","UNKNOWN"],["Multi-lot sampling approach","UNKNOWN"],
  ["Shipping requirements","UNKNOWN"],["Turnaround = calendar or business days?","UNKNOWN"],
  ["Clock starts at order or receipt?","UNKNOWN"],["Who interprets the report?","UNKNOWN"]],
 [3.0*inch,3.6*inch]), Spacer(1,6),
 P("A <b>drafted, unsent laboratory confirmation message</b> is provided covering: panel adequacy for identity/composition and contaminant questions; unanswered questions; sampling approach across lots; acceptance specifications to agree <b>before</b> testing; whether the work establishes shelf life or only assesses current condition; evidence needed to support date marking; whether supplier stability data can be relied upon; and whether the lab can participate in Amazon's supplement verification pathway."),
 callout("Discipline",
 "No universal contaminant limits or arbitrary pass/fail values are invented. Unresolved criteria stay explicit and are agreed with a qualified reviewer before samples ship. "
 "If a material panel gap appears it is FLAGGED FOR APPROVAL — additional testing is not ordered.",tone="note")]

# 4 SHELF LIFE
st += [P("4. Shelf-life evidence gate",st_h1), rule(),
 P("Four things that must not be conflated:")]
st += [tbl(["Type","Question it answers","Covered by the quoted work?"],
 [["A. Current-condition testing","Is the stock now acceptable?","Likely yes"],
  ["B. Identity / composition testing","Is it what it claims to be?","Likely yes"],
  ["C. Safety / contaminant testing","Is it safe to sell?","Likely yes"],
  ["D. Shelf-life / date-marking evidence","How long is it defensibly good, and what date may we print?","<b>NOT addressed</b>"]],
 [1.75*inch,2.85*inch,2.0*inch]), Spacer(1,6),
 P("<b>Inputs required for D:</b> actual manufacture date · supplier stability evidence · exact formulation · packaging barrier and seal · storage history · real-time or accelerated study evidence · remaining shelf life at Amazon check-in."),
 callout("Rules that are not negotiable",
 "Do NOT reset product age to the testing date. Do NOT invent or extend an expiration date to satisfy Amazon. If D remains unresolved it is a LAUNCH BLOCKER with a specific closure action.",tone="bad")]

# 5 CLASSIFICATION
st += [PageBreak(), P("5. Food versus supplement pathway",st_h1), rule(),
 P("<b>Unresolved.</b> Classification depends on the actual label, directions, intended use, ingredients and claims — not on the fact that it is a mushroom powder. Some mushroom products are conventional foods, some are supplements. <b>A category must not be chosen to avoid requirements.</b>")]
st += [tbl(["Pathway","Label","Amazon implications"],
 [["Conventional food","Nutrition Facts or a valid exemption; limited permitted claims","Food compliance; identification rules"],
  ["Dietary supplement","Supplement Facts; structure/function claims need substantiation + disclaimer","<b>2026 policy: verified cGMP via an Amazon-approved TIC provider</b>"]],
 [1.3*inch,2.6*inch,2.7*inch]), Spacer(1,6),
 callout("Keep the $800 separate",
 "The ~$800 test is DISTINCT from any additional Amazon-authorised TIC validation, facility-document review, label review or retesting. Those costs sit outside it and are currently unknown.",tone="warn"),
 P("<b>Not assumed:</b> seller-account readiness, category eligibility, Brand Registry, product identifiers, or compliance approval. None is confirmed.")]

# 6 ORGANIC / LABEL
st += [P("6. Organic and labelling readiness",st_h1), rule(),
 P("<b>Organic is owner-reported.</b> Laboratory testing does not prove organic certification."),
 P("<b>Label-gap review for this exact SKU</b> must cover: product identity · net quantity · ingredient declaration · responsible business information · appropriate facts panel or exemption basis · directions and warnings · organic wording and marks · lot/date marking · barcode and Amazon-label placement · claims appearing on <b>both</b> package and listing."),
 callout("Claim discipline",
 "No disease-treatment claims, guaranteed cognitive performance, 'lead-free', 'FDA-approved' or superiority claims without a lawful, substantiated basis. "
 "If bags need only EXTERNAL labelling that is a labelling workflow; if they must be opened, resealed or repacked that is a SEPARATE QUALIFIED PACKING TASK that may affect certification.",tone="bad"),
 P("<b>Label approval is owner-reported; its scope is NOT audited by this research.</b>")]

# 7 LISTING
st += [PageBreak(), P("7. Listing and photography deliverables",st_h1), rule(),
 P("Package readiness only — <b>no listing is created or submitted</b>. Full draft: listing_readiness_package.md."),
 tbl(["Deliverable","Status"],
 [["Product brief + final-specification checklist","PLACEHOLDERS — composition, weight, part, dates unknown"],
  ["GTIN / product-identifier decision checklist","Pending Brand Registry + category determination"],
  ["Seller-account and category readiness","NOT confirmed — nothing assumed"],
  ["Brand-name consistency check","Pending entity verification"],
  ["Draft title / bullets / description","Claim-safe; fact placeholders only"],
  ["Keyword clusters","Small researched set derives from product identity, NOT measured search data"],
  ["Photo shot list + image brief","8 shots specified; final shots may await approved packaging"],
  ["Dimension and weight measurement sheet","All fields unknown — required for FBA fees"],
  ["Price scenarios","PLACEHOLDER — hypothetical only"],
  ["Compliance-document checklist","Tied to gates G4–G8"]],
 [2.4*inch,4.2*inch]), Spacer(1,6),
 callout("Nothing invented",
 "No extract ratio, beta-glucan percentage, serving size, certification, origin claim or health benefit is fabricated. Unknown product details remain placeholders. "
 "No search volumes, CPCs or conversion rates are asserted.",tone="note")]

# 8 FBA
st += [P("8. FBA preparation and release",st_h1), rule(),
 callout("A laboratory report is not automatic authorisation to ship",
 "Each state below is distinct and later than the one before it.",tone="warn")]
st += [P("<b>TESTS RECEIVED → RESULTS ACCEPTED → COMPLIANCE READY → PACKAGING READY → DISPATCHED → DELIVERED → RECEIVED / AVAILABLE → BUYABLE</b>")]
st += [tbl(["Pre-release check","Status"],
 [["Unit seal and packaging inspection","Pending inspection"],["Product/expiration attributes at ASIN creation","Pending G5"],
  ["Supported date marking","Blocked by G5"],["Sufficient remaining shelf life","UNKNOWN"],
  ["Barcode / FNSKU","Pending identification decision"],["Label placement not covering mandatory information","Pending label review"],
  ["Case packing and carton labels","Pending specs"],["Separate handling of lots / date codes","Pending lot reconciliation"],
  ["Shipment-plan inputs","Pending"],["Listing buyability check","Pending"]],
 [3.4*inch,3.2*inch]), Spacer(1,4),
 P("<b>Do not dispatch quarantined inventory. Do not assume all units must go in the first shipment.</b>")]

# 9 SCHEDULE
st += [PageBreak(), P("9. Parallel workstreams and dated schedule",st_h1), rule(),
 P("Five workstreams run in parallel, not in sequence."),
 tbl(["#","Workstream"],[
 ["1","Inventory reconciliation & testing"],["2","Testing / laboratory confirmation"],
 ["3","Listing drafts, documentation, photography planning, pricing, FBA specifications"],
 ["4","Classification, organic, labelling, Amazon compliance"],
 ["5","Shelf-life decision, FBA preparation, listing activation"]],[0.35*inch,6.25*inch]), Spacer(1,6),
 P("<b>Illustrative schedule (baseline 2026-10-02):</b>"),
 tbl(["Date","Milestone"],
 [["Oct 5","Confirm inventory facts, lab instructions, panel, classification questions, sample plan"],
  ["Oct 6–7","Sample dispatch; <b>record actual laboratory receipt</b>"],
  ["Oct 5–16","<b>In parallel:</b> listing drafts, documentation, label-gap review, photography planning, pricing, FBA specs"],
  ["~Oct 21","<b>Illustrative results only</b> — valid only if lab receives Oct 7 <b>and</b> confirms 14 <b>calendar</b> days"],
  ["Oct 22–28","Qualified results review; shelf-life decision; applicable Amazon verification; final labelling; release prep"],
  ["Oct 29–Nov 4","Pilot inspection and FBA dispatch window <b>if all gates are satisfied</b>"],
  ["November","Transit, receiving, listing status, buyable inventory monitoring"]],
 [0.95*inch,5.65*inch]), Spacer(1,6),
 tbl(["Scenario","Buyable","Condition"],
 [["Fast","~18 Nov 2026","Lab receipt Oct 7 + 14 calendar days; all gates clear"],
  ["Base","~23 Nov – 1 Dec 2026","One receipt day later, business-day TAT, or verification slipping"],
  ["Delay","1 Dec 2026 or later","Later receipt, business-day turnaround, or supplement verification added"]],
 [0.85*inch,1.5*inch,4.25*inch]), Spacer(1,4),
 callout("Targets are not guarantees",
 "Business target 25 Nov; latest acceptable 1 Dec. Neither is guaranteed. Amazon supplement verification is NOT assumed to complete inside this window.",tone="bad"),
 P("Full detail: launch_schedule.csv (25 tasks) with scenario, date, role, dependencies, evidence, status, delay consequence and backup action.",st_small)]

# 10 BUDGET
st += [PageBreak(), P("10. Launch budget and unit economics",st_h1), rule(),
 P("<b>Treated entirely separately from the herb/spice purchase budget.</b>"),
 tbl(["Line","Amount","Type"],
 [["Acquisition cost of the ~500 bags already owned","—","OWNER_INPUT_REQUIRED"],
  ["Laboratory test panel","~$800","OWNER-REPORTED QUOTE"],
  ["<b>Preliminary testing allocation per bag</b>","<b>~$1.60</b>","800 ÷ 500 — <b>PRELIMINARY TESTING ALLOCATION ONLY</b>"],
  ["Sample shipping","—","QUOTE REQUIRED"],
  ["Additional Amazon-authorised TIC verification (if supplement)","—","UNKNOWN"],
  ["cGMP facility documentation / label review","—","UNKNOWN"],
  ["Labels and packaging remediation","—","QUOTE REQUIRED"],
  ["Photography, GTIN, FBA prep","—","UNKNOWN"],
  ["Inbound shipping and placement charges","—","UNKNOWN"],
  ["Amazon selling / fulfilment fees","—","UNKNOWN"],
  ["<b>Launch advertising</b>","—","<b>SEPARATE BUDGET</b>"]],
 [3.1*inch,1.1*inch,2.4*inch]), Spacer(1,6),
 callout("$1.60 is a testing allocation, not unit COGS",
 "Recalculate on the ACTUAL sellable count and TOTAL testing cost. Inventory already paid for is not economically free; sampling, retained samples and damaged units are not sellable. "
 "Neither total is presented because too many inputs are unknown.",tone="warn"),
 tbl(["View","Includes"],
 [["A — incremental cash to launch inventory already owned","Excludes acquisition cost"],
  ["B — full product economics","Adds acquisition cost (owner input)"]],[3.0*inch,3.6*inch])]

# 11 GATES
st += [P("11. Release gates and contingencies",st_h1), rule()]
rg=rows_of("release_gates.csv")
st += [tbl(["Gate","Pass condition","Status"],
 [[r["gate_id"],trunc(r["pass_condition"],96),r["status"]] for r in rg],
 [0.5*inch,4.5*inch,1.6*inch]), Spacer(1,6),
 callout("On failed or inconclusive results",
 "Keep affected inventory ON HOLD. Identify the investigation, retest or qualified-review path. Do NOT dilute, blend, re-date, or make unsupported claims to bypass a failure. "
 "Disposal or remediation requires SEPARATE APPROVAL. A merchant-fulfilled contingency does not bypass product safety, labelling or Amazon compliance.",tone="bad")]

# 12 OWNER
st += [P("12. Owner decisions and immediate actions",st_h1), rule(),
 P("<b>Decisions:</b> classification path and who reviews · whether to send the lab message before shipping samples · SKU count and format · price scenarios · whether to pursue the organic claim · legal contracting entity."),
 P("<b>Immediate actions:</b>")]
for t in ["Verify exact legal spelling of the purchasing entity from business records.",
 "Count bags; sort by lot; photograph every lot.",
 "Weigh sample bags; record material, seal and damage.",
 "Locate invoice, specification, organic certificate, any COA or stability documents.",
 "Confirm lab identity, quote reference, panel and sample instructions.",
 "Approve the drafted lab confirmation message for sending.",
 "Decide who performs qualified results review and the shelf-life determination."]:
    st.append(B(t))

# APPENDICES
st += [PageBreak(), P("Appendix A — Inventory audit template",st_h1), rule(),
 tbl(["ID","Inspection item","Status","Blocks"],
 [[r["check_id"],trunc(r["inspection_item"],40),r["status"],r["blocks_which_gate"]] for r in ia],
 [0.5*inch,2.6*inch,1.9*inch,1.6*inch],fs=7.4)]

st += [PageBreak(), P("Appendix B — Testing and document checklist",st_h1), rule()]
td=rows_of("testing_and_document_checklist.csv")
st += [tbl(["ID","Category","Item","Status","Blocks"],
 [[r["item_id"],trunc(r["category"],16),trunc(r["item"],38),r["status"],r["blocks_which_gate"]] for r in td],
 [0.5*inch,0.95*inch,2.6*inch,1.35*inch,1.2*inch],fs=7.2)]

st += [PageBreak(), P("Appendix C — Full launch schedule",st_h1), rule()]
ls=rows_of("launch_schedule.csv")
st += [tbl(["Date","Scenario","Task","Role","Status"],
 [[r["est_completion_date"],r["scenario"],trunc(r["task"],52),trunc(r["responsible"],16),r["status"].replace("planning allowance","planning")] for r in ls],
 [0.75*inch,0.6*inch,3.05*inch,1.1*inch,0.9*inch],fs=6.8)]

st += [PageBreak(), P("Appendix D — Launch budget detail",st_h1), rule()]
lb=rows_of("launch_budget.csv")
st += [tbl(["ID","Category","Line","Amount","Type"],
 [[r["line_id"],r["category"],trunc(r["line"],52),r["amount_usd"],r["value_type"]] for r in lb],
 [0.55*inch,0.95*inch,2.7*inch,0.7*inch,1.7*inch],fs=7.0)]

st += [PageBreak(), P("Appendix E — Sources",st_h1), rule()]
sr=rows_of("source_evidence_register.csv")
st += [tbl(["ID","Title","Type","Limitation"],
 [[r["source_id"],trunc(r["title"],42),trunc(r["source_type"],28),trunc(r["limitations"],58)] for r in sr],
 [0.55*inch,2.0*inch,1.55*inch,2.5*inch],fs=7.0), Spacer(1,8),
 P("No Lion's Mane laboratory, supplier or certificate documents were found anywhere in the project tree. Absence of files is not proof the documents do not exist.",st_small)]

st += [Spacer(1,12), rule(PINE,1.2,4,4),
 Paragraph("WORKING PLAN — INVENTORY NOT RELEASED UNTIL GATES ARE MET",S("end",fontName=HEAD_B,fontSize=10,leading=14,textColor=RED,alignment=TA_CENTER)),
 Paragraph("No lab ordered · no payment · no Amazon submission · no shipment · no external message sent · baseline "+TODAY,
           S("end2",fontName=BODY_I,fontSize=8.3,leading=12,textColor=MUTED,alignment=TA_CENTER))]

Doc(PDF,pagesize=letter).build(st)
print("PDF WRITTEN:",PDF); print("SIZE:",os.path.getsize(PDF))
