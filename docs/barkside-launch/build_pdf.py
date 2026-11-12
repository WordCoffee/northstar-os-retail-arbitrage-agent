"""Build the BARKSIDE launch pack PDF from the markdown sources.

Offline, deterministic. Reads the five source docs plus the computed appendix,
renders them to a single typographic PDF with a cover, a contents page and
running header/footer.

Usage:  python docs/barkside-launch/build_pdf.py
"""

from __future__ import annotations

import re
import sys
from html.parser import HTMLParser
from pathlib import Path

import markdown
from reportlab.lib.colors import HexColor
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    BaseDocTemplate,
    Flowable,
    Frame,
    KeepTogether,
    NextPageTemplate,
    PageBreak,
    PageTemplate,
    Paragraph,
    Preformatted,
    Spacer,
    Table,
    TableStyle,
)
from reportlab.platypus.tableofcontents import TableOfContents

HERE = Path(__file__).resolve().parent
OUT = HERE / "BARKSIDE-launch-pack-20261112.pdf"

SOURCES = [
    ("1", "Brand & strategy", "README.md"),
    ("2", "Formulation", "formulas.md"),
    ("3", "Claims & labelling", "compliance.md"),
    ("4", "Unit economics", "economics.md"),
    ("5", "Supplier brief", "supplier_brief.md"),
    ("6", "Appendix \u2014 computed report", "sodium_report.md"),
]

# ------------------------------------------------------------------ palette
INK = HexColor("#1E2A23")
MUTED = HexColor("#6B6A63")
RULE = HexColor("#D8D2C6")
PAPER = HexColor("#FBF9F4")
TINT = HexColor("#F7F3E9")
COPPER = HexColor("#B4642A")
GOLD = HexColor("#B08A2E")
CRIMSON = HexColor("#8C2F2A")

# ------------------------------------------------------------------- fonts
FONTS = {
    "Georgia": ("georgia.ttf", "georgiab.ttf", "georgiai.ttf", "georgiaz.ttf"),
    "SegoeUI": ("segoeui.ttf", "segoeuib.ttf", "segoeuii.ttf", "segoeuiz.ttf"),
    "Consolas": ("consola.ttf", "consolab.ttf", "consolai.ttf", "consolaz.ttf"),
}
FONT_DIR = Path("C:/Windows/Fonts")
BODY = "SegoeUI"
DISPLAY = "Georgia"
MONO = "Consolas"

_DOC = None


def register_fonts() -> None:
    for family, files in FONTS.items():
        paths = [FONT_DIR / f for f in files]
        if not all(p.exists() for p in paths):
            continue
        names = {
            0: family,
            1: f"{family}-Bold",
            2: f"{family}-Italic",
            3: f"{family}-BoldItalic",
        }
        for idx, path in enumerate(paths):
            pdfmetrics.registerFont(TTFont(names[idx], str(path)))
        pdfmetrics.registerFontFamily(
            family,
            normal=names[0],
            bold=names[1],
            italic=names[2],
            boldItalic=names[3],
        )


# ------------------------------------------------------------------ styles
def build_styles() -> dict[str, ParagraphStyle]:
    s: dict[str, ParagraphStyle] = {}
    s["body"] = ParagraphStyle(
        "body", fontName=BODY, fontSize=9.3, leading=12.9, textColor=INK,
        spaceAfter=4.6, alignment=TA_LEFT,
    )
    s["kicker"] = ParagraphStyle(
        "kicker", fontName=BODY, fontSize=7.4, leading=10, textColor=COPPER,
        spaceBefore=0, spaceAfter=2,
    )
    s["h1"] = ParagraphStyle(
        "h1", fontName=DISPLAY, fontSize=21, leading=25, textColor=INK,
        spaceBefore=4, spaceAfter=10,
    )
    s["h2"] = ParagraphStyle(
        "h2", fontName=DISPLAY, fontSize=12.4, leading=15.4, textColor=INK,
        spaceBefore=11, spaceAfter=3, keepWithNext=1,
    )
    s["h3"] = ParagraphStyle(
        "h3", fontName=BODY, fontSize=9.6, leading=12.8, textColor=COPPER,
        spaceBefore=9, spaceAfter=2.5, keepWithNext=1,
    )
    s["bullet"] = ParagraphStyle(
        "bullet", parent=s["body"], leftIndent=13, bulletIndent=3, spaceAfter=2.6,
    )
    s["quotep"] = ParagraphStyle(
        "quotep", parent=s["body"], spaceAfter=3, textColor=INK,
    )
    s["cell"] = ParagraphStyle(
        "cell", fontName=BODY, fontSize=7.9, leading=10.3, textColor=INK,
        spaceAfter=0, spaceBefore=0,
    )
    s["chead"] = ParagraphStyle(
        "chead", fontName=BODY, fontSize=7.3, leading=9.4, textColor=PAPER,
        spaceAfter=0,
    )
    s["code"] = ParagraphStyle(
        "code", fontName=MONO, fontSize=7.5, leading=10.2,
        textColor=HexColor("#43372C"),
    )
    return s


# --------------------------------------------------------------- html parse
class Node:
    __slots__ = ("tag", "attrs", "children")

    def __init__(self, tag: str, attrs=None):
        self.tag = tag
        self.attrs = dict(attrs or [])
        self.children: list = []


class TreeBuilder(HTMLParser):
    VOID = {"br", "hr", "img", "meta", "link"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.root = Node("root")
        self.stack = [self.root]

    def handle_starttag(self, tag, attrs):
        node = Node(tag, attrs)
        self.stack[-1].children.append(node)
        if tag not in self.VOID:
            self.stack.append(node)

    def handle_startendtag(self, tag, attrs):
        self.stack[-1].children.append(Node(tag, attrs))

    def handle_endtag(self, tag):
        for i in range(len(self.stack) - 1, 0, -1):
            if self.stack[i].tag == tag:
                del self.stack[i:]
                return

    def handle_data(self, data):
        if data:
            self.stack[-1].children.append(data)


def md_to_tree(text: str) -> Node:
    html = markdown.Markdown(
        extensions=["tables", "fenced_code", "sane_lists"]
    ).convert(text)
    tb = TreeBuilder()
    tb.feed(html)
    tb.close()
    return tb.root


def esc(t: str) -> str:
    return t.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def inline(node) -> str:
    out: list[str] = []
    for ch in node.children:
        if isinstance(ch, str):
            out.append(esc(ch))
            continue
        tag = ch.tag
        if tag in ("strong", "b"):
            out.append("<b>" + inline(ch) + "</b>")
        elif tag in ("em", "i"):
            out.append("<i>" + inline(ch) + "</i>")
        elif tag == "code":
            out.append(
                f'<font face="{MONO}" size="7.6" color="#6B4A2F">'
                + inline(ch)
                + "</font>"
            )
        elif tag == "br":
            out.append("<br/>")
        else:
            out.append(inline(ch))
    return "".join(out)


def plain(node) -> str:
    return "".join(
        ch if isinstance(ch, str) else plain(ch) for ch in node.children
    )


def looks_numeric(cells: list[str]) -> bool:
    hits = 0
    total = 0
    for c in cells:
        c = c.strip()
        if not c:
            continue
        total += 1
        if re.search(r"[\d%$£€]", c) and len(c) <= 18:
            hits += 1
    return total > 0 and hits / total >= 0.7


class Rule(Flowable):
    def __init__(self, width: float, thickness=0.7, color=RULE, space=5):
        super().__init__()
        self.width = width
        self.thickness = thickness
        self.color = color
        self.space = space

    def wrap(self, aw, ah):
        return (self.width, self.space)

    def draw(self):
        self.canv.setStrokeColor(self.color)
        self.canv.setLineWidth(self.thickness)
        self.canv.line(0, self.space / 2, self.width, self.space / 2)


class SectionMarker(Flowable):
    """Registers a contents entry for the current page."""

    def __init__(self, text: str):
        super().__init__()
        self.text = text
        self.width = 0
        self.height = 0

    def wrap(self, aw, ah):
        return (0, 0)

    def draw(self):
        if _DOC is not None:
            _DOC.notify("TOCEntry", (0, self.text, self.canv.getPageNumber()))


# ------------------------------------------------------------- block render
def render_children(node, styles, width) -> list:
    out: list = []
    for ch in node.children:
        if isinstance(ch, str):
            if ch.strip():
                out.append(Paragraph(esc(ch.strip()), styles["body"]))
            continue
        out.extend(render_block(ch, styles, width))
    return out


def render_block(node, styles, width) -> list:
    tag = node.tag

    if tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
        level = int(tag[1])
        key = {1: "h1", 2: "h2"}.get(level, "h3")
        p = Paragraph(inline(node), styles[key])
        if level == 1:
            return [SectionMarker(plain(node)), p]
        if level == 2:
            return [p, Rule(width, 0.5, RULE, 5)]
        return [p]

    if tag == "p":
        txt = inline(node).strip()
        return [Paragraph(txt, styles["body"])] if txt else []

    if tag == "blockquote":
        parts = []
        for ch in node.children:
            if isinstance(ch, str):
                if ch.strip():
                    parts.append(Paragraph(esc(ch.strip()), styles["quotep"]))
            else:
                parts.append(Paragraph(inline(ch), styles["quotep"]))
        if not parts:
            return []
        box = Table([[parts]], colWidths=[width])
        box.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), TINT),
                    ("LEFTPADDING", (0, 0), (-1, -1), 10),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                    ("TOPPADDING", (0, 0), (-1, -1), 7),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
                    ("LINEBEFORE", (0, 0), (0, -1), 2.4, COPPER),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ]
            )
        )
        return [Spacer(1, 3), box, Spacer(1, 9)]

    if tag in ("ul", "ol"):
        items = []
        n = 0
        for ch in node.children:
            if isinstance(ch, str) or ch.tag != "li":
                continue
            n += 1
            bullet = "\u2022" if tag == "ul" else f"{n}."
            items.append(Paragraph(inline(ch), styles["bullet"], bulletText=bullet))
        return items + [Spacer(1, 3)]

    if tag == "pre":
        code = plain(node).rstrip("\n")
        pre = Preformatted(code, styles["code"])
        box = Table([[pre]], colWidths=[width])
        box.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), HexColor("#F6F2E8")),
                    ("LEFTPADDING", (0, 0), (-1, -1), 9),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 9),
                    ("TOPPADDING", (0, 0), (-1, -1), 6),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                    ("LINEBEFORE", (0, 0), (0, -1), 2.4, COPPER),
                ]
            )
        )
        return [Spacer(1, 2), box, Spacer(1, 7)]

    if tag == "hr":
        return [Rule(width, 0.5, RULE, 8)]

    if tag == "table":
        tbl, nrows = render_table(node, styles, width)
        if nrows <= 5:
            return [KeepTogether([tbl, Spacer(1, 10)])]
        return [tbl, Spacer(1, 10)]

    if tag in ("div", "section"):
        return render_children(node, styles, width)

    return render_children(node, styles, width)


def render_table(node, styles, width) -> tuple[Table, int]:
    rows: list[list[Node]] = []
    header: list[Node] | None = None

    def walk(n):
        nonlocal header
        for ch in n.children:
            if isinstance(ch, str):
                continue
            if ch.tag == "thead":
                for tr in ch.children:
                    if isinstance(tr, Node) and tr.tag == "tr":
                        header = [c for c in tr.children if isinstance(c, Node)]
            elif ch.tag == "tbody":
                walk(ch)
            elif ch.tag == "tr":
                cells = [c for c in ch.children if isinstance(c, Node)]
                if cells and cells[0].tag == "th":
                    header = cells
                else:
                    rows.append(cells)

    walk(node)

    ncols = 0
    for r in ([header] if header else []) + rows:
        ncols = max(ncols, len(r))
    if ncols == 0:
        return Table([[""]]), 1

    def pad(r):
        r = list(r)
        while len(r) < ncols:
            r.append(Node("td"))
        return r

    if header:
        header = pad(header)
    rows = [pad(r) for r in rows]

    weights = []
    for c in range(ncols):
        lens = [len(plain(r[c])) for r in rows]
        if header:
            lens.append(len(plain(header[c])))
        w = max(lens) if lens else 6
        weights.append(max(4.0, min(46.0, w ** 0.82)))
    total = sum(weights)
    widths = [width * w / total for w in weights]

    data = []
    if header:
        data.append([Paragraph(inline(c), styles["chead"]) for c in header])
    for r in rows:
        data.append([Paragraph(inline(c), styles["cell"]) for c in r])

    numeric = [looks_numeric([plain(r[c]) for r in rows]) for c in range(ncols)]

    t = Table(data, colWidths=widths, repeatRows=1 if header else 0, hAlign="LEFT")
    style = [
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4.5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4.5),
        ("TOPPADDING", (0, 0), (-1, -1), 3.0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3.0),
        ("LINEBELOW", (0, 0), (-1, -1), 0.35, RULE),
        ("LINEBELOW", (0, -1), (-1, -1), 0.9, HexColor("#B9B2A4")),
    ]
    if header:
        style += [
            ("BACKGROUND", (0, 0), (-1, 0), INK),
            ("LINEBELOW", (0, 0), (-1, 0), 0.9, INK),
        ]
    for c in range(ncols):
        if numeric[c]:
            style.append(("ALIGN", (c, 1 if header else 0), (c, -1), "RIGHT"))
    t.setStyle(TableStyle(style))
    return t, len(data)


# --------------------------------------------------------------- page decor
def make_header_footer(canvas, doc):
    canvas.saveState()
    w, h = LETTER
    if doc.page > 1:
        canvas.setFillColor(MUTED)
        canvas.setFont(BODY, 7.0)
        canvas.drawString(0.72 * inch, h - 0.55 * inch, "BARKSIDE BBQ Co.")
        canvas.drawRightString(
            w - 0.72 * inch, h - 0.55 * inch, "Launch pack  \u00b7  12 November 2026"
        )
        canvas.setStrokeColor(RULE)
        canvas.setLineWidth(0.5)
        canvas.line(0.72 * inch, h - 0.62 * inch, w - 0.72 * inch, h - 0.62 * inch)

        canvas.setFillColor(MUTED)
        canvas.setFont(BODY, 7.0)
        canvas.drawCentredString(w / 2, 0.45 * inch, str(doc.page))

        canvas.setFillColor(COPPER)
        canvas.rect(0.72 * inch, 0.545 * inch, 0.42 * inch, 1.6, stroke=0, fill=1)
    canvas.restoreState()


def draw_cover(canvas, doc):
    w, h = LETTER
    canvas.saveState()
    canvas.setFillColor(PAPER)
    canvas.rect(0, 0, w, h, stroke=0, fill=1)

    canvas.setFillColor(INK)
    canvas.rect(0, h - 0.42 * inch, w, 0.42 * inch, stroke=0, fill=1)

    left = 0.9 * inch
    canvas.setFillColor(COPPER)
    canvas.setFont(BODY, 8.0)
    canvas.drawString(left, h - 1.9 * inch, "P R O D U C T   L A U N C H   P A C K")

    canvas.setFillColor(INK)
    canvas.setFont(DISPLAY, 62)
    canvas.drawString(left, h - 2.88 * inch, "BARKSIDE")
    canvas.setFont(DISPLAY, 24)
    canvas.setFillColor(HexColor("#3A453C"))
    canvas.drawString(left, h - 3.24 * inch, "BBQ Co.")

    canvas.setStrokeColor(INK)
    canvas.setLineWidth(1.6)
    canvas.line(left, h - 3.5 * inch, w - left, h - 3.5 * inch)

    canvas.setFillColor(INK)
    canvas.setFont(DISPLAY, 15)
    canvas.drawString(left, h - 3.9 * inch, "Three low-sodium blends. 80 g pouches.")
    canvas.setFillColor(HexColor("#3A453C"))
    canvas.drawString(left, h - 4.18 * inch, "The bark is the point.")

    chips = [
        (COPPER, "No.1 COPPER", "Brisket + pork butt"),
        (GOLD, "No.2 GOLD", "Pulled pork + chicken"),
        (CRIMSON, "No.3 CRIMSON", "Steak + chicken + veg"),
    ]
    y = h - 5.2 * inch
    x = left
    for col, name, use in chips:
        canvas.setFillColor(col)
        canvas.rect(x, y, 0.34 * inch, 0.34 * inch, stroke=0, fill=1)
        canvas.setFillColor(INK)
        canvas.setFont(BODY, 8.4)
        canvas.drawString(x + 0.48 * inch, y + 0.20 * inch, name)
        canvas.setFillColor(MUTED)
        canvas.setFont(BODY, 7.6)
        canvas.drawString(x + 0.48 * inch, y + 0.05 * inch, use)
        x += 2.32 * inch

    canvas.setStrokeColor(RULE)
    canvas.setLineWidth(0.5)
    canvas.line(left, 1.62 * inch, w - left, 1.62 * inch)
    canvas.setFillColor(MUTED)
    canvas.setFont(BODY, 7.2)
    canvas.drawString(left, 1.34 * inch, "Prepared 12 November 2026  \u00b7  Northstar OS")
    canvas.drawString(
        left, 1.16 * inch,
        "Confidential \u2014 internal and supplier use. Formulation values are model output until a lab panel confirms them.",
    )
    canvas.setFillColor(INK)
    canvas.drawRightString(w - left, 1.34 * inch, "6 sections  \u00b7  3 SKUs  \u00b7  80 g")
    canvas.restoreState()


def build_toc() -> TableOfContents:
    toc = TableOfContents()
    toc.levelStyles = [
        ParagraphStyle(
            "toc0", fontName=BODY, fontSize=9.8, leading=21, textColor=INK,
            leftIndent=0, firstLineIndent=0, spaceBefore=0, spaceAfter=0,
        )
    ]
    toc.dotsMinLevel = 0
    return toc


def build(out: Path) -> None:
    global _DOC
    register_fonts()
    styles = build_styles()
    width = LETTER[0] - 1.44 * inch

    doc = BaseDocTemplate(
        str(out),
        pagesize=LETTER,
        leftMargin=0.72 * inch,
        rightMargin=0.72 * inch,
        topMargin=0.95 * inch,
        bottomMargin=0.85 * inch,
        title="BARKSIDE BBQ Co. - launch pack",
        author="Northstar OS",
        subject="Three low-sodium BBQ blends, 80 g pouches",
    )
    cover_frame = Frame(
        doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id="cover"
    )
    body_frame = Frame(
        doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id="body"
    )
    doc.addPageTemplates(
        [
            PageTemplate(id="cover", frames=[cover_frame], onPage=draw_cover),
            PageTemplate(id="main", frames=[body_frame], onPage=make_header_footer),
        ]
    )
    _DOC = doc

    story: list = [NextPageTemplate("main"), PageBreak()]

    story.append(Paragraph("Contents", styles["h1"]))
    story.append(Rule(width, 1.2, INK, 6))
    story.append(Spacer(1, 14))
    story.append(build_toc())
    story.append(Spacer(1, 24))
    story.append(Paragraph(
        "Brand platform, gram-level formulas, the claims position for both the US and "
        "UK/EU, the 80 g unit economics, and a supplier brief that can be sent under NDA. "
        f"Every sodium figure is computed by <font face='{MONO}' size='7.8'>sodium_model.py</font> "
        "and reproduced in the appendix.",
        styles["body"],
    ))
    story.append(PageBreak())

    for num, title, name in SOURCES:
        text = (HERE / name).read_text(encoding="utf-8").lstrip("\ufeff")
        tree = md_to_tree(text)
        story.append(Paragraph(f"SECTION {num}", styles["kicker"]))
        first_h1 = True
        for ch in tree.children:
            if isinstance(ch, str):
                continue
            if first_h1 and ch.tag == "h1":
                first_h1 = False
                story.append(SectionMarker(title))
                story.append(Paragraph(title, styles["h1"]))
                story.append(Rule(width, 1.2, INK, 8))
                story.append(Spacer(1, 8))
                continue
            story.extend(render_block(ch, styles, width))
        if name != SOURCES[-1][2]:
            story.append(PageBreak())

    doc.multiBuild(story)


def main() -> int:
    if not (FONT_DIR / "georgia.ttf").exists():
        print("warning: Georgia missing, falling back to base-14 fonts", file=sys.stderr)
    build(OUT)
    print(f"wrote {OUT}  {OUT.stat().st_size:,} bytes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
