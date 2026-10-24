# Shared builder for the three printable decision-sheet pages
# (Suppliers / Packagers / Shipping).
#
# DESIGN RULE: each sheet must fit ONE landscape page at full readable font size.
# Where a whole class of fields shares one identical value (e.g. every stock,
# sample, lead-time and arrival field is UNKNOWN because no provider has
# responded), the page collapses them into a single "all <value>" cell instead of
# repeating the same unknown nine times. Full per-field detail lives in the
# canonical CSVs, which act as the supporting appendix.
#
# Used for BOTH the standalone printable PDF and the canonical partner-review PDF.
import csv, os, re
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph, Spacer, Table, TableStyle, PageBreak

BASE = os.path.join("docs", "mogra-organics-research-2026-10-02")
FD = r"C:\Windows\Fonts"


def _reg(n, f):
    p = os.path.join(FD, f)
    if os.path.exists(p):
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        pdfmetrics.registerFont(TTFont(n, p))
        return True
    return False


HG = _reg("Georg", "georgia.ttf") and _reg("Georg-B", "georgiab.ttf")
if _reg("Ari", "arial.ttf"):
    _reg("Ari-B", "arialbd.ttf"); _reg("Ari-I", "ariali.ttf")
    BODY, BODY_B, BODY_I = "Ari", "Ari-B", "Ari-I"
else:
    BODY, BODY_B, BODY_I = "Helvetica", "Helvetica-Bold", "Helvetica-Oblique"
HEAD, HEAD_B = ("Georg", "Georg-B") if HG else ("Times-Roman", "Times-Bold")

PAPER = colors.HexColor("#FBFAF7"); INK = colors.HexColor("#1E2A26"); PINE = colors.HexColor("#22463A")
SAGE = colors.HexColor("#6E8B74"); CLAY = colors.HexColor("#9A6A4F"); RULE = colors.HexColor("#D8D4CB")
MUTED = colors.HexColor("#6B6B63"); WARNBG = colors.HexColor("#F3EFE7")
TODAY = "2026-10-02"


def S(n, **k):
    return ParagraphStyle(n, **k)


h1 = S("h1", fontName=HEAD_B, fontSize=15, leading=18, textColor=PINE, spaceAfter=2)
h2 = S("h2x", fontName=HEAD_B, fontSize=9.4, leading=11.5, textColor=PINE, spaceBefore=3, spaceAfter=2.5)
sub = S("sub", fontName=BODY, fontSize=7.4, leading=9, textColor=MUTED, spaceAfter=3)
leg = S("leg", fontName=BODY, fontSize=6.9, leading=8.4, textColor=MUTED, spaceAfter=3)
cell = S("c", fontName=BODY, fontSize=7.3, leading=9.2, textColor=INK)
cellh = S("ch", fontName=BODY_B, fontSize=7.2, leading=9, textColor=colors.white)
boxh = S("bh", fontName=HEAD_B, fontSize=10, leading=12, textColor=PINE)
boxb = S("bb", fontName=BODY, fontSize=7.8, leading=10, textColor=INK)


def P(t, s=cell):
    return Paragraph(t, s)


def rows(fn):
    return list(csv.DictReader(open(os.path.join(BASE, fn), newline="", encoding="utf-8")))


def sh(s, n):
    s = re.sub(r"\s+", " ", (s or "").strip())
    s = s.replace("CONFIRMATION REQUIRED", "UNCONFIRMED").replace("NOT confirmed", "unconfirmed")
    return s if len(s) <= n else s[:n - 2] + ".."


def fieldset(values, n=30):
    """Collapse a group of fields that share one identical value."""
    vals = [(v or "").strip() for v in values]
    if len(set(vals)) == 1:
        return "all " + sh(vals[0], n)
    return "<br/>".join(sh(v, n) for v in vals)


_W = 705.0


def mk(header, data, widths, fs=7.3, pad=3.0):
    tot = float(sum(widths))
    cols = [max(w / tot * _W, pad * 2 + 6) for w in widths]
    scale = _W / sum(cols)
    cols = [c * scale for c in cols]
    cs = S("cx", fontName=BODY, fontSize=fs, leading=fs + 1.9, textColor=INK)
    d = [[Paragraph(h, cellh) for h in header]]
    for r in data:
        d.append([Paragraph(str(c) if c not in (None, "") else "&mdash;", cs) for c in r])
    t = Table(d, colWidths=cols, repeatRows=1, hAlign="LEFT")
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), PINE), ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 2.8), ("BOTTOMPADDING", (0, 0), (-1, -1), 2.8),
        ("LEFTPADDING", (0, 0), (-1, -1), pad), ("RIGHTPADDING", (0, 0), (-1, -1), pad),
        ("LINEBELOW", (0, 0), (-1, -1), 0.3, RULE),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, PAPER])]))
    return t


def decisionbox(lines):
    inner = [[Paragraph("OWNER / PARTNER DECISION", boxh)]]
    for l in lines:
        inner.append([Paragraph(l, boxb)])
    t = Table(inner, hAlign="LEFT")
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), WARNBG), ("BOX", (0, 0), (-1, -1), 0.7, RULE),
                           ("LINEBEFORE", (0, 0), (0, -1), 2.6, SAGE),
                           ("LEFTPADDING", (0, 0), (-1, -1), 8), ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                           ("TOPPADDING", (0, 0), (-1, -1), 2.8), ("BOTTOMPADDING", (0, 0), (-1, -1), 2.8)]))
    return t


LEGEND = ("<b>Legend</b> &mdash; <b>VERIFIED</b> independently corroborated &middot; <b>SUPPLIER-CLAIMED</b> provider assertion &middot; "
          "<b>QUOTE REQUIRED</b> no price exists &middot; <b>UNCONFIRMED</b> not yet established &middot; "
          "<b>OWNER_INPUT_REQUIRED</b> needs owner record &middot; <b>PLANNING ALLOWANCE</b> internal estimate, not a supplier commitment. "
          "Full field-by-field detail: supporting CSV appendices.")


def build_pages(W):
    """W = available frame width in points. Returns flowables for 3 printable pages."""
    global _W
    _W = float(W)
    out = []

    # ================= SHEET 1 : SUPPLIERS =================
    sd = rows("supplier_decision_sheets.csv")
    out += [P("PRINTABLE DECISION SHEET 1 &mdash; SUPPLIERS", h1),
            P("Prepared %s &middot; Project: <b>HERBS/SPICES</b> holiday launch &middot; buyable target 25 Nov 2026 (latest 1 Dec 2026) &middot; "
              "product budget $1,500&ndash;$2,500 &middot; 2&ndash;4 SKUs if MOQ and economics permit. &middot; "
              "<b>No provider has been contacted, so no stock level, sample time, lead time, dispatch date or arrival date is known &mdash; "
              "none is invented.</b>" % TODAY, sub),
            P(LEGEND, leg)]
    turn = [r for r in sd if r["category"] == "Turnkey finished-product"]
    ing = [r for r in sd if r["category"] == "Ingredient supplier"]

    out += [P("A. Turnkey finished-product providers (ingredient + packing under one roof)", h2)]
    data = [[f"<b>{sh(r['company'], 30)}</b><br/>{sh(r['country'], 16)}", sh(r["public_contact"], 26),
             sh(r["products_and_exact_forms"], 50),
             "supply " + sh(r["supply_only"], 8) + "<br/>turnkey " + sh(r["turnkey_finished"], 10),
             sh(r["evidence_status"], 32) + "<br/><i>gaps:</i> " + sh(r["documentation_gaps"], 34),
             sh(r["moq"], 9) + "<br/>" + sh(r["price"], 9),
             fieldset([r["stock_availability"], r["sample_dispatch_time"], r["production_packing_lead_time"],
                       r["earliest_dispatch_date"], r["est_arrival_us_packer"]], 26),
             "<b>" + r["outreach_priority"] + "</b>"] for r in turn]
    out += [mk(["Provider / country", "Public contact", "Products & exact forms", "Capability",
                "Evidence + documentation gaps", "MOQ / price",
                "Stock &middot; sample &middot; lead &middot; earliest dispatch &middot; US arrival", "Priority"],
               data, [10, 10, 15, 8, 17, 6, 12, 5])]

    out += [Spacer(1,4), P("B. Ingredient suppliers (supply-only)", h2)]
    data = [[f"<b>{sh(r['company'], 30)}</b><br/>{sh(r['country'], 16)}", sh(r["public_contact"], 26),
             sh(r["products_and_exact_forms"], 50), sh(r["turnkey_finished"], 10),
             sh(r["evidence_status"], 32) + "<br/><i>gaps:</i> " + sh(r["documentation_gaps"], 34),
             sh(r["moq"], 9) + "<br/>" + sh(r["price"], 9),
             fieldset([r["stock_availability"], r["production_packing_lead_time"],
                       r["earliest_dispatch_date"], r["est_arrival_us_packer"]], 26),
             "<b>" + r["outreach_priority"] + "</b>"] for r in ing]
    out += [mk(["Provider / country", "Public contact", "Products & exact forms", "Turnkey?",
                "Evidence + documentation gaps", "MOQ / price",
                "Stock &middot; lead &middot; earliest dispatch &middot; US arrival", "Priority"],
               data, [10, 10, 15, 5, 17, 6, 12, 5])]

    out += [Spacer(1,3),
            P("<b>Ranking rule:</b> ranked first by ability to meet our order size and target date &mdash; <b>not</b> by air-freight availability. An overseas "
              "provider is not treated as fast merely because air freight exists; production readiness and export documentation are separate gates.", leg),
            decisionbox([
                "&#9744; Confirm which providers to approach, in what order, and who signs off. &#9744; Provide origin and US-packer ZIP codes so arrival can be replaced with real quotes.",
                "&#9744; Record contact owner, next action and date per provider. &#9744; No price, stock level or lead time is confirmed for any provider listed here."])]

    # ================= SHEET 2 : PACKAGERS =================
    pk = rows("packager_decision_sheets.csv")
    out += [PageBreak(), P("PRINTABLE DECISION SHEET 2 &mdash; PACKAGERS", h1),
            P("Prepared %s &middot; Project: <b>HERBS/SPICES</b> holiday launch &middot; filling and sealing are outsourced; we supply label artwork. &middot; "
              "Proximity cannot be stated without our actual pickup and delivery ZIP codes, so it is marked OWNER_INPUT_REQUIRED rather than guessed." % TODAY, sub),
            P(LEGEND, leg)]
    data = [[sh(r["provider_class"], 20), f"<b>{sh(r['company'], 30)}</b><br/>{sh(r['location'], 22)}",
             sh(r["public_contact"], 22), "<b>" + sh(r["customer_supplied_ingredients"], 20) + "</b>",
             sh(r["whole_spice_capability"], 18) + "<br/>powder: " + sh(r["powder_capability"], 18),
             sh(r["stock_jars_pouches"], 16),
             "fill " + sh(r["filling"], 9) + " &middot; seal " + sh(r["sealing"], 9) + "<br/>code " + sh(r["lot_date_coding"], 11) + " &middot; label " + sh(r["label_application"], 16),
             sh(r["organic_handling_capability_and_evidence"], 66),
             sh(r["minimum_run"], 9) + "<br/>" + sh(r["setup_charges"], 9) + "<br/>" + sh(r["receiving_storage_charges"], 9),
             fieldset([r["earliest_production_slot"], r["finished_goods_ready_date"]], 24) + "<br/>FBA prep " + sh(r["fba_prep_and_carrier_pickup"], 22),
             sh(r["distance_to_us"], 16), "<b>" + r["outreach_priority"] + "</b>"] for r in pk]
    out += [mk(["Class", "Provider /<br/>location", "Public<br/>contact", "Customer-supplied<br/>ingredients?",
                "Whole / powder<br/>capability", "Stock jars /<br/>pouches", "Fill &middot; seal &middot; code &middot; label",
                "Organic-handling capability<br/>and evidence", "Min run &middot; setup<br/>&middot; storage",
                "Slot &middot; FG-ready<br/>&middot; FBA prep", "Distance<br/>to us", "Priority"],
               data, [8, 9, 8, 12, 8, 7, 10, 14, 8, 10, 8, 5], fs=7.0, pad=2.4)]
    out += [Spacer(1,6),
            decisionbox([
                "<b>CAUTION &mdash; FBA prep centres:</b> a sealed-unit label / FBA-prep provider is <b>not</b> established as authorised to open, "
                "reseal or repack food. Use one only for label application and poly-bagging of already-sealed units. Repacking food is a "
                "qualified-packer task.",
                "&#9744; Confirm which packers accept <b>customer-supplied</b> organic ingredient (currently unconfirmed for all).",
                "&#9744; Confirm packer NOP handler certification &mdash; SQF and GMP are food-safety schemes, <b>not</b> organic certification.",
                "&#9744; Provide pickup and delivery ZIP codes so &lsquo;nearby&rsquo; can be assessed.",
                "&#9744; Decide the label model: provider-applied vs receive-sealed-and-apply-ourselves (price both)."])]

    # ================= SHEET 3 : SHIPPING =================
    so = rows("shipping_options_comparison.csv")
    si = rows("shipping_input_checklist.csv")
    rs = rows("route_speed_ranking.csv")
    out += [PageBreak(), P("PRINTABLE DECISION SHEET 3 &mdash; SHIPPING OPTIONS &amp; ROUTES", h1),
            P("Prepared %s &middot; Applies to the <b>HERBS/SPICES</b> legs (supplier&rarr;packer, packer&rarr;Amazon). &middot; "
              "The Lion&rsquo;s Mane project is separate, sits on inventory already at the owner&rsquo;s home, and does not require international sourcing. &middot; "
              "<b>No freight rate or delivery date is guaranteed; no route is claimed cheapest.</b> &middot; "
              "This sheet is set across two landscape pages because ten service options, fourteen quote inputs and five routes cannot be shown on one page "
              "at readable type; type has not been shrunk to force a fit." % TODAY, sub)]

    out += [P("A. Apples-to-apples: request every quote on this identical input set", h2)]
    cols_n = 4
    chunks = [si[i:i + cols_n] for i in range(0, len(si), cols_n)]
    chunks = [c + [None] * (cols_n - len(c)) for c in chunks]
    grid = [[(f"{sh(r['input_required'], 26)}<br/><font color='#6B6B63'>{sh(r['why_needed'], 30)}</font><br/><b>{sh(r['status'], 18)}</b>"
              if r else "") for r in row] for row in zip(*chunks)]
    out += [mk(["Input &middot; why &middot; status"] * cols_n, grid, [25] * cols_n, fs=6.8, pad=2.6)]
    out += [Spacer(1,3),
            P("<b>Always separate these charge lines:</b> origin pickup &amp; export &middot; main transport &middot; insurance &middot; customs brokerage &middot; "
              "duties and applicable import charges &middot; destination handling &middot; final delivery &middot; storage, detention and other exclusions &middot; "
              "<b>Amazon inbound transportation and placement charges (separate).</b> An airport-only freight quote must not be compared with a delivered quote "
              "without adding the remaining charges. Compare the same endpoint; the Amazon FBA destination is still unresolved, so the US leg uses a provisional "
              "receiving point and the Amazon leg is flagged.", leg)]

    out += [P("B. Service options", h2)]
    data = [[f"<b>{sh(r['option'], 34)}</b><br/>{sh(r['company_or_service'], 34)}",
             sh(r["transport_mode"], 12) + "<br/>" + sh(r["door_to_door_vs_terminal"], 15) + "<br/>pickup " + sh(r["origin_pickup_coverage"], 20),
             sh(r["customs_brokerage"], 28), sh(r["food_organic_acceptance_questions"], 34),
             sh(r["published_transit_indication"], 42), "<b>" + sh(r["actual_delivery_estimate"], 16) + "</b>",
             sh(r["cost_coverage"], 38), sh(r["suitability_small_initial_order"], 26),
             sh(r["recommended_next_quote_request"], 34)] for r in so]
    out += [mk(["Option / service", "Mode &middot; coverage", "Customs brokerage", "Food / organic acceptance questions",
                "Published transit indication", "Actual delivered estimate", "Cost coverage", "Suitability (small order)", "Next quote request"],
               data, [12, 13, 10, 12, 13, 8, 12, 9, 12], fs=6.4, pad=2.0)]

    out += [P("C. Complete-route speed ranking (source-confirmed dates kept separate from planning allowances)", h2)]
    data = [[f"<b>{r['route_id']}</b>", sh(r["route_description"], 44), sh(r["product_order_size_fit"], 34),
             sh(r["documentation_readiness"], 34), "<b>" + sh(r["earliest_credible_finished_unit"], 32) + "</b>",
             "<b>" + sh(r["route_label"], 24) + "</b>"] for r in rs]
    out += [mk(["Route", "Description", "Product / order-size fit", "Documentation readiness",
                "Earliest credible finished unit", "Label"], data, [4, 25, 19, 19, 18, 15], fs=6.7, pad=2.2)]
    out += [Spacer(1,3),
            P("Rank order: product/order-size fit and required documentation &rarr; earliest credible finished-unit availability &rarr; fully delivered cost &rarr; "
              "coordination complexity and cash exposure. <b>Where timing is unknown the route is UNRANKED / CONFIRMATION REQUIRED</b>; no favourable estimate is "
              "assigned silently.", leg),
            decisionbox([
                "&#9744; Confirm which shipping option(s) to quote from and who books them. &#9744; Supply origin + US-packer ZIP, carton count, weight, dimensions, declared value.",
                "&#9744; Fix the Amazon FBA destination before quoting the final leg. &#9744; Record per quote: performing carrier, included charges, exclusions, duty/tax terms.",
                "&#9744; A marketplace such as Freightos is a <b>comparison platform</b>; identify the carrier actually performing pickup per quote."])]
    return out