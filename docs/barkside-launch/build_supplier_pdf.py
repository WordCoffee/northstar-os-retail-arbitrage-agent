"""Build the supplier-facing blend specification PDF.

Short and practical: one page per blend, ingredient amounts in the units a
blender works in (kg per 100 kg batch), plus % w/w and the per-pouch weight.

Formulation data is read from sodium_model.BLENDS so there is one source of
truth and this sheet cannot drift from the model.

Usage:  python docs/barkside-launch/build_supplier_pdf.py
"""

from __future__ import annotations

import sys
from pathlib import Path

from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    KeepTogether,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import sodium_model as sm  # noqa: E402

from build_pdf import (  # noqa: E402
    BODY,
    COPPER,
    CRIMSON,
    DISPLAY,
    GOLD,
    INK,
    MONO,
    MUTED,
    PAPER,
    RULE,
    TINT,
    register_fonts,
)

OUT = HERE / "BARKSIDE-supplier-blend-specs-20261112.pdf"

BATCH_KG = 100.0
POUCH_G = sm.POUCH_G

# presentation metadata only - formulation lives in sodium_model.py
META = {
    "COPPER": {
        "colour": COPPER,
        "use": "Brisket and pork butt",
        "grind": "Coarse. Black pepper cracked to 6-8 mesh; all other inputs through 20 mesh.",
        "allergens": "Mustard, celery (EU/UK Annex II). None of the US major allergens.",
        "note": "No sugar in this blend by design.",
    },
    "GOLD": {
        "colour": GOLD,
        "use": "Pulled pork and chicken",
        "grind": "40 mesh throughout.",
        "allergens": "Mustard, celery (EU/UK Annex II). None of the US major allergens.",
        "note": "Contains 8% coconut sugar.",
    },
    "CRIMSON": {
        "colour": CRIMSON,
        "use": "Steak, chicken and charred vegetables",
        "grind": "30-40 mesh.",
        "allergens": "None. No mustard, no celery, no US major allergens.",
        "note": "No sugar, no turmeric.",
    },
}


def styles() -> dict[str, ParagraphStyle]:
    return {
        "title": ParagraphStyle(
            "title", fontName=DISPLAY, fontSize=27, leading=31, textColor=INK,
            spaceAfter=2,
        ),
        "sub": ParagraphStyle(
            "sub", fontName=BODY, fontSize=9.6, leading=14, textColor=MUTED,
            spaceAfter=0,
        ),
        "body": ParagraphStyle(
            "body", fontName=BODY, fontSize=9.4, leading=13.4, textColor=INK,
            spaceAfter=6,
        ),
        "num": ParagraphStyle(
            "num", fontName=BODY, fontSize=9.4, leading=13.4, textColor=INK,
            spaceAfter=5, leftIndent=16, bulletIndent=2,
        ),
        "kicker": ParagraphStyle(
            "kicker", fontName=BODY, fontSize=7.4, leading=10, textColor=COPPER,
            spaceAfter=3,
        ),
        "h2": ParagraphStyle(
            "h2", fontName=DISPLAY, fontSize=19, leading=23, textColor=INK,
            spaceBefore=0, spaceAfter=1,
        ),
        "blenduse": ParagraphStyle(
            "blenduse", fontName=BODY, fontSize=9.4, leading=13, textColor=MUTED,
            spaceAfter=0,
        ),
        "cell": ParagraphStyle(
            "cell", fontName=BODY, fontSize=8.6, leading=11, textColor=INK,
            spaceAfter=0,
        ),
        "chead": ParagraphStyle(
            "chead", fontName=BODY, fontSize=7.6, leading=10, textColor=PAPER,
            spaceAfter=0,
        ),
        "small": ParagraphStyle(
            "small", fontName=BODY, fontSize=8.0, leading=11.6, textColor=MUTED,
            spaceAfter=3,
        ),
        "label": ParagraphStyle(
            "label", fontName=BODY, fontSize=7.2, leading=9.6, textColor=MUTED,
            spaceAfter=1,
        ),
    }


def pretty(name: str) -> str:
    return name[:1].upper() + name[1:]


def ingredient_table(key: str, st: dict, width: float) -> Table:
    f = sm.BLENDS[key]["formula"]
    rows = sorted(f.items(), key=lambda kv: -kv[1])

    data = [["Ingredient", "% w/w", f"kg per {BATCH_KG:.0f} kg", f"g per {POUCH_G:.0f} g pouch"]]
    for ing, pct in rows:
        data.append(
            [
                pretty(ing),
                f"{pct:.1f}",
                f"{pct * BATCH_KG / 100:.1f}",
                f"{pct * POUCH_G / 100:.1f}",
            ]
        )
    data.append(["Total", "100.0", f"{BATCH_KG:.1f}", f"{POUCH_G:.1f}"])

    body = [[Paragraph(c, st["chead"]) for c in data[0]]]
    for r in data[1:-1]:
        body.append([Paragraph(r[0], st["cell"])] + [Paragraph(c, st["cell"]) for c in r[1:]])
    body.append([Paragraph(f"<b>{r}</b>", st["cell"]) for r in data[-1]])

    widths = [width * 0.40, width * 0.14, width * 0.23, width * 0.23]
    t = Table(body, colWidths=widths, repeatRows=1, hAlign="LEFT")
    style = [
        ("BACKGROUND", (0, 0), (-1, 0), INK),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
        ("LEFTPADDING", (0, 0), (-1, -1), 7),
        ("RIGHTPADDING", (0, 0), (-1, -1), 7),
        ("TOPPADDING", (0, 0), (-1, -1), 4.2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4.2),
        ("LINEBELOW", (0, 1), (-1, -2), 0.35, RULE),
        ("LINEABOVE", (0, -1), (-1, -1), 1.0, INK),
        ("BACKGROUND", (0, -1), (-1, -1), TINT),
    ]
    for i in range(2, len(body) - 1, 2):
        style.append(("BACKGROUND", (0, i), (-1, i), HexColor("#FAF8F2")))
    t.setStyle(TableStyle(style))
    return t


def blend_page(key: str, st: dict, width: float) -> list:
    spec = sm.BLENDS[key]
    meta = META[key]
    salt = spec["formula"]["sea salt, coarse"]
    na = spec["formula"]
    sodium = sum(pct * sm.SODIUM[i] / 100.0 for i, pct in na.items())

    head = Table(
        [[
            Paragraph(
                f'<font color="#{meta["colour"].hexval()[2:]}">\u25a0</font>',
                ParagraphStyle("sq", fontName=BODY, fontSize=15, leading=18,
                               textColor=meta["colour"]),
            ),
            [
                Paragraph(f"BLEND {spec['no'].replace('No.', 'NO.')}", st["kicker"]),
                Paragraph(key, st["h2"]),
                Paragraph(meta["use"], st["blenduse"]),
            ],
        ]],
        colWidths=[0.34 * inch, width - 0.34 * inch],
    )
    head.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ]
        )
    )

    facts = Table(
        [[
            [Paragraph("TARGET SALT", st["label"]), Paragraph(f"{salt:.1f}% w/w", st["cell"])],
            [Paragraph("SODIUM", st["label"]), Paragraph(f"{sodium:,.0f} mg / 100 g", st["cell"])],
            [Paragraph("NET FILL", st["label"]), Paragraph(f"{POUCH_G:.0f} g pouch", st["cell"])],
            [Paragraph("BATCH", st["label"]), Paragraph(f"{BATCH_KG:.0f} kg", st["cell"])],
        ]],
        colWidths=[width / 4.0] * 4,
    )
    facts.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("BACKGROUND", (0, 0), (-1, -1), TINT),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 7),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
            ]
        )
    )

    tail = [
        Paragraph(f"<b>Grind.</b> {meta['grind']}", st["small"]),
        Paragraph(f"<b>Allergens.</b> {meta['allergens']}", st["small"]),
        Paragraph(f"<b>Note.</b> {meta['note']}", st["small"]),
    ]

    return [
        head,
        Spacer(1, 10),
        facts,
        Spacer(1, 12),
        ingredient_table(key, st, width),
        Spacer(1, 10),
        *tail,
    ]


def header_footer(canvas, doc):
    canvas.saveState()
    w, h = LETTER
    canvas.setFillColor(MUTED)
    canvas.setFont(BODY, 7.0)
    canvas.drawString(0.75 * inch, h - 0.62 * inch, "BARKSIDE BBQ Co.")
    canvas.drawRightString(
        w - 0.75 * inch, h - 0.62 * inch, "Blend specifications  \u00b7  12 November 2026"
    )
    canvas.setStrokeColor(RULE)
    canvas.setLineWidth(0.5)
    canvas.line(0.75 * inch, h - 0.69 * inch, w - 0.75 * inch, h - 0.69 * inch)

    canvas.setFillColor(MUTED)
    canvas.setFont(BODY, 7.0)
    canvas.drawCentredString(w / 2, 0.5 * inch, str(doc.page))
    canvas.setFillColor(COPPER)
    canvas.rect(0.75 * inch, 0.60 * inch, 0.42 * inch, 1.6, stroke=0, fill=1)
    canvas.setFillColor(MUTED)
    canvas.drawRightString(
        w - 0.75 * inch, 0.5 * inch, "Confidential \u2014 for supplier review"
    )
    canvas.restoreState()


def build(out: Path) -> None:
    register_fonts()
    st = styles()

    doc = BaseDocTemplate(
        str(out),
        pagesize=LETTER,
        leftMargin=0.75 * inch,
        rightMargin=0.75 * inch,
        topMargin=1.0 * inch,
        bottomMargin=0.9 * inch,
        title="BARKSIDE - blend specifications for supplier",
        author="Northstar OS",
    )
    frame = Frame(
        doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id="body",
        leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0,
    )
    doc.addPageTemplates([PageTemplate(id="main", frames=[frame], onPage=header_footer)])
    width = doc.width

    story: list = []
    story.append(Paragraph("BARKSIDE BBQ Co.", st["kicker"]))
    story.append(Paragraph("Blend specifications", st["title"]))
    story.append(Spacer(1, 4))
    story.append(Paragraph(
        "Three blends, 80 g net pouches. Amounts are given as kilograms per "
        f"{BATCH_KG:.0f} kg finished batch, with percentage and per-pouch weights "
        "for checking. Pilot order is 40 kg per blend.",
        st["body"],
    ))
    story.append(Spacer(1, 8))

    overview = [
        ["Blend", "Use", "Salt", "Allergens (EU/UK)"],
        ["No.1 COPPER", META["COPPER"]["use"], "13.0%", "mustard, celery"],
        ["No.2 GOLD", META["GOLD"]["use"], "12.0%", "mustard, celery"],
        ["No.3 CRIMSON", META["CRIMSON"]["use"], "11.0%", "none"],
    ]
    body = [[Paragraph(c, st["chead"]) for c in overview[0]]]
    for r in overview[1:]:
        body.append([Paragraph(r[0], st["cell"])] + [Paragraph(c, st["cell"]) for c in r[1:]])
    t = Table(
        body,
        colWidths=[width * 0.22, width * 0.40, width * 0.14, width * 0.24],
        hAlign="LEFT",
    )
    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), INK),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("ALIGN", (2, 0), (2, -1), "RIGHT"),
                ("LEFTPADDING", (0, 0), (-1, -1), 7),
                ("RIGHTPADDING", (0, 0), (-1, -1), 7),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ("LINEBELOW", (0, 1), (-1, -1), 0.35, RULE),
            ]
        )
    )
    story.append(t)

    story.append(Spacer(1, 22))
    story.append(Paragraph("What we need back", st["kicker"]))
    asks = [
        "Price per kg at 40 kg, 100 kg and 250 kg per blend, and the price per filled 80 g pouch.",
        "Minimum order per blend and minimum per ingredient.",
        "Lead time for samples and for first production.",
        "A lot-specific COA with each shipment: moisture, water activity, and micro.",
        "Confirmation that no input carries an undeclared carrier, anti-caking agent or added flavour.",
    ]
    for i, a in enumerate(asks, 1):
        story.append(Paragraph(a, st["num"], bulletText=f"{i}."))

    story.append(Spacer(1, 22))
    story.append(Paragraph("Quantities to quote", st["kicker"]))
    qty = [
        ["Tier", "Per blend", "Pouches", "Purpose"],
        ["Pilot", "40 kg", "500", "sample and taste test"],
        ["First run", "100 kg", "1,250", "launch stock"],
        ["Scale", "250 kg", "3,125", "reorder"],
    ]
    qbody = [[Paragraph(c, st["chead"]) for c in qty[0]]]
    for r in qty[1:]:
        qbody.append([Paragraph(r[0], st["cell"])] + [Paragraph(c, st["cell"]) for c in r[1:]])
    qt = Table(
        qbody,
        colWidths=[width * 0.18, width * 0.18, width * 0.16, width * 0.48],
        hAlign="LEFT",
    )
    qt.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), INK),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("ALIGN", (1, 0), (2, -1), "RIGHT"),
                ("LEFTPADDING", (0, 0), (-1, -1), 7),
                ("RIGHTPADDING", (0, 0), (-1, -1), 7),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ("LINEBELOW", (0, 1), (-1, -1), 0.35, RULE),
            ]
        )
    )
    story.append(qt)
    story.append(Spacer(1, 20))
    story.append(Paragraph("Packing", st["kicker"]))
    story.append(Paragraph(
        "80 g net in an opaque, foil-lined stand-up pouch with a resealable zip. "
        "No window: the colours are light-sensitive. Lot code and best-before "
        "inkjet on the seal. Dieline required before artwork.",
        st["body"],
    ))

    story.append(PageBreak())
    for i, key in enumerate(["COPPER", "GOLD", "CRIMSON"]):
        story.extend(blend_page(key, st, width))
        if i < 2:
            story.append(PageBreak())

    doc.build(story)


def main() -> int:
    build(OUT)
    print(f"wrote {OUT}  {OUT.stat().st_size:,} bytes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
