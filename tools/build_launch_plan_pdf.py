"""Build the two-SKU Q4 launch plan PDF (Letter, 4 pages).

Data sources:
  reports/q4_sourcing_director_brief_20261104.md  (Green Wrap landed cost, lead time)
  Bright Data Amazon scan 2026-11-05               (velocity, review counts, price points)
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
            size: float, color: Color, track: float = 1.6) -> float:
    """Letter-spaced small caps line. Returns end x."""
    c.setFont("Body", size)
    c.setFillColor(color)
    cx = x
    for ch in text:
        c.drawString(cx, y, ch)
        cx += pdfmetrics.stringWidth(ch, "Body", size) + track
    return cx - track


def rule(c: canvas.Canvas, x: float, y: float, w: float, color: Color = RULE, lw: float = 0.6) -> None:
    c.setStrokeColor(color)
    c.setLineWidth(lw)
    c.line(x, y, x + w, y)


def money(v: float) -> str:
    return "${:,.2f}".format(v)


def footer(c: canvas.Canvas, page: int, total: int, note: str) -> None:
    rule(c, M, 46, W - 2 * M, RULE, 0.5)
    c.setFont("Body", 6.6)
    c.setFillColor(MUTED)
    c.drawString(M, 34, note)
    c.drawRightString(W - M, 34, "%02d / %02d" % (page, total))


# ---------------------------------------------------------------- cover

def cover(c: canvas.Canvas) -> None:
    bg(c)
    # left spine
    c.setFillColor(INK)
    c.rect(0, 0, 14, H, stroke=0, fill=1)

    tracked(c, M, H - 92, "NORTHSTAR  /  SOURCING", 7.2, BRASS, 2.2)

    c.setFont("Display", 46)
    c.setFillColor(INK)
    c.drawString(M, H - 156, "Two SKUs.")
    c.drawString(M, H - 206, "Five hundred units.")

    c.setFont("Body", 10.2)
    c.setFillColor(MUTED)
    c.drawString(M, H - 240, "A Q4 launch plan built on measured Amazon demand, not guesswork.")
    c.drawString(M, H - 258, "Landed costs and lead times from Green Wrap. Velocity from a 5 Nov scan.")

    rule(c, M, H - 288, W - 2 * M, INK, 1.1)

    # headline stats
    stats = [
        ("CAPITAL OUTLAY", money(3471), "to the supplier"),
        ("PROJECTED PROFIT", money(5089), "if all 500 sell"),
        ("BLENDED ROI", "147%", "on landed cost"),
        ("SELLABLE FROM", "Dec 1", "misses Black Friday"),
    ]
    y = H - 340
    for i, (label, value, sub) in enumerate(stats):
        x = M + i * ((W - 2 * M) / 4)
        tracked(c, x, y, label, 6.4, MUTED, 1.5)
        c.setFont("Display", 25)
        c.setFillColor(INK)
        c.drawString(x, y - 32, value)
        c.setFont("Body", 7.4)
        c.setFillColor(MUTED)
        c.drawString(x, y - 46, sub)

    # the two products, side by side cards
    cards = [
        ("01", "Cotton Unpaper Towels", "24-pack, double layer", "300 sets",
         "$29.99", "$12.59", "144%"),
        ("02", "Beeswax Wraps", "Patterned 3-pack", "200 sets",
         "$17.99", "$6.56", "155%"),
    ]
    top = 300
    cw = (W - 2 * M - 18) / 2
    for i, (num, name, desc, qty, price, net, roi) in enumerate(cards):
        x = M + i * (cw + 18)
        c.setFillColor(PAPER)
        c.roundRect(x, top - 150, cw, 150, 3, stroke=0, fill=1)
        c.setFillColor(SAND)
        c.roundRect(x, top - 150, 4, 150, 2, stroke=0, fill=1)

        c.setFont("Display", 15)
        c.setFillColor(BRASS)
        c.drawString(x + 18, top - 30, num)
        c.setFont("Display", 15.5)
        c.setFillColor(INK)
        c.drawString(x + 44, top - 30, name)
        c.setFont("Body", 7.6)
        c.setFillColor(MUTED)
        c.drawString(x + 44, top - 45, desc)

        rows = [("Order", qty), ("Sells at", price), ("Net / unit", net), ("ROI", roi)]
        ry = top - 72
        for label, val in rows:
            c.setFont("Body", 7.8)
            c.setFillColor(MUTED)
            c.drawString(x + 18, ry, label)
            c.setFont("Body", 9.4)
            c.setFillColor(INK)
            c.drawRightString(x + cw - 18, ry, val)
            rule(c, x + 18, ry - 5, cw - 36, RULE, 0.4)
            ry -= 19

    # bottom note
    c.setFont("Body", 7.4)
    c.setFillColor(MUTED)
    c.drawString(M, 118, "Unpaper COGS is a working estimate pending Nico's final quote. Every other figure is sourced.")
    c.drawString(M, 104, "Fee stack: 15% referral, FBA at 2026 standard rates, $0.25 / $0.15 prep, landed cost includes freight.")

    footer(c, 1, 4, "Northstar OS  ·  launch plan  ·  5 November 2026")
    c.showPage()


# ---------------------------------------------------------------- product page

def product_page(c: canvas.Canvas, page: int, *, index: str, title: str, subtitle: str,
                 price: float, qty: int, landed: float, referral: float, fba: float,
                 prep: float, net: float, roi: str, revenue: float, profit: float,
                 capital: float, market: list[tuple[str, str, str]],
                 shipping: list[tuple[str, str, str]], sourcing: str,
                 note: str) -> None:
    bg(c)

    tracked(c, M, H - 74, "SKU %s  /  AMAZON.COM" % index, 7.0, BRASS, 2.0)

    c.setFont("Display", 31)
    c.setFillColor(INK)
    c.drawString(M, H - 112, title)
    c.setFont("Body", 9.4)
    c.setFillColor(MUTED)
    c.drawString(M, H - 132, subtitle)

    # price badge
    bw = 118
    c.setFillColor(INK)
    c.roundRect(W - M - bw, H - 128, bw, 52, 3, stroke=0, fill=1)
    c.setFont("Body", 6.4)
    c.setFillColor(HexColor("#B9C6BE"))
    c.drawCentredString(W - M - bw / 2, H - 92, "SELLS AT")
    c.setFont("Display", 20)
    c.setFillColor(PAPER)
    c.drawCentredString(W - M - bw / 2, H - 118, money(price))

    rule(c, M, H - 152, W - 2 * M, INK, 1.0)

    # ---------------- fee waterfall bar
    y = H - 196
    tracked(c, M, y + 20, "WHERE THE MONEY GOES", 6.6, MUTED, 1.6)

    segs = [
        ("Landed cost", landed, HexColor("#B7AE9C")),
        ("Referral 15%", referral, HexColor("#8FA396")),
        ("FBA", fba, HexColor("#6E8A79")),
        ("Prep", prep, HexColor("#A9BCB0")),
        ("Your net", net, GOOD),
    ]
    bar_w = W - 2 * M
    bx = M
    for label, val, col in segs:
        sw = bar_w * (val / price)
        c.setFillColor(col)
        c.rect(bx, y - 14, sw, 26, stroke=0, fill=1)
        if sw > 34:
            c.setFont("Body", 6.6)
            c.setFillColor(PAPER if col == GOOD else INK)
            c.drawCentredString(bx + sw / 2, y - 5, money(val))
        bx += sw
    c.setFillColor(PAPER)
    c.rect(bx, y - 14, max(0, M + bar_w - bx), 26, stroke=0, fill=1)

    # legend
    lx = M
    ly = y - 30
    for label, val, col in segs:
        c.setFillColor(col)
        c.circle(lx + 2.5, ly + 2.2, 2.6, stroke=0, fill=1)
        c.setFont("Body", 7.0)
        c.setFillColor(MUTED)
        c.drawString(lx + 9, ly, label)
        lx += pdfmetrics.stringWidth(label, "Body", 7.0) + 30

    # ---------------- stat cards
    y2 = H - 258
    cards = [
        ("ORDER", "%d sets" % qty, "one air shipment"),
        ("LANDED / UNIT", money(landed), "freight + duty in"),
        ("NET / UNIT", money(net), "after all Amazon fees"),
        ("ROI", roi, "on landed cost"),
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
        c.setFont("Body", 6.3)
        c.setFillColor(MUTED)
        c.drawString(x + 10, y2 - 48, sub)

    # ---------------- money table
    ty = y2 - 86
    tracked(c, M, ty, "THE FULL STACK, PER UNIT", 6.6, MUTED, 1.6)
    ty -= 18
    lines = [
        ("Retail price", money(price), False),
        ("Referral fee (15%)", "-" + money(referral), False),
        ("FBA fulfilment", "-" + money(fba), False),
        ("Prep & labelling", "-" + money(prep), False),
        ("Landed cost", "-" + money(landed), False),
    ]
    colw = 250
    for label, val, _ in lines:
        c.setFont("Body", 8.2)
        c.setFillColor(MUTED)
        c.drawString(M, ty, label)
        c.setFont("Body", 8.2)
        c.setFillColor(INK)
        c.drawRightString(M + colw, ty, val)
        rule(c, M, ty - 4.5, colw, RULE, 0.4)
        ty -= 16

    c.setFont("Body", 8.6)
    c.setFillColor(INK)
    c.drawString(M, ty, "Net profit")
    c.setFont("Display", 12)
    c.setFillColor(GOOD)
    c.drawRightString(M + colw, ty, money(net))
    rule(c, M, ty - 5, colw, INK, 0.9)

    # at-quantity column
    rx = M + colw + 46
    c.setFont("Body", 7.4)
    c.setFillColor(MUTED)
    c.drawString(rx, ty + 18, "AT %d SETS" % qty)
    qty_rows = [
        ("Retail revenue", money(revenue)),
        ("Supplier payment", money(capital)),
        ("Total profit", money(profit)),
    ]
    qy = ty + 2
    for label, val in qty_rows:
        c.setFont("Body", 8.0)
        c.setFillColor(MUTED)
        c.drawString(rx, qy, label)
        c.setFont("Body", 8.4)
        c.setFillColor(INK)
        c.drawRightString(W - M, qy, val)
        rule(c, rx, qy - 4.5, W - M - rx, RULE, 0.4)
        qy -= 16

    # ---------------- market proof
    my = qy - 20
    rule(c, M, my + 14, W - 2 * M, RULE, 0.5)
    tracked(c, M, my, "MARKET, MEASURED 5 NOV", 6.6, MUTED, 1.6)
    my -= 22
    mw = (W - 2 * M - 2 * 12) / 3
    for i, (val, label, sub) in enumerate(market):
        x = M + i * (mw + 12)
        c.setFont("Display", 17)
        c.setFillColor(INK)
        c.drawString(x, my, val)
        c.setFont("Body", 7.4)
        c.setFillColor(MUTED)
        c.drawString(x, my - 12, label)
        c.setFont("Body", 6.6)
        c.setFillColor(MUTED)
        c.drawString(x, my - 22, sub)

    # ---------------- shipping timeline
    sy = my - 44
    rule(c, M, sy + 14, W - 2 * M, RULE, 0.5)
    tracked(c, M, sy, "LEAD TIME  /  GREEN WRAP, HENAN", 6.6, MUTED, 1.6)
    sy -= 30

    # timeline rail
    c.setStrokeColor(SAND)
    c.setLineWidth(3)
    c.line(M + 4, sy + 4, W - M - 4, sy + 4)
    step = (W - 2 * M - 16) / (len(shipping) - 1)
    for i, (when, what, detail) in enumerate(shipping):
        x = M + 4 + i * step
        c.setFillColor(BONE)
        c.circle(x, sy + 4, 6.5, stroke=0, fill=1)
        c.setStrokeColor(INK if i < len(shipping) - 1 else CLAY)
        c.setLineWidth(1.4)
        c.circle(x, sy + 4, 6.5, stroke=1, fill=0)
        c.setFillColor(INK if i < len(shipping) - 1 else CLAY)
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

    # sourcing line
    c.setFont("Body", 7.2)
    c.setFillColor(MUTED)
    c.drawString(M, sy - 56, sourcing)

    # callout
    c.setFillColor(HexColor("#FBF7EE"))
    c.roundRect(M, sy - 100, W - 2 * M, 34, 2, stroke=0, fill=1)
    c.setFillColor(BRASS)
    c.rect(M, sy - 100, 3, 34, stroke=0, fill=1)
    c.setFont("Body", 7.8)
    c.setFillColor(INK)
    c.drawString(M + 12, sy - 79, note)

    footer(c, page, 4, "Northstar OS  ·  launch plan  ·  sources: Green Wrap quote, Bright Data scan 5 Nov 2026")
    c.showPage()


# ---------------------------------------------------------------- summary

def summary(c: canvas.Canvas) -> None:
    bg(c, PAPER)
    c.setFillColor(INK)
    c.rect(0, H - 8, W, 8, stroke=0, fill=1)

    tracked(c, M, H - 76, "THE ORDER", 7.0, BRASS, 2.0)
    c.setFont("Display", 34)
    c.setFillColor(INK)
    c.drawString(M, H - 118, "One shipment. Two bets.")

    c.setFont("Body", 9.2)
    c.setFillColor(MUTED)
    c.drawString(M, H - 142, "Unpaper towels carry the entry risk — thin moat, high price, absorbs ad spend.")
    c.drawString(M, H - 158, "Beeswax wraps carry the ceiling — bigger category, proven seasonal velocity.")

    rule(c, M, H - 186, W - 2 * M, INK, 1.0)

    # table
    rows = [
        ("", "UNPAPER TOWELS", "BEESWAX WRAPS", "COMBINED"),
        ("Units", "300 sets", "200 sets", "500"),
        ("Retail", "$29.99", "$17.99", ""),
        ("Landed / unit", "$8.75", "$4.23", ""),
        ("Net / unit", "$12.59", "$6.56", "$10.18"),
        ("ROI", "144%", "155%", "147%"),
        ("Revenue if all sells", "$8,997", "$3,598", "$12,595"),
        ("Supplier payment", "$2,625", "$846", "$3,471"),
        ("Profit", "$3,777", "$1,312", "$5,089"),
    ]
    ty = H - 224
    colx = [M, M + 150, M + 300, M + 440]
    for r, row in enumerate(rows):
        if r == 0:
            for ci, cell in enumerate(row):
                tracked(c, colx[ci], ty, cell, 6.4, MUTED, 1.4)
            ty -= 12
            rule(c, M, ty, W - 2 * M, INK, 0.7)
            ty -= 18
            continue
        for ci, cell in enumerate(row):
            c.setFont("Display" if ci == 0 else "Body", 10.5 if ci == 0 else 9.2)
            c.setFillColor(INK if ci else MUTED)
            if ci == 0:
                c.setFont("Body", 8.2)
                c.setFillColor(MUTED)
                c.drawString(colx[ci], ty, cell)
            elif ci == 3:
                c.setFillColor(GOOD if r in (5, 8) else INK)
                c.drawRightString(W - M, ty, cell)
            else:
                c.drawString(colx[ci], ty, cell)
        ty -= 9
        rule(c, M, ty, W - 2 * M, RULE, 0.4)
        ty -= 15

    # order-by box
    by = ty - 26
    c.setFillColor(BONE)
    c.roundRect(M, by - 92, W - 2 * M, 92, 3, stroke=0, fill=1)
    c.setFillColor(CLAY)
    c.rect(M, by - 92, 4, 92, stroke=0, fill=1)

    tracked(c, M + 18, by - 22, "ORDER BY", 6.8, CLAY, 1.8)
    c.setFont("Display", 24)
    c.setFillColor(INK)
    c.drawString(M + 18, by - 50, "This week — 6 November")

    c.setFont("Body", 8.0)
    c.setFillColor(MUTED)
    c.drawString(M + 18, by - 68, "Factory gate 7 days + air freight 7 + customs 4 + FBA receiving 7 = sellable 1–10 December.")
    c.drawString(M + 18, by - 81, "Black Friday is 27 November. This shipment cannot reach it. It catches the 1–20 December gifting run instead.")

    # risk list
    ry = by - 128
    tracked(c, M, ry, "WHAT WOULD CHANGE THIS PLAN", 6.6, MUTED, 1.6)
    ry -= 20
    risks = [
        ("Unpaper COGS above $10", "The 24-pack stops working at $29.99. Stay in wraps instead."),
        ("Freight stays at $1.10/unit", "At 500 units combined it should fall toward $0.50 — confirm with Nico."),
        ("FBA receiving slips past 10 Dec", "Goods land after the gifting window. Hold for January."),
    ]
    for head, body in risks:
        c.setFillColor(BRASS)
        c.circle(M + 3, ry + 2.5, 2.2, stroke=0, fill=1)
        c.setFont("Body", 8.4)
        c.setFillColor(INK)
        c.drawString(M + 14, ry, head)
        c.setFont("Body", 7.8)
        c.setFillColor(MUTED)
        c.drawString(M + 14, ry - 11, body)
        ry -= 34

    footer(c, 4, 4, "Northstar OS  ·  launch plan  ·  sources: Green Wrap quote, Bright Data scan 5 Nov 2026")
    c.showPage()


def main() -> None:
    register()
    out = os.path.join(ROOT, "reports", "launch_plan_2skus_20261105.pdf")
    c = canvas.Canvas(out, pagesize=letter)
    c.setTitle("Q4 Launch Plan — Two SKUs")
    c.setAuthor("Northstar OS")

    cover(c)

    product_page(
        c, 2,
        index="01", title="Cotton Unpaper Towels", subtitle="24-pack  ·  double layer  ·  25 × 25 cm  ·  GOTS flannel",
        price=29.99, qty=300, landed=8.75, referral=4.50, fba=3.90, prep=0.25,
        net=12.59, roi="144%", revenue=8997, profit=3777, capital=2625,
        market=[
            ("3,450", "units / month", "category velocity, 15 listings"),
            ("700+", "leader velocity", "24-pack at $29.99"),
            ("1,784", "reviews to beat", "vs 10,817 on beeswax"),
        ],
        shipping=[
            ("DAY 0–7", "Factory gate", "production + QC"),
            ("DAY 7–14", "Air freight", "Henan → US"),
            ("DAY 14–18", "Customs", "duty ~25%"),
            ("DAY 18–25", "FBA receiving", "check-in + live"),
        ],
        sourcing="Green Wrap, Henan  ·  300 sets at $8.75 landed  ·  MOQ 100  ·  $2,625 to supplier",
        note="Thin moat is the whole case: 1,784 reviews ahead of you, not 10,817. At $29.99 the margin absorbs ad spend.",
    )

    product_page(
        c, 3,
        index="02", title="Beeswax Wraps", subtitle="Patterned 3-pack  ·  cotton + beeswax  ·  kraft sleeve",
        price=17.99, qty=200, landed=4.23, referral=2.70, fba=4.35, prep=0.15,
        net=6.56, roi="155%", revenue=3598, profit=1312, capital=846,
        market=[
            ("6,000", "units / month", "category velocity, 15 listings"),
            ("2,000+", "leader velocity", "Bee's Wrap roll at $21"),
            ("10,817", "reviews to beat", "dominant brand, hard shelf"),
        ],
        shipping=[
            ("DAY 0–7", "Factory gate", "production + QC"),
            ("DAY 7–14", "Air freight", "Henan → US"),
            ("DAY 14–18", "Customs", "duty ~25%"),
            ("DAY 18–25", "FBA receiving", "check-in + live"),
        ],
        sourcing="Green Wrap, Henan  ·  200 sets at $4.23 landed  ·  FOB $2.50 + $1.10 freight + $0.63 duty",
        note="Bigger category, harder shelf. Patterned is what lets you hold $17.99 — natural kraft fails at $15.99.",
    )

    summary(c)
    c.save()
    print("wrote", out, os.path.getsize(out), "bytes")


if __name__ == "__main__":
    main()
