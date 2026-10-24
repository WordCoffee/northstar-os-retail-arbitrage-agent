# Build the Mogra Organics review PDF with ReportLab.
import csv, os
from datetime import date
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_JUSTIFY
from reportlab.platypus import (BaseDocTemplate, PageTemplate, Frame, Paragraph, Spacer,
                                Table, TableStyle, PageBreak, KeepTogether, HRFlowable)
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

ROOT = os.path.join("docs", "mogra-organics-research-2026-10-02")
OUT = os.path.join(ROOT, "review_packet")
os.makedirs(OUT, exist_ok=True)
PDF = os.path.join(OUT, "Mogra_Organics_Sourcing_Launch_Working_Blueprint_2026-10-02.pdf")

# ---------- fonts (premium editorial: serif headings + clean sans body) ----------
FONT_DIR = r"C:\Windows\Fonts"
def reg(name, fname):
    p = os.path.join(FONT_DIR, fname)
    if os.path.exists(p):
        pdfmetrics.registerFont(TTFont(name, p)); return True
    return False

HAS_GEORGIA = reg("Georg", "georgia.ttf") and reg("Georg-B", "georgiab.ttf") and reg("Georg-I", "georgiai.ttf")
if reg("Ari", "arial.ttf"): 
    reg("Ari-B", "arialbd.ttf"); reg("Ari-I", "ariali.ttf")
    BODY, BODY_B, BODY_I = "Ari", "Ari-B", "Ari-I"
else:
    BODY, BODY_B, BODY_I = "Helvetica", "Helvetica-Bold", "Helvetica-Oblique"
if HAS_GEORGIA:
    HEAD, HEAD_B, HEAD_I = "Georg", "Georg-B", "Georg-I"
else:
    HEAD, HEAD_B, HEAD_I = "Times-Roman", "Times-Bold", "Times-Italic"

# ---------- palette (neutral paper + pine ink + restrained botanical) ----------
PAPER   = colors.HexColor("#FBFAF7")
INK     = colors.HexColor("#1E2A26")
PINE    = colors.HexColor("#22463A")
SAGE    = colors.HexColor("#6E8B74")
CLAY    = colors.HexColor("#9A6A4F")
RULE    = colors.HexColor("#D8D4CB")
MUTED   = colors.HexColor("#6B6B63")
WARNBG  = colors.HexColor("#F3EFE7")
OKBG    = colors.HexColor("#EDF2EE")

# ---------- styles ----------
def S(name, **kw):
    return ParagraphStyle(name, **kw)
st_title = S("t", fontName=HEAD_B, fontSize=30, leading=35, textColor=PINE)
st_sub   = S("s", fontName=HEAD_I, fontSize=15, leading=20, textColor=MUTED)
st_h1    = S("h1", fontName=HEAD_B, fontSize=17, leading=21, textColor=PINE, spaceBefore=2, spaceAfter=7)
st_h2    = S("h2", fontName=HEAD_B, fontSize=12.5, leading=16, textColor=INK, spaceBefore=9, spaceAfter=4)
st_body  = S("b", fontName=BODY, fontSize=9.6, leading=13.6, textColor=INK, spaceAfter=5, alignment=TA_JUSTIFY)
st_bullet= S("bu", fontName=BODY, fontSize=9.6, leading=13.4, textColor=INK, leftIndent=13, bulletIndent=3, spaceAfter=2.5)
st_small = S("sm", fontName=BODY, fontSize=8.3, leading=11.4, textColor=MUTED, spaceAfter=3, alignment=TA_JUSTIFY)
st_cell  = S("c", fontName=BODY, fontSize=8.1, leading=10.6, textColor=INK)
st_cellb = S("cb", fontName=BODY_B, fontSize=8.1, leading=10.6, textColor=INK)
st_cellh = S("ch", fontName=BODY_B, fontSize=8.1, leading=10.6, textColor=colors.white)
st_status= S("sta", fontName=BODY, fontSize=8.6, leading=12, textColor=CLAY)
st_cap   = S("cap", fontName=BODY_I, fontSize=8, leading=10.6, textColor=MUTED, spaceAfter=6)

def P(t, s=st_body): return Paragraph(t, s)
def B(t): return Paragraph(t, st_bullet, bulletText="•")

def rule(c=RULE, w=0.7, sb=2, sa=6):
    return HRFlowable(width="100%", thickness=w, color=c, spaceBefore=sb, spaceAfter=sa)

def tbl(header, rows, widths, aligns=None):
    # Normalise column widths to exactly the 6.6in frame so no table overflows the margin.
    total = float(sum(widths))
    target = 6.6 * inch
    widths = [w * target / total for w in widths]
    data = [[Paragraph(h, st_cellh) for h in header]]
    for r in rows:
        data.append([Paragraph(str(c) if c is not None else "—", st_cell) for c in r])
    t = Table(data, colWidths=widths, repeatRows=1, hAlign="LEFT")
    cmds = [
        ("BACKGROUND", (0,0), (-1,0), PINE),
        ("VALIGN", (0,0), (-1,-1), "TOP"),
        ("TOPPADDING", (0,0), (-1,-1), 4.2),
        ("BOTTOMPADDING", (0,0), (-1,-1), 4.2),
        ("LEFTPADDING", (0,0), (-1,-1), 5),
        ("RIGHTPADDING", (0,0), (-1,-1), 5),
        ("LINEBELOW", (0,0), (-1,-1), 0.35, RULE),
        ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.white, PAPER]),
    ]
    if aligns:
        for i,a in enumerate(aligns): cmds.append(("ALIGN",(i,0),(i,-1),a))
    t.setStyle(TableStyle(cmds))
    return t

def callout(title, body, tone="note"):
    bg = OKBG if tone=="ok" else (WARNBG if tone=="warn" else PAPER)
    inner = [[Paragraph(f"<b>{title}</b>", S("ct", fontName=HEAD_B, fontSize=10.5, leading=13, textColor=PINE))],
             [Paragraph(body, S("cb2", fontName=BODY, fontSize=9.3, leading=12.8, textColor=INK))]]
    t = Table(inner, colWidths=[6.6*inch], hAlign="LEFT")
    t.setStyle(TableStyle([
        ("BACKGROUND",(0,0),(-1,-1), bg),
        ("BOX",(0,0),(-1,-1),0.6, RULE),
        ("LINEBEFORE",(0,0),(0,-1),2.4, SAGE),
        ("LEFTPADDING",(0,0),(-1,-1),9),("RIGHTPADDING",(0,0),(-1,-1),9),
        ("TOPPADDING",(0,0),(-1,-1),6),("BOTTOMPADDING",(0,0),(-1,-1),6),
    ]))
    return t

# ---------- counts from CSV ----------
def nrows(fn):
    p = os.path.join(ROOT, fn)
    with open(p, newline="", encoding="utf-8") as f:
        return sum(1 for _ in csv.DictReader(f))
C = {k: nrows(v) for k,v in {
    "suppliers":"supplier_master.csv","resources":"resources_and_directories.csv",
    "products":"supplier_product_matrix.csv","pricing":"pricing_comparison.csv",
    "verify":"organic_verification.csv","checks":"priority_verification_queue.csv",
    "routes":"route_comparison.csv","evidence":"evidence_register.csv",
    "risk":"risk_register.csv","decision":"decision_register.csv",
}.items()}

TODAY = "2026-10-02"

# ---------- page template ----------
class Doc(BaseDocTemplate):
    def __init__(self, fn, **kw):
        super().__init__(fn, **kw)
        frame = Frame(0.95*inch, 0.95*inch, 6.6*inch, 9.1*inch, id="main")
        self.addPageTemplates([PageTemplate(id="v", frames=[frame], onPage=self.deco)])
    def deco(self, canv, doc):
        canv.saveState()
        w,h = letter
        canv.setFillColor(PAPER); canv.rect(0,0,w,h,stroke=0,fill=1)
        # header
        canv.setFont(BODY, 7.4); canv.setFillColor(MUTED)
        canv.drawString(0.95*inch, h-0.62*inch, "MOGRA ORGANICS — SOURCING & LAUNCH WORKING BLUEPRINT")
        canv.setFont(BODY_I, 7.4); canv.setFillColor(CLAY)
        canv.drawRightString(w-0.95*inch, h-0.62*inch, "WORKING BLUEPRINT — NOT PURCHASE OR LAUNCH AUTHORIZATION")
        canv.setStrokeColor(RULE); canv.setLineWidth(0.5)
        canv.line(0.95*inch, h-0.70*inch, w-0.95*inch, h-0.70*inch)
        # footer
        canv.setStrokeColor(RULE); canv.line(0.95*inch, 0.78*inch, w-0.95*inch, 0.78*inch)
        canv.setFont(BODY, 7.4); canv.setFillColor(MUTED)
        canv.drawString(0.95*inch, 0.63*inch, f"T2Holdings LLC · entity spelling unverified · {TODAY}")
        canv.drawRightString(w-0.95*inch, 0.63*inch, f"Page {doc.page}")
        canv.restoreState()

story = []

# ============ COVER ============
story += [Spacer(1, 1.15*inch),
    Paragraph("Mogra Organics", st_title),
    Spacer(1, 4),
    Paragraph("Sourcing &amp; Launch Working Blueprint", S("x", fontName=HEAD, fontSize=18, leading=23, textColor=INK)),
    Spacer(1, 16), rule(PINE, 1.4, 0, 12),
    Paragraph("Organic culinary spices, herbs and seasoning — supplier intelligence, "
              "certification and import review, and a route blueprint for owner review.",
              S("lede", fontName=HEAD_I, fontSize=12.5, leading=17.5, textColor=MUTED)),
    Spacer(1, 22),
]
story += [callout("WORKING BLUEPRINT — NOT PURCHASE OR LAUNCH AUTHORIZATION",
    "This document is review-ready, not purchase-ready. It contains no supplier quotes, no duty determination, "
    "and no owner approval. Every material claim is labelled VERIFIED, PROVISIONAL, SUPPLIER_CLAIMED, PROPOSED or UNKNOWN. "
    "No supplier has been contacted, no account created, no sample ordered, and nothing purchased.",
    tone="warn")]
story += [Spacer(1, 20),
    tbl(["Field","Value"],
        [["Document date", TODAY],
         ["Business entity", "T2Holdings LLC (owner-supplied spelling — NOT yet verified against business records)"],
         ["Brand", "Mogra Organics (packaging use pending certifier label review)"],
         ["Scope of this pass", "Organic culinary spices, herbs and salt-containing seasoning; black pepper and turmeric prioritised"],
         ["Not in scope", "Mushroom, supplement, cosmetic and agricultural-development workstreams (documented future interests only)"],
         ["Commercial suppliers assessed", str(C["suppliers"])],
         ["Resources / directories (excluded from supplier counts)", str(C["resources"])],
         ["Organic evidence verified", "1 of 51 suppliers (Pearl Group Corporation, Vietnam)"]],
        [1.85*inch, 4.85*inch]),
    Spacer(1, 20),
    Paragraph("Prepared for owner review. Nothing in this document authorises a purchase, import, production run or launch.", st_small),
]
story.append(PageBreak())

# ============ 1 STATUS ============
story += [P("1. How to read this document", st_h1), rule(),
    P("Every material claim carries an evidence status so the reader can tell verified fact from supplier marketing from scenario.")]
status_rows = [
 ["VERIFIED","Authoritative or independently corroborated evidence supports the exact claim."],
 ["PROVISIONAL","Useful documentation whose currency or exact applicability is unresolved."],
 ["SUPPLIER_CLAIMED","Supplier marketing, specification or assertion."],
 ["REPORTED","Inherited assertion not independently re-checked in this pass."],
 ["PROPOSED","Recommendation or scenario — not an approved decision."],
 ["UNKNOWN","Evidence or input unavailable."],
 ["NOT_APPLICABLE","Only where a documented reason exists."],
]
story += [tbl(["Status","Meaning"], status_rows, [1.35*inch, 5.35*inch]), Spacer(1, 8),
 P("<b>A high supplier grade never implies that all of that supplier's products or processes are verified.</b> "
   "In particular, a certified ingredient does not automatically make a finished, Mogra-packaged product eligible for the USDA organic seal.")]

# ============ 2 EXEC BRIEF ============
story += [P("2. Executive decision brief", st_h1), rule()]
for t in [
 "<b>One of fifty-one suppliers has independently verified organic status.</b> Pearl Group Corporation (Vietnam) is certified USDA-NOP by <b>Control Union Certifications B.V.</b>, scope <b>CROPS + HANDLING</b>, confirmed in the public <b>USDA Organic Integrity Database on "+TODAY+"</b>.",
 "<b>Pearl's certified list explicitly covers organic whole and ground black pepper</b>, plus a broad herb and spice range relevant to Mogra.",
 "<b>Organic turmeric powder is not yet verified.</b> Pearl's website advertises it, but certificate coverage for the powder form is unconfirmed. This is a named gap with a precise closure action — not an assumption.",
 "<b>A second evidence gain this pass:</b> JAPC (Sri Lanka) names <b>Control Union</b> as its certifier (no certificate number). Status <b>PROVISIONAL</b>.",
 "<b>Three sourcing routes exist and none is cheapest.</b> Route A (overseas finished), Route B (imported bulk + US co-packing), Route C (US turnkey). Every international landed cost is incomplete because <b>no duty, AD/CVD or freight position exists yet</b>.",
 "<b>The largest hidden cost is certification of Mogra's own activity.</b> An organic input does not automatically make a Mogra pack seal-eligible. Importing, repacking or blending likely requires Mogra to certify that activity — a process, not a purchase.",
]:
    story.append(P(t))
story += [Spacer(1, 4), callout("Decide first",
 "Confirm the legal entity spelling (D1), the initial product and form (D2), the organic labelling pathway (D3), and the preferred route (D5). "
 "These four unblock outreach. None can be resolved by public research.", tone="ok")]

# ============ 3 SCOPE ============
story += [P("3. Current scope and brand context", st_h1), rule(),
 P("<b>Researched scope:</b> organic culinary spices, herbs and associated salt-containing seasoning, sourced for a US-branded food product, with <b>black pepper and turmeric prioritised</b>."),
 P("<b>Documented future interests (NOT researched here):</b> Mogra Organics is described as a premium mushroom and herb wellness brand with interests in edible and topical products and possible future vertical integration. These are recorded as interests only. No mushroom, supplement, cosmetic or agricultural-development work was performed in this pass."),
 P("<b>Scope boundaries:</b> Mogra is kept separate from Word Coffee, NorthstarOS and Northstar's resale product-exclusion rules. Those non-food resale filters do not apply to Mogra's own products. No SKU is treated as an approved launch SKU merely because an ingredient was researched."),
 P("<b>Owner approvals:</b> no owner approval of any product, route, price or label is recorded. Where a decision is implied it is marked <b>OWNER_INPUT_REQUIRED</b>.")]

# ============ 4 COVERAGE ============
story += [PageBreak(), P("4. Research coverage and evidence limitations", st_h1), rule()]
story += [tbl(["Measure","Count","Canonical table"],
 [[f"Commercial suppliers", str(C["suppliers"]), "supplier_master.csv"],
  [f"Resources / directories (excluded)", str(C["resources"]), "resources_and_directories.csv"],
  [f"Supplier × product × form rows", str(C["products"]), "supplier_product_matrix.csv"],
  [f"Pricing lines", str(C["pricing"]), "pricing_comparison.csv"],
  [f"Organic verification rows", str(C["verify"]), "organic_verification.csv"],
  [f"Priority verification checks", str(C["checks"]), "priority_verification_queue.csv"],
  [f"Route arrangements", str(C["routes"]), "route_comparison.csv"],
  [f"Evidence register entries", str(C["evidence"]), "evidence_register.csv"],
  [f"Risks", str(C["risk"]), "risk_register.csv"],
  [f"Decisions", str(C["decision"]), "decision_register.csv"],
  [f"Unsent RFQ drafts", "5", "rfq_drafts/"]],
  [3.5*inch, 1.0*inch, 2.2*inch]),
 Spacer(1, 6),
 P("<b>Correction recorded:</b> an earlier report stated “54 pricing lines.” The canonical file contains <b>"+str(C["pricing"])+"</b>. The earlier figure came from a malformed intermediate and is withdrawn. Pricing lines differ from suppliers because most suppliers publish no price at all."),
 P("<b>Organic evidence distribution (denominator stated):</b>")]
story += [tbl(["Grade","Rows","Suppliers","Meaning"],
 [["A (verified)","9","1","Pearl — 9 rows are 9 product forms of ONE supplier"],
  ["PROVISIONAL","1","1","JAPC — certifier named, no certificate number"],
  ["CONFIRMATION_REQUIRED","1","1","Pearl organic turmeric powder"],
  ["C (claim only)","22","21","Marketing assertion, no verifiable certificate"],
  ["D (not established)","27","27","No organic evidence found"]],
 [1.5*inch, 0.6*inch, 0.8*inch, 3.8*inch])]
story += [Spacer(1, 6),
 B("<b>Only 1 of 51 suppliers is verified.</b> The remainder are leads."),
 B("The USDA OID is public and needs no login, but automated interaction is unreliable — a force-click returns <b>unfiltered</b> results, which would create false matches. Verification therefore routes through manual lookups plus supplier certificate documents."),
 B("Control Union certificate verification sits behind a client-portal login — not publicly queryable, and account creation is out of bounds for this task."),
 B("<b>No qualifying lead was found within the completed searches</b> for Cambodia, Laos, Philippines, Malaysia, Singapore, Nepal or Bangladesh. This describes the searches, not the markets."),
 B("Retail prices are not wholesale quotes. Unknown costs are not zero. No route has been established as cheapest.")]

# ============ 5 PRODUCTS ============
story += [PageBreak(), P("5. Product and form overview", st_h1), rule(),
 P("Product forms are kept strictly separate. Certification of one form does not establish another.")]
story += [tbl(["Product","Forms in scope","Evidence state"],
 [["Black pepper","whole, cracked, coarse-ground, fine-ground","Whole + ground <b>VERIFIED</b> at Pearl"],
  ["Turmeric","dried sliced, fresh, powder","Sliced + fresh <b>VERIFIED</b>; <b>powder CONFIRMATION_REQUIRED</b>"],
  ["Cinnamon / cassia","whole, ground — species must be stated","Verified at Pearl (observed); species documentation to request"],
  ["Ginger","dried sliced, powder","Sliced verified; powder to confirm"],
  ["Chilli / flakes","dried, flaked","Verified at Pearl (observed)"],
  ["Coriander, cumin, fennel, cardamom, mustard","seed / whole","Verified at Pearl (observed)"],
  ["Dried herbs","cut &amp; sifted (basil, thyme, rosemary, parsley, dill, mint, marjoram)","Verified at Pearl (observed)"],
  ["Salt (plain)","grain, flake","<b>NOT_APPLICABLE for organic</b> — salt cannot be USDA-organic"],
  ["Salt-containing seasoning blend","blend","Only route to an organic claim on a salted product"]],
 [1.75*inch, 2.35*inch, 2.6*inch]),
 Spacer(1, 6),
 callout("Never merge", "whole vs ground pepper · turmeric powder vs dried sliced vs fresh · bulk ingredient vs finished retail unit · "
         "conventional vs organic offer · packing-only vs turnkey service.", tone="note")]

# ============ 6 LANDSCAPE ============
story += [P("6. Supplier landscape", st_h1), rule(),
 P(f"<b>{C['suppliers']} commercial suppliers</b> across 12+ countries, grouped by type.")]
story += [tbl(["Type","Count","Representative"],
 [["Exporters / processor-exporters","20","Pearl (A), Radiance, Shree Agro, JAPC (PROVISIONAL), DK Commodity"],
  ["Importers / distributors","12","Flavoric, Bata Food, Multiple Organics, Frontier, Starwest"],
  ["Co-packers / private-label manufacturers","7","Spices Inc, Specialty Food Co-Packers, Organic Spices Inc, Rocky Mountain"],
  ["Producers","3","White Rabbit Acres (US-FL), Amazon Andes (PE), SBimal (FJ)"],
  ["Salt","5","Cargill, SF Salt, Sea Salt Superstore, SeaSalt.com, Baker's Authority"],
  ["Other brands / manufacturers","4","Badia, Quintal, Especias Moy, Canadian Organic Spice"]],
 [2.6*inch, 0.7*inch, 3.4*inch]),
 Spacer(1, 6),
 P(f"<b>Separated resources (not suppliers, {C['resources']} total):</b> USDA OID · Oregon Tilth co-packer list · CoPacker Index · Cornell CALS (university resource) · Penn State Extension · Sri Lanka EDB · International Pepper Community."),
 B("No supplier-wide grade is a product approval. Pearl's grade A applies only to the product forms listed on its certificate.")]

story.append(PageBreak())
# ============ 7 SHORTLIST ============
story += [P("7. Priority shortlist", st_h1), rule(),
 P("Ordered by commercial usefulness and evidence strength — not by any prior ranking.")]
story += [tbl(["#","Supplier","Country","Type","Organic evidence","Why it is on the list"],
 [["1","Pearl Group Corporation","Vietnam","processor-exporter","<b>A — VERIFIED</b>","Only verified organic supplier; covers pepper + many herbs"],
  ["2","JAPC","Sri Lanka","processor-exporter","<b>PROVISIONAL</b> (Control Union named)","Broad organic range; strongest public spec sheet; private label"],
  ["3","Radiance Overseas","India","exporter","C","Specific public claims; per-shipment OTC; MOQ 1 MT"],
  ["4","Bata Food","TR/NL/US","importer-distributor","C","Only published MOQ (800 kg); cleared Rotterdam stock"],
  ["5","Amazon Andes","Peru","producer-exporter","C (Control Union Peru named)","Most checkable unverified bulk turmeric"],
  ["6","Spices Inc","USA","co-packer","C","Best turnkey operational fit; salt blends too"],
  ["7","Specialty Food Co-Packers","USA","co-packer","C","USDA Organic + SQF + GMP claimed"],
  ["8","Organic Spices Inc","USA","importer-co-packer","C","Contract manufacturing + private label"],
  ["9","Prime Food Products","Sri Lanka","processor-exporter","C","Only SL pepper lead claiming USDA organic with specs"],
  ["10","White Rabbit Acres","USA (FL)","producer","C","Only US-domestic organic turmeric grower (pilot scale)"]],
 [0.3*inch,1.35*inch,0.85*inch,1.1*inch,1.25*inch,1.85*inch])]

# ============ 8 PEARL ============
story += [PageBreak(), P("8. Pearl evidence and remaining gaps", st_h1), rule()]
story += [tbl(["Field","Verified value"],
 [["Operation","<b>PEARL GROUP CORPORATION (PEARL GROUP)</b>"],
  ["Program","USDA-NOP"],
  ["Certifier","<b>[CUC] Control Union Certifications B.V.</b>"],
  ["Status","<b>Certified</b>"],
  ["Country","Viet Nam"],
  ["Scope","<b>CROPS + HANDLING</b>"]],
 [1.6*inch, 5.1*inch]), Spacer(1, 7),
 P("<b>Product-form separation (critical).</b>")]
story += [tbl(["Form","Status","Note"],
 [["Organic Whole Black Pepper","<b>VERIFIED</b>","On certified product list"],
  ["Organic Ground Black Pepper","<b>VERIFIED</b>","Separate certified line from whole"],
  ["Organic Dried Sliced Turmeric","<b>VERIFIED</b>",""],
  ["Organic Fresh Turmeric","<b>VERIFIED</b>","Fresh is not a shelf-stable culinary powder"],
  ["<b>Organic Turmeric Powder</b>","<b>CONFIRMATION_REQUIRED</b>","Website advertises it; certificate coverage unconfirmed"]],
 [2.2*inch,1.6*inch,2.9*inch]), Spacer(1, 7),
 callout("HANDLING is a scope — not a blanket approval",
 "HANDLING is a certification scope. It is not proof that every facility, process, product or Mogra label is approved. "
 "The entity appearing as exporter of record has not been matched to the certified operation.", tone="warn"),
 Spacer(1, 6),
 P("<b>Open items, all CONFIRMATION_REQUIRED:</b> MOQ · facility scope · grinding within certified scope · treatment method · "
   "retail packing organic status · Mogra-label permission · lot COAs · exporter/importer responsibilities · finished-unit pricing · certificate number and expiry."),
 P("<b>Correction:</b> the earlier inference that turmeric powder was “not established because it was absent from the certificate” was wrong — "
   "the certificate capture was <b>truncated</b>, so absence there is not evidence of absence. Powder is properly <b>supplier-claimed</b> and awaits confirmation.", st_small)]

# ============ 9 CO-PACKERS ============
story += [PageBreak(), P("9. Domestic co-packer comparison", st_h1), rule(),
 P("<b>NOP organic evidence is kept strictly separate from SQF/GMP food-safety evidence.</b> SQF and GMP are not organic certification.")]
story += [tbl(["Supplier","Entity / facility","Organic claim","Food-safety","Packing-only","Turnkey"],
 [["Spices Inc","Spices Inc., Lowell MA","claimed, certifier not named","—","yes","yes (sourcing+blending)"],
  ["Specialty Food Co-Packers","claimed USDA Organic facility","claimed, certifier not named","SQF + GMP","yes","yes"],
  ["Organic Spices Inc","McKinney TX","claimed, certifier not named","—","yes","yes (contract mfg)"],
  ["Rocky Mountain Spice","—","USDA badge, no certifier","—","yes","blending"],
  ["Vanns Spices","—","not stated","—","yes","yes"],
  ["1000 Springs Mill","—","claimed, certifier not named","—","yes","yes"]],
 [1.35*inch,1.5*inch,1.35*inch,0.85*inch,0.75*inch,0.9*inch]), Spacer(1, 6),
 P("<b>Unverified for all:</b> actual NOP handler certification, certifier name, certificate number, and scope covering <b>repacking</b>.")]

# ============ 10 ROUTES ============
story += [P("10. Route comparisons by product", st_h1), rule()]
story += [tbl(["Product","Route","Arrangement","Evidence state"],
 [["Black pepper","A","Pearl — certified finished/private-label","Organic VERIFIED; packing claimed"],
  ["Black pepper","A (alt)","Radiance / JAPC","Organic unverified"],
  ["Black pepper","B","Pearl / Bata / Radiance bulk + US co-packer","Bulk organic verified; co-packer organic unverified"],
  ["Black pepper","B (alt)","India bulk + US co-packer","Different duty treatment possible"],
  ["Black pepper","C","Spicy Organic / Spices Inc + US co-packer","Ingredient + co-packer unverified"],
  ["Black pepper","C (alt)","McKinney TX cluster","Cluster relationship unconfirmed"],
  ["Turmeric","A","Pearl","Sliced/fresh verified; powder BLOCKED on confirmation"],
  ["Turmeric","A (alt)","JAPC","Organic provisional"],
  ["Turmeric","B","Radiance / Shree Agro / Ecopharma bulk + US pack","Organic unverified"],
  ["Turmeric","B (alt)","Amazon Andes (Peru) bulk + US pack","Certifier named; certificate not sighted"],
  ["Turmeric","C","White Rabbit Acres / Spicy Organic + US pack","Thin domestic supply"],
  ["Turmeric","C (alt)","McKinney TX cluster","All costs unknown"]],
 [0.9*inch,0.8*inch,2.6*inch,2.4*inch]), Spacer(1, 6),
 P("<b>Tradeoffs:</b> Route A is fastest but concentrates on one overseas entity. Route B gives bulk flexibility and label ownership but adds two entities and an import obligation. Route C avoids import but likely costs more per unit (unproven). <b>Certification certainty exists only for Pearl; every other route rests on advertised capability.</b>"),
 P("In <font face='%s'>route_comparison.csv</font>, ingredient, packaging, packing, testing, freight/import and Amazon costs are held separately — and every one is <b>unknown</b>." % BODY, st_small)]

story.append(PageBreak())
# ============ 11 LABELLING ============
story += [P("11. Organic labelling pathways", st_h1), rule()]
story += [tbl(["Pathway","When it applies","USDA seal"],
 [["“100% organic”","Only organic ingredients (excluding salt and water)","Permitted"],
  ["“Organic”","≥95% organic ingredients (excluding salt and water)","Permitted"],
  ["“Made with organic [ingredient/category]”","≥70% organic ingredients","<b>Not permitted</b> — limited identification only"],
  ["Ingredient-only organic identification","<70% organic; organic items named in ingredient panel only","Not permitted"]],
 [2.1*inch,3.3*inch,1.3*inch]), Spacer(1, 6),
 B("A <b>single-ingredient</b> spice can be certified “organic” only if the <b>finished pack</b> is certified — the ingredient being organic is not sufficient."),
 B("A <b>multi-ingredient blend containing salt</b> may only support “made with organic,” because salt cannot itself be organic."),
 B("<b>Removing the seal does not necessarily remove certification obligations.</b>"),
 B("For every proposed SKU the specific pathway remains a <b>certifier / label-review question</b>. Final approval is <b>NOT documented</b>."),
 P("Proposed packaging use of “Mogra Organics” is flagged for certifier label review. No legal conclusion is drawn here. "
   "Business activities are assessed separately — brand ownership, buying/selling, importing, storage, processing, packing, distribution — and a certifier or qualified professional must confirm the specific arrangement.")]

# ============ 12 CERT CHAIN ============
story += [P("12. Certification chain and approval gaps", st_h1), rule()]
chain = tbl(["Stage","Status"],
 [["Grower (Pearl)","VERIFIED"],
  ["Processor (Pearl)","VERIFIED for listed forms"],
  ["Exporter of record","entity match to certified operation — UNKNOWN"],
  ["Importer (Mogra?)","certification obligation — UNKNOWN"],
  ["Mogra handling / packing","eligibility — UNKNOWN"],
  ["Finished pack label","label review required — UNDOCUMENTED"]],
 [2.6*inch,4.1*inch])
story += [chain, Spacer(1, 6),
 callout("The central unresolved point",
 "An organic input does not make the final Mogra product eligible for the USDA organic seal. Whether Mogra must certify its own importing, "
 "handling or repacking activity is the largest open question in this blueprint, and it is a process — not a purchase.", tone="warn")]

# ============ 13 FOOD SAFETY ============
story += [P("13. Food-safety and documentation requirements", st_h1), rule()]
story += [tbl(["Control","Applies to","Evidence state"],
 [["Product identity (botanical / species)","All; critical for cinnamon","Supplier spec needed"],
  ["Lot traceability","All","Supplier claim; verify"],
  ["Microbiological (e.g. Salmonella)","All spices","Shree Agro publishes “Salmonella absent/25 g”"],
  ["Heavy metals","All; critical for turmeric","White Rabbit publishes independent results"],
  ["Adulteration (lead chromate, colourants)","Turmeric especially","Must be requested explicitly"],
  ["Pesticide residues","All organic","Supplier COA"],
  ["Allergen / cross-contact","Herbs; co-packers","Ask co-packers"],
  ["Treatment / processing","All","Must be organic-compatible (irradiation is not)"],
  ["Shelf life, storage","All","Supplier data"],
  ["COA and testing arrangements","All","Ask for a sample COA"],
  ["Recall capability","All","Supplier claim"]],
 [2.3*inch,1.9*inch,2.5*inch]), Spacer(1, 6),
 P("<b>A generic COA does not prove every safety requirement.</b> Specific limits must come from the supplier and, where regulatory, from official sources.")]

# ============ 14 IMPORT MAP ============
story += [PageBreak(), P("14. Import responsibility map", st_h1), rule(),
 P("Multiple distinct roles exist. No single party absorbs all of them.")]
story += [tbl(["Role","Who","Notes"],
 [["Importer of Record","Mogra or its importer","Files entry; liable for duty and AD/CVD cash deposits"],
  ["FSVP importer","The US importer","Must verify foreign supplier food-safety compliance"],
  ["Certified organic importer","The importer","Generally must itself be certified organic to import organic product"],
  ["Exporter / final handler","Overseas supplier","Must hold certification covering product and export"],
  ["Manufacturer / processor","Overseas supplier","FDA food-facility registration"],
  ["Customs broker","Engaged by importer","Classification, PGA flags, entry filing"],
  ["Freight forwarder","Engaged by importer","Transport — not compliance"]],
 [1.8*inch,1.5*inch,3.4*inch]), Spacer(1, 6),
 P("<b>Do not assume a broker, forwarder, overseas supplier or delivery term assumes every obligation.</b> An Incoterm allocates transport cost and risk — not regulatory responsibility.")]

# ============ 15 CUSTOMS ============
story += [P("15. Customs and tariff review status", st_h1), rule(),
 P("<b>Status: preliminary. Not a customs determination.</b>")]
story += [tbl(["Item","Position"],
 [["Indicative HTS","Black pepper 0904.11 (whole) / 0904.12 (crushed or ground); turmeric 0910.30; cinnamon 0906.11 / 0906.20"],
  ["Base duty","<b>NOT confirmed</b> — read from live USITC HTS per confirmed line"],
  ["AD/CVD","Confirmed that AD/CVD is <b>not in the HTS</b> (USITC) and depends on specific orders and scope. <b>No order covering pepper or turmeric from in-scope origins has been confirmed.</b>"],
  ["Additional tariffs","Volatile; confirm per import"],
  ["Official query route","access.trade.gov/adcvd/ (identified and reachable)"]],
 [1.5*inch,5.2*inch]), Spacer(1, 6),
 callout("Broker review required",
 "Absence of a confirmed order is not confirmation that no order applies. No duty or AD/CVD figure appears anywhere in this blueprint. "
 "See customs_broker_review_packet.md.", tone="warn")]

# ============ 16 COST ============
story += [P("16. Cost coverage and missing quotes", st_h1), rule(),
 P("<b>What is known — three published prices, all US domestic, all retail or retail-tier references. None is a wholesale quote.</b>")]
story += [tbl(["Item","Price","Status"],
 [["Flavoric organic turmeric","$12.98–$111.98 / lb","PUBLISHED_RETAIL_REFERENCE"],
  ["Flavoric organic black pepper","$49.98–$369.98 / lb","PUBLISHED_RETAIL_REFERENCE"],
  ["Spices Inc chipotle salt","$6.55 / unit","PUBLISHED_RETAIL_REFERENCE"]],
 [2.3*inch,2.1*inch,2.3*inch]), Spacer(1, 6),
 P("<b>Quote-required:</b> ingredient, processing/packing, packaging, setup, testing, freight/insurance, duty/entry/broker, domestic transport, storage, Amazon fees."),
 P("<b>Unknown:</b> duty and AD/CVD (broker-dependent) · Mogra's own certification cost (role-dependent) · Amazon fees and demand (no authorised data)."),
 P("<b>Consequence:</b> every international route is <b>LANDED_COST_INCOMPLETE</b>. No total is computed from incomplete inputs. Retail prices must not be converted into wholesale costs.")]

# ============ 17 SCENARIOS ============
story += [P("17. Economic scenarios (clearly labelled)", st_h1), rule(),
 P("No owner volumes or prices exist, so the model is built as illustrative scenarios with an isolated assumption register (assumptions_register.csv).")]
story += [tbl(["Assumption","Value","Status"],
 [["Pilot finished units","500","PROPOSED illustrative — NOT an owner demand forecast"],
  ["Retail pack net weight","2 oz","PROPOSED illustrative"],
  ["Yield loss in grinding/packing","2%","PROPOSED placeholder"],
  ["Organic premium on bulk ingredient","20%","PROPOSED placeholder"],
  ["Lead time","—","UNKNOWN"],
  ["Freight / duty / AD-CVD / broker","—","UNKNOWN"],
  ["Amazon fees and demand","—","UNKNOWN"],
  ["Mogra certification cost","—","UNKNOWN"]],
 [2.3*inch,0.9*inch,3.5*inch]), Spacer(1, 6),
 P("<b>Sensitivity:</b> landed cost is dominated by freight + duty + AD/CVD, all currently unknown. Ingredient cost is secondary. "
   "Unit economics cannot be meaningfully assessed until the broker review and at least one supplier quote exist."),
 P("<b>No total is presented, because any total from incomplete inputs would be false.</b>")]

story.append(PageBreak())
# ============ 18 PACKAGING ============
story += [P("18. Packaging and channel-readiness", st_h1), rule(),
 B("Formats under consideration: jar, pouch, sachet — <b>PROPOSED</b>, not decided."),
 B("FBA implications: a pouch is lighter and less breakage-prone than glass. Relevant only if Amazon is confirmed as the primary channel."),
 B("Label dependencies: organic pathway choice (D3), species identity for cinnamon, net quantity, country of origin."),
 P("<b>Amazon readiness checklist (not asserted to exist):</b> Seller Central account · category/grocery approval where required · "
   "FBA-ready packaging and labelling · compliance documentation · listing content. None of these is claimed to exist today.")]

# ============ 19 RFQ ============
story += [P("19. RFQ readiness", st_h1), rule(),
 P("<b>Five finalized, unsent RFQ drafts:</b> Pearl bulk organic · Pearl certified finished/private-label · Spices Inc · Specialty Food Co-Packers · Organic Spices Inc (each co-packer draft covers packing-only and turnkey).")]
story += [tbl(["Requested from every supplier",""],
 [["Specifications (form-specific)","MOQ and real price breaks"],
  ["Certification documents and coverage","Pack formats available"],
  ["Packaging and setup costs","Ingredient / processing / packing / testing priced separately"],
  ["Sample options and charges","Lead time and quote validity"],
  ["Currency and Incoterm + named place","Origin and shipping point"],
  ["Lot traceability","Testing documentation"],
  ["Label-review and certification responsibilities",""]],
 [3.35*inch,3.35*inch]), Spacer(1, 6),
 callout("Outreach-readiness blocker", "The legal entity spelling (D1) is a placeholder in every draft. Nothing has been sent.", tone="warn")]

# ============ 20 GATES ============
story += [P("20. Sample, pilot and launch gates", st_h1), rule(),
 P("Dependency-based sequence — no invented calendar dates or lead times.")]
story += [tbl(["Stage","Required inputs","Acceptance criteria","Gate"],
 [["1. Owner scope selection","D1–D5 answered","Product/form + route chosen","Stop if entity unresolved"],
  ["2. Supplier/document confirmation","Certificate PDFs, specs","Organic scope matches activity","Stop if scope mismatch"],
  ["3. Quote collection","Tier prices, Incoterms","Comparable quotes","Stop if MOQs unworkable"],
  ["4. Compliance-role confirmation","Certifier opinion; broker position","Importer/FSVP/cert roles settled","Stop if duty unknown"],
  ["5. Sample evaluation","Samples","Meets spec; COA supports","Stop if purity/adulteration fails"],
  ["6. Packaging & label review","Chosen format; pathway","Certifier label review completed","Stop if label unapproved"],
  ["7. Pilot production","Setup paid; ingredient","Units meet spec","Stop if yield/fill fails"],
  ["8. Receiving & lot acceptance","COA + inspection","Lot accepted","Stop if lot fails"],
  ["9. Channel setup","Amazon readiness items","Listing + compliance ready","Stop if category blocked"],
  ["10. Controlled launch","Inventory; pricing","First orders fulfilled","Go/no-go on sell-through"],
  ["11. Reorder evaluation","Actual costs + sales","Margin assessed on real data","Stop if margin fails"]],
 [1.6*inch,1.7*inch,1.9*inch,1.5*inch])]

# ============ 21 RISK ============
story += [PageBreak(), P("21. Risk register (highest impact)", st_h1), rule()]
story += [tbl(["ID","Risk","Impact"],
 [["RK-01","Supplier-wide organic grade mistaken for product/process approval","High"],
  ["RK-02","Certified input mistaken for an approved finished pack","High"],
  ["RK-03","No-seal pathway assumed to remove certification obligations","High"],
  ["RK-05","AD/CVD order applies but is unverified — material unbudgeted duty","<b>Very High</b>"],
  ["RK-06","Origin-specific tariffs change after quoting","High"],
  ["RK-07","Turmeric adulteration not detected","High"],
  ["RK-09","Missing costs treated as zero producing false economics","High"]],
 [0.6*inch,4.4*inch,1.7*inch]),
 P("Full register: risk_register.csv (13 entries).", st_cap)]

# ============ 22 DECISIONS ============
story += [P("22. Owner decisions", st_h1), rule(),
 P("Only decisions that public research cannot resolve. Full detail in owner_decision_brief.md and decision_register.csv.")]
story += [tbl(["When","Decisions"],
 [["Now","D1 legal entity · D2 initial product/form · D3 organic labelling pathway"],
  ["Before outreach","D4 target volumes · D5 preferred route · D6 budget"],
  ["Before samples","D7 package format and net quantity"],
  ["Before importing / production","D8 importer &amp; FSVP posture · D9 certification arrangement"],
  ["Before launch","D10 sales channels"]],
 [2.0*inch,4.7*inch]), Spacer(1, 6),
 callout("The four that unblock everything",
 "D1 (legal entity spelling), D2 (product and form), D3 (labelling pathway) and D5 (preferred route). Until these exist, quotes cannot be compared and labels cannot be designed.", tone="ok")]

# ============ 23 NEXT ACTIONS ============
story += [P("23. Recommended next actions", st_h1), rule()]
for i,t in enumerate([
 "<b>Confirm T2Holdings LLC exact legal spelling</b> — blocks all outreach (D1).",
 "<b>Request Pearl's certificate PDF and full product list</b> — closes turmeric powder, packing scope, expiry and exporter-of-record in one step.",
 "<b>Commission a customs-broker review</b> using the broker packet — no landed cost is valid without it.",
 "<b>Verify JAPC's certificate</b> (certifier now named: Control Union) — the highest-value provisional lead.",
 "<b>Confirm NOP handler certification</b> (distinct from SQF/GMP) for the three US co-packers.",
 "<b>Run the manual USDA OID lookups</b> in priority_verification_queue.csv.",
 "<b>Decide D2 (product/form) and D5 (route)</b> so quotes can be collected.",
],1):
    story.append(Paragraph(f"<b>{i}.</b> {t}", st_body))

# ============ 24 EVIDENCE ============
story += [PageBreak(), P("24. Evidence appendix", st_h1), rule(),
 P("Full register: evidence_register.csv (20 entries). Key sources cited in this document:")]
story += [tbl(["ID","Source","Observation","Limitation"],
 [["EV-001","USDA Organic Integrity Database","2026-10-02","Truncated product list; no certificate number"],
  ["EV-006","JAPC certifications page","2026-10-02","Certifier named; no certificate number"],
  ["EV-011","USDA NOP framework","2026-10-02","Regulatory, not a supplier fact"],
  ["EV-012","USITC FAQ","2026-10-02","AD/CVD not in the HTS"],
  ["EV-013","ITA AD/CVD portal","2026-10-02","Not queried per product"],
  ["EV-014","Control Union certificate listing","2026-10-02","Client login required"],
  ["EV-018","Vietnam Pepper &amp; Spice Association","2026-01","Aggregate market anchor only"],
  ["EV-019","Peacock Tariff Consulting","2026-10-02","Industry secondary source"]],
 [0.7*inch,2.3*inch,0.9*inch,2.8*inch]), Spacer(1, 8),
 P("<b>Corrections log (withdrawn claims retained):</b>", st_h2)]
for t in [
 "“54 pricing lines” → corrected to "+str(C["pricing"])+" (withdrawn).",
 "“Exporters cannot provide certified finished units” → withdrawn.",
 "HANDLING reframed as a scope, not facility/process/product approval.",
 "Especias Moy reclassified E → D (ambiguous, not contradictory).",
 "“Structural absence” → “no qualifying lead found within the completed searches.”",
 "Pearl turmeric powder: inference-from-absence corrected to supplier-claimed with a truncated-capture caveat.",
]:
    story.append(B(t))
# ============ APPENDICES (rendered from canonical CSVs) ============
def csv_rows(fn):
    with open(os.path.join(ROOT, fn), newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))

def trunc(s, n):
    s = (s or "").strip()
    return s if len(s) <= n else s[:n-1] + "…"

story += [PageBreak(), P("Appendix A — Full commercial supplier inventory", st_h1), rule(),
 P("All %d commercial suppliers. Resources and directories are excluded and listed separately in Appendix C." % C["suppliers"], st_cap)]
sup = csv_rows("supplier_master.csv")
rowsA = [[s["supplier_id"], s["legal_name"], s["hq_country"], s["supplier_type"], trunc(s["notes"], 150)] for s in sup]
story += [tbl(["ID","Legal name","Country","Type","Evidence summary"],
 rowsA, [1.05*inch,1.55*inch,0.7*inch,1.0*inch,2.3*inch])]

story += [PageBreak(), P("Appendix B — Full evidence register", st_h1), rule(),
 P("All %d evidence entries with claim status and observation date." % C["evidence"], st_cap)]
ev = csv_rows("evidence_register.csv")
rowsB = [[e["evidence_id"], trunc(e["claim"], 170), e["claim_status"], e["observation_date"]] for e in ev]
story += [tbl(["ID","Claim","Status","Observed"],
 rowsB, [0.6*inch,4.0*inch,1.0*inch,1.0*inch])]

story += [PageBreak(), P("Appendix C — Full risk register", st_h1), rule(),
 P("All %d risks." % C["risk"], st_cap)]
rk = csv_rows("risk_register.csv")
rowsC = [[r["risk_id"], r["category"], trunc(r["description"], 200), r["likelihood"], r["impact"]] for r in rk]
story += [tbl(["ID","Category","Description","Likelihood","Impact"],
 rowsC, [0.5*inch,0.85*inch,3.65*inch,0.8*inch,0.8*inch])]

story += [PageBreak(), P("Appendix D — Full decision register", st_h1), rule(),
 P("All %d owner decisions, with the stage by which each is required." % C["decision"], st_cap)]
dc = csv_rows("decision_register.csv")
rowsD = [[d["decision_id"], d["decision"], d["needed_by_stage"], d["owner_input_required"]] for d in dc]
story += [tbl(["ID","Decision","Needed by stage","Owner input"],
 rowsD, [0.5*inch,3.3*inch,1.4*inch,1.4*inch])]

story += [P("Appendix E — Product and route readiness", st_h2), rule()]
pr = csv_rows("product_route_readiness.csv")
rowsE = [[x["readiness_id"], x["product"], x["form"], x["route"], x["best_supported"], x["purchase_ready"]] for x in pr]
story += [tbl(["ID","Product","Form","Route","Best-supported","Purchase-ready"],
 rowsE, [0.55*inch,1.5*inch,1.2*inch,0.6*inch,1.55*inch,1.2*inch])]

story += [PageBreak(), P("Appendix F — Priority verification queue status", st_h1), rule(),
 P("All %d checks, in commercial-priority order. Every entry is open." % C["checks"], st_cap)]
pq = csv_rows("priority_verification_queue.csv")
rowsF = [[x["priority"], x["legal_name"], x["country"], trunc(x["evidence_needed"], 150), x["status"]] for x in pq]
story += [tbl(["#","Legal name","Country","Evidence needed","Status"],
 rowsF, [0.35*inch,1.75*inch,0.85*inch,2.75*inch,0.9*inch])]

story += [PageBreak(), P("Appendix G — Resources and directories (not commercial suppliers)", st_h1), rule()]
rs = csv_rows("resources_and_directories.csv")
rowsG = [[x["name"], x["resource_type"], trunc(x["what_it_provides"], 170)] for x in rs]
story += [tbl(["Name","Type","Provides"],
 rowsG, [1.7*inch,1.5*inch,3.4*inch]), Spacer(1, 5),
 P("These are discovery and verification resources. They are excluded from every supplier count in this document.")]

story += [Spacer(1, 14), rule(PINE,1.2,4,4),
 Paragraph("WORKING BLUEPRINT — NOT PURCHASE OR LAUNCH AUTHORIZATION", S("end", fontName=HEAD_B, fontSize=10, leading=14, textColor=CLAY, alignment=TA_CENTER)),
 Paragraph("Prepared for owner review · T2Holdings LLC (entity spelling unverified) · "+TODAY, S("end2", fontName=BODY_I, fontSize=8.5, leading=12, textColor=MUTED, alignment=TA_CENTER))]

doc = Doc(PDF, pagesize=letter)
doc.build(story)
print("PDF WRITTEN:", PDF)
print("SIZE:", os.path.getsize(PDF), "bytes")
