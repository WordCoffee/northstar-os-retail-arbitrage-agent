"""Build the Creative Pipeline v2 improvement report as a designed PDF.

Reads nothing at runtime except the evidence images under renders/ and the
numbers recorded in this session's commits/reports. Output:
reports/Creative_Pipeline_v2_Improvements_20261019.pdf

Usage: python tools/build_improvement_pdf.py
"""

from __future__ import annotations

import tempfile
from datetime import date
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    BaseDocTemplate, Frame, Image, KeepTogether, PageBreak, PageTemplate,
    Paragraph, Spacer, Table, TableStyle,
)

ROOT = Path(__file__).resolve().parents[1]
FONTS = ROOT / "Northstar_backend" / "assets" / "fonts"
OUT = ROOT / "reports" / "Creative_Pipeline_v2_Improvements_20261019.pdf"

# ── brand ───────────────────────────────────────────────────────────────────
PAPER = colors.HexColor("#F7F4EC")
BONE = colors.HexColor("#EFE9DC")
INK = colors.HexColor("#1F2A20")
PINE = colors.HexColor("#2F4434")
MUTED = colors.HexColor("#6B6F62")
GOLD = colors.HexColor("#C4A04A")
BLOCK = colors.HexColor("#A23B2A")
GREEN = colors.HexColor("#3E6B4A")
LINE = colors.HexColor("#D8D2C2")

pdfmetrics.registerFont(TTFont("Display", str(FONTS / "PlayfairDisplay.ttf")))
pdfmetrics.registerFont(TTFont("Body", str(FONTS / "Inter.ttf")))
pdfmetrics.registerFont(TTFont("Serif", str(FONTS / "CormorantGaramond.ttf")))

ss = getSampleStyleSheet()


def st(name, **kw) -> ParagraphStyle:
    base = dict(fontName="Body", fontSize=9.4, leading=13.6, textColor=INK,
                spaceAfter=5)
    base.update(kw)
    return ParagraphStyle(name, **base)


H1 = st("H1", fontName="Display", fontSize=24, leading=28, spaceAfter=6)
H2 = st("H2", fontName="Display", fontSize=15, leading=19, spaceBefore=10,
        spaceAfter=5, textColor=PINE)
H3 = st("H3", fontName="Body", fontSize=10.5, leading=14, spaceBefore=6,
        textColor=PINE)
LEAD = st("Lead", fontName="Serif", fontSize=12.5, leading=17, textColor=PINE)
BODY = st("Body")
SMALL = st("Small", fontSize=8.2, leading=11.2, textColor=MUTED)
CELL = st("Cell", fontSize=8.2, leading=10.8, spaceAfter=0)
CELLB = st("CellB", fontSize=8.2, leading=10.8, spaceAfter=0, textColor=colors.white)
EYEBROW = st("Eyebrow", fontSize=7.6, leading=9, textColor=GOLD)
BIG = st("Big", fontName="Display", fontSize=30, leading=32, textColor=PINE,
         alignment=TA_LEFT)
CAP = st("Cap", fontSize=7.8, leading=10.4, textColor=MUTED)


def p(text, style=BODY):
    return Paragraph(text, style)


def rule(width=170 * mm, color=LINE, thickness=0.7):
    t = Table([[""]], colWidths=[width], rowHeights=[0.1])
    t.setStyle(TableStyle([("LINEABOVE", (0, 0), (-1, -1), thickness, color)]))
    return t


def stat_tile(value, label, tint=BONE):
    return Table(
        [[Paragraph(value, st("v", fontName="Display", fontSize=17, leading=19,
                              textColor=PINE, alignment=1, spaceAfter=0))],
         [Paragraph(label, st("l", fontSize=7.4, leading=9, textColor=MUTED,
                              alignment=1, spaceAfter=0))]],
        colWidths=[38 * mm],
        style=TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), tint),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ]))


# ── page furniture ──────────────────────────────────────────────────────────

def _chrome(canvas, doc):
    canvas.saveState()
    canvas.setFillColor(PAPER)
    canvas.rect(0, 0, A4[0], A4[1], fill=1, stroke=0)
    # top hairline + eyebrow
    canvas.setStrokeColor(LINE)
    canvas.setLineWidth(0.6)
    canvas.line(20 * mm, A4[1] - 15 * mm, A4[0] - 20 * mm, A4[1] - 15 * mm)
    canvas.setFont("Body", 7.2)
    canvas.setFillColor(MUTED)
    canvas.drawString(20 * mm, A4[1] - 12.4 * mm,
                      "NORTHSTAR OS  ·  CREATIVE PIPELINE v2  ·  19 OCTOBER 2026")
    canvas.drawRightString(A4[0] - 20 * mm, A4[1] - 12.4 * mm,
                           f"Page {doc.page}")
    canvas.setFont("Body", 7.2)
    canvas.setFillColor(MUTED)
    canvas.drawString(20 * mm, 10 * mm,
                      "All work local. No paid provider called. Evidence committed in git.")
    canvas.drawRightString(A4[0] - 20 * mm, 10 * mm, "Northstar OS")
    canvas.restoreState()


def build() -> Path:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    doc = BaseDocTemplate(str(OUT), pagesize=A4,
                          leftMargin=20 * mm, rightMargin=20 * mm,
                          topMargin=22 * mm, bottomMargin=16 * mm,
                          title="Creative Pipeline v2 — Improvements",
                          author="Northstar OS")
    frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height,
                  id="main", leftPadding=0, rightPadding=0,
                  topPadding=0, bottomPadding=0)
    doc.addPageTemplates([PageTemplate(id="all", frames=[frame],
                                       onPage=_chrome)])
    story: list = []

    # ── cover ───────────────────────────────────────────────────────────────
    story.append(Spacer(1, 6 * mm))
    story.append(p("WHAT CHANGED AND WHY IT MATTERS", EYEBROW))
    story.append(Spacer(1, 2 * mm))
    story.append(p("Creative Pipeline v2", H1))
    story.append(p(
        "A local, frontier-grade image and packaging pipeline: what we built, "
        "what it now does better than before, and the evidence for every claim.",
        LEAD))
    story.append(Spacer(1, 5 * mm))

    tiles = Table([[
        stat_tile("47,323", "GitHub repos researched"),
        stat_tile("57,355", "sources in the local index"),
        stat_tile("3,928", "tests passing"),
        stat_tile("21", "commits, all local"),
    ]], colWidths=[42 * mm] * 4)
    tiles.setStyle(TableStyle([
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 2),
    ]))
    story.append(tiles)
    story.append(Spacer(1, 7 * mm))

    story.append(p("The one-paragraph version", H2))
    story.append(p(
        "We set out to compete with Packify.ai on image generation and on real, "
        "retail-ready packaging — entirely on this machine. The work fell into "
        "four buckets. <b>Research:</b> a wave of 57,700+ verified sources, now "
        "indexed and searchable inside the app. <b>Realism:</b> the mockup "
        "compositor gained the printed-on-surface recipe (displacement, "
        "soft-light, specular, grain, fold shadows, tonal match), which is what "
        "makes a label look printed rather than pasted. <b>Accuracy:</b> a "
        "Qwen edit lane, an OCR gate that blocks an edit which rewrites the copy, "
        "BiRefNet cutouts framed to Amazon MAIN rules, and a real ICC prepress "
        "chain with a gamut mapper that names the colour that will actually "
        "print. <b>Truth:</b> a single readiness verdict that ties those checks "
        "together, plus a doypack dieline and a calibration tool for the one "
        "question only a tape measure can answer.", BODY))
    story.append(rule())
    story.append(Spacer(1, 2 * mm))
    story.append(p(
        "Two honest caveats are on the last page: model upscaling is disabled "
        "after a measured crash, and four untracked files from an older session "
        "keep the project's own test runner red. Both are recorded, not hidden.",
        SMALL))
    story.append(PageBreak())

    # ── research ────────────────────────────────────────────────────────────
    story.append(p("1 · Research", H2))
    story.append(p(
        "The brief asked for at least 15,000 sources. We enumerated and "
        "metadata-verified roughly <b>57,700</b>. The distinction matters: "
        "<i>enumerated</i> means name, stars, licence, language and last activity "
        "were checked through the APIs; <i>read in substance</i> is a much smaller "
        "number and is reported separately. The 15,000 target is exceeded about "
        "3.8 times on the enumerated layer alone.", BODY))

    rows = [["Channel", "Verified", "How"],
            ["GitHub", "47,323 repos", "256 generated queries, up to 3 pages each"],
            ["Hugging Face", "9,513 assets", "5,152 model searches, 1,121 tag-filtered, 1,890 datasets, 1,350 spaces"],
            ["YouTube", "829 videos", "yt-dlp search enumeration; 339 caption files; 55 transcribed locally"],
            ["Web and docs", "~40 pages", "fetched and read this session"],
            ["Local corpus", "57,355 records", "GitHub 47,323 · HF 9,148 · YouTube 884"]]
    t = Table([[Paragraph(c, CELLB if i == 0 else CELL) for c in row] for i, row in enumerate(rows)],
              colWidths=[30 * mm, 32 * mm, 108 * mm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), PINE),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, BONE]),
        ("GRID", (0, 0), (-1, -1), 0.4, LINE),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(t)
    story.append(Spacer(1, 3 * mm))
    story.append(p(
        "<b>What the wave found that changed decisions.</b> The corpus/agent layer "
        "is the fastest-moving area (Firecrawl 192k stars, Crawl4AI 85k, MinerU "
        "82k). Doypack dieline generation has <i>no</i> open-source equivalent — "
        "every project found generates folding cartons — which confirmed that our "
        "custom generator stays. The free local prepress chain is real: littleCMS "
        "through Pillow, Ghostscript for CMYK, and Windows already ships a SWOP "
        "CMYK profile, so prepress needs no download. For realism, the canonical "
        "reference is the bcmi composition indexes plus the 2026 shadow and "
        "reflection work. Blender is <b>not</b> installed, so there is no 3D lane "
        "yet — recorded as a decision rather than assumed away.", BODY))
    story.append(p(
        "<b>A security finding, fixed.</b> Repo descriptions sometimes contain "
        "other people's sample tokens — a Discord bot token and a Ruby "
        "<font name='Body'>secret =&gt;</font> sample among them. Committing "
        "those into our research data would be careless, so a scrubber now "
        "redacts credential-shaped strings in place, keeps every row, reports "
        "per-rule counts, and runs inside the sweep before it writes.", SMALL))
    story.append(PageBreak())

    # ── before/after ────────────────────────────────────────────────────────
    story.append(p("2 · What improved, area by area", H2))
    story.append(p(
        "Each row is a working change with evidence behind it, not an intention.",
        BODY))
    ba = [
        ["Area", "Before", "Now"],
        ["Mockup realism",
         "Flat paste: one homography and a single 55% multiply. Read as a sticker.",
         "Displacement follows folds, soft-light takes the surface shading, specular "
         "sits over the ink, grain synced to the plate, fold shadows, tonal match. "
         "A/B: 7.1% of pixels changed at the print."],
        ["Editing a render",
         "No edit lane. Any change meant regenerating.",
         "Qwen-Image-Edit-2511 edits scene and light in 94.5 s — and an OCR gate "
         "compares the copy before and after. It caught the model rewriting "
         "6 oz as 8 oz, so that output can never ship silently."],
        ["Cutouts and listing images",
         "Manual cutout, no framing rules, no compliance check.",
         "BiRefNet cutout, automatic white-background framing, and a measurement "
         "pass: live result compliant at 2000 px, product fill 0.8795, "
         "background pure white."],
        ["Print readiness",
         "sRGB only. No idea what a press would do to the colours.",
         "Real ICC conversion, soft proof, CIE76 gamut shift and ink limit. Live: "
         "18.09% of the artwork moves more than 8 dE, and the gamut mapper names "
         "what the dark green actually prints as."],
        ["Packaging structure",
         "A draft doypack sketch with no seals or keep-outs.",
         "True-millimetre structure: top seal and zipper keep-out, both bottom "
         "seals, gusset centre crease, side welds, print-safe areas — plus a "
         "published-ladder proportion check that flags a wrong gusset."],
        ["The gusset question",
         "Open risk with no artefact.",
         "A calibration tool records a measured pouch against the spec: 148x205+78 "
         "vs 150x210+40 gives gusset +38 mm (+95%) and a gusset-mismatch verdict."],
        ["The final answer",
         "Separate checks, no single verdict.",
         "One readiness call across prepress, copy, MAIN and dieline — with "
         "blockers grouped and nothing reported as passed when it was not measured."],
    ]
    t = Table([[Paragraph(c, CELLB if i == 0 else CELL) for c in row]
               for i, row in enumerate(ba)],
              colWidths=[27 * mm, 55 * mm, 88 * mm], repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), PINE),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, BONE]),
        ("GRID", (0, 0), (-1, -1), 0.4, LINE),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(t)
    story.append(PageBreak())

    # ── evidence images ─────────────────────────────────────────────────────
    story.append(p("3 · See it", H2))
    story.append(p(
        "The two images below are real outputs from this session, committed in "
        "the repository. Left: the same mockup rendered flat and with the "
        "realism passes, cropped at 100%. Right: the finished listing image "
        "after cutout and MAIN framing.", BODY))

    crop = ROOT / "renders" / "ab_realism_crop.png"
    main_img = ROOT / "renders" / "smoke_main_2000.png"
    blocks = []
    if crop.is_file():
        small = _scaled(crop)
        blocks.append(Image(str(small), width=84 * mm,
                            height=84 * mm * (crop_image_ratio(small))))
    if main_img.is_file():
        blocks.append(Image(str(_scaled(main_img)), width=84 * mm, height=84 * mm))
    if blocks:
        row = Table([blocks], colWidths=[84 * mm] * len(blocks))
        row.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"),
                                 ("LEFTPADDING", (0, 0), (-1, -1), 0),
                                 ("RIGHTPADDING", (0, 0), (-1, -1), 2)]))
        story.append(row)
        caps = []
        if crop.is_file():
            caps.append(Paragraph("Flat paste (left) vs realism passes (right). "
                                  "Look at the fold shading crossing the type.", CAP))
        if main_img.is_file():
            caps.append(Paragraph("Cutout + MAIN framing: pure white, product "
                                  "fills the frame, copy intact.", CAP))
        c = Table([caps[:1]] if len(caps) == 1 else [caps[:2]],
                  colWidths=[84 * mm] * len(caps[:2]) if caps else [170 * mm])
        c.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"),
                               ("LEFTPADDING", (0, 0), (-1, -1), 0)]))
        story.append(c)
    else:
        story.append(p("Evidence images not found on disk in this checkout.", SMALL))
    story.append(Spacer(1, 4 * mm))

    story.append(p("The edit lane, and the gate that stops it lying", H3))
    story.append(p(
        "The edit lane changes the world around a product — background, light, "
        "contact shadow — and is genuinely good at it. It is also capable of "
        "re-drawing the label while it is there. In our live test it turned "
        "<font name='Body'>6 oz (170 g)</font> into "
        "<font name='Body'>(6 0/L) Z0 9</font> and "
        "<font name='Body'>8 oz (227 g)</font> into "
        "<font name='Body'>902 (227 g)</font>. That is exactly the failure that "
        "reaches a customer, so the pipeline now measures it: text is OCR'd on "
        "both sides of an edit, the token sets are diffed, and numeric drift is "
        "called out separately. The verdict was <b>drift_numeric</b> with "
        "<font name='Body'>preserves_copy = false</font>, which means the output "
        "is not shippable until the deterministic text layer is re-composed. "
        "Diffusion proposes; the compositor decides.", BODY))
    story.append(PageBreak())

    # ── the pipeline now ────────────────────────────────────────────────────
    story.append(p("4 · How the pipeline runs now", H2))
    steps = [
        ("1", "Generate", "Clean plate only — the model paints material and scene, never type."),
        ("2", "Edit (optional)", "Qwen changes light or scene. An OCR gate checks the copy did not move."),
        ("3", "Upscale", "Deterministic LANCZOS. Always before the text composite, never after."),
        ("4", "Compose type", "Real logo, real fonts, exact spelling, warped onto the surface with the realism passes."),
        ("5", "Cut out + frame", "BiRefNet alpha, trimmed and centred on white to fill the frame."),
        ("6", "Prepress", "ICC to CMYK, soft proof, gamut shift and ink limit — with a printable colour suggestion."),
        ("7", "Readiness", "One verdict across prepress, copy, MAIN and dieline. Blockers grouped."),
    ]
    flow = [[Paragraph(f"<font color='#C4A04A'><b>{n}</b></font>", CELL),
             Paragraph(f"<b>{name}</b>", CELL), Paragraph(desc, CELL)]
            for n, name, desc in steps]
    ft = Table(flow, colWidths=[8 * mm, 32 * mm, 130 * mm])
    ft.setStyle(TableStyle([
        ("ROWBACKGROUNDS", (0, 0), (-1, -1), [colors.white, BONE]),
        ("GRID", (0, 0), (-1, -1), 0.4, LINE),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(ft)
    story.append(Spacer(1, 5 * mm))
    story.append(p(
        "The order is the point. Generation is good at surfaces and hopeless at "
        "truth; the compositor is the reverse. Every step that could corrupt the "
        "copy happens <i>before</i> the copy is laid down, and the one step that "
        "could still touch it (the edit) is measured.", BODY))

    story.append(p("What the studio can call", H3))
    api = [
        ["Endpoint", "Does"],
        ["GET /api/design-studio/lanes/status", "Which lanes are usable, and why"],
        ["POST /api/design-studio/lanes/cutout", "BiRefNet cutout, MAIN framing and compliance"],
        ["POST /api/design-studio/lanes/upscale", "Deterministic upscale, no GPU"],
        ["POST /api/design-studio/lanes/main-check", "Measure any stored image against MAIN rules"],
        ["POST /api/design-studio/lanes/readiness", "One verdict across all four checks"],
        ["POST /api/design-studio/print/prepress/check", "ICC gamut, ink limit, CMYK + proof assets"],
        ["POST /api/design-studio/compose/mockup", "Deterministic type with a realism override"],
    ]
    at = Table([[Paragraph(c, CELLB if i == 0 else CELL) for c in row]
                for i, row in enumerate(api)],
               colWidths=[82 * mm, 88 * mm])
    at.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), PINE),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, BONE]),
        ("GRID", (0, 0), (-1, -1), 0.4, LINE),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(at)
    story.append(PageBreak())

    # ── numbers and tests ───────────────────────────────────────────────────
    story.append(p("5 · The numbers behind the claims", H2))
    ev = [
        ["Evidence", "Measured result"],
        ["Realism A/B (same plate, two renders)", "mean absolute change 2.65 · 99th percentile 78 · 7.14% of pixels changed by more than 8"],
        ["Edit lane", "8 steps in 94.5 s · scene changed correctly · copy drift detected and blocked"],
        ["Cutout to MAIN", "compliant at 2000×2000 · product fill 0.8795 · background white 1.0 · 21.9 s from cold"],
        ["Prepress on the real artwork", "profile RSWOP.icm · 18.09% of pixels shift more than 8 dE · max ink coverage 262%"],
        ["Gamut suggestion", "dark green #213800 prints as #38392E, a 26 dE shift to muddy olive"],
        ["Doypack dieline", "168 × 486 mm sheet · bleed 3 mm · 21 vector items · gusset flagged 40 mm vs the published 80 mm"],
        ["Pouch calibration", "148×205+78 measured · gusset +38 mm (+95%) · verdict spec_adjust"],
        ["Readiness on the real package", "needs_work · two real blockers, both actionable"],
    ]
    et = Table([[Paragraph(c, CELLB if i == 0 else CELL) for c in row]
                for i, row in enumerate(ev)],
               colWidths=[62 * mm, 108 * mm])
    et.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), PINE),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, BONE]),
        ("GRID", (0, 0), (-1, -1), 0.4, LINE),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(et)
    story.append(Spacer(1, 4 * mm))

    story.append(p("Tests", H3))
    story.append(p(
        "<b>3,928 passed, 65 skipped</b> on the tracked backend tree. The other "
        "four project suites are green: Golden Goose 511, SPA UI contract 1,122, "
        "Shell 307, Cloudflare Functions 31. The creative pipeline itself carries "
        "84 dedicated assertions.", BODY))
    story.append(p(
        "Two real defects were found by those tests and fixed: ComfyUI's "
        "RemoveBackground node returns the <i>background</i> mask, so our first "
        "cutouts kept the room and blanked the product; and an environment leak "
        "between tests made two reasoning tests fail only in a full run. Both are "
        "now covered.", SMALL))
    story.append(PageBreak())

    # ── decisions ───────────────────────────────────────────────────────────
    story.append(p("6 · Two decisions for you", H2))
    dec = [
        ["Decision", "Why it is yours", "What is already true"],
        ["Model upscaling",
         "RealESRGAN x4 aborted the ComfyUI process on a 1216 px input. Revisiting "
         "needs a careful tiled experiment and a restart budget.",
         "Deterministic LANCZOS replacement is in place and cannot crash. The "
         "incident is recorded in the state file."],
        ["Four untracked files",
         "Northstar_backend/costco_non_kirkland/ holds four files from 27 September "
         "that import symbols which do not exist. They make the project's own test "
         "runner report red. They may be your unfinished work, so they were not "
         "deleted.",
         "The tracked tree is green regardless. Finish, commit or remove them and "
         "the runner returns to green."],
    ]
    dt = Table([[Paragraph(c, CELLB if i == 0 else CELL) for c in row]
                for i, row in enumerate(dec)],
               colWidths=[28 * mm, 74 * mm, 68 * mm])
    dt.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), PINE),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, BONE]),
        ("GRID", (0, 0), (-1, -1), 0.4, LINE),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(dt)
    story.append(Spacer(1, 5 * mm))

    story.append(p("Try it in one command", H3))
    story.append(p(
        "<font name='Body'>python scripts/package_readiness_live.py</font>", BODY))
    story.append(p(
        "It runs the composed artwork, the framed listing image and a doypack "
        "dieline through every check and prints one verdict with grouped "
        "blockers. The operator guide at "
        "<font name='Body'>docs/CREATIVE_PIPELINE_V2_OPERATOR_GUIDE.md</font> "
        "lists every command, and each one in it was executed rather than merely "
        "written down.", SMALL))
    story.append(Spacer(1, 3 * mm))
    story.append(rule())
    story.append(Spacer(1, 2 * mm))
    story.append(p(
        "Full narrative: <font name='Body'>reports/creative_pipeline_v2_20261019.md</font>"
        "  ·  Research: <font name='Body'>research/research_wave2_20261019/REPORT.md</font>"
        "  ·  Evidence images: <font name='Body'>renders/</font>"
        "  ·  Every change is a local commit on feature/v4.1-mesh.", SMALL))

    doc.build(story)
    return OUT


def _scaled(path: Path, max_px: int = 900) -> Path:
    """Downscale an evidence image for embedding (keeps the PDF small)."""
    from PIL import Image as PILImage
    tmp_dir = Path(tempfile.mkdtemp(prefix="ns_pdf_"))
    out = tmp_dir / (path.stem + "_small.png")
    with PILImage.open(path) as im:
        im = im.convert("RGB")
        if max(im.size) > max_px:
            im.thumbnail((max_px, max_px), PILImage.LANCZOS)
        im.save(out, format="PNG", optimize=True)
    return out


def crop_image_ratio(path: Path) -> float:
    from PIL import Image as PILImage
    with PILImage.open(path) as im:
        w, h = im.size
    return h / float(w)


if __name__ == "__main__":
    out = build()
    size = out.stat().st_size
    print(f"OK {out} ({size/1024:.0f} KB)")
