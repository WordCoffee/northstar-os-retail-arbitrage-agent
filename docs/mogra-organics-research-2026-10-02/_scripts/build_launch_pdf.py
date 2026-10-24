# Build the Mogra holiday-launch PDF (ReportLab).
import csv, os
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.enums import TA_JUSTIFY, TA_CENTER
from reportlab.platypus import (BaseDocTemplate, PageTemplate, Frame, Paragraph, Spacer,
                                Table, TableStyle, PageBreak, HRFlowable, NextPageTemplate)
import sys as _sys
_sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from decision_sheet_pages import build_pages as _ds_pages
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

ROOT = os.path.join("docs", "mogra-organics-research-2026-10-02")
OUT = os.path.join(ROOT, "review_packet"); os.makedirs(OUT, exist_ok=True)
PDF = os.path.join(OUT, "Mogra_Organics_Holiday_Amazon_Launch_Blueprint_2026-10-02.pdf")
FD = r"C:\Windows\Fonts"
def reg(n,f):
    p=os.path.join(FD,f)
    if os.path.exists(p): pdfmetrics.registerFont(TTFont(n,p)); return True
    return False
HG = reg("Georg","georgia.ttf") and reg("Georg-B","georgiab.ttf") and reg("Georg-I","georgiai.ttf")
if reg("Ari","arial.ttf"): reg("Ari-B","arialbd.ttf"); reg("Ari-I","ariali.ttf"); BODY,BODY_B,BODY_I="Ari","Ari-B","Ari-I"
else: BODY,BODY_B,BODY_I="Helvetica","Helvetica-Bold","Helvetica-Oblique"
HEAD,HEAD_B,HEAD_I = ("Georg","Georg-B","Georg-I") if HG else ("Times-Roman","Times-Bold","Times-Italic")

PAPER=colors.HexColor("#FBFAF7"); INK=colors.HexColor("#1E2A26"); PINE=colors.HexColor("#22463A")
SAGE=colors.HexColor("#6E8B74"); CLAY=colors.HexColor("#9A6A4F"); RULE=colors.HexColor("#D8D4CB")
MUTED=colors.HexColor("#6B6B63"); WARNBG=colors.HexColor("#F3EFE7"); OKBG=colors.HexColor("#EDF2EE")
RED=colors.HexColor("#8C3B2E")
def S(n,**k): return ParagraphStyle(n,**k)
st_title=S("t",fontName=HEAD_B,fontSize=27,leading=32,textColor=PINE)
st_sub=S("s",fontName=HEAD_I,fontSize=14,leading=19,textColor=MUTED)
st_h1=S("h1",fontName=HEAD_B,fontSize=16.5,leading=20.5,textColor=PINE,spaceBefore=2,spaceAfter=7)
st_h2=S("h2",fontName=HEAD_B,fontSize=12,leading=15.5,textColor=INK,spaceBefore=9,spaceAfter=4)
st_body=S("b",fontName=BODY,fontSize=9.6,leading=13.6,textColor=INK,spaceAfter=5,alignment=TA_JUSTIFY)
st_bul=S("bu",fontName=BODY,fontSize=9.6,leading=13.4,textColor=INK,leftIndent=13,bulletIndent=3,spaceAfter=2.5)
st_small=S("sm",fontName=BODY,fontSize=8.3,leading=11.4,textColor=MUTED,spaceAfter=3,alignment=TA_JUSTIFY)
st_cell=S("c",fontName=BODY,fontSize=8.1,leading=10.5,textColor=INK)
st_cellh=S("ch",fontName=BODY_B,fontSize=8.1,leading=10.5,textColor=colors.white)
def P(t,s=st_body): return Paragraph(t,s)
def B(t): return Paragraph(t,st_bul,bulletText="•")
def rule(c=RULE,w=0.7,sb=2,sa=6): return HRFlowable(width="100%",thickness=w,color=c,spaceBefore=sb,spaceAfter=sa)
def tbl(header,rows,widths,fs=8.1):
    tot=float(sum(widths)); tgt=6.6*inch; widths=[w*tgt/tot for w in widths]
    cs=ParagraphStyle("cx",parent=st_cell,fontSize=fs,leading=fs+2.4)
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
    inner=[[Paragraph(f"<b>{title}</b>",S("ct",fontName=HEAD_B,fontSize=10.5,leading=13,textColor=tc))],
           [Paragraph(body,S("cb2",fontName=BODY,fontSize=9.3,leading=12.7,textColor=INK))]]
    t=Table(inner,colWidths=[6.6*inch],hAlign="LEFT")
    t.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,-1),bg),("BOX",(0,0),(-1,-1),0.6,RULE),
        ("LINEBEFORE",(0,0),(0,-1),2.4,SAGE),("LEFTPADDING",(0,0),(-1,-1),9),
        ("RIGHTPADDING",(0,0),(-1,-1),9),("TOPPADDING",(0,0),(-1,-1),6),("BOTTOMPADDING",(0,0),(-1,-1),6)]))
    return t

def rows_of(fn):
    with open(os.path.join(ROOT,fn),newline="",encoding="utf-8") as f: return list(csv.DictReader(f))
def trunc(s,n):
    s=(s or "").strip()
    return s if len(s)<=n else s[:n-1]+"…"
C={k:len(rows_of(v)) for k,v in {"rank":"product_opportunity_ranking.csv","comp":"competitor_observations.csv",
   "ps":"product_supplier_matrix.csv","ec":"economics_scenarios.csv","la":"launch_action_plan.csv","sr":"source_evidence_register.csv"}.items()}
TODAY="2026-10-02"

class Doc(BaseDocTemplate):
    def __init__(s,fn,**k):
        super().__init__(fn,**k)
        s.addPageTemplates([PageTemplate(id="v",frames=[Frame(0.95*inch,0.95*inch,6.6*inch,9.1*inch,id="m")],onPage=s.deco)])

    def deco(s,c,d):
        c.saveState(); w,h=letter
        c.setFillColor(PAPER); c.rect(0,0,w,h,stroke=0,fill=1)
        c.setFont(BODY,7.4); c.setFillColor(MUTED)
        c.drawString(0.95*inch,h-0.62*inch,"MOGRA ORGANICS — HOLIDAY AMAZON LAUNCH BLUEPRINT")
        c.setFont(BODY_I,7.4); c.setFillColor(CLAY)
        c.drawRightString(w-0.95*inch,h-0.62*inch,"RESEARCH AND WORKING PLAN — NOT A SALES GUARANTEE")
        c.setStrokeColor(RULE); c.setLineWidth(0.5); c.line(0.95*inch,h-0.70*inch,w-0.95*inch,h-0.70*inch)
        c.line(0.95*inch,0.78*inch,w-0.95*inch,0.78*inch)
        c.setFont(BODY,7.4); c.setFillColor(MUTED)
        c.drawString(0.95*inch,0.63*inch,f"T2 Holdings LLC · target Nov 15 2026 (planning) · {TODAY}")
        c.drawRightString(w-0.95*inch,0.63*inch,f"Page {d.page}")
        c.restoreState()

st=[]
# COVER
st += [Spacer(1,1.05*inch), Paragraph("Mogra Organics",st_title), Spacer(1,4),
 Paragraph("Wholesale Sourcing &amp; Holiday Amazon Launch Blueprint",S("x",fontName=HEAD,fontSize=17,leading=22,textColor=INK)),
 Spacer(1,14), rule(PINE,1.4,0,12),
 Paragraph("Which herbs and spices to launch, where to source them, what configuration to sell, "
           "what the economics could look like, and whether the mid-November target is credible.",
           S("lede",fontName=HEAD_I,fontSize=12,leading=17,textColor=MUTED)), Spacer(1,20),
 callout("RESEARCH AND WORKING PLAN — NOT A SALES GUARANTEE",
  "No sales are promised and no ‘guaranteed winner’ is identified. Amazon prices and ranks are single public observations on 2026-10-02 "
  "and may vary. Costs that are not verified are left blank, never zero. No supplier has been contacted, no account created, nothing purchased.",tone="warn"),
 Spacer(1,18),
 tbl(["Field","Value"],[
  ["Date",TODAY],
  ["Target","Buyable Amazon inventory by 2026-11-25 (latest acceptable 2026-12-01) — planning target"],
  ["Product budget","$1,500–$2,500 (product only; advertising shown separately)"],
  ["Assortment","2–4 SKUs, contingent on MOQ and economics"],
  ["Fulfilment","Food filling and sealing outsourced; artwork supplied by us"],
  ["Studio goal","Launch Mogra Organics culinary herbs/spices on Amazon US; December momentum"],
  ["Candidates researched",f"{C['rank']} products scored; {C['comp']} competitor observations captured"],
  ["Recommended first assortment","2 SKUs (Ceylon cinnamon ground; whole black pepper)"],
  ["Critical timing finding","BFCM FBA inbound deadlines (Oct 14/21/28) fall BEFORE the Nov 15 target"],
  ["Supply chain status","REVIEW-READY — no route is purchase-ready"],
  ["Entity","T2 Holdings LLC (owner-supplied spelling — not verified against records)"]],
  [1.7*inch,4.9*inch])]

# 0 FRONT-PAGE DECISION BRIEF
st += [PageBreak(), P("0. Front-page decision brief",st_h1), rule(),
 P("<b>Products recommended (provisional — no route is purchase-ready):</b>")]
st += [tbl(["SKU","Recommendation","Confidence","Why"],
 [["Ground Ceylon cinnamon","<b>Primary — provisional</b>","MEDIUM-HIGH","Premium band ($0.93–$1.56/oz) rewards quality differentiation; category BSR #1 is a Ceylon product"],
  ["Whole black pepper","<b>Primary — provisional</b>","MEDIUM","Verified organic supply; whole/refill format escapes the commodity floor"],
  ["Ceylon cinnamon sticks","Secondary — evaluate","MEDIUM","Giftable; needs quill grading"],
  ["Whole nutmeg / cloves","Candidate — not first launch","LOW-MEDIUM","Smaller categories; organic supply unconfirmed"],
  ["Baking-spice set","<b>Defer</b>","LOW","Multiplies packing and MSRP complexity"]],
 [1.35*inch,1.5*inch,0.9*inch,2.85*inch]), Spacer(1,7),
 P("<b>Why these:</b> commodity spices (turmeric, garlic, onion, paprika) are dominated by Amazon’s own private labels at "
   "<b>$0.30–$0.45/oz</b> and by incumbents with 11k–32k ratings. A new brand cannot win a price war. The premium band is where a quality claim can compete."),
 P("<b>Evidence confidence:</b> MEDIUM overall — demand and price evidence is observed; <b>supply timing is unproven</b>."),
 P("<b>Supply/timing feasibility:</b> <b>unresolved</b> — no supplier has provided a lead time. Nov 15 is planning, not a commitment."),
 P("<b>Economic conditions that must hold:</b> FBA fee and landed unit cost must leave material contribution <b>after</b> a realistic ACOS. Neither is known, so <b>no contribution figure is asserted</b>."),
 callout("Decisions and supplier responses needed next",
 "Decisions: final 2–4 SKUs · legal entity spelling · package format · route · label application model. "
 "Supplier responses: lead time, MOQ, price, and a LOT COA with heavy-metal results for Ceylon cinnamon.",tone="ok")]

# 1 FEASIBILITY
st += [PageBreak(), P("1. Objective and mid-November feasibility (corrected)",st_h1), rule()]
st += [callout("Published guidance establishes readiness RISK — not impossibility",
 "Amazon’s published Black Friday / Cyber Monday arrival dates fall in October, before the mid-November target. Those dates govern "
 "event readiness (Prime-badge/event eligibility); they do NOT prove that a later shipment cannot be received and become buyable. "
 "A 15 November launch therefore carries HIGH RISK of missing event readiness and cannot be guaranteed event-ready.",tone="warn"),
 Spacer(1,7),
 tbl(["Channel","Published arrival date","Meaning"],
  [["AWD","Oct 14, 2026","Event-readiness guidance"],
   ["FBA (minimal shipment splits)","Oct 21, 2026","Event-readiness guidance"],
   ["FBA (Amazon-optimized splits)","Oct 28, 2026","Event-readiness guidance"]],[1.7*inch,1.6*inch,3.3*inch]),
 Spacer(1,6),
 P("<b>Four separate things — do not conflate them:</b>"),
 tbl(["Stage","What it means","Status"],
  [["1. Published holiday arrival guidance","Amazon’s stated event-readiness dates","VERIFIED"],
   ["2. Supplier production timing","How long a supplier takes to produce","UNKNOWN — no supplier has quoted a lead time"],
   ["3. Delivery to Amazon","Shipment physically arrives at a fulfilment centre","UNKNOWN"],
   ["4. Receiving and buyable inventory","Check-in completes; ASIN is buyable","UNKNOWN — always later than delivery"],
   ["Actual event / program eligibility","Whether the listing qualifies for the event/Prime badge","UNRESOLVED"]],
  [1.75*inch,3.05*inch,1.8*inch]),
 Spacer(1,6),
 callout("No availability is guaranteed",
 "No guarantee is made for November 15, Black Friday, Cyber Monday, or December availability. Two honest paths: Path 1 (target-honest) — buyable "
 "by ~Nov 15 and compete for December; Path 2 (BFCM-honest) — only with pre-existing stock or an extremely fast US co-packer, which is not supportable from a cold start today.",tone="bad")]

# 2 SHORTLIST
st += [P("2. Recommended initial product shortlist",st_h1), rule(),
 P(f"Scored on 12 criteria (1 weak – 5 strong) across {C['rank']} candidates. Confidence is reported separately, and <b>unknowns never raise a score</b>. Full table: product_opportunity_ranking.csv.")]
rk=rows_of("product_opportunity_ranking.csv")
top=[r for r in rk if r["best_product_rank"] in ("1","2","3","4","5")]
top=sorted(top,key=lambda r:int(r["best_product_rank"]))
st += [tbl(["Rank","Product","Confidence","Verdict","Why"],
 [[r["best_product_rank"],r["product"],r["evidence_confidence"],r["verdict"],r["why_it_could_work"][:120]] for r in top],
 [0.45*inch,1.35*inch,0.85*inch,1.1*inch,2.85*inch]), Spacer(1,6),
 callout("Recommended focused assortment: 2 SKUs",
 "Ceylon cinnamon (ground) and whole black pepper. A third (cinnamon sticks) only if packing and lead time support it. "
 "The evidence does not support forcing 3–4 SKUs.",tone="ok")]

# 3 DEMAND
st += [PageBreak(), P("3. Demand and seasonality evidence",st_h1), rule()]
st += [P("<b>Confirmed publicly:</b> cinnamon, nutmeg, ginger, cloves and allspice are the documented holiday baking/spice set; Amazon maintains dedicated Nutmeg and Cinnamon BSR subcategories."),
 P("<b>Adverse finding that shapes everything:</b> Amazon’s own private labels hold many top category positions at sub-$2 prices on commodity spices."),
 tbl(["Commodity product","Observed price","$/oz","Owner"],
  [["Amazon Saver Garlic Powder 2.5 oz","$0.80","$0.32","Amazon private label"],
   ["Amazon Grocery Garlic Powder 3.9 oz","$1.60","$0.41","Amazon private label"],
   ["Happy Belly Onion Powder","$1.29","—","Amazon private label"],
   ["Happy Belly Ground Cinnamon","$1.32","—","Amazon private label"],
   ["Amazon Grocery Paprika 2.75 oz","$1.25","$0.45","Amazon private label"]],
  [2.7*inch,1.3*inch,0.8*inch,1.8*inch]), Spacer(1,6),
 callout("Interpretation","A new brand cannot win a price contest on commodity spices against Amazon’s own labels. The opportunity must be a quality/differentiation play, not a price play.",tone="warn"),
 P("<b>Note:</b> salt dominates 8 of the top-30 Herbs/Spices positions — but plain salt cannot be USDA organic and is outside Mogra’s premise.",st_small)]

# 4 COMPETITION
st += [P("4. New-brand competition assessment (corrected)",st_h1), rule()]
comp=rows_of("competitor_observations.csv")
st += [tbl(["Category","Incumbent scale (public, with context)","New-listing accessibility"],
 [["Organic turmeric","B08HYBN4DJ 12,402 · B00H3QRW6E 11,052 · ~$0.59–0.62/oz","Poor — price war"],
  ["Organic garlic powder","B07QW1GKR1 32,169 (private label) · B074ZK8MQS 25,885","Poor — entrenched + private label"],
  ["Ceylon cinnamon","Premium band $0.93–$1.56/oz across several listings","Better — quality differentiation possible"],
  ["Whole black pepper","premium whole listing ~$9.60 in top-15 (ASIN not captured)","Moderate — format differentiation"]],
 [1.3*inch,3.3*inch,2.0*inch]), Spacer(1,6),
 callout("Ratings-context correction",
 "The 34,526 figure appears on THREE Simply Organic Ceylon variants (B00ZK8YIXW, B0GVVQV4S7, B07BRPCK32) — it is a variation-family/parent-level count, "
 "NOT a single child ASIN’s reviews. The same applies to Micro Ingredients (4,639 across its sizes). Broad family review counts must not be attributed to one specific Ceylon product.",tone="warn"),
 P("Commodity products are kept separate from directly comparable premium offers in competitor_observations.csv via a <b>comparable_class</b> field.",st_small),
 P("<b>Category demand ≠ attainable demand.</b> Nothing here promises sales.")]

# 5 FINALIST COMPARISON
st += [P("5. Finalist decision comparison",st_h1), rule(),
 P(f"Six finalists compared across demand, seasonality, accessibility, competitor observations, price/pack, differentiation, supply timing and confidence. Full table: finalist_decision_comparison.csv.")]
fd=rows_of("finalist_decision_comparison.csv")
st += [tbl(["Candidate","Decision","Confidence","Supply timing","Why vs alternatives"],
 [[r["candidate"],r["decision"],r["confidence"],trunc(r["supply_timing_evidence"],44),trunc(r["why_this_vs_alternatives"],86)] for r in fd],
 [1.2*inch,1.25*inch,0.7*inch,1.5*inch,1.95*inch],fs=7.2), Spacer(1,5),
 P("<b>Why each recommended SKU wins:</b> ground Ceylon cinnamon beats turmeric and garlic because the premium band rewards a quality claim while those are "
   "$0.30–$0.62/oz price wars; whole black pepper beats ground because the whole/refill format escapes the private-label floor; cinnamon sticks lose to ground "
   "cinnamon on quill-grading and packing-format risk; nutmeg and cloves rank lower on category size and unconfirmed organic supply."),
 P("<b>Reclassification:</b> both primary recommendations remain <b>PROVISIONAL</b>. Where evidence did not support the original ranking, the recommendation is downgraded accordingly.",st_small)]

# 6 CINNAMON POSITIONING (separated concerns)
st += [PageBreak(), P("6. Cinnamon positioning — separated concerns",st_h1), rule(),
 P("These three are kept strictly apart. Conflating them is how unsupported claims get made.")]
st += [tbl(["Category","What belongs here","Status"],
 [["<b>Food-safety & lot-verification</b>","Heavy metals, microbiology, adulteration screening, lot traceability","Requirement — a <b>lot</b> COA, not a generic one"],
  ["<b>Proposed consumer differentiation</b>","Species-verified true Ceylon; transparency about testing","PROPOSED positioning (not a claim)"],
  ["<b>Evidence of willingness to pay</b>","Observed premium band $0.93–$1.56/oz for Ceylon powder; $1.72–$2.27/oz for sticks","Observed prices only; not proof Mogra can price there"]],
 [1.35*inch,3.3*inch,1.95*inch]), Spacer(1,6),
 callout("Claim discipline",
 "Do NOT use “lead-free”, “safer”, or competitor-superiority language without appropriate substantiation. A generic COA is NOT equivalent to testing the "
 "lot Mogra actually supplies. Any testing claim must be supported by a lot-specific result for the supplied lot.",tone="bad"),
 P("<b>Differentiation, stated safely:</b> Mogra may position on <b>species identity</b> (true Ceylon, not cassia) and on supplying <b>lot-level</b> heavy-metal "
   "results for the specific lot sold. Both are substantiable only with documents in hand.",st_small)]

# 7 AVOID
st += [P("7. Avoid or defer",st_h1), rule()]
av=[r for r in rk if r["verdict"] in ("AVOID OR DEFER","SEPARATE TRACK - NOT ORGANIC")]
st += [tbl(["Product","Why avoid / defer"],
 [[r["product"],r["why_it_could_fail"][:150]] for r in av],[1.7*inch,4.9*inch]),
 Spacer(1,4),
 P("Also defer: <b>cumin, oregano, thyme, rosemary</b> (commodity, weak differentiation) and <b>complex blends / gift boxes</b> (production burden incompatible with the timeline).")]

# 7 PACKAGING
st += [P("8. Package formats and positioning",st_h1), rule(),
 tbl(["SKU","Format","Net qty","Positioning","Setup dependency"],
 [["Ceylon cinnamon","Pouch or jar","2 oz (proposed)","Premium, lab-tested single-origin Ceylon","Pouch faster/lighter; jar premium but heavier"],
  ["Black pepper","Refill pouch","3 oz (proposed)","Verified organic, whole/refill","Pouch"]],
 [1.15*inch,0.95*inch,0.9*inch,1.9*inch,1.7*inch]),
 Spacer(1,4), P("<b>Do not assume</b> custom molds or elaborate printed packaging can be ready by the deadline. Standard pouch/jar formats only for launch.")]

# 8 SUPPLIERS
st += [PageBreak(), P("9. Wholesale suppliers matched to products",st_h1), rule(),
 P(f"Using the existing supplier research. Full matrix: product_supplier_matrix.csv ({C['ps']} rows).")]
ps=rows_of("product_supplier_matrix.csv")
st += [tbl(["Product","Supplier","Role","Organic","MOQ","Price"],
 [[r["product"][:34],r["supplier_name"][:30],r["supplier_role"][:26],r["organic_status_verified"][:26],r["moq_known"],r["price_status"]] for r in ps],
 [1.15*inch,1.25*inch,1.15*inch,1.25*inch,0.75*inch,1.05*inch],fs=7.5), Spacer(1,5),
 P("2–3 options exist per recommended product where evidence permits. <b>No option has a price.</b>")]

# 9 ROUTES
st += [P("10. Sourcing routes (corrected language)",st_h1), rule(),
 tbl(["Route","Launch role","Characterisation (corrected)"],
 [["A Overseas finished / private-label (Pearl)","candidate","<b>Potentially fastest</b> to a finished unit IF packing is certified and lead time is short — UNPROVEN"],
  ["B Overseas bulk + US co-packer","candidate","<b>Cost hypothesis</b>: bulk pricing may improve margin; import lead time and obligations are unquantified"],
  ["C US turnkey (McKinney TX cluster)","candidate","<b>Potentially fastest</b> (no import) — UNPROVEN"],
  ["D US ingredients + US packing","fallback","Domestic simplicity; cost unproven"]],
 [1.9*inch,0.85*inch,3.85*inch]), Spacer(1,5),
 callout("Withdrawn claims",
 "Prior statements that any route is “fastest” or has “best long-term margin” are WITHDRAWN as unsupported — no comparable lead times or sufficiently "
 "complete costs exist. No route is proven cheapest or fastest.",tone="warn")]

# 10 COST
st += [P("11. Cost coverage and hypothetical economics",st_h1), rule(),
 P("<b>Known prices: three, all US domestic retail references — none a wholesale quote.</b>"),
 tbl(["Item","Price","Type"],
 [["Flavoric organic turmeric","$12.98–$111.98/lb","PUBLISHED_RETAIL_REFERENCE"],
  ["Flavoric organic black pepper","$49.98–$369.98/lb","PUBLISHED_RETAIL_REFERENCE"],
  ["Spices Inc chipotle salt","$6.55/unit","PUBLISHED_RETAIL_REFERENCE"]],
 [2.3*inch,2.1*inch,2.2*inch]), Spacer(1,5),
 P("<b>Preserved as null (never zero):</b> ingredient, processing, packaging, packing, setup, testing, freight, duty/AD-CVD/broker, storage, FBA fees, PPC."),
 P("<b>Formulas (shown without validated results):</b>"),
 tbl(["Metric","Formula"],
 [["Max acceptable finished-unit cost","price − referral − FBA fee − target contribution"],
  ["Contribution before advertising","price − referral − FBA fee − landed unit cost"],
  ["Break-even ACOS","contribution before advertising ÷ price"]],[1.9*inch,4.7*inch]),
 Spacer(1,5),
 callout("HYPOTHETICAL illustration — every input assumed, NOT a forecast, NOT validated",
 "Ceylon cinnamon 2 oz: 12.99 − (12.99×0.15) − 3.50 − 4.00 = <b>3.54/unit</b>; break-even ACOS = 3.54 ÷ 12.99 = <b>27.3%</b>. "
 "Whole black pepper 3 oz: 11.99 − 1.80 − 3.50 − 3.50 = <b>3.19/unit</b>; break-even ACOS = <b>26.6%</b>. "
 "Assumed: price, 15% referral, FBA fee $3.50, landed cost $3.50–$4.00. <b>No supplier quote, CPC or sales forecast is invented.</b>",tone="warn"),
 P("<b>Initial inventory (500 units) is PROPOSED illustrative only.</b> Cash exposure = 500 × landed unit cost, which cannot be computed. Full detail: hypothetical_economics.csv (26 lines)."),
 P("<b>Pricing-lines reconciliation (54 → 15):</b> the earlier 54 figure came from a malformed intermediate CSV whose unquoted commas split rows and inflated a naive count. "
   "The rebuilt table contains <b>15</b> genuine pricing lines, because most suppliers publish no price. The 54 figure is WITHDRAWN.",st_small),
 P("<b>Pricing lines (15) ≠ economics lines (17).</b> Pricing lines are one row per actual price or explicit quote-required position; economics lines are one row per cost/price component in a modelled SKU, many UNKNOWN or FORMULA_ONLY.",st_small)]

st.append(PageBreak())
# 11 AMAZON PLAN
st += [P("12. Amazon listing and advertising plan",st_h1), rule()]
for t in [
 "<b>Eligibility first:</b> Seller Central account, grocery category approval if required, brand-name consistency, product identifiers.",
 "<b>Brand Registry:</b> <b>do not assume it is available</b>. If unregistered, A+ content and Vine may be unavailable.",
 "<b>Listing:</b> title, bullets, description, backend search terms; compliant claims only; <b>no unverified organic claims</b>; product photography.",
 "<b>FBA prep:</b> correct labelling and expiration-date requirements if applicable — confirm current Amazon policy.",
 "<b>PPC:</b> small structured test — exact-match on core terms, modest daily budget; scale on conversion.",
 "<b>Reviews:</b> compliant options only. <b>No incentivised reviews, no manipulation, no ranking guarantees.</b>",
 "<b>Metrics:</b> impressions, CTR, conversion, ACOS, contribution — with per-SKU scale/pause criteria.",
]: st.append(B(t))
st += [P("<b>Keyword clusters are PROPOSED and unmeasured.</b> No search volumes, CPCs or conversion rates are asserted.",st_small)]

# 12 CRITICAL PATH
st += [P("13. Dated launch critical path",st_h1), rule(),
 P(f"Full plan: launch_action_plan.csv ({C['la']} rows). <b>All durations are planning allowances, not supplier promises.</b>")]
la=rows_of("launch_action_plan.csv")
st += [tbl(["Date","Milestone","Type"],
 [[r["target_date"],r["milestone"],r["date_type"]] for r in la if r["seq"] not in ("X",)][:16],
 [1.35*inch,3.75*inch,1.5*inch],fs=7.8), Spacer(1,5),
 callout("Delivery ≠ sellable inventory",
 "Arrival at a fulfilment centre is not the same as buyable inventory — receiving and check-in take additional time. "
 "Contingency: Plan B compliant merchant-fulfilled availability (NOT automatically Prime-eligible); Plan C a single SKU or revised timing.",tone="warn")]

# 13 DECEMBER
st += [P("14. December sales and inventory scenarios",st_h1), rule(),
 P("<b>No operating history exists, so no revenue is forecast.</b> Three structural scenarios are given instead of invented numbers."),
 tbl(["Scenario","Character","Response"],
 [["Conservative","Weak first-week conversion; ads paused early","Preserve stock; protect cash"],
  ["Base","Modest conversion; ads scaled slowly","Controlled reorder at ~2 weeks"],
  ["Upside","Strong conversion; ads scaled","Reorder risk and stockout risk"]],
 [1.2*inch,3.0*inch,2.4*inch]), Spacer(1,5),
 P("<b>Modeled fields (all assumption-labeled):</b> units sold, revenue, ad spend, contribution, inventory remaining, reorder timing, stockout risk, cash requirement."),
 P("<b>First-week / second-week logic:</b> if week-1 conversion is below break-even, reduce spend and hold stock; if above, scale gradually. "
   "<b>Do not assume demand stays strong through December 31</b> — some holiday spice demand peaks before December.")]

# 14 RISK
st += [P("15. Risks and contingency",st_h1), rule(),
 tbl(["ID","Risk","Impact","Mitigation"],
 [["RK-05","AD/CVD or duty applies, unverified","Very High","Broker review before import"],
  ["RK-02","Certified input mistaken for certified finished pack","High","Certifier label review"],
  ["RK-14","Nov 15 target missed → no BFCM","High","Accept December framing; Plan B/C"],
  ["RK-15","Commodity price war on chosen SKU","High","Choose cinnamon / whole pepper, not commodities"],
  ["RK-07","Turmeric adulteration / cinnamon heavy metals","High","Lot COA required"],
  ["RK-16","Amazon private label undercuts entry price","Med-High","Avoid commodity SKUs"],
  ["RK-09","Missing costs treated as zero","High","Nulls stay null"]],
 [0.55*inch,2.75*inch,0.85*inch,2.45*inch]), Spacer(1,4),
 P("<b>Contingency:</b> if supplier responses slip past ~Oct 13, shift to Plan C — a <b>single</b> SKU (Ceylon cinnamon) rather than two.")]

st.append(PageBreak())
# 15 DECISIONS
st += [P("16. Owner decisions and immediate next actions",st_h1), rule(),
 P("<b>Immediate decisions:</b>")]
for t in ["<b>Final 2 SKUs</b> — recommend Ceylon cinnamon ground + whole black pepper.",
 "<b>Legal entity spelling</b> — blocks all outreach.","<b>Package format + net qty</b> (pouch vs jar; 2 oz / 3 oz).",
 "<b>Route</b> — investigate A and C for speed, B for long-term.","<b>Budget ceiling</b> for pilot + PPC."]: st.append(B(t))
st += [P("<b>Immediate actions:</b>")]
for t in ["Send the 5 prepared RFQs (blocked only on entity spelling).","Commission the customs-broker review.",
 "Request a <b>lot COA with heavy-metal results</b> for candidate Ceylon cinnamon.",
 "Verify NOP handler certification for the US co-packers."]: st.append(B(t))

# 17 PARTNER DECISION PACKET
st += [PageBreak(), P("17. Partner decision packet", st_h1), rule(),
 P("Providers compared on the SAME product specification and quantity basis. Full detail: partner_decision_packet.csv (8 providers). "
   "Every unknown field is marked <b>QUOTE REQUIRED</b> — no price is invented.")]
pp=rows_of("partner_decision_packet.csv")
st += [tbl(["#","Provider","Country","Capability","MOQ","Price","Cust. ingredient?","Our labels?","Priority"],
 [[r["provider_id"].replace("PP-",""),trunc(r["company"],26),trunc(r["country"],16),trunc(r["capability"],40),
   trunc(r["moq"],18),r["price_status"],trunc(r["customer_supplied_ingredients"],12),trunc(r["our_labels_applied"],14),r["outreach_priority"]] for r in pp],
 [0.3*inch,1.05*inch,0.75*inch,1.45*inch,0.85*inch,0.7*inch,0.75*inch,0.75*inch,0.55*inch],fs=6.6), Spacer(1,6),
 P("<b>Outreach priority and reasons</b> (first three):")]
st += [tbl(["Provider","Why this priority"],
 [[trunc(r["company"],26),trunc(r["outreach_reason"],104)] for r in pp[:3]],[1.4*inch,5.2*inch]), Spacer(1,6),
 callout("Two sourcing models compared — not ranked on price alone",
 "(A) <b>same-company supply + packing</b> (turnkey: e.g. Pearl, JAPC, Spices Inc, Specialty Food Co-Packers, Organic Spices Inc), versus "
 "(B) <b>bulk supply + a separate qualified food packer</b> (e.g. Pearl bulk + Spices Inc). Model B needs two contracts and separate import responsibility; "
 "Model A is simpler but concentrates on one firm. <b>No route is declared cheapest or fastest</b> — that requires comparable quotes.",tone="note"),
 Spacer(1,4),
 P("<b>Label application</b> is compared explicitly: (i) <b>provider-applied</b> label artwork (we supply artwork; they print/apply), versus "
   "(ii) <b>receiving sealed units</b> and applying our label ourselves. Column “Our labels?” shows each provider's stated capability, all QUOTE REQUIRED.",st_small),
 P("<b>Label approval is owner-reported and its scope is NOT audited by this research.</b> Nothing here implies the label has been reviewed or cleared.",st_small)]

# 18 DATED ACTION PLAN
st += [PageBreak(), P("18. Dated action plan (Oct 5 – Dec 1)", st_h1), rule(),
 P("Three parallel workstreams. Every milestone carries a date, owner role, dependencies, required evidence, status, delay consequence and backup. "
   "Full detail: launch_schedule.csv (23 milestones).")]
ls=rows_of("launch_schedule.csv")
ws={"Owner/scope":"Owner &amp; scope","Supplier/samples":"1 · Supplier selection &amp; samples",
    "Compliance/label":"2 · Packaging, labelling &amp; compliance","Amazon/launch":"3 · Amazon listing, shipment &amp; ads"}
st += [tbl(["Date","Workstream","Milestone","Role","Status","If delayed"],
 [[r["est_completion_date"],trunc(ws.get(r["workstream"],r["workstream"]),26),trunc(r["milestone"],52),
   r["responsible_role"],r["status"].replace("planning allowance","planning"),trunc(r["consequence_of_delay"],34)] for r in ls],
 [0.72*inch,1.5*inch,2.35*inch,0.7*inch,0.6*inch,1.0*inch],fs=6.5), Spacer(1,6),
 callout("Five distinct states — never conflate them",
 "1. <b>Production complete</b> (units built)  →  2. <b>Shipment dispatched</b> (leaves origin)  →  3. <b>Delivered to Amazon</b> (arrives at FC)  →  "
 "4. <b>Received / available inventory</b> (check-in complete)  →  5. <b>Buyable listing</b> (live ASIN with active offer). "
 "Each is later than the one before; delivery is NOT buyable inventory.",tone="warn")]

# 19 DECISION GATES
st += [PageBreak(), P("19. Decision gates", st_h1), rule(),
 P("Use these to reduce assortment, change providers, or revise fulfilment. <b>Documentation and safety are not compromised to preserve a date.</b>")]
dg=rows_of("decision_gates.csv")
st += [tbl(["Gate","Trigger","Decision","Options"],
 [[r["gate_id"],trunc(r["trigger"],66),r["decision_required"],trunc(r["options"],72)] for r in dg],
 [0.45*inch,2.1*inch,1.25*inch,2.8*inch],fs=6.8), Spacer(1,6),
 P("<b>Rule:</b> if a gate fires and the target is no longer supported, prefer reducing the assortment or moving to 2026-12-01 over shipping with incomplete documentation or an unverified organic claim.",st_small),
 P("<b>Budget:</b> product budget is $1,500–$2,500. Advertising, testing, freight and any certification are shown <b>separately</b> and are not part of that figure.",st_small)]

# APPENDICES
def trunc(s,n): s=(s or "").strip(); return s if len(s)<=n else s[:n-1]+"…"
st += [PageBreak(), P("Appendix A — Product opportunity ranking (all candidates)",st_h1), rule(),
 P(f"All {C['rank']} candidates. Scores 1–5; confidence separate; unknowns never raise a score.",st_small),
 tbl(["Rank","Product","Confidence","Verdict"],
 [[r["best_product_rank"],r["product"],r["evidence_confidence"],r["verdict"]] for r in sorted(rk,key=lambda x:int(x["best_product_rank"]))],
 [0.45*inch,3.15*inch,1.2*inch,1.8*inch],fs=7.6)]

st += [PageBreak(), P("Appendix B — Competitor observations",st_h1), rule(),
 P(f"All {C['comp']} public observations (2026-10-02). Single observation; may vary by session.",st_small),
 tbl(["ID","Brand","Product","Qty","Price","$/oz","Rating","Ratings"],
 [[r["obs_id"],trunc(r["brand"],24),trunc(r["product"],36),r["net_qty"],r["price_usd"],r["price_per_oz_usd"],r["rating"],r["ratings_count"]] for r in comp],
 [0.45*inch,1.1*inch,1.85*inch,0.62*inch,0.62*inch,0.55*inch,0.5*inch,0.7*inch],fs=7.2)]

st += [PageBreak(), P("Appendix C — Economics scenario lines",st_h1), rule(),
 P(f"All {C['ec']} lines. Verified / assumed / unknown is labelled on every line.",st_small),
 tbl(["Scenario","Line","Value","Unit","Type"],
 [[trunc(r["sku_scenario"],34),trunc(r["cost_or_price_line"],40),r["value_usd"],r["unit"],r["value_type"]] for r in rows_of("economics_scenarios.csv")],
 [1.75*inch,2.25*inch,0.6*inch,0.75*inch,1.25*inch],fs=7.2)]

st += [PageBreak(), P("Appendix D — Sources",st_h1), rule(),
 P(f"{C['sr']} sources. Amazon observations are public, dated 2026-10-02, and may vary.",st_small),
 tbl(["ID","Title","Type","Used for"],
 [[r["source_id"],trunc(r["title"],52),trunc(r["source_type"],26),trunc(r["used_for"],70)] for r in rows_of("source_evidence_register.csv")],
 [0.5*inch,2.1*inch,1.1*inch,2.9*inch],fs=7.2), Spacer(1,10),
 P("Corrections and limitations retained: retail prices are not wholesale quotes; unknown costs remain unknown; no route is proven cheapest; "
   "Amazon BSR rank is not unit sales; ‘bought in past month’ is not a precise sales figure; review count is not current velocity.",st_small)]

st += [Spacer(1,12), rule(PINE,1.2,4,4),
 Paragraph("RESEARCH AND WORKING PLAN — NOT A SALES GUARANTEE",S("end",fontName=HEAD_B,fontSize=10,leading=14,textColor=CLAY,alignment=TA_CENTER)),
 Paragraph("Prepared for owner review · T2 Holdings LLC (entity spelling unverified) · "+TODAY,S("end2",fontName=BODY_I,fontSize=8.5,leading=12,textColor=MUTED,alignment=TA_CENTER))]

Doc(PDF,pagesize=letter).build(st)
print("PDF WRITTEN:",PDF); print("SIZE:",os.path.getsize(PDF))
