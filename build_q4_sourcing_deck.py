#!/usr/bin/env python3
"""Q4 Sourcing Director Brief -> presentation PDF (sourcing guide + path).

Single source of truth: reports/q4_sourcing_director_brief_20261104.md
Every figure, verdict and warning below is transcribed from that brief.
Output: reports/Q4_Sourcing_Guide_and_Path_20261104.pdf
"""
from reportlab.lib.pagesizes import landscape, letter
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT
from reportlab.platypus import (BaseDocTemplate, PageTemplate, Frame, Paragraph,
                                Spacer, Table, TableStyle, PageBreak,
                                NextPageTemplate, KeepTogether)
from reportlab.graphics.shapes import Drawing, Rect, String, Line

OUT = 'reports/Q4_Sourcing_Guide_and_Path_20261104.pdf'

# ---------- palette (house: paper / pine / kraft) ----------
INK    = colors.HexColor('#171717')
FOREST = colors.HexColor('#253628')
PAPER  = colors.HexColor('#FBF7F0')
KRAFT  = colors.HexColor('#D5A77A')
OLIVE  = colors.HexColor('#9DBA8B')
SAGE   = colors.HexColor('#9FA9A4')
CREAM  = colors.HexColor('#D0C5AC')
COFFEE = colors.HexColor('#6B4A32')
CLAY   = colors.HexColor('#A85B48')
AMBER  = colors.HexColor('#A2762F')
GREEN  = colors.HexColor('#2F6B3A')
WHITE  = colors.white
MUTED  = colors.HexColor('#6B6B63')
RULE   = colors.HexColor('#E3DACA')
TINT   = colors.HexColor('#F4EFE5')

PAGE = landscape(letter)
LM = RM = 0.5 * inch
TM = 0.62 * inch
BM = 0.55 * inch
USABLE = PAGE[0] - LM - RM


def S(name, **kw):
    base = dict(fontName='Helvetica', fontSize=9.8, leading=13.2, textColor=INK)
    base.update(kw)
    return ParagraphStyle(name, **base)


st_kick    = S('k', fontName='Helvetica-Bold', fontSize=8.5, leading=11, textColor=KRAFT)
st_ctitle  = S('ct', fontName='Times-Bold', fontSize=43, leading=48, textColor=WHITE)
st_csub    = S('cs', fontName='Helvetica', fontSize=11.5, leading=17,
               textColor=colors.HexColor('#D8D2C6'))
st_h1      = S('h1', fontName='Times-Bold', fontSize=28, leading=33, textColor=FOREST)
st_h2      = S('h2', fontName='Helvetica-Bold', fontSize=10.2, leading=14,
               textColor=FOREST, spaceBefore=3)
st_body    = S('b', fontSize=10.1, leading=15.2)
st_body_s  = S('bs', fontSize=9.1, leading=13.4)
st_note    = S('n', fontSize=8.5, leading=12.2, textColor=MUTED)
st_cell    = S('c', fontSize=8.5, leading=11.0)
st_cell_b  = S('cb', fontName='Helvetica-Bold', fontSize=8.5, leading=11.0)
st_cell_r  = S('cr', fontSize=8.5, leading=11.0, alignment=TA_RIGHT)
st_cell_c  = S('cc', fontSize=8.5, leading=11.0, alignment=TA_CENTER)
st_th      = S('th', fontName='Helvetica-Bold', fontSize=7.7, leading=9.8, textColor=WHITE)
st_th_c    = S('thc', fontName='Helvetica-Bold', fontSize=7.7, leading=9.8,
               textColor=WHITE, alignment=TA_CENTER)
st_th_r    = S('thr', fontName='Helvetica-Bold', fontSize=7.7, leading=9.8,
               textColor=WHITE, alignment=TA_RIGHT)
st_tile_n  = S('tn', fontName='Times-Bold', fontSize=28, leading=31, textColor=FOREST)
st_tile_l  = S('tl', fontName='Helvetica-Bold', fontSize=7, leading=9.4, textColor=MUTED)
st_quote   = S('q', fontName='Times-Italic', fontSize=13, leading=19, textColor=FOREST)


def hexc(c):
    return '#%02X%02X%02X' % (int(c.red * 255), int(c.green * 255), int(c.blue * 255))


# ---------- page furniture ----------
def bg(canv, doc):
    canv.saveState()
    canv.setFillColor(PAPER)
    canv.rect(0, 0, PAGE[0], PAGE[1], stroke=0, fill=1)
    canv.restoreState()


def chrome(canv, doc, section):
    canv.saveState()
    canv.setFillColor(SAGE)
    canv.setFont('Helvetica-Bold', 7)
    canv.drawString(LM, PAGE[1] - 0.34 * inch, 'NORTHSTAR OS')
    canv.setFillColor(CREAM)
    canv.drawString(LM + 0.86 * inch, PAGE[1] - 0.34 * inch, '/')
    canv.setFillColor(COFFEE)
    canv.drawString(LM + 0.96 * inch, PAGE[1] - 0.34 * inch, 'SOURCING')
    canv.setFillColor(SAGE)
    canv.setFont('Helvetica', 7)
    canv.drawRightString(PAGE[0] - RM, PAGE[1] - 0.34 * inch, section)
    canv.setStrokeColor(RULE)
    canv.setLineWidth(0.6)
    canv.line(LM, PAGE[1] - 0.42 * inch, PAGE[0] - RM, PAGE[1] - 0.42 * inch)
    canv.line(LM, BM - 0.10 * inch, PAGE[0] - RM, BM - 0.10 * inch)
    canv.setFillColor(SAGE)
    canv.setFont('Helvetica', 6.8)
    canv.drawString(LM, BM - 0.26 * inch,
                    'Q4 Sourcing Guide & Path  \u00b7  Word Coffee \u00b7 Mogro Organics \u00b7 4 November 2026')
    canv.drawRightString(PAGE[0] - RM, BM - 0.26 * inch, '%02d' % doc.page)
    canv.restoreState()


def cover_bg(canv, doc):
    canv.saveState()
    canv.setFillColor(FOREST)
    canv.rect(0, 0, PAGE[0], PAGE[1], stroke=0, fill=1)
    canv.setFillColor(KRAFT)
    canv.rect(0, 0, 0.13 * inch, PAGE[1], stroke=0, fill=1)
    canv.setFillColor(colors.HexColor('#2E4231'))
    canv.setFont('Times-Italic', 150)
    canv.drawRightString(PAGE[0] - 0.40 * inch, PAGE[1] - 2.30 * inch, 'Q4')
    canv.restoreState()


def P(t, s=st_body):
    return Paragraph(t, s)


# ---------- components ----------
def kpi(items, height_pad=10):
    n = len(items)
    gap = 0.12 * inch
    w = (USABLE - gap * (n - 1)) / n
    row, style = [], [('VALIGN', (0, 0), (-1, -1), 'TOP'),
                      ('LEFTPADDING', (0, 0), (-1, -1), 10),
                      ('RIGHTPADDING', (0, 0), (-1, -1), 8),
                      ('TOPPADDING', (0, 0), (-1, -1), height_pad),
                      ('BOTTOMPADDING', (0, 0), (-1, -1), height_pad)]
    for i, (val, label, col) in enumerate(items):
        row.append([Paragraph(val, ParagraphStyle('q%d' % i, fontName='Times-Bold',
                                                  fontSize=27, leading=30, textColor=col)),
                    Paragraph(label.upper(), st_tile_l)])
        style += [('BACKGROUND', (i, 0), (i, 0), WHITE),
                  ('BOX', (i, 0), (i, 0), 0.6, RULE),
                  ('LINEABOVE', (i, 0), (i, 0), 2.4, col)]
    t = Table([row], colWidths=[w] * n)
    t.setStyle(TableStyle(style))
    t.hAlign = 'LEFT'
    return t


def data_table(rows, widths, head, brand=FOREST, aligns=None, dense=False, pad=None):
    """rows: list of list of flowables. widths in inches (pre-scaled)."""
    hs = {'l': st_th, 'c': st_th_c, 'r': st_th_r}
    aligns = aligns or ['c', 'l', 'l', 'r', 'r', 'r', 'r', 'l']
    hdr = [Paragraph(h, hs[aligns[i] if i < len(aligns) else 'l']) for i, h in enumerate(head)]
    body = [hdr] + rows
    t = Table(body, colWidths=widths, repeatRows=1)
    pad = pad if pad is not None else (3.2 if dense else 5.6)
    style = [('BACKGROUND', (0, 0), (-1, 0), brand),
             ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
             ('LEFTPADDING', (0, 0), (-1, -1), 5),
             ('RIGHTPADDING', (0, 0), (-1, -1), 5),
             ('TOPPADDING', (0, 0), (-1, -1), pad),
             ('BOTTOMPADDING', (0, 0), (-1, -1), pad),
             ('LINEBELOW', (0, 0), (-1, -1), 0.35, RULE)]
    for r in range(1, len(body)):
        if r % 2 == 0:
            style.append(('BACKGROUND', (0, r), (-1, r), TINT))
    t.setStyle(TableStyle(style))
    t.hAlign = 'LEFT'
    return t


def callout(text, accent=AMBER, width=None, bgc=WHITE, size=st_body_s):
    t = Table([[Paragraph(text, size)]], colWidths=[width or USABLE])
    t.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, -1), bgc),
                           ('LINEBEFORE', (0, 0), (0, 0), 3.0, accent),
                           ('LEFTPADDING', (0, 0), (-1, -1), 13),
                           ('RIGHTPADDING', (0, 0), (-1, -1), 13),
                           ('TOPPADDING', (0, 0), (-1, -1), 10),
                           ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
                           ('BOX', (0, 0), (-1, -1), 0.5, RULE)]))
    t.hAlign = 'LEFT'
    return t


def tag(label, col):
    """Small status chip."""
    return Paragraph('<font color="%s"><b>%s</b></font>' % (hexc(col), label), st_cell_c)


def net_bar(v, maxv, w=0.85 * inch, h=7.0, col=FOREST):
    d = Drawing(w, h)
    d.add(Rect(0, 0, w, h, fillColor=colors.HexColor('#EDE6D8'), strokeColor=None))
    frac = max(0.0, min(1.0, v / maxv))
    d.add(Rect(0, 0, max(1.2, w * frac), h, fillColor=col, strokeColor=None))
    return d


def gantt(rows, width, height, ticks):
    """rows: [(label, start_frac, end_frac, colour)] ; ticks: [(frac, label)]."""
    d = Drawing(width, height)
    label_w = 1.50 * inch
    track_w = width - label_w - 0.10 * inch
    row_h = 0.215 * inch
    top = height - 0.30 * inch
    for i, (label, s, e, col) in enumerate(rows):
        y = top - (i + 1) * row_h
        d.add(String(0, y + 5, label, fontName='Helvetica', fontSize=7.8, fillColor=INK))
        d.add(Rect(label_w, y, track_w, 0.125 * inch,
                   fillColor=colors.HexColor('#EDE6D8'), strokeColor=None))
        d.add(Rect(label_w + track_w * s, y, max(2.0, track_w * (e - s)), 0.125 * inch,
                   fillColor=col, strokeColor=None))
    for frac, lab in ticks:
        x = label_w + track_w * frac
        anchor = 'start' if frac <= 0.02 else ('end' if frac >= 0.98 else 'middle')
        d.add(String(x, height - 0.17 * inch, lab, fontName='Helvetica-Bold', fontSize=6.6,
                     fillColor=MUTED, textAnchor=anchor))
        d.add(Line(x, 0, x, height - 0.22 * inch, strokeColor=RULE, strokeWidth=0.5))
    return d


def text_strip(items, width=USABLE, accent=FOREST, bgc=WHITE):
    """items: [(headline, body)] rendered as equal tiles with a top rule."""
    n = len(items)
    w = width / float(n)
    cells = []
    for head, body in items:
        cells.append([Paragraph(head, ParagraphStyle('ts', fontName='Times-Bold', fontSize=15,
                                                     leading=18, textColor=accent)),
                      Spacer(1, 0.06 * inch),
                      Paragraph(body, st_body_s)])
    t = Table([cells], colWidths=[w] * n)
    t.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'TOP'),
                           ('LEFTPADDING', (0, 0), (-1, -1), 11),
                           ('RIGHTPADDING', (0, 0), (-1, -1), 11),
                           ('TOPPADDING', (0, 0), (-1, -1), 11),
                           ('BOTTOMPADDING', (0, 0), (-1, -1), 11),
                           ('BACKGROUND', (0, 0), (-1, -1), bgc),
                           ('LINEABOVE', (0, 0), (-1, 0), 2.4, accent),
                           ('INNERGRID', (0, 0), (-1, -1), 0.4, RULE),
                           ('BOX', (0, 0), (-1, -1), 0.4, RULE)]))
    t.hAlign = 'LEFT'
    return t


def hbar_rows(rows, width, maxv, fmt='$%.2f'):
    """rows: [(label, value, colour)] -> label | bar | value table."""
    label_w, val_w = 2.45 * inch, 1.05 * inch
    bar_w = width - label_w - val_w
    body = []
    for label, val, col in rows:
        body.append([Paragraph(label, st_cell),
                     net_bar(val, maxv, bar_w, 9.0, col),
                     Paragraph(fmt % val, st_cell_r)])
    t = Table(body, colWidths=[label_w, bar_w, val_w])
    t.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                           ('LEFTPADDING', (0, 0), (-1, -1), 0),
                           ('RIGHTPADDING', (0, 0), (-1, -1), 8),
                           ('TOPPADDING', (0, 0), (-1, -1), 3.4),
                           ('BOTTOMPADDING', (0, 0), (-1, -1), 3.4)]))
    t.hAlign = 'LEFT'
    return t


def swatch_legend(items, width):
    cells, widths = [], []
    for label, col in items:
        cells += [Paragraph('', st_cell), Paragraph(label, st_cell)]
        widths += [0.11 * inch, width / len(items) - 0.11 * inch]
    t = Table([cells], colWidths=widths)
    style = [('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
             ('LEFTPADDING', (0, 0), (-1, -1), 0),
             ('RIGHTPADDING', (0, 0), (-1, -1), 6),
             ('TOPPADDING', (0, 0), (-1, -1), 1),
             ('BOTTOMPADDING', (0, 0), (-1, -1), 1)]
    for i, (label, col) in enumerate(items):
        style.append(('BACKGROUND', (i * 2, 0), (i * 2, 0), col))
    t.setStyle(TableStyle(style))
    return t


def price_ladder(width, height, rows, top=19.99):
    """rows: [(headline, [(label, amt, colour)...], total)]"""
    d = Drawing(width, height)
    n = len(rows)
    slot = width / float(n)
    bar_w = min(1.05 * inch, slot * 0.52)
    base_y = 0.46 * inch
    usable_h = height - base_y - 0.22 * inch
    for i, (headline, segs, total) in enumerate(rows):
        cx = slot * (i + 0.5)
        x = cx - bar_w / 2.0
        y = base_y
        d.add(String(cx, height - 0.14 * inch, headline, fontName='Helvetica-Bold',
                     fontSize=8.4, fillColor=FOREST, textAnchor='middle'))
        for label, amt, col in segs:
            h = usable_h * (amt / top)
            d.add(Rect(x, y, bar_w, h, fillColor=col, strokeColor=WHITE, strokeWidth=0.8))
            if h > 0.17 * inch and amt >= 0.4:
                d.add(String(cx, y + h / 2 - 3.0, '$%.2f' % amt,
                             fontName='Helvetica-Bold', fontSize=7.2,
                             fillColor=WHITE, textAnchor='middle'))
            y += h
        d.add(String(cx, base_y - 0.20 * inch, '$%.2f retail' % total,
                     fontName='Helvetica', fontSize=7.6, fillColor=MUTED, textAnchor='middle'))
    return d


def phase_card(num, title, when, bullets, accent, width, gate=''):
    inner = [Paragraph('<font color="%s">%s</font>' % (hexc(accent), num),
                       ParagraphStyle('pn%s' % num, fontName='Times-Bold', fontSize=19,
                                      leading=21)),
             Spacer(1, 0.03 * inch),
             Paragraph(title, ParagraphStyle('pt%s' % num, fontName='Helvetica-Bold',
                                             fontSize=9.4, leading=12.4, textColor=FOREST)),
             Paragraph('<font color="%s">%s</font>' % (hexc(MUTED), when),
                       ParagraphStyle('pw%s' % num, fontName='Helvetica-Oblique',
                                      fontSize=7.2, leading=9.6)),
             Spacer(1, 0.06 * inch)]
    for b in bullets:
        inner.append(Paragraph('\u2022&nbsp;' + b,
                               ParagraphStyle('pb%s' % num, fontName='Helvetica', fontSize=7.5,
                                              leading=10.6, textColor=INK, spaceAfter=2.4)))
    if gate:
        inner.append(Spacer(1, 0.05 * inch))
        inner.append(Paragraph('<font color="%s">GATE</font>&nbsp; %s' % (hexc(accent), gate),
                               ParagraphStyle('pg%s' % num, fontName='Helvetica-Bold',
                                              fontSize=7.0, leading=9.6, textColor=MUTED)))
    t = Table([[inner]], colWidths=[width])
    t.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, -1), WHITE),
                           ('BOX', (0, 0), (-1, -1), 0.5, RULE),
                           ('LINEABOVE', (0, 0), (-1, 0), 3.0, accent),
                           ('LEFTPADDING', (0, 0), (-1, -1), 10),
                           ('RIGHTPADDING', (0, 0), (-1, -1), 10),
                           ('TOPPADDING', (0, 0), (-1, -1), 9),
                           ('BOTTOMPADDING', (0, 0), (-1, -1), 9),
                           ('VALIGN', (0, 0), (-1, -1), 'TOP')]))
    return t


# =====================================================================
# DATA  (verbatim from q4_sourcing_director_brief_20261104.md)
# =====================================================================

SECTION_A = [
    ('A1', 'Motivational Postcard Set, 20', 'StationeryHQ, CA', 5.00, 19.99, 7.54, 154,
     'Top Etsy gift sub-category'),
    ('A2', 'Quote Cards + Display Stand, 52-ct', 'StationeryHQ, CA', 6.00, 19.99, 6.24, 83,
     'Decks at $24.99 hold 186\u2013671 reviews'),
    ('A3', 'Bookmark Set, 4-pack', 'StationeryHQ, CA', 2.50, 14.99, 6.04, 208,
     'Cheapest add-on; stacks carts'),
    ('A4', 'Minimalist Desk Calendar', 'PrintPPS, NM', 5.08, 17.99, 5.76, 89,
     'Ships in 1 business day \u00b7 MOQ 1'),
    ('A5', 'Daily Planner Notepad / Desk Pad', 'StationeryHQ, CA', 6.50, 19.99, 5.74, 67,
     'One listing shows 19.7k sales'),
]

B1_SUPPLIERS = [
    ('Green Wrap (Henan)', 'China', '~$2.50 FOB \u00b7 $4.23 landed', '100 sets',
     'ONLY VIABLE', GREEN),
    ('Sunella Co.', 'USA (Faire)', '$7.99', '20 sets, $100 min', 'REJECT \u00b7 47% ratio', CLAY),
    ('Bee Kind Wraps', 'Canada', '40\u201350% of resale', '700 sets / pattern',
     'REJECT \u00b7 8\u201313 wk', CLAY),
    ('SWEDEdishcloths', 'N. America', 'Quote', 'None', 'DISHCLOTHS, NOT WRAPS', AMBER),
]

B1_LANDED = [('FOB', 2.50), ('Air freight (~15 kg)', 1.10), ('Duty (~25%)', 0.63)]

B1_ECON = [
    ('Patterned 3-pack', 17.99, 6.56, '155%', 'WINS', GREEN),
    ('Natural / kraft 3-pack', 15.99, 4.86, '\u2014', 'BELOW FLOOR', CLAY),
    ('Multi-pack (5)', 24.99, 9.80, '155%', 'CLEARS', GREEN),
]

SECTION_B2 = [
    ('B1', 'Beeswax Wraps, patterned 3-pack', 'Green Wrap, CN', '4.23 landed', 17.99, 6.56, 155),
    ('B2', 'Natural Sea Sponge, bath', 'SeaSationals, FL', '4.50', 18.99, 7.09, 148),
    ('B3', 'Loofah Facial Disks, 10-pack', 'SeaSationals, FL', '2.20', 14.99, 6.34, 274),
    ('B4', 'Swedish Dishcloths, 2-pack', 'Lollygag / SWEDEdishcloths', '6.50', 19.99, 6.24, 83),
    ('B5', 'Beeswax Wraps, 5-pack', 'Green Wrap, CN', '~6.30 landed', 24.99, 9.80, 155),
]

SECTION_C = [
    (1, 'Beeswax candle-making kit', 19.99, 5.00, 7.24, '25%'),
    (2, 'Cable management box', 19.99, 4.50, 7.74, '23%'),
    (3, 'Packing cubes, 3-pc', 19.99, 4.50, 7.74, '23%'),
    (4, 'Cloth coffee filter (reusable)', 16.99, 3.00, 6.94, '18%'),
    (5, 'Desk cable management tray', 17.99, 4.00, 6.79, '22%'),
    (6, 'Wooden coaster set, 4-pc', 17.99, 4.00, 6.54, '22%'),
    (7, 'Silicone spatula set, 3-pc', 16.99, 3.50, 6.44, '21%'),
    (8, 'Gel pen set, 6-pc', 16.99, 3.50, 6.44, '21%'),
    (9, 'Adjustable phone stand', 16.99, 3.50, 6.44, '21%'),
    (10, 'Tea infuser, stainless ball', 14.99, 2.00, 6.44, '13%'),
    (11, 'Cork phone grip', 14.99, 2.00, 6.44, '13%'),
    (12, 'Aesthetic pen holder', 16.99, 3.50, 6.44, '21%'),
    (13, 'Reusable produce bags, 5-pk', 17.99, 4.50, 6.29, '25%'),
    (14, 'Cable organizer clips, 10-pk', 14.99, 2.00, 6.24, '13%'),
    (15, 'Acrylic bookmark set', 14.99, 2.00, 6.24, '13%'),
    (16, 'Self-watering plant spikes, 12-pk', 14.99, 2.00, 6.24, '13%'),
    (17, 'Washi tape set, 10 rolls', 15.99, 3.00, 6.09, '19%'),
    (18, 'Silicone stretch lids, 6-pk', 15.99, 3.00, 6.09, '19%'),
    (19, 'Magnetic fridge list pad', 15.99, 3.00, 6.09, '19%'),
    (21, 'Aesthetic car diffuser (hanging)', 14.99, 2.50, 5.74, '17%'),
    (22, 'Sticky note set, layered', 14.99, 2.50, 5.74, '17%'),
    (23, 'GOTS cotton tote', 19.99, 6.50, 5.74, '33%'),
]

PRINTER = [
    ('Avery / OnlineLabels 6-up sheet', '~$0.45'),
    ('Per label', '$0.075'),
    ('Ink (XL colour, ~$0.08/page \u00f7 6)', '$0.013'),
    ('Total per label', '~$0.09'),
    ('Print time, 50 sheets @ 2 min', '~100 minutes'),
]

PRINTER_OPTIONS = [
    ('Thermal \u2014 Rollo X1040 / Zebra ZD220', '$180\u2013$250', '~$0.02',
     'BUY THIS FIRST', GREEN),
    ('Epson EcoTank ET-2850', '$250\u2013$300', '~$0.02 colour',
     'ONLY ABOVE 1,000 UNITS', AMBER),
    ('Brother colour laser', '$250\u2013$350', '$0.15\u2013$0.25',
     'REJECT \u2014 TONER KILLS MARGIN', CLAY),
    ('Outsourced roll labels', '\u2014', '$0.06\u2013$0.10',
     'BEST ABOVE 500 UNITS', GREEN),
]

BUDGET = [
    ('Wholesale, 200 \u00d7 $6.00 (postcards)', '$1,200', False),
    ('Labels, 200 \u00d7 $0.09', '$18', False),
    ('Thermal printer', '$200', False),
    ('Inbound freight to FBA (2 lanes)', '$250', False),
    ('Contingency 15%', '$250', False),
    ('TOTAL', '$1,918', True),
]

W = {}


def build():
    doc = BaseDocTemplate(OUT, pagesize=PAGE, leftMargin=LM, rightMargin=RM,
                          topMargin=TM, bottomMargin=BM,
                          title='Q4 Sourcing Guide & Path \u2014 Word Coffee, Mogro Organics, Non-Brand, Printers',
                          author='Northstar OS',
                          subject='Sourcing guide and execution path, Q4 2026')
    frame = Frame(LM, BM, USABLE, PAGE[1] - TM - BM, id='b',
                  leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
    doc.addPageTemplates([
        PageTemplate(id='cover', frames=[frame], onPage=cover_bg),
        PageTemplate(id='main', frames=[frame], onPage=lambda c, d: (bg(c, d), chrome(c, d, 'THE ARITHMETIC'))),
        PageTemplate(id='word', frames=[frame], onPage=lambda c, d: (bg(c, d), chrome(c, d, 'SECTION A \u00b7 WORD COFFEE'))),
        PageTemplate(id='mogro', frames=[frame], onPage=lambda c, d: (bg(c, d), chrome(c, d, 'SECTION B \u00b7 MOGRO ORGANICS'))),
        PageTemplate(id='nonbrand', frames=[frame], onPage=lambda c, d: (bg(c, d), chrome(c, d, 'SECTION C \u00b7 NON-BRAND'))),
        PageTemplate(id='print', frames=[frame], onPage=lambda c, d: (bg(c, d), chrome(c, d, 'SECTION D \u00b7 PRINTER ECONOMICS'))),
        PageTemplate(id='plan', frames=[frame], onPage=lambda c, d: (bg(c, d), chrome(c, d, 'THE PATH'))),
    ])

    F = []

    # ================= 01 COVER =================
    F.append(Spacer(1, 1.05 * inch))
    F.append(P('Q4 SOURCING DIRECTOR BRIEF  \u00b7  SOURCING GUIDE &amp; PATH  \u00b7  4 NOVEMBER 2026', st_kick))
    F.append(Spacer(1, 0.16 * inch))
    F.append(P('Where the<br/>money actually is', st_ctitle))
    F.append(Spacer(1, 0.20 * inch))
    F.append(P('Word Coffee \u00b7 Mogro Organics \u00b7 non-brand catalog \u00b7 printer economics. '
               'Thirty SKUs modelled against one formula, five supplier decisions, and the '
               'sequence to ship the first test.', st_csub))
    F.append(Spacer(1, 0.34 * inch))
    chips = Table([[
        P('<font color="#D5A77A"><b>$7.54</b></font> best paper net', st_csub),
        P('<font color="#D5A77A"><b>$9.80</b></font> best net overall', st_csub),
        P('<font color="#9DBA8B"><b>274%</b></font> best ROI (B3)', st_csub),
        P('<font color="#9DBA8B"><b>$1,918</b></font> first test, all-in', st_csub),
    ]], colWidths=[USABLE / 4.0] * 4)
    chips.setStyle(TableStyle([('LEFTPADDING', (0, 0), (-1, -1), 0),
                               ('TOPPADDING', (0, 0), (-1, -1), 0)]))
    F.append(chips)
    F.append(Spacer(1, 2.55 * inch))
    meta = Table([[
        P('<font color="#7E8C7E">SOURCE</font>&nbsp;&nbsp; q4_sourcing_director_brief_20261104.md', st_kick),
        P('<font color="#7E8C7E">MODEL</font>&nbsp;&nbsp; Net = Retail \u2013 WS \u2013 15% \u2013 FBA \u2013 $0.40', st_kick),
        P('<font color="#7E8C7E">SCOPE</font>&nbsp;&nbsp; turnkey only \u00b7 zero gating', st_kick),
    ]], colWidths=[USABLE / 3.0] * 3)
    meta.setStyle(TableStyle([('LEFTPADDING', (0, 0), (-1, -1), 0),
                              ('TOPPADDING', (0, 0), (-1, -1), 10),
                              ('LINEABOVE', (0, 0), (-1, 0), 0.6, colors.HexColor('#3A4C3C'))]))
    F.append(meta)
    F.append(NextPageTemplate('main'))
    F.append(PageBreak())

    # ================= 02 THE ARITHMETIC =================
    F.append(P('One formula decides every row', st_h1))
    F.append(Spacer(1, 0.05 * inch))
    F.append(P('Nothing in this deck is a hunch about demand. Every SKU is filtered by the same '
               'arithmetic, and the arithmetic is what kills most of them.', st_body))
    F.append(Spacer(1, 0.14 * inch))

    formula = Table([[P('Net = Retail \u2013 Wholesale \u2013 (0.15 \u00d7 Retail) \u2013 FBA fee \u2013 $0.40',
                        ParagraphStyle('f', fontName='Times-Bold', fontSize=15, leading=20,
                                       textColor=WHITE))]],
                    colWidths=[USABLE])
    formula.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, -1), FOREST),
                                 ('LEFTPADDING', (0, 0), (-1, -1), 16),
                                 ('TOPPADDING', (0, 0), (-1, -1), 13),
                                 ('BOTTOMPADDING', (0, 0), (-1, -1), 13)]))
    F.append(formula)
    F.append(Spacer(1, 0.05 * inch))
    F.append(P('The $0.40 is fixed overhead: $0.15 label/prep + $0.25 inbound freight. '
               'Referral is 15% of retail, so it rises with price \u2014 the fixed costs do not.', st_note))
    F.append(Spacer(1, 0.20 * inch))

    ladder_rows = [
        ('$19.99', [('Wholesale', 7.49, OLIVE), ('Referral', 3.00, AMBER),
                    ('FBA', 4.10, COFFEE), ('Prep', 0.40, CREAM), ('Net', 5.00, FOREST)], 19.99),
        ('$16.99', [('Wholesale', 4.94, OLIVE), ('Referral', 2.55, AMBER),
                    ('FBA', 4.10, COFFEE), ('Prep', 0.40, CREAM), ('Net', 5.00, FOREST)], 16.99),
        ('$14.99', [('Wholesale', 3.94, OLIVE), ('Referral', 2.25, AMBER),
                    ('FBA', 3.40, COFFEE), ('Prep', 0.40, CREAM), ('Net', 5.00, FOREST)], 14.99),
    ]
    left = [price_ladder(5.15 * inch, 3.05 * inch, ladder_rows)]
    left.append(Spacer(1, 0.06 * inch))
    left.append(swatch_legend([('Wholesale', OLIVE), ('Referral 15%', AMBER),
                               ('FBA fee', COFFEE), ('Prep + freight', CREAM),
                               ('Net profit', FOREST)], 5.15 * inch))
    left.append(Spacer(1, 0.05 * inch))
    left.append(P('Bars are full retail price. The FBA block is whatever remains after '
                  'wholesale, referral, prep and a $5 net \u2014 the fee ceiling a product must fit.',
                  st_note))

    right = [P('What you can afford to pay', st_h2)]
    cap_rows = [
        ['Retail', 'WS for $5 net', 'WS for $7 net'],
        ['$19.99', '$7.49', '$5.49'],
        ['$16.99', '$4.94', '$2.94'],
        ['$14.99', '$3.94', '$1.94'],
    ]
    body = [[P(cap_rows[0][0], st_th), P(cap_rows[0][1], st_th_r), P(cap_rows[0][2], st_th_r)]]
    for r in cap_rows[1:]:
        body.append([P('<b>%s</b>' % r[0], st_cell_b), P(r[1], st_cell_r), P(r[2], st_cell_r)])
    t = Table(body, colWidths=[0.95 * inch, 1.15 * inch, 1.15 * inch])
    t.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, 0), COFFEE),
                           ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                           ('LEFTPADDING', (0, 0), (-1, -1), 7),
                           ('RIGHTPADDING', (0, 0), (-1, -1), 7),
                           ('TOPPADDING', (0, 0), (-1, -1), 6),
                           ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
                           ('LINEBELOW', (0, 0), (-1, -1), 0.35, RULE),
                           ('BACKGROUND', (0, 2), (-1, 2), TINT)]))
    right.append(t)
    right.append(Spacer(1, 0.16 * inch))
    right.append(callout('At <b>$19.99</b> you can afford <b>$7.49</b> wholesale. '
                         'At <b>$16.99</b>, only <b>$4.94</b>. At <b>$14.99</b>, <b>$3.94</b>. '
                         'That is why almost every viable row prices at $16.99\u2013$19.99, '
                         'not $14.99.', accent=KRAFT, width=3.55 * inch, bgc=colors.HexColor('#F7F2E7')))
    right.append(Spacer(1, 0.14 * inch))
    right.append(P('<b>Model assumptions:</b> 15% referral \u00b7 label/prep $0.15 \u00b7 '
                   'inbound freight $0.25 \u00b7 MOQ up to 500 \u00b7 test 100\u2013300 units. '
                   'Turnkey only \u2014 no gating, no custom tooling.', st_note))

    combo = Table([[left, right]], colWidths=[USABLE * 0.56, USABLE * 0.44])
    combo.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'TOP'),
                               ('LEFTPADDING', (0, 0), (-1, -1), 0),
                               ('RIGHTPADDING', (0, 0), (0, 0), 0.34 * inch),
                               ('RIGHTPADDING', (1, 0), (1, 0), 0)]))
    F.append(combo)
    F.append(Spacer(1, 0.26 * inch))
    F.append(text_strip([
        ('Rule 1 \u00b7 price band',
         'Price at <b>$16.99\u2013$19.99</b>. At $14.99 the wholesale ceiling is $3.94, and almost '
         'nothing real sits under it.'),
        ('Rule 2 \u00b7 cost ratio',
         'Wholesale comes out of net dollar-for-dollar \u2014 nothing downstream absorbs it. At '
         '$19.99, $1.00 more wholesale is $1.00 less profit.'),
        ('Rule 3 \u00b7 honest ceiling',
         '<b>$6\u2013$8 net</b> is the real band. $10+ needs $24.99 retail or wholesale under '
         '$2.00 \u2014 not a better supplier.'),
    ]))

    # ================= 03 SECTION A =================
    F.append(NextPageTemplate('word'))
    F.append(PageBreak())
    F.append(P('Word Coffee \u2014 five paper goods', st_h1))
    F.append(Spacer(1, 0.03 * inch))
    F.append(P('Every row is turnkey: stock product, our label, no tooling. Best net $7.54 \u00b7 '
               'average $6.26 \u00b7 all five clear the floor.', st_body))
    F.append(Spacer(1, 0.16 * inch))

    rows = []
    for code, name, sup, ws, ret, net, roi, note in SECTION_A:
        rows.append([
            P('<b>%s</b>' % code, st_cell_c),
            P(name, st_cell_b),
            P(sup, st_cell),
            P('$%.2f' % ws, st_cell_r),
            P('$%.2f' % ret, st_cell_r),
            P('<b>$%.2f</b>' % net, st_cell_r),
            P('%d%%' % roi, st_cell_r),
            P(note, st_cell),
        ])
    CW_A = [0.42 * inch, 2.30 * inch, 1.30 * inch, 0.78 * inch, 0.72 * inch,
            0.72 * inch, 0.60 * inch, 2.30 * inch]
    scale = USABLE / sum(CW_A)
    F.append(data_table(rows, [w * scale for w in CW_A],
                        ['#', 'Product', 'Supplier', 'WS', 'Retail', 'Net', 'ROI',
                         'Market validation'],
                        brand=COFFEE, aligns=['c', 'l', 'l', 'r', 'r', 'r', 'r', 'l'], pad=9.5))
    F.append(Spacer(1, 0.20 * inch))

    pick = [P('Best of the five \u2014 A1 Postcards', st_h2),
            Spacer(1, 0.04 * inch),
            P('$7.54 net at $19.99. Lowest cost ratio in the set (25%), lightest shipping, '
              'and postcard/quote packs are an established Etsy gift category with '
              '<b>no dominant brand</b>.', st_body_s)]
    a2 = [P('The A2 price trap', st_h2),
          Spacer(1, 0.04 * inch),
          P('The 52-card deck is the only paper SKU where competitors hold <b>under 700 '
            'reviews</b> \u2014 but at $19.99 it nets $6.24, not the $10.24 quoted at $24.99. '
            '<b>The price band you set changes the answer.</b>', st_body_s)]
    pair = Table([[pick, a2]], colWidths=[USABLE * 0.5, USABLE * 0.5])
    pair.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'TOP'),
                              ('LEFTPADDING', (0, 0), (-1, -1), 0),
                              ('RIGHTPADDING', (0, 0), (0, 0), 0.40 * inch),
                              ('RIGHTPADDING', (1, 0), (1, 0), 0)]))
    F.append(pair)
    F.append(Spacer(1, 0.95 * inch))
    F.append(text_strip([
        ('A1 \u00b7 the launch pick',
         '<b>$7.54 net</b> \u00b7 154% ROI \u00b7 25% cost ratio. Lowest cost ratio, lightest '
         'shipping, no dominant brand in the category.'),
        ('A3 \u00b7 the best ROI',
         '<b>208%</b> on a $2.50 bookmark set at $14.99. Cheapest add-on in the catalog and the '
         'one that stacks carts.'),
        ('A4 \u00b7 the fastest ship',
         '<b>1 business day</b> from PrintPPS at MOQ 1. The only row in Section A that can move '
         'without a lead-time argument.'),
    ]))

    # ================= 04 B1 SUPPLIER =================
    F.append(NextPageTemplate('mogro'))
    F.append(PageBreak())
    F.append(P('Beeswax wraps \u2014 the supplier decision', st_h1))
    F.append(Spacer(1, 0.03 * inch))
    F.append(P('Four suppliers were costed. Only one survives the arithmetic, and it survives '
               'because it is the only one priced in the Far East at volume.', st_body))
    F.append(Spacer(1, 0.16 * inch))

    rows = []
    for name, origin, cost, moq, verdict, col in B1_SUPPLIERS:
        rows.append([
            P('<b>%s</b>' % name, st_cell_b), P(origin, st_cell), P(cost, st_cell_r),
            P(moq, st_cell_c), tag(verdict, col),
        ])
    CW = [1.85 * inch, 1.25 * inch, 2.25 * inch, 1.55 * inch, 2.60 * inch]
    scale = USABLE / sum(CW)
    F.append(data_table(rows, [w * scale for w in CW],
                        ['Supplier', 'Origin', '3-pack cost', 'MOQ', 'Verdict'],
                        brand=FOREST, aligns=['l', 'l', 'r', 'c', 'c']))
    F.append(Spacer(1, 0.24 * inch))

    # landed build
    lb = [P('Green Wrap landed cost, 100 sets', st_h2), Spacer(1, 0.06 * inch)]
    body = [[P('Line', st_th), P('Per set', st_th_r)]]
    for label, amt in B1_LANDED:
        body.append([P(label, st_cell), P('$%.2f' % amt, st_cell_r)])
    body.append([P('<b>LANDED</b>', st_cell_b), P('<b>$4.23</b>', st_cell_b)])
    t = Table(body, colWidths=[2.05 * inch, 0.85 * inch])
    t.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, 0), FOREST),
                           ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                           ('LEFTPADDING', (0, 0), (-1, -1), 7),
                           ('RIGHTPADDING', (0, 0), (-1, -1), 7),
                           ('TOPPADDING', (0, 0), (-1, -1), 5),
                           ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
                           ('LINEBELOW', (0, 0), (-1, -1), 0.35, RULE),
                           ('BACKGROUND', (0, 4), (-1, 4), colors.HexColor('#E8EDE4')),
                           ('LINEABOVE', (0, 4), (-1, 4), 1.0, FOREST)]))
    lb.append(t)

    # stacked bar of landed cost
    bar = Drawing(3.55 * inch, 0.95 * inch)
    segs = [('FOB 2.50', 2.50, OLIVE), ('Freight 1.10', 1.10, KRAFT),
            ('Duty 0.63', 0.63, COFFEE)]
    x = 0.0
    for label, amt, col in segs:
        w = 3.55 * inch * (amt / 4.23)
        bar.add(Rect(x, 22, w, 26, fillColor=col, strokeColor=WHITE, strokeWidth=0.8))
        bar.add(String(x + w / 2, 31, '$%.2f' % amt, fontName='Helvetica-Bold', fontSize=7.4,
                       fillColor=WHITE, textAnchor='middle'))
        x += w
    bar.add(String(0, 8, 'Landed $4.23 per set \u2014 23.5% of a $17.99 retail',
                   fontName='Helvetica', fontSize=7.4, fillColor=MUTED))
    lb.append(Spacer(1, 0.10 * inch))
    lb.append(bar)

    why = [P('Why the others fail', st_h2),
           Spacer(1, 0.04 * inch),
           P('<b>Sunella</b> at $7.99 is a 47% cost ratio \u2014 $1.81 net at their own MSRP. '
             'No retail price fixes a wholesale that high.', st_body_s),
           Spacer(1, 0.09 * inch),
           P('<b>Bee Kind</b> wants 700 sets per pattern and 8\u201313 weeks. That is a Q1 '
             'decision, not a Q4 one.', st_body_s),
           Spacer(1, 0.09 * inch),
           P('<b>SWEDEdishcloths</b> is the right partner for dishcloths \u2014 in-house printing, '
             'no minimums \u2014 but they are not a wrap source.', st_body_s),
           Spacer(1, 0.14 * inch),
           P('The decision', st_h2),
           Spacer(1, 0.04 * inch),
           P('<b>Green Wrap, 100 sets, patterned.</b> It is the only source whose landed cost '
             'leaves a real margin at a $17.99 shelf price.', st_body_s)]

    pair = Table([[lb, why]], colWidths=[USABLE * 0.5, USABLE * 0.5])
    pair.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'TOP'),
                              ('LEFTPADDING', (0, 0), (-1, -1), 0),
                              ('RIGHTPADDING', (0, 0), (0, 0), 0.40 * inch),
                              ('RIGHTPADDING', (1, 0), (1, 0), 0)]))
    F.append(pair)
    F.append(Spacer(1, 0.30 * inch))
    F.append(P('Cost ratio at a $17.99 shelf price', st_h2))
    F.append(Spacer(1, 0.08 * inch))
    F.append(hbar_rows([
        ('Green Wrap \u2014 $4.23 landed', 4.23, OLIVE),
        ('Bee Kind Wraps \u2014 40\u201350% of resale', 7.20, CLAY),
        ('Sunella \u2014 $7.99', 7.99, CLAY),
    ], USABLE * 0.62, 17.99, fmt='$%.2f'))
    F.append(Spacer(1, 0.06 * inch))
    F.append(P('Bars are wholesale as a share of a $17.99 retail. Green Wrap sits at 23.5%; '
               'the other two are 40% and above, where no retail price rescues the margin. '
               'Bee Kind is shown at the bottom of its 40\u201350% band.', st_note))

    # ================= 05 B1 ECONOMICS + TIMELINE =================
    F.append(PageBreak())
    F.append(P('Patterned wins. Natural fails.', st_h1))
    F.append(Spacer(1, 0.03 * inch))
    F.append(P('Same supplier, same landed cost, three price points. The pattern is the entire '
               'reason the margin exists.', st_body))
    F.append(Spacer(1, 0.16 * inch))

    rows = []
    for style_name, ret, net, roi, verdict, col in B1_ECON:
        rows.append([
            P('<b>%s</b>' % style_name, st_cell_b), P('$%.2f' % ret, st_cell_r),
            P('<b>$%.2f</b>' % net, st_cell_r), P(roi, st_cell_r), tag(verdict, col),
        ])
    CW = [2.60 * inch, 1.15 * inch, 1.10 * inch, 0.95 * inch, 1.95 * inch]
    scale = (USABLE * 0.52) / sum(CW)
    F.append(data_table(rows, [w * scale for w in CW],
                        ['Style', 'Retail', 'Net', 'ROI', 'Verdict'],
                        brand=COFFEE, aligns=['l', 'r', 'r', 'r', 'c']))
    F.append(Spacer(1, 0.10 * inch))
    F.append(P('The $2.00 gap between patterned and natural is not decoration \u2014 it is the '
               'difference between a viable SKU and one that sits below the floor.', st_note))
    F.append(Spacer(1, 0.22 * inch))

    F.append(P('The timeline problem', st_h2))
    F.append(Spacer(1, 0.10 * inch))
    steps = [
        ('WEEK 1', 'Ships from\nfactory', KRAFT),
        ('+ AIR', 'Freight to\nUS port', KRAFT),
        ('+ CUSTOMS', 'Clearance\nand duty', KRAFT),
        ('+ FBA', 'Receiving at\nfulfilment centre', KRAFT),
        ('EARLY\u2013MID DEC', 'Sellable', FOREST),
    ]
    cells, style = [], [('VALIGN', (0, 0), (-1, -1), 'TOP'),
                        ('LEFTPADDING', (0, 0), (-1, -1), 8),
                        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
                        ('TOPPADDING', (0, 0), (-1, -1), 9),
                        ('BOTTOMPADDING', (0, 0), (-1, -1), 9)]
    row = []
    for i, (date, txt, col) in enumerate(steps):
        fg = WHITE if i == len(steps) - 1 else INK
        inner = [Paragraph('<font color="%s"><b>%s</b></font>'
                           % (hexc(OLIVE if i == len(steps) - 1 else KRAFT), date),
                           ParagraphStyle('d%d' % i, fontName='Helvetica-Bold', fontSize=7.4,
                                          leading=9.4)),
                 Spacer(1, 0.04 * inch),
                 Paragraph(txt.replace('\n', '<br/>'),
                           ParagraphStyle('t%d' % i, fontName='Helvetica', fontSize=7.6,
                                          leading=10.4, textColor=fg))]
        row.append(inner)
        style += [('BACKGROUND', (i, 0), (i, 0), col if i == len(steps) - 1 else WHITE),
                  ('BOX', (i, 0), (i, 0), 0.5, RULE if i < len(steps) - 1 else FOREST)]
    t = Table([row], colWidths=[USABLE / 5.0] * 5)
    t.setStyle(TableStyle(style))
    F.append(t)
    F.append(Spacer(1, 0.18 * inch))

    F.append(callout('<b>Green Wrap cannot reach 25 November.</b> Factory-gate ship in one week, '
                     'plus air freight, customs and FBA receiving, lands sellable stock in '
                     '<b>early-to-mid December</b>. That catches the 1\u201320 December gifting run '
                     'and misses Black Friday entirely. Decide on that basis, not on hope.',
                     accent=CLAY, bgc=colors.HexColor('#FAF1EC')))
    F.append(Spacer(1, 0.16 * inch))
    F.append(callout('<b>Freight economics invert at 100 units.</b> 15 kg by air costs about as '
                     'much as the goods themselves \u2014 $1.10 per set. At 300\u2013500 sets that '
                     'drops to roughly $0.50, which is where the SKU becomes genuinely cheap. '
                     'The 100-set order is a market test, not an efficient order.',
                     accent=AMBER))
    F.append(Spacer(1, 0.26 * inch))
    F.append(text_strip([
        ('Option A \u00b7 order now',
         'Sellable <b>early-to-mid December</b>. Catches the 1\u201320 Dec gifting run. Misses '
         'Black Friday. Pays a $1.10 freight penalty per set.'),
        ('Option B \u00b7 defer to Q1',
         'Order <b>300\u2013500 sets</b> and freight drops to ~$0.50 per set. No December revenue, '
         'but a materially cheaper unit cost and no air-freight premium.'),
    ], accent=AMBER))

    # ================= 06 B2 TOP FIVE =================
    F.append(PageBreak())
    F.append(P('Mogro Organics \u2014 the top five', st_h1))
    F.append(Spacer(1, 0.03 * inch))
    F.append(P('Five survivors from the full category scan. Two clear $7 net, one clears $9.80, '
               'and the highest ROI in the entire brief is a $2.20 item.', st_body))
    F.append(Spacer(1, 0.16 * inch))

    rows = []
    for code, name, sup, ws, ret, net, roi in SECTION_B2:
        rows.append([
            P('<b>%s</b>' % code, st_cell_c), P(name, st_cell_b), P(sup, st_cell),
            P(ws, st_cell_r), P('$%.2f' % ret, st_cell_r),
            P('<b>$%.2f</b>' % net, st_cell_r), P('%d%%' % roi, st_cell_r),
            net_bar(net, 9.80, 1.05 * inch, 7.5, FOREST),
        ])
    CW = [0.45 * inch, 2.70 * inch, 2.15 * inch, 1.05 * inch, 0.75 * inch,
          0.70 * inch, 0.62 * inch, 1.20 * inch]
    scale = USABLE / sum(CW)
    F.append(data_table(rows, [w * scale for w in CW],
                        ['#', 'Product', 'Supplier', 'WS', 'Retail', 'Net', 'ROI', ''],
                        brand=FOREST, aligns=['c', 'l', 'l', 'r', 'r', 'r', 'r', 'l']))
    F.append(Spacer(1, 0.22 * inch))

    hero = [P('B3 \u2014 the best ROI in the brief', st_h2),
            Spacer(1, 0.04 * inch),
            P('<b>274%</b> on Loofah Facial Disks. $0.22 per unit wholesale, featherweight, and '
              'SeaSationals ships to Amazon prep centres. This is the cheapest real SKU on the '
              'list and the easiest to test.', st_body_s)]
    fails = [P('What fails, and why', st_h2),
             Spacer(1, 0.04 * inch),
             P('<b>Organic cotton produce bags:</b> ECOBAGS at $8.23 is 41% of a $19.99 retail. '
               'No price point fixes that. <b>Excluded.</b>', st_body_s),
             Spacer(1, 0.08 * inch),
             P('<b>Dishcloth sourcing:</b> SWEDEdishcloths prints in-house with <b>no minimums</b> '
               '\u2014 best fit for a 100\u2013300 test. Lollygag is $6.50 with a $125 opening '
               'minimum; PrintGlobe covers in-stock custom logo. Made-in-China at $0.40\u2013$0.53 '
               'needs 2,000\u201330,000 pieces \u2014 out of range.', st_body_s)]
    pair = Table([[hero, fails]], colWidths=[USABLE * 0.42, USABLE * 0.58])
    pair.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'TOP'),
                              ('LEFTPADDING', (0, 0), (-1, -1), 0),
                              ('RIGHTPADDING', (0, 0), (0, 0), 0.36 * inch),
                              ('RIGHTPADDING', (1, 0), (1, 0), 0)]))
    F.append(pair)
    F.append(Spacer(1, 0.55 * inch))
    F.append(kpi([
        ('$9.80', 'best net in the brief (B5)', FOREST),
        ('$7.09', 'best single-unit net (B2)', GREEN),
        ('274%', 'best ROI (B3)', AMBER),
        ('$7.21', 'average net across the five', MUTED),
    ]))

    # ================= 07 SECTION C =================
    F.append(NextPageTemplate('nonbrand'))
    F.append(PageBreak())
    F.append(P('Twenty-two fast-flippers', st_h1))
    F.append(Spacer(1, 0.03 * inch))
    F.append(P('All ungated, small, light, sticker-ready. FBA modelled at $3.90\u2013$4.35. '
               'Order follows the working sheet; the bars show net per unit.', st_body))
    F.append(Spacer(1, 0.12 * inch))

    rows = []
    for num, name, ret, ws, net, ratio in SECTION_C:
        col = FOREST if net >= 6.9 else (AMBER if net >= 6.0 else SAGE)
        rows.append([
            P(str(num), st_cell_c), P(name, st_cell), P('$%.2f' % ret, st_cell_r),
            P('$%.2f' % ws, st_cell_r), P('<b>$%.2f</b>' % net, st_cell_r),
            P(ratio, st_cell_r), net_bar(net, 7.74, 0.95 * inch, 6.5, col),
        ])
    # two side-by-side blocks of 11 rows for legibility
    CW = [0.36 * inch, 3.30 * inch, 0.72 * inch, 0.80 * inch, 0.66 * inch, 0.60 * inch, 1.15 * inch]
    scale = USABLE / sum(CW)
    cw = [w * scale for w in CW]
    head = ['#', 'Product', 'Retail', 'Target WS', 'Net', 'Ratio', '']
    al = ['c', 'l', 'r', 'r', 'r', 'r', 'l']
    F.append(data_table(rows, cw, head, brand=FOREST, aligns=al, dense=True))
    F.append(Spacer(1, 0.14 * inch))

    F.append(P('<b>Honest ceiling: $5.74\u2013$7.74 net at $14.99\u2013$19.99.</b> Nothing in this '
               'band hits a $10+ target \u2014 that needs $24.99 retail or wholesale under $2.00. '
               'Row 20 is still pending in the working sheet and is excluded here.', st_body_s))
    F.append(Spacer(1, 0.10 * inch))
    F.append(P('<b>Excluded on compliance:</b> shower steamers and bath bombs (cosmetics/MoCRA), '
               'mini humidifiers and LED devices (electrical/UL), anything with a health claim. '
               '<b>Excluded on economics:</b> anything at $14.99 needing wholesale above $3.94. '
               '<b>Warning:</b> these wholesale figures are estimates, not quotes \u2014 no supplier '
               'has been contacted for these 22 items.', st_note))

    # ================= 08 PRINTER =================
    F.append(NextPageTemplate('print'))
    F.append(PageBreak())
    F.append(P('The printer you have', st_h1))
    F.append(Spacer(1, 0.03 * inch))
    F.append(P('Canon PIXMA TR4720. Adequate, not optimal \u2014 and it fails at exactly one '
               'thing that matters.', st_body))
    F.append(Spacer(1, 0.18 * inch))

    body = [[P('Line', st_th), P('Cost', st_th_r)]]
    for label, val in PRINTER:
        bold = label.startswith('Total')
        body.append([P('<b>%s</b>' % label if bold else label, st_cell_b if bold else st_cell),
                     P('<b>%s</b>' % val if bold else val, st_cell_r)])
    t = Table(body, colWidths=[2.95 * inch, 1.10 * inch])
    t.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, 0), FOREST),
                           ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                           ('LEFTPADDING', (0, 0), (-1, -1), 8),
                           ('RIGHTPADDING', (0, 0), (-1, -1), 8),
                           ('TOPPADDING', (0, 0), (-1, -1), 6),
                           ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
                           ('LINEBELOW', (0, 0), (-1, -1), 0.35, RULE),
                           ('BACKGROUND', (0, 4), (-1, 4), colors.HexColor('#E8EDE4')),
                           ('LINEABOVE', (0, 4), (-1, 4), 1.0, FOREST)]))
    left = [P('Cost per label, today', st_h2), Spacer(1, 0.08 * inch), t]

    verdicts = [
        ('ADEQUATE', GREEN, 'Fine for <b>100\u2013300 colour brand labels</b> \u2014 about $27 in '
                            'materials and one afternoon of printing.'),
        ('FAILS AT SCALE', CLAY, 'At <b>1,000+ units</b> both ink cost and print time scale badly. '
                                 '100 minutes for 50 sheets is not a production process.'),
        ('FAILS IN USE', CLAY, 'Inkjet ink is <b>water-soluble</b>. On bath salts, dishcloths or '
                               'kitchen goods a damp hand smears the label \u2014 a direct returns driver.'),
    ]
    right = [P('Verdict on the TR4720', st_h2), Spacer(1, 0.08 * inch)]
    for label, col, text in verdicts:
        blk = Table([[
            P('<font color="%s"><b>%s</b></font>' % (hexc(col), label),
              ParagraphStyle('v%s' % label, fontName='Helvetica-Bold', fontSize=7.2, leading=9.4)),
            P(text, st_body_s)]], colWidths=[1.10 * inch, 2.90 * inch])
        blk.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'TOP'),
                                 ('LEFTPADDING', (0, 0), (-1, -1), 0),
                                 ('RIGHTPADDING', (0, 0), (-1, -1), 4),
                                 ('TOPPADDING', (0, 0), (-1, -1), 6),
                                 ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
                                 ('LINEBELOW', (0, 0), (-1, 0), 0.35, RULE)]))
        right.append(blk)

    pair = Table([[left, right]], colWidths=[USABLE * 0.45, USABLE * 0.55])
    pair.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'TOP'),
                              ('LEFTPADDING', (0, 0), (-1, -1), 0),
                              ('RIGHTPADDING', (0, 0), (0, 0), 0.36 * inch),
                              ('RIGHTPADDING', (1, 0), (1, 0), 0)]))
    F.append(pair)
    F.append(Spacer(1, 0.26 * inch))

    warn = Table([[
        Paragraph('DO NOT PRINT FNSKU ON THE TR4720',
                  ParagraphStyle('w1', fontName='Times-Bold', fontSize=15, leading=19, textColor=WHITE)),
        Paragraph('Barcodes must scan at FC receiving. Inkjet barcodes on gloss stock are the single '
                  'most common avoidable failure flagged across this project. One physical sample, '
                  'scanned with a phone, before any label run.',
                  ParagraphStyle('w2', fontName='Helvetica', fontSize=8.4, leading=12.2,
                                 textColor=colors.HexColor('#F0E7DA')))]],
        colWidths=[3.10 * inch, USABLE - 3.10 * inch])
    warn.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, -1), CLAY),
                              ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                              ('LEFTPADDING', (0, 0), (-1, -1), 14),
                              ('RIGHTPADDING', (0, 0), (-1, -1), 14),
                              ('TOPPADDING', (0, 0), (-1, -1), 12),
                              ('BOTTOMPADDING', (0, 0), (-1, -1), 12)]))
    F.append(warn)
    F.append(Spacer(1, 0.45 * inch))
    F.append(P('Cost per label by method', st_h2))
    F.append(Spacer(1, 0.08 * inch))
    F.append(hbar_rows([
        ('TR4720 inkjet (colour)', 0.09, COFFEE),
        ('Thermal \u2014 Rollo / Zebra', 0.02, OLIVE),
        ('Outsourced roll labels', 0.08, KRAFT),
        ('Brother colour laser (low end)', 0.15, CLAY),
    ], USABLE * 0.62, 0.25, fmt='$%.2f'))
    F.append(Spacer(1, 0.06 * inch))
    F.append(P('Outsourced rolls are shown at the top of their $0.06\u2013$0.10 range; the colour '
               'laser at the bottom of $0.15\u2013$0.25, which flatters it. Thermal still wins.', st_note))

    # ================= 09 PRINTER DECISION =================
    F.append(PageBreak())
    F.append(P('The printer you should add', st_h1))
    F.append(Spacer(1, 0.03 * inch))
    F.append(P('One purchase, about $200, and it removes both failure modes. Everything else on '
               'this page is a reason not to spend.', st_body))
    F.append(Spacer(1, 0.16 * inch))

    rows = []
    for name, price, cost, verdict, col in PRINTER_OPTIONS:
        rows.append([
            P('<b>%s</b>' % name, st_cell_b), P(price, st_cell_r), P(cost, st_cell_r),
            tag(verdict, col),
        ])
    CW = [3.05 * inch, 1.25 * inch, 1.35 * inch, 2.55 * inch]
    scale = USABLE / sum(CW)
    F.append(data_table(rows, [w * scale for w in CW],
                        ['Option', 'Price', 'Cost / label', 'Verdict'],
                        brand=FOREST, aligns=['l', 'r', 'r', 'c']))
    F.append(Spacer(1, 0.24 * inch))

    F.append(kpi([
        ('~$0.11', 'all-in per unit, both printers', FOREST),
        ('~$0.02', 'thermal label cost', GREEN),
        ('$200', 'one-time thermal spend', AMBER),
        ('0', 'colour lasers that pay back', CLAY),
    ]))
    F.append(Spacer(1, 0.24 * inch))

    rec = [P('The verdict', st_h2),
           Spacer(1, 0.05 * inch),
           P('Keep the TR4720 for colour brand labels. Add a thermal printer for FNSKU and '
             'shipping labels. That combination costs about <b>$0.11 per unit all-in</b> and '
             'removes the two failure modes \u2014 smeared ink and unscannable barcodes.', st_body_s)]
    buy = [P('And do not buy anything else', st_h2),
           Spacer(1, 0.05 * inch),
           P('Skip the colour laser entirely: at 100\u2013300 units it cannot pay back its toner. '
             'A second inkjet is not an asset. The thermal printer is, because it is used forever. '
             '<b>Buy nothing beyond it until one test run has shipped.</b>', st_body_s)]
    pair = Table([[rec, buy]], colWidths=[USABLE * 0.5, USABLE * 0.5])
    pair.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'TOP'),
                              ('LEFTPADDING', (0, 0), (-1, -1), 0),
                              ('RIGHTPADDING', (0, 0), (0, 0), 0.40 * inch),
                              ('RIGHTPADDING', (1, 0), (1, 0), 0)]))
    F.append(pair)
    F.append(Spacer(1, 0.30 * inch))
    F.append(text_strip([
        ('$0.07', 'Saved per label by moving FNSKU and shipping labels to thermal \u2014 $0.09 inkjet '
                  'against $0.02 thermal.'),
        ('$70', 'Saved on a single 1,000-label run. The gap widens with volume because inkjet ink '
                'scales linearly.'),
        ('~2,900', 'Labels needed to repay the $200 printer at $0.07 saved each. Inside the first '
                   'production run.'),
    ], accent=GREEN))
    F.append(PageBreak())
    F.append(P('What the first test costs', st_h1))
    F.append(Spacer(1, 0.03 * inch))
    F.append(P('One SKU, 200 units, A1 postcards at $6.00 wholesale. Everything below is cash out '
               'before the first sale.', st_body))
    F.append(Spacer(1, 0.20 * inch))

    body = [[P('Line', st_th), P('Amount', st_th_r)]]
    for label, amt, bold in BUDGET:
        body.append([P('<b>%s</b>' % label if bold else label, st_cell_b if bold else st_cell),
                     P('<b>%s</b>' % amt if bold else amt, st_cell_r)])
    t = Table(body, colWidths=[3.30 * inch, 1.25 * inch])
    t.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, 0), FOREST),
                           ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                           ('LEFTPADDING', (0, 0), (-1, -1), 9),
                           ('RIGHTPADDING', (0, 0), (-1, -1), 9),
                           ('TOPPADDING', (0, 0), (-1, -1), 7),
                           ('BOTTOMPADDING', (0, 0), (-1, -1), 7),
                           ('LINEBELOW', (0, 0), (-1, -1), 0.35, RULE),
                           ('BACKGROUND', (0, len(body) - 1), (-1, len(body) - 1),
                            colors.HexColor('#E8EDE4')),
                           ('LINEABOVE', (0, len(body) - 1), (-1, len(body) - 1), 1.2, FOREST)]))

    side = [P('$1,918', ParagraphStyle('big', fontName='Times-Bold', fontSize=40, leading=42,
                                       textColor=FOREST)),
            Spacer(1, 0.06 * inch),
            P('UNDER THE $3,000 CEILING', st_tile_l),
            Spacer(1, 0.14 * inch),
            P('With room left for a second SKU \u2014 which is why B3 loofah disks at $2.20 '
              'wholesale can go into the same order without a second approval cycle.', st_body_s),
            Spacer(1, 0.16 * inch),
            P('What is not in this number', st_h2),
            P('No supplier quotes for Section C. No Amazon demand data. No returns allowance '
              'beyond the 15% contingency. This is a test budget, not a P&amp;L.', st_note)]
    pair = Table([[t, side]], colWidths=[USABLE * 0.50, USABLE * 0.50])
    pair.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'TOP'),
                              ('LEFTPADDING', (0, 0), (-1, -1), 0),
                              ('RIGHTPADDING', (0, 0), (0, 0), 0.55 * inch),
                              ('RIGHTPADDING', (1, 0), (1, 0), 0)]))
    F.append(pair)
    F.append(Spacer(1, 0.95 * inch))
    F.append(kpi([
        ('$1,918', 'cash out before the first sale', FOREST),
        ('$9.59', 'all-in cost per unit, 200 units', AMBER),
        ('$1,508', 'net if all 200 sell at $7.54', GREEN),
        ('$3,000', 'ceiling \u2014 $1,082 of headroom', MUTED),
    ]))
    F.append(Spacer(1, 0.10 * inch))
    F.append(P('The $1,508 is arithmetic, not a forecast: 200 units \u00d7 the A1 net of $7.54. '
               'It excludes the $200 printer and $250 contingency, which are one-time or unspent. '
               'Sell-through is the unknown \u2014 which is exactly why the order is 200 and not 2,000.',
               st_note))

    # ================= 11 THE PATH =================
    F.append(NextPageTemplate('plan'))
    F.append(PageBreak())
    F.append(P('The path from here', st_h1))
    F.append(Spacer(1, 0.03 * inch))
    F.append(P('Four phases. Each one either earns the next or stops the line \u2014 no phase '
               'assumes the one before it worked.', st_body))
    F.append(Spacer(1, 0.18 * inch))

    CARD_W = USABLE / 4.0 - 0.10 * inch
    p1 = phase_card('01', 'Validate the numbers', 'This week \u00b7 no cash out', [
        'Section C wholesale figures are <b>estimates, not quotes</b>. Validate the top 3 before '
        'any order.',
        'Confirm the A1 StationeryHQ quote and that they will apply labels.',
        'Confirm PrintPPS 1-business-day ship and MOQ 1 for A4.',
        'Get the Green Wrap 100-set landed quote in writing: FOB, air, duty.',
        'Scan one physical FNSKU sample before ordering labels.',
    ], KRAFT, CARD_W, 'Quotes in writing before any PO.')

    p2 = phase_card('02', 'Ship the A1 test', 'Weeks 1\u20134 \u00b7 $1,918', [
        'Order <b>200 postcard sets at $6.00</b> \u2014 $1,200.',
        'Buy the thermal printer, $200. Print FNSKU on thermal only.',
        'Colour brand labels on the TR4720 \u2014 200 at $0.09.',
        'Two freight lanes to FBA, $250. Contingency $250.',
        'No second SKU spend until this one is live.',
    ], FOREST, CARD_W, 'First sale recorded on the listing.')

    p3 = phase_card('03', 'Add the second SKU', 'Weeks 3\u20136 \u00b7 within budget', [
        'B3 Loofah Facial Disks: <b>274% ROI</b>, $2.20 wholesale, featherweight.',
        'Fits inside the same $3,000 ceiling.',
        'Green Wrap decision: 100 sets lands <b>early\u2013mid December</b>.',
        'If 1\u201320 Dec gifting is worth it, order now. If not, defer to Q1.',
        'Never order wraps expecting Black Friday.',
    ], AMBER, CARD_W, 'A1 clears its floor before SKU two ships.')

    p4 = phase_card('04', 'Scale what sold', 'Q1 \u00b7 only on evidence', [
        'Reorder winners at <b>300\u2013500 units</b>, not 200.',
        'Green Wrap freight drops $1.10 to ~$0.50 per set at that volume.',
        'At 500+ units move labels to outsourced rolls ($0.06\u2013$0.10).',
        'Drop anything that did not clear its floor in the test window.',
        'Re-run the arithmetic before every reorder.',
    ], OLIVE, CARD_W, 'Sell-through, not opinion.')

    cards = Table([[p1, p2, p3, p4]], colWidths=[USABLE / 4.0] * 4)
    cards.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'TOP'),
                               ('LEFTPADDING', (0, 0), (0, 0), 0),
                               ('RIGHTPADDING', (0, 0), (0, 0), 0.10 * inch),
                               ('LEFTPADDING', (1, 0), (1, 0), 0.05 * inch),
                               ('RIGHTPADDING', (1, 0), (1, 0), 0.10 * inch),
                               ('LEFTPADDING', (2, 0), (2, 0), 0.05 * inch),
                               ('RIGHTPADDING', (2, 0), (2, 0), 0.10 * inch),
                               ('LEFTPADDING', (3, 0), (3, 0), 0.05 * inch),
                               ('RIGHTPADDING', (3, 0), (3, 0), 0)]))
    F.append(cards)
    F.append(Spacer(1, 0.26 * inch))
    F.append(P('Calendar view', st_h2))
    F.append(Spacer(1, 0.06 * inch))
    F.append(gantt([
        ('01 \u00b7 Validate', 0.00, 0.08, KRAFT),
        ('02 \u00b7 A1 test', 0.00, 0.32, FOREST),
        ('03 \u00b7 Second SKU', 0.16, 0.48, AMBER),
        ('04 \u00b7 Scale', 0.66, 1.00, OLIVE),
    ], USABLE, 1.25 * inch, [(0.0, 'NOV 4'), (0.16, 'NOV 18'), (0.32, 'DEC 2'),
                             (0.48, 'DEC 16'), (0.66, 'JAN 1'), (1.0, 'JAN 31')]))
    F.append(Spacer(1, 0.20 * inch))

    F.append(callout('<b>The one dependency that gates everything:</b> FNSKU barcodes must exist '
                     'before label artwork is final. Listing creation comes before printing, not '
                     'after. Every phase above assumes that order.', accent=CLAY,
                     bgc=colors.HexColor('#FAF1EC')))

    # ================= 12 WHAT NOT TO DO =================
    F.append(PageBreak())
    F.append(P('What we will not do', st_h1))
    F.append(Spacer(1, 0.03 * inch))
    F.append(P('Five decisions already made. Revisiting any of them without new data is how the '
               'margin disappears.', st_body))
    F.append(Spacer(1, 0.20 * inch))

    donts = [
        ('01', 'Do not source beeswax wraps from Sunella at $7.99.',
         '47% cost ratio, $1.81 net at their own MSRP. The arithmetic does not close at any price.'),
        ('02', 'Do not expect $10+ net in the $14.99\u2013$19.99 band.',
         'At 30% COGS the arithmetic does not allow it. $6\u2013$8 is the honest ceiling; '
         '$10+ needs $24.99 retail or wholesale under $2.00.'),
        ('03', 'Do not put organic produce bags on this list.',
         '41% cost ratio at ECOBAGS. There is no price point that fixes it.'),
        ('04', 'Do not print FNSKU labels on the Canon.',
         'Inkjet barcodes on gloss stock fail at FC receiving. Thermal, or outsource the roll.'),
        ('05', 'Do not treat Section C wholesale as quoted.',
         'No supplier has been contacted for those 22 items. Validate the top 3 before ordering.'),
    ]
    for num, title, body in donts:
        blk = Table([[
            P(num, ParagraphStyle('z%s' % num, fontName='Times-Bold', fontSize=20,
                                  leading=23, textColor=KRAFT)),
            [P('<b>%s</b>' % title, ParagraphStyle('zt%s' % num, fontName='Helvetica-Bold',
                                                   fontSize=9.4, leading=12.6, textColor=FOREST)),
             Spacer(1, 0.02 * inch),
             P(body, st_body_s)]]],
            colWidths=[0.60 * inch, USABLE - 0.60 * inch])
        blk.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'TOP'),
                                 ('LEFTPADDING', (0, 0), (-1, -1), 0),
                                 ('TOPPADDING', (0, 0), (-1, -1), 8),
                                 ('BOTTOMPADDING', (0, 0), (-1, 0), 9),
                                 ('LINEBELOW', (0, 0), (-1, 0), 0.35, RULE)]))
        F.append(blk)

    F.append(Spacer(1, 0.22 * inch))
    F.append(callout('<b>The whole brief in one line:</b> price at $16.99\u2013$19.99, hold '
                     'wholesale to roughly a quarter of retail, launch A1 postcards at 200 units '
                     'for $1,918, and label with thermal \u2014 everything else is a distraction '
                     'until that first run ships.', accent=FOREST, bgc=colors.HexColor('#EDF0E9')))
    F.append(Spacer(1, 0.30 * inch))
    F.append(P('Next action', st_h2))
    F.append(Spacer(1, 0.08 * inch))
    F.append(text_strip([
        ('Confirm the A1 quote',
         'StationeryHQ: $6.00 per set at 200 units, and written confirmation they will apply '
         'our label. Nothing else moves until this is real.'),
        ('Validate three wholesales',
         'Pick the top three from Section C and get actual quotes. Those figures are estimates; '
         'the whole catalog page is unvalidated.'),
        ('Price the wraps in writing',
         'Green Wrap: FOB, air freight and duty for 100 sets. Then choose Option A or B on '
         'the December timeline.'),
    ], accent=FOREST))

    doc.build(F)
    print('Wrote %s (%d pages)' % (OUT, doc.page))


if __name__ == '__main__':
    build()
