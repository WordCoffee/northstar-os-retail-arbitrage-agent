"""Build the Q4 launch plan PDF v2 — built on Nico's 5 Nov quote.

Source data:
  Nico / Green Wrap email 2026-11-05  (FOB $2.23, MOQ 100/500, fabric stock)
  reports/q4_sourcing_director_brief_20261104.md  (freight + duty model)
  Bright Data Amazon scan 2026-11-05  (velocity, reviews, price points)
"""
from __future__ import annotations

import os
from reportlab.lib.colors import HexColor, Color
from reportlab.lib.pagesizes import letter
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
FONTS = os.path.join(ROOT, "Northstar_backend", "assets", "fonts")

BONE = HexColor("#F7F4EF")
PAPER = HexColor("#FFFDF9")
INK = HexColor("#1B2E24")
MUTED = HexColor("#6B7A70")
BRASS = HexColor("#8A6A3F")
RULE = HexColor("#DED8CC")
GOOD = HexColor("#2F6B4F")
CLAY = HexColor("#9A5B2C")
SAND = HexColor("#E8E1D4")

W, H = letter
M = 54.0


def register() -> None:
    pdfmetrics.registerFont(TTFont("Display", os.path.join(FONTS, "PlayfairDisplay.ttf")))
    pdfmetrics.registerFont(TTFont("Body", os.path.join(FONTS, "Inter.ttf")))


def bg(c: canvas.Canvas, tone: Color = BONE) -> None:
    c.setFillColor(tone)
    c.rect(0, 0, W, H, stroke=0, fill=1)


def tracked(c: canvas.Canvas, x: float, y: float, text: str,
            size: float, color: Color, track: float = 1.6) -> None:
    c.setFont("Body", size)
    c.setFillColor(color)
    cx = x
    for ch in text:
        c.drawString(cx, y, ch)
        cx += pdfmetrics.stringWidth(ch, "Body", size) + track


def rule(c: canvas.Canvas, x: float, y: float, w: float,
         color: Color = RULE, lw: float = 0.6) -> None:
    c.setStrokeColor(color)
    c.setLineWidth(lw)
    c.line(x, y, x + w, y)


def money(v: float) -> str:
    return "${:,.2f}".format(v)


def footer(c: canvas.Canvas, page: int, note: str) -> None:
    rule(c, M, 46, W - 2 * M, RULE, 0.5)
    c.setFont("Body", 6.6)
    c.setFillColor(MUTED)
    c.drawString(M, 34, note)
    c.drawRightString(W - M, 34, "%02d / 04" % page)


# ---------------------------------------------------------------- 1 cover

def cover(c: canvas.Canvas) -> None:
    bg(c)
    c.setFillColor(INK)
    c.rect(0, 0, 14, H, stroke=0, fill=1)

    tracked(c, M, H - 92, "NORTHSTAR  /  SOURCING", 7.2, BRASS, 2.2)

    c.setFont("Display", 44)
    c.setFillColor(INK)
    c.drawString(M, H - 154, "The quote is in.")
    c.drawString(M, H - 202, "$2.23 a set.")

    c.setFont("Body", 10.0)
    c.setFillColor(MUTED)
    c.drawString(M, H - 234, "Green Wrap came back at $2.23 FOB — 11% under the $2.50 we modelled.")
    c.drawString(M, H - 251, "Same price at 100 sets as at 500. There is no volume discount.")

    rule(c, M, H - 280, W - 2 * M, INK, 1.1)

    stats = [
        ("RECOMMENDED ORDER", "100 sets", "70 Christmas · 30 floral"),
        ("CAPITAL AT RISK", money(389), "goods + freight + duty"),
        ("PROFIT IF SOLD", money(809), "at $19.99 / $17.99"),
        ("ROI", "208%", "on landed cost"),
    ]
    y = H - 330
    for i, (label, value, sub) in enumerate(stats):
        x = M + i * ((W - 2 * M) / 4)
        tracked(c, x, y, label, 6.2, MUTED, 1.4)
        c.setFont("Display", 24)
        c.setFillColor(INK)
        c.drawString(x, y - 31, value)
        c.setFont("Body", 7.2)
        c.setFillColor(MUTED)
        c.drawString(x, y - 45, sub)

    # the two quotes, side by side
    top = 330
    cw = (W - 2 * M - 18) / 2
    cards = [
        ("100 SETS", "Stock envelope", "$2.23", "per set · $223 goods",
         ["Custom envelope: no — MOQ 500", "Christmas fabric: 100 available", "Freight: ~$1.10 / set"], GOOD),
        ("500 SETS", "Custom branded envelope", "$2.23", "per set · $1,115 goods",
         ["Custom envelope: yes", "Christmas capped at 100 of 500", "Freight: ~$0.50 / set"], BRASS),
    ]
    for i, (head, sub, price, per, lines, accent) in enumerate(cards):
        x = M + i * (cw + 18)
        c.setFillColor(PAPER)
        c.roundRect(x, top - 168, cw, 168, 3, stroke=0, fill=1)
        c.setFillColor(accent)
        c.roundRect(x, top - 168, 4, 168, 2, stroke=0, fill=1)

        tracked(c, x + 18, top - 28, head, 6.6, accent, 1.6)
        c.setFont("Display", 16)
        c.setFillColor(INK)
        c.drawString(x + 18, top - 50, sub)

        c.setFont("Display", 22)
        c.setFillColor(INK)
        c.drawString(x + 18, top - 82, price)
        c.setFont("Body", 7.4)
        c.setFillColor(MUTED)
        c.drawString(x + 18 + pdfmetrics.stringWidth(price, "Display", 22) + 8, top - 82, "per set")

        c.setFont("Body", 7.0)
        c.setFillColor(MUTED)
        c.drawString(x + 18, top - 96, per)

        ly = top - 118
        for ln in lines:
            c.setFillColor(SAND)
            c.circle(x + 21, ly + 2.4, 1.8, stroke=0, fill=1)
            c.setFont("Body", 7.2)
            c.setFillColor(MUTED)
            c.drawString(x + 29, ly, ln)
            ly -= 15

    c.setFont("Body", 7.2)
    c.setFillColor(MUTED)
    c.drawString(M, 108, "Freight and duty are modelled, not quoted. Nico has not yet sent shipping cost — that is the last open number.")
    c.drawString(M, 94, "Fee stack: 15% referral, FBA $4.35, $0.15 prep. Duty 25% of FOB, charged on goods value not freight.")

    footer(c, 1, "Northstar OS  ·  launch plan v2  ·  5 November 2026")
    c.showPage()


# ---------------------------------------------------------------- 2 beeswax

def beeswax(c: canvas.Canvas) -> None:
    bg(c)

    tracked(c, M, H - 74, "SKU 01  /  QUOTED  /  AMAZON.COM", 7.0, BRASS, 2.0)

    c.setFont("Display", 31)
    c.setFillColor(INK)
    c.drawString(M, H - 112, "Beeswax Wraps")
    c.setFont("Body", 9.2)
    c.setFillColor(MUTED)
    c.drawString(M, H - 132, "3-piece set  ·  cotton + beeswax  ·  $2.23 FOB  ·  MOQ 100")

    bw = 118
    c.setFillColor(INK)
    c.roundRect(W - M - bw, H - 128, bw, 52, 3, stroke=0, fill=1)
    c.setFont("Body", 6.4)
    c.setFillColor(HexColor("#B9C6BE"))
    c.drawCentredString(W - M - bw / 2, H - 92, "SELLS AT")
    c.setFont("Display", 20)
    c.setFillColor(PAPER)
    c.drawCentredString(W - M - bw / 2, H - 118, "$17.99")

    rule(c, M, H - 152, W - 2 * M, INK, 1.0)

    # waterfall at the 100-set landed cost
    y = H - 196
    tracked(c, M, y + 20, "WHERE THE MONEY GOES  /  100-SET LANDED COST", 6.6, MUTED, 1.6)
    price, landed, referral, fba, prep, net = 17.99, 3.89, 2.70, 4.35, 0.15, 6.90
    segs = [
        ("Landed $3.89", landed, HexColor("#B7AE9C")),
        ("Referral", referral, HexColor("#8FA396")),
        ("FBA", fba, HexColor("#6E8A79")),
        ("Prep", prep, HexColor("#A9BCB0")),
        ("Net $6.90", net, GOOD),
    ]
    bar_w = W - 2 * M
    bx = M
    for label, val, col in segs:
        sw = bar_w * (val / price)
        c.setFillColor(col)
        c.rect(bx, y - 14, sw, 26, stroke=0, fill=1)
        if sw > 40:
            c.setFont("Body", 6.6)
            c.setFillColor(PAPER if col == GOOD else INK)
            c.drawCentredString(bx + sw / 2, y - 5, money(val))
        bx += sw
    c.setFillColor(BONE)
    c.rect(bx, y - 14, max(0, M + bar_w - bx), 26, stroke=0, fill=1)

    lx = M
    for label, val, col in segs:
        c.setFillColor(col)
        c.circle(lx + 2.5, y - 27.8, 2.6, stroke=0, fill=1)
        c.setFont("Body", 7.0)
        c.setFillColor(MUTED)
        c.drawString(lx + 9, y - 30, label)
        lx += pdfmetrics.stringWidth(label, "Body", 7.0) + 30

    # stat cards
    y2 = H - 262
    cards = [
        ("ORDER", "100 sets", "70 Christmas · 30 floral"),
        ("LANDED / SET", "$3.89", "freight $1.10 + duty $0.56"),
        ("NET / SET", "$6.90", "at $17.99 retail"),
        ("ROI", "177%", "on landed cost"),
    ]
    cw = (W - 2 * M - 3 * 10) / 4
    for i, (label, val, sub) in enumerate(cards):
        x = M + i * (cw + 10)
        c.setFillColor(PAPER)
        c.roundRect(x, y2 - 60, cw, 60, 2.5, stroke=0, fill=1)
        tracked(c, x + 10, y2 - 16, label, 5.9, MUTED, 1.2)
        c.setFont("Display", 16)
        c.setFillColor(INK)
        c.drawString(x + 10, y2 - 36, val)
        c.setFont("Body", 6.2)
        c.setFillColor(MUTED)
        c.drawString(x + 10, y2 - 48, sub)

    # cost build
    ty = y2 - 86
    tracked(c, M, ty, "COST BUILD, PER SET", 6.6, MUTED, 1.6)
    ty -= 18
    colw = 250
    lines = [
        ("FOB  (Nico, quoted)", "$2.23", False),
        ("Air freight  (modelled)", "$1.10", True),
        ("Duty 25% of FOB", "$0.56", True),
        ("Landed cost", "$3.89", False),
    ]
    for label, val, est in lines:
        c.setFont("Body", 8.2)
        c.setFillColor(MUTED)
        c.drawString(M, ty, label)
        c.setFont("Body", 8.2)
        c.setFillColor(INK if not est else MUTED)
        c.drawRightString(M + colw, ty, val)
        if est:
            c.setFont("Body", 5.6)
            c.setFillColor(BRASS)
            c.drawRightString(M + colw + 26, ty, "est")
        rule(c, M, ty - 4.5, colw, RULE, 0.4)
        ty -= 16

    c.setFont("Body", 8.6)
    c.setFillColor(INK)
    c.drawString(M, ty, "Net profit per set")
    c.setFont("Display", 12)
    c.setFillColor(GOOD)
    c.drawRightString(M + colw, ty, "$6.90")

    # scenario column
    rx = M + colw + 52
    c.setFont("Body", 7.2)
    c.setFillColor(MUTED)
    c.drawString(rx, ty + 20, "IF YOU ORDER 500 INSTEAD")
    rows = [
        ("Freight / set", "$0.50"),
        ("Landed / set", "$3.29"),
        ("Net / set", "$7.50"),
        ("ROI", "228%"),
        ("Extra capital", "+$1,256"),
        ("Extra profit", "+$3,060"),
    ]
    qy = ty + 4
    for label, val in rows:
        c.setFont("Body", 8.0)
        c.setFillColor(MUTED)
        c.drawString(rx, qy, label)
        c.setFont("Body", 8.4)
        c.setFillColor(GOOD if "Extra" in label else INK)
        c.drawRightString(W - M, qy, val)
        rule(c, rx, qy - 4.5, W - M - rx, RULE, 0.4)
        qy -= 15

    # market
    my = qy - 20
    rule(c, M, my + 14, W - 2 * M, RULE, 0.5)
    tracked(c, M, my, "MARKET, MEASURED 5 NOV", 6.6, MUTED, 1.6)
    my -= 22
    mw = (W - 2 * M - 2 * 12) / 3
    market = [
        ("6,000", "units / month", "category velocity, 15 listings"),
        ("2,000+", "leader velocity", "Bee's Wrap roll at $21"),
        ("10,817", "reviews to beat", "dominant brand, hard shelf"),
    ]
    for i, (val, label, sub) in enumerate(market):
        x = M + i * (mw + 12)
        c.setFont("Display", 17)
        c.setFillColor(INK)
        c.drawString(x, my, val)
        c.setFont("Body", 7.4)
        c.setFillColor(MUTED)
        c.drawString(x, my - 12, label)
        c.setFont("Body", 6.5)
        c.setFillColor(MUTED)
        c.drawString(x, my - 22, sub)

    # timeline
    sy = my - 44
    rule(c, M, sy + 14, W - 2 * M, RULE, 0.5)
    tracked(c, M, sy, "LEAD TIME  /  ORDER THIS WEEK", 6.6, MUTED, 1.6)
    sy -= 30
    c.setStrokeColor(SAND)
    c.setLineWidth(3)
    c.line(M + 4, sy + 4, W - M - 4, sy + 4)
    steps = [("DAY 0–7", "Factory gate", "100 sets, 2 designs"),
             ("DAY 7–14", "Air freight", "Henan → US"),
             ("DAY 14–18", "Customs", "duty 25%"),
             ("DAY 18–25", "FBA receiving", "live 1 Dec")]
    step = (W - 2 * M - 16) / (len(steps) - 1)
    for i, (when, what, detail) in enumerate(steps):
        x = M + 4 + i * step
        c.setFillColor(BONE)
        c.circle(x, sy + 4, 6.5, stroke=0, fill=1)
        c.setStrokeColor(INK if i < len(steps) - 1 else CLAY)
        c.setLineWidth(1.4)
        c.circle(x, sy + 4, 6.5, stroke=1, fill=0)
        c.setFillColor(INK if i < len(steps) - 1 else CLAY)
        c.circle(x, sy + 4, 2.6, stroke=0, fill=1)
        c.setFont("Body", 7.2)
        c.setFillColor(BRASS)
        c.drawCentredString(x, sy + 18, when)
        c.setFont("Body", 7.8)
        c.setFillColor(INK)
        c.drawCentredString(x, sy - 14, what)
        c.setFont("Body", 6.4)
        c.setFillColor(MUTED)
        c.drawCentredString(x, sy - 25, detail)

    c.setFillColor(HexColor("#FBF7EE"))
    c.roundRect(M, sy - 100, W - 2 * M, 34, 2, stroke=0, fill=1)
    c.setFillColor(BRASS)
    c.rect(M, sy - 100, 3, 34, stroke=0, fill=1)
    c.setFont("Body", 7.8)
    c.setFillColor(INK)
    c.drawString(M + 12, sy - 79,
                 "Confirm by 6 Nov and the goods are live 1 Dec — the full 20-day Christmas window survives.")

    footer(c, 2, "Northstar OS  ·  launch plan v2  ·  FOB quoted by Nico 5 Nov 2026")
    c.showPage()


# ---------------------------------------------------------------- 3 unpaper

def unpaper(c: canvas.Canvas) -> None:
    bg(c)

    tracked(c, M, H - 74, "SKU 02  /  NO QUOTE YET", 7.0, CLAY, 2.0)

    c.setFont("Display", 31)
    c.setFillColor(INK)
    c.drawString(M, H - 112, "Cotton Unpaper Towels")
    c.setFont("Body", 9.2)
    c.setFillColor(MUTED)
    c.drawString(M, H - 132, "24-pack  ·  double layer  ·  25 × 25 cm  ·  GOTS flannel")

    bw = 118
    c.setFillColor(HexColor("#EFEAE1"))
    c.roundRect(W - M - bw, H - 128, bw, 52, 3, stroke=0, fill=1)
    c.setFont("Body", 6.4)
    c.setFillColor(MUTED)
    c.drawCentredString(W - M - bw / 2, H - 92, "TARGET PRICE")
    c.setFont("Display", 20)
    c.setFillColor(MUTED)
    c.drawCentredString(W - M - bw / 2, H - 118, "$29.99")

    rule(c, M, H - 152, W - 2 * M, INK, 1.0)

    # warning band
    c.setFillColor(HexColor("#FBF1E8"))
    c.roundRect(M, H - 214, W - 2 * M, 44, 3, stroke=0, fill=1)
    c.setFillColor(CLAY)
    c.rect(M, H - 214, 3, 44, stroke=0, fill=1)
    c.setFont("Body", 8.6)
    c.setFillColor(CLAY)
    c.drawString(M + 14, H - 190, "No supplier has quoted this SKU.")
    c.setFont("Body", 7.6)
    c.setFillColor(MUTED)
    c.drawString(M + 14, H - 204, "Everything below runs on a $7.00 working estimate. It is not a price.")

    # stat cards
    y2 = H - 268
    cards = [
        ("ORDER", "300 sets", "if the estimate holds"),
        ("LANDED / SET", "~$8.75", "estimate, not quoted"),
        ("NET / SET", "~$12.59", "at $29.99 retail"),
        ("ROI", "~144%", "on estimated cost"),
    ]
    cw = (W - 2 * M - 3 * 10) / 4
    for i, (label, val, sub) in enumerate(cards):
        x = M + i * (cw + 10)
        c.setFillColor(PAPER)
        c.roundRect(x, y2 - 60, cw, 60, 2.5, stroke=0, fill=1)
        tracked(c, x + 10, y2 - 16, label, 5.9, MUTED, 1.2)
        c.setFont("Display", 16)
        c.setFillColor(MUTED)
        c.drawString(x + 10, y2 - 36, val)
        c.setFont("Body", 6.2)
        c.setFillColor(MUTED)
        c.drawString(x + 10, y2 - 48, sub)

    # break-even
    ty = y2 - 90
    tracked(c, M, ty, "THE NUMBER THAT DECIDES IT", 6.6, MUTED, 1.6)
    ty -= 44

    c.setFont("Display", 30)
    c.setFillColor(INK)
    c.drawString(M, ty, "$10.00")
    c.setFont("Body", 8.4)
    c.setFillColor(MUTED)
    c.drawString(M + 118, ty + 2, "landed cost is the ceiling. Above it, the 24-pack stops working at $29.99.")
    c.drawString(M + 118, ty - 12, "Below it, this is the better of the two SKUs — thinner moat, higher ticket.")

    ty -= 40
    rule(c, M, ty, W - 2 * M, RULE, 0.5)

    # sensitivity table
    ty -= 22
    tracked(c, M, ty, "SENSITIVITY AT $29.99", 6.6, MUTED, 1.6)
    ty -= 20
    head = ["LANDED COST", "NET / UNIT", "ROI", "VERDICT"]
    colx = [M, M + 150, M + 280, M + 360]
    for i, h in enumerate(head):
        tracked(c, colx[i], ty, h, 6.0, MUTED, 1.2)
    ty -= 12
    rule(c, M, ty, W - 2 * M, INK, 0.6)
    ty -= 18

    rows = [
        ("$7.50", "$13.84", "185%", "strong", GOOD),
        ("$8.75", "$12.59", "144%", "works", GOOD),
        ("$10.00", "$11.34", "113%", "thin", BRASS),
        ("$11.50", "$9.84", "86%", "walk away", CLAY),
    ]
    for landed_s, net_s, roi_s, verdict, col in rows:
        c.setFont("Body", 9.0)
        c.setFillColor(INK)
        c.drawString(colx[0], ty, landed_s)
        c.drawString(colx[1], ty, net_s)
        c.drawString(colx[2], ty, roi_s)
        c.setFillColor(col)
        c.drawString(colx[3], ty, verdict)
        ty -= 9
        rule(c, M, ty, W - 2 * M, RULE, 0.4)
        ty -= 17

    # market
    my = ty - 14
    tracked(c, M, my, "MARKET, MEASURED 5 NOV", 6.6, MUTED, 1.6)
    my -= 22
    mw = (W - 2 * M - 2 * 12) / 3
    market = [
        ("3,450", "units / month", "category velocity, 15 listings"),
        ("700+", "leader velocity", "24-pack at $29.99"),
        ("1,784", "reviews to beat", "vs 10,817 on beeswax"),
    ]
    for i, (val, label, sub) in enumerate(market):
        x = M + i * (mw + 12)
        c.setFont("Display", 17)
        c.setFillColor(INK)
        c.drawString(x, my, val)
        c.setFont("Body", 7.4)
        c.setFillColor(MUTED)
        c.drawString(x, my - 12, label)
        c.setFont("Body", 6.5)
        c.setFillColor(MUTED)
        c.drawString(x, my - 22, sub)

    c.setFillColor(HexColor("#FBF7EE"))
    c.roundRect(M, my - 78, W - 2 * M, 34, 2, stroke=0, fill=1)
    c.setFillColor(BRASS)
    c.rect(M, my - 78, 3, 34, stroke=0, fill=1)
    c.setFont("Body", 7.8)
    c.setFillColor(INK)
    c.drawString(M + 12, my - 57,
                 "Do not order 300 of these against a guess. Get a quote first — then decide.")

    footer(c, 3, "Northstar OS  ·  launch plan v2  ·  no supplier quote on file for this SKU")
    c.showPage()


# ---------------------------------------------------------------- 4 decision

def decision(c: canvas.Canvas) -> None:
    bg(c, PAPER)
    c.setFillColor(INK)
    c.rect(0, H - 8, W, 8, stroke=0, fill=1)

    tracked(c, M, H - 76, "THE DECISION", 7.0, BRASS, 2.0)
    c.setFont("Display", 33)
    c.setFillColor(INK)
    c.drawString(M, H - 116, "Start at 100. Not 500.")

    c.setFont("Body", 9.0)
    c.setFillColor(MUTED)
    c.drawString(M, H - 140, "$2.23 a set either way. The only thing 500 buys you is custom envelopes and cheaper freight.")

    rule(c, M, H - 166, W - 2 * M, INK, 1.0)

    rows = [
        ("", "100 SETS", "500 SETS"),
        ("Goods cost", "$223", "$1,115"),
        ("Freight (est.)", "$110", "$250"),
        ("Duty (est.)", "$56", "$279"),
        ("Total capital", "$389", "$1,645"),
        ("Landed / set", "$3.89", "$3.29"),
        ("Net / set", "$6.90", "$7.50"),
        ("ROI", "177%", "228%"),
        ("Profit if sold", "$690", "$3,750"),
        ("Envelope", "stock", "custom branded"),
        ("Christmas stock", "100 sets", "100 of 500"),
        ("Reorder risk", "none", "locked into 400 floral"),
    ]
    ty = H - 196
    colx = [M, M + 210, M + 360]
    for r, row in enumerate(rows):
        if r == 0:
            for ci, cell in enumerate(row):
                tracked(c, colx[ci], ty, cell, 6.4, MUTED, 1.4)
            ty -= 12
            rule(c, M, ty, W - 2 * M, INK, 0.7)
            ty -= 16
            continue
        c.setFont("Body", 8.2)
        c.setFillColor(MUTED)
        c.drawString(colx[0], ty, row[0])
        for ci in (1, 2):
            c.setFont("Body", 9.0)
            c.setFillColor(INK)
            c.drawString(colx[ci], ty, row[ci])
        if row[0] in ("ROI", "Profit if sold"):
            c.setFillColor(GOOD)
            c.setFont("Body", 9.0)
            c.drawString(colx[2], ty, row[2])
        ty -= 8
        rule(c, M, ty, W - 2 * M, RULE, 0.4)
        ty -= 13

    # why
    by = ty - 16
    tracked(c, M, by, "WHY 100", 6.6, MUTED, 1.6)
    by -= 20
    reasons = [
        ("The price does not move.", "There is no volume discount, so ordering 500 buys you nothing but envelopes."),
        ("Christmas is capped at 100 anyway.", "Nico has fabric for 100 reindeer / snowflake sets. That is your seasonal ceiling."),
        ("$389 is a test. $1,645 is a bet.", "You have no sales history on this SKU, no reviews, and no shipping quote yet."),
        ("Custom envelopes can wait one cycle.", "Branded packaging is a reorder decision, not a launch decision."),
    ]
    for head, body in reasons:
        c.setFillColor(BRASS)
        c.circle(M + 3, by + 2.5, 2.2, stroke=0, fill=1)
        c.setFont("Body", 8.2)
        c.setFillColor(INK)
        c.drawString(M + 14, by, head)
        c.setFont("Body", 7.5)
        c.setFillColor(MUTED)
        c.drawString(M + 14, by - 11, body)
        by -= 29

    # what to send nico
    ny = by - 8
    c.setFillColor(BONE)
    c.roundRect(M, ny - 108, W - 2 * M, 108, 3, stroke=0, fill=1)
    c.setFillColor(INK)
    c.rect(M, ny - 108, 4, 108, stroke=0, fill=1)

    tracked(c, M + 18, ny - 20, "REPLY TO NICO WITH", 6.8, BRASS, 1.8)
    ny -= 38
    asks = [
        "1.  Confirm 100 sets — 70 reindeer/snowflake, 30 floral. Ask which floral numbers he recommends.",
        "2.  Shipping cost to your FC, and whether it is DDP or DDU (who pays the 25% duty on arrival).",
        "3.  Whether the $2.23 includes the stock envelope, or envelope is billed separately.",
        "4.  Lead time in writing — can 100 sets leave the factory within 7 days of artwork approval?",
        "5.  Ask to hold the 500-set custom envelope option for a Q1 reorder at the same $2.23.",
    ]
    for a in asks:
        c.setFont("Body", 7.4)
        c.setFillColor(INK if a.startswith("1") else MUTED)
        c.drawString(M + 18, ny, a)
        ny -= 13.5

    footer(c, 4, "Northstar OS  ·  launch plan v2  ·  sources: Nico 5 Nov quote, Bright Data scan 5 Nov 2026")
    c.showPage()


def main() -> None:
    register()
    out = os.path.join(ROOT, "reports", "launch_plan_v2_nico_quote_20261105.pdf")
    c = canvas.Canvas(out, pagesize=letter)
    c.setTitle("Q4 Launch Plan v2 — Nico Quote")
    c.setAuthor("Northstar OS")
    cover(c)
    beeswax(c)
    unpaper(c)
    decision(c)
    c.save()
    print("wrote", out, os.path.getsize(out), "bytes")


if __name__ == "__main__":
    main()
