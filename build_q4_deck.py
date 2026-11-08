#!/usr/bin/env python3
"""Q4 Launch Data Package — executive PDF deck."""
from reportlab.lib.pagesizes import landscape, letter
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT
from reportlab.platypus import (BaseDocTemplate, PageTemplate, Frame, Paragraph,
                                Spacer, Table, TableStyle, PageBreak,
                                NextPageTemplate)
from reportlab.graphics.shapes import Drawing, Rect, String

# ---------- palette ----------
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
    base = dict(fontName='Helvetica', fontSize=9, leading=12, textColor=INK)
    base.update(kw)
    return ParagraphStyle(name, **base)

st_kick    = S('k', fontName='Helvetica-Bold', fontSize=8.5, leading=11, textColor=KRAFT)
st_ctitle  = S('ct', fontName='Times-Bold', fontSize=40, leading=45, textColor=WHITE)
st_csub    = S('cs', fontName='Helvetica', fontSize=11.5, leading=17,
               textColor=colors.HexColor('#D8D2C6'))
st_h1      = S('h1', fontName='Times-Bold', fontSize=26, leading=31, textColor=FOREST)
st_h2      = S('h2', fontName='Helvetica-Bold', fontSize=9.5, leading=13,
               textColor=FOREST, spaceBefore=3)
st_body    = S('b', fontSize=9.4, leading=14)
st_body_s  = S('bs', fontSize=8.5, leading=12.4)
st_note    = S('n', fontSize=7.9, leading=11.4, textColor=MUTED)
st_cell    = S('c', fontSize=7.8, leading=9.8)
st_cell_b  = S('cb', fontName='Helvetica-Bold', fontSize=7.8, leading=9.8)
st_cell_r  = S('cr', fontSize=7.8, leading=9.8, alignment=TA_RIGHT)
st_cell_c  = S('cc', fontSize=7.8, leading=9.8, alignment=TA_CENTER)
st_th      = S('th', fontName='Helvetica-Bold', fontSize=7.2, leading=9.2, textColor=WHITE)
st_th_c    = S('thc', fontName='Helvetica-Bold', fontSize=7.2, leading=9.2,
               textColor=WHITE, alignment=TA_CENTER)
st_th_r    = S('thr', fontName='Helvetica-Bold', fontSize=7.2, leading=9.2,
               textColor=WHITE, alignment=TA_RIGHT)
st_tile_n  = S('tn', fontName='Times-Bold', fontSize=28, leading=31, textColor=FOREST)
st_tile_l  = S('tl', fontName='Helvetica-Bold', fontSize=7, leading=9.4, textColor=MUTED)


def hexc(c):
    return '#%02X%02X%02X' % (int(c.red * 255), int(c.green * 255), int(c.blue * 255))


def bg(canv, doc):
    canv.saveState()
    canv.setFillColor(PAPER)
    canv.rect(0, 0, PAGE[0], PAGE[1], stroke=0, fill=1)
    canv.restoreState()


def chrome(canv, doc, section):
    canv.saveState()
    canv.setFillColor(SAGE)
    canv.setFont('Helvetica-Bold', 7)
    canv.drawString(LM, PAGE[1] - 0.34 * inch, 'MOGRA ORGANICS')
    canv.setFillColor(CREAM)
    canv.drawString(LM + 0.98 * inch, PAGE[1] - 0.34 * inch, '/')
    canv.setFillColor(COFFEE)
    canv.drawString(LM + 1.07 * inch, PAGE[1] - 0.34 * inch, 'WORD COFFEE')
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
                    'Q4 Launch Data Package  \u00b7  Prepared for Tyler  \u00b7  2 November 2026')
    canv.drawRightString(PAGE[0] - RM, BM - 0.26 * inch, '%02d' % doc.page)
    canv.restoreState()


def cover_bg(canv, doc):
    canv.saveState()
    canv.setFillColor(FOREST)
    canv.rect(0, 0, PAGE[0], PAGE[1], stroke=0, fill=1)
    canv.setFillColor(KRAFT)
    canv.rect(0, 0, 0.13 * inch, PAGE[1], stroke=0, fill=1)
    canv.setFillColor(colors.HexColor('#2E4231'))
    canv.setFont('Times-Italic', 74)
    canv.drawRightString(PAGE[0] - 0.45 * inch, PAGE[1] - 1.35 * inch, 'Q4')
    canv.restoreState()


def P(t, s=st_body):
    return Paragraph(t, s)


def kpi(items):
    n = len(items)
    gap = 0.12 * inch
    w = (USABLE - gap * (n - 1)) / n
    row, style = [], [('VALIGN', (0, 0), (-1, -1), 'TOP'),
                      ('LEFTPADDING', (0, 0), (-1, -1), 10),
                      ('RIGHTPADDING', (0, 0), (-1, -1), 8),
                      ('TOPPADDING', (0, 0), (-1, -1), 10),
                      ('BOTTOMPADDING', (0, 0), (-1, -1), 10)]
    for i, (val, label, col) in enumerate(items):
        row.append([Paragraph(val, ParagraphStyle('q%d' % i, fontName='Times-Bold',
                                                  fontSize=27, leading=30, textColor=col)),
                    Paragraph(label.upper(), st_tile_l)])
        style += [('BACKGROUND', (i, 0), (i, 0), WHITE),
                  ('BOX', (i, 0), (i, 0), 0.6, RULE),
                  ('LINEABOVE', (i, 0), (i, 0), 2.4, col)]
    t = Table([row], colWidths=[w] * n)
    t.setStyle(TableStyle(style))
    return t


def bridge(total, segments, width, height):
    """segments = [(label, amount, colour)] ; last is net profit."""
    d = Drawing(width, height)
    x = 0.0
    for label, amt, col in segments:
        w = width * (amt / total)
        d.add(Rect(x, 12, w, height - 34, fillColor=col, strokeColor=None))
        if w > 0.55 * inch:
            d.add(String(x + w / 2, 4, '%.2f' % amt, fontName='Helvetica-Bold',
                         fontSize=7.4, fillColor=col, textAnchor='middle'))
        x += w
    return d


def legend(items, width):
    cells, style = [], [('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                        ('LEFTPADDING', (0, 0), (-1, -1), 0),
                        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
                        ('TOPPADDING', (0, 0), (-1, -1), 1),
                        ('BOTTOMPADDING', (0, 0), (-1, -1), 1)]
    row = []
    for i, (label, col) in enumerate(items):
        row.append([Paragraph('<font color="%s">\u25A0</font> %s'
                              % (hexc(col), label), st_cell)])
    t = Table([row], colWidths=[width / len(items)] * len(items))
    t.setStyle(TableStyle(style))
    return t


def data_table(rows, widths, head, brand=FOREST):
    hs = {'l': st_th, 'c': st_th_c, 'r': st_th_r}
    align = ['c', 'l', 'l', 'c', 'r', 'r', 'r', 'r', 'c', 'c']
    hdr = [Paragraph(h, hs[align[i] if i < len(align) else 'l']) for i, h in enumerate(head)]
    body = [hdr] + rows
    t = Table(body, colWidths=widths, repeatRows=1)
    style = [('BACKGROUND', (0, 0), (-1, 0), brand),
             ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
             ('LEFTPADDING', (0, 0), (-1, -1), 5),
             ('RIGHTPADDING', (0, 0), (-1, -1), 5),
             ('TOPPADDING', (0, 0), (-1, -1), 3.2),
             ('BOTTOMPADDING', (0, 0), (-1, -1), 3.2),
             ('LINEBELOW', (0, 0), (-1, -1), 0.35, RULE)]
    for r in range(1, len(body)):
        if r % 2 == 0:
            style.append(('BACKGROUND', (0, r), (-1, r), TINT))
    t.setStyle(TableStyle(style))
    return t


def demand_chip(d):
    col = {'HOT': '#A85B48', 'SEASONAL': '#A2762F', 'STEADY': '#9FA9A4'}[d]
    return Paragraph('<font color="%s"><b>%s</b></font>' % (col, d), st_cell_c)


def speed_chip(s):
    if s == 'FAST':
        return Paragraph('<font color="#2F6B3A"><b>FAST</b></font>', st_cell_c)
    return Paragraph('\u2014', st_cell_c)


# ---------- data ----------
MOGRA = [
    ('Organic Herbal Tea Tin, 30 sachets', 'Adagio XL', 'CA', 5.60, 29.99, 12.69, 73, 'HOT', 'FAST'),
    ('Heirloom Seed Starter Kit, 5-var', 'True Leaf Market', 'UT', 6.00, 24.99, 9.79, 64, 'SEASONAL', ''),
    ('3-Herb Garden Kit', 'True Leaf Market', 'UT', 8.00, 26.99, 9.04, 50, 'SEASONAL', ''),
    ('Mushroom Growing Kit', 'True Leaf Market', 'UT', 10.00, 29.99, 8.49, 39, 'HOT', ''),
    ('Microgreens Growing Kit', 'True Leaf Market', 'UT', 9.00, 27.99, 8.44, 43, 'SEASONAL', ''),
    ('Sprouting Kit', 'True Leaf Market', 'UT', 8.50, 26.99, 8.09, 43, 'STEADY', ''),
    ('Whipped Shea Body Butter, 7.5 oz', 'Bulk Apothecary', 'OH', 7.74, 24.99, 7.95, 47, 'HOT', 'FAST'),
    ('Brown Sugar Scrub, 8 oz', 'Bulk Apothecary', 'OH', 7.74, 24.99, 7.70, 45, 'HOT', 'FAST'),
    ('Botanical Body Lotion, 8 oz', 'Bulk Apothecary', 'OH', 4.41, 19.99, 7.34, 58, 'SEASONAL', 'FAST'),
    ('Botanical Body Mist, 8 oz', 'Bulk Apothecary', 'OH', 4.41, 19.99, 7.34, 58, 'HOT', 'FAST'),
    ('Natural Loofah Spa Set, 5-pc', 'SeaSationals', 'FL', 6.60, 21.99, 6.84, 45, 'SEASONAL', 'FAST'),
    ('Natural Sea Sponge, bath', 'SeaSationals', 'FL', 4.50, 18.99, 6.74, 55, 'STEADY', 'FAST'),
    ('Pre-Filled Organic Spice Jar, 5.5 oz', "Sugar 'N Spice", 'WI', 7.50, 21.99, 6.44, 41, 'SEASONAL', 'FAST'),
    ('Calming Lavender Bath Salts, 16 oz', 'Bulk Apothecary', 'OH', 4.46, 19.99, 6.18, 45, 'SEASONAL', 'FAST'),
    ('Loofah Facial Disks, 10-pack', 'SeaSationals', 'FL', 2.20, 14.99, 6.09, 68, 'STEADY', 'FAST'),
    ('3-Wick Scented Candle', 'Bulk Apothecary', 'OH', 14.95, 34.99, 5.99, 21, 'HOT', 'FAST'),
    ('Beeswax Food Wraps, 3-pack', 'Meli Wraps', 'HI', 6.00, 19.99, 5.99, 43, 'SEASONAL', ''),
    ('GOTS Organic Cotton Tote', 'Organic Blank', 'US', 6.50, 19.99, 5.69, 40, 'STEADY', ''),
    ('Organic Cotton Produce Bags, 5-pk', 'ECOBAGS', 'US', 8.23, 21.99, 5.66, 35, 'SEASONAL', ''),
    ('Foaming Hand Soap, 10 oz', 'Bulk Apothecary', 'OH', 7.40, 21.99, 5.34, 32, 'STEADY', 'FAST'),
]

WC = [
    ('Hardcover Ruled Journal, 5.5x8.5', 'USA Custom Pad', 'NY', 7.25, 29.99, 12.34, 70, 'HOT', ''),
    ('Motivational Postcard Set, 20', 'StationeryHQ', 'CA', 5.00, 24.99, 11.59, 86, 'SEASONAL', 'FAST'),
    ('Large UltraHyde Casebound Journal', 'USA Custom Pad', 'NY', 10.98, 32.99, 11.54, 54, 'HOT', ''),
    ('Desktop Calendar, 8.5x5.5', 'PrintPPS', 'NM', 5.08, 24.99, 11.26, 82, 'HOT', 'FAST'),
    ('Hot Color Accent Journal', 'USA Custom Pad', 'NY', 4.99, 24.99, 10.80, 76, 'HOT', ''),
    ('Colored Bonded Leather Journal', 'USA Custom Pad', 'NY', 9.90, 29.99, 9.69, 48, 'SEASONAL', ''),
    ('Boxed Note Card Set, 10', 'Vervante', 'UT', 7.00, 24.99, 9.24, 59, 'SEASONAL', 'FAST'),
    ('Motivational Poster', 'Printful', 'US', 8.00, 24.99, 7.59, 44, 'STEADY', ''),
    ('Pebble-Grain Hardcover Journal', 'USA Custom Pad', 'NY', 7.33, 24.99, 7.31, 41, 'STEADY', ''),
    ('12-Month Motivational Planner', 'StationeryHQ', 'CA', 12.00, 29.99, 7.09, 31, 'HOT', ''),
    ('Wall Art Print Set, 3-piece', 'Printful', 'US', 12.00, 29.99, 7.09, 31, 'SEASONAL', ''),
    ('Motivational Sticker Sheets, 10', 'Sticker Mule', 'US', 3.00, 15.99, 6.74, 73, 'HOT', 'FAST'),
    ('Hardcover Sketchbook', 'StationeryHQ', 'CA', 10.50, 26.99, 6.69, 33, 'STEADY', ''),
    ('Gratitude Journal', 'StationeryHQ', 'CA', 9.00, 24.99, 6.34, 34, 'HOT', ''),
    ('Poly Spiral Journal w/ Pen Loop', 'USA Custom Pad', 'NY', 3.22, 16.99, 6.32, 59, 'STEADY', ''),
    ('Weekly Desk Pad', 'StationeryHQ', 'CA', 7.50, 21.99, 6.19, 39, 'STEADY', ''),
    ('Bookmark Set, 4-pack', 'StationeryHQ', 'CA', 2.50, 14.99, 6.09, 68, 'STEADY', ''),
    ('Lined Hardcover Journal', 'StationeryHQ', 'CA', 9.50, 24.99, 5.84, 31, 'HOT', ''),
    ('Habit Tracker Notebook', 'StationeryHQ', 'CA', 9.50, 24.99, 5.84, 31, 'STEADY', ''),
    ('Dot-Grid Notebook', 'StationeryHQ', 'CA', 8.50, 22.99, 5.39, 31, 'STEADY', ''),
]


def prod_rows(data):
    out = []
    for i, (name, sup, st, ws, ret, net, roi, dem, spd) in enumerate(data, 1):
        out.append([
            P(str(i), st_cell_c),
            P(name, st_cell_b),
            P('%s \u2014 %s' % (sup, st), st_cell),
            P('$%.2f' % ws, st_cell_r),
            P('$%.2f' % ret, st_cell_r),
            P('<b>$%.2f</b>' % net, st_cell_r),
            P('%d%%' % roi, st_cell_r),
            demand_chip(dem),
            speed_chip(spd),
        ])
    return out


HEAD = ['#', 'Product', 'Supplier \u2014 State', 'Wholesale', 'Retail', 'Net', 'ROI', 'Demand', 'Speed']
W = [0.32, 3.05, 1.70, 0.72, 0.66, 0.62, 0.50, 0.72, 0.50]
scale = USABLE / (sum(W) * inch)
CW = [w * inch * scale for w in W]


def build():
    doc = BaseDocTemplate('reports/Q4_Launch_Data_Package_Tyler_20261102.pdf',
                          pagesize=PAGE, leftMargin=LM, rightMargin=RM,
                          topMargin=TM, bottomMargin=BM,
                          title='Q4 Launch Data Package \u2014 Private Label & Slap',
                          author='Northstar OS')
    frame = Frame(LM, BM, USABLE, PAGE[1] - TM - BM, id='b',
                  leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
    doc.addPageTemplates([
        PageTemplate(id='cover', frames=[frame], onPage=cover_bg),
        PageTemplate(id='main', frames=[frame], onPage=lambda c, d: (bg(c, d), chrome(c, d, 'OVERVIEW'))),
        PageTemplate(id='mogra', frames=[frame], onPage=lambda c, d: (bg(c, d), chrome(c, d, 'MOGRA ORGANICS'))),
        PageTemplate(id='wc', frames=[frame], onPage=lambda c, d: (bg(c, d), chrome(c, d, 'WORD COFFEE'))),
        PageTemplate(id='risk', frames=[frame], onPage=lambda c, d: (bg(c, d), chrome(c, d, 'RISK & DECISION'))),
    ])

    F = []

    # ---------- COVER ----------
    F.append(Spacer(1, 1.20 * inch))
    F.append(P('Q4 LAUNCH DATA PACKAGE  \u00b7  PRIVATE LABEL &amp; SLAP', st_kick))
    F.append(Spacer(1, 0.18 * inch))
    F.append(P('23 Days<br/>to Black Friday', st_ctitle))
    F.append(Spacer(1, 0.22 * inch))
    F.append(P('Forty pre-packaged US SKUs, two launch candidates, and a $5,018 '
               'test budget. Prepared for Tyler \u2014 decision required today.', st_csub))
    F.append(Spacer(1, 0.40 * inch))
    chips = Table([[
        P('<font color="#D5A77A"><b>25 Nov</b></font> sellable', st_csub),
        P('<font color="#D5A77A"><b>$12.69</b></font> best net', st_csub),
        P('<font color="#D5A77A"><b>$5,018</b></font> test capital', st_csub),
        P('<font color="#9DBA8B"><b>250</b></font> units per SKU', st_csub),
    ]], colWidths=[USABLE / 4.0] * 4)
    chips.setStyle(TableStyle([('LEFTPADDING', (0, 0), (-1, -1), 0),
                               ('TOPPADDING', (0, 0), (-1, -1), 0)]))
    F.append(chips)
    F.append(NextPageTemplate('main'))
    F.append(PageBreak())

    # ---------- P2 EXEC BRIEF ----------
    F.append(P('The strategy in one page', st_h1))
    F.append(Spacer(1, 0.06 * inch))
    F.append(P('We are not manufacturing. We buy finished, retail-ready inventory already '
               'sitting in US warehouses, apply our brand and FNSKU labels at the supplier '
               'or a regional prep centre, and route direct to Amazon FBA. The 6\u201312 week '
               'co-packing cycle disappears. The trade-off is honest: we can customise the '
               'presentation, not the product. For a Q4 test, that is the right trade.', st_body))
    F.append(Spacer(1, 0.22 * inch))
    F.append(kpi([
        ('23', 'days to sellable', FOREST),
        ('40', 'SKUs modelled', AMBER),
        ('6', 'clear $10+ net', FOREST),
        ('$5k', 'total cash outlay', AMBER),
    ]))
    F.append(Spacer(1, 0.26 * inch))

    cmp_rows = [
        [P('Traditional private label', st_th), P('This sprint', st_th)],
        [P('6\u201312 weeks', st_cell), P('<b>23 days</b>', st_cell_b)],
        [P('MOQ 1,000\u20135,000 units', st_cell), P('<b>250\u2013500 units</b>', st_cell_b)],
        [P('Custom packaging tooling', st_cell), P('<b>Stock packaging + label</b>', st_cell_b)],
        [P('Capital $15k\u2013$50k', st_cell), P('<b>~$5,000</b>', st_cell_b)],
        [P('Risk: unsellable inventory', st_cell), P('<b>Risk: capped at 250 units/SKU</b>', st_cell_b)],
    ]
    t = Table(cmp_rows, colWidths=[USABLE * 0.25, USABLE * 0.25])
    t.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, 0), FOREST),
                           ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                           ('LEFTPADDING', (0, 0), (-1, -1), 8),
                           ('RIGHTPADDING', (0, 0), (-1, -1), 8),
                           ('TOPPADDING', (0, 0), (-1, -1), 4.5),
                           ('BOTTOMPADDING', (0, 0), (-1, -1), 4.5),
                           ('LINEBELOW', (0, 0), (-1, -1), 0.35, RULE)] +
                          [('BACKGROUND', (0, r), (-1, r), TINT) for r in (2, 4)]))

    side = [
        P('Why the 250-unit cap matters', st_h2),
        P('With no Amazon demand data available, this is a paid test rather than a forecast. '
          'At 250 units per SKU the maximum write-off is roughly $2,500 \u2014 survivable. '
          'At 1,000 units it is $10,000 and the downside stops being a test.', st_body_s),
        Spacer(1, 0.10 * inch),
        P('Demand evidence we do have', st_h2),
        P('Self-care journals sell 700\u20131,000 units/month at $29.99\u2013$39.95. The $20\u2013$50 '
          'band holds 40% of the self-care gift assortment. Etsy\u2019s F/W 2026 edit names '
          'greeting cards and calendars. All three point the same direction.', st_body_s),
    ]
    combo = Table([[t, side]], colWidths=[USABLE * 0.54, USABLE * 0.46])
    combo.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'TOP'),
                               ('LEFTPADDING', (0, 0), (-1, -1), 0),
                               ('RIGHTPADDING', (0, 0), (0, 0), 0.30 * inch),
                               ('RIGHTPADDING', (1, 0), (1, 0), 0)]))
    F.append(combo)

    # ---------- P3 CAPITAL ----------
    F.append(PageBreak())
    F.append(P('Capital forecast', st_h1))
    F.append(Spacer(1, 0.06 * inch))
    F.append(P('Two SKUs, 250 units each. Everything below is cash out before the first sale.', st_body))
    F.append(Spacer(1, 0.20 * inch))

    cap = [
        ['Line item', 'Amount'],
        ['Tea Tin \u2014 250 \u00d7 $5.60 wholesale', '$1,400'],
        ['Hardcover Journal \u2014 250 \u00d7 $7.25 wholesale', '$1,813'],
        ['Labels + prep (550 units incl. overrun)', '$250'],
        ['Inbound freight (2 lanes to FBA)', '$500'],
        ['Samples and proofs', '$150'],
        ['GS1 UPC registration', '$250'],
        ['Subtotal', '$4,363'],
        ['Contingency 15%', '$655'],
        ['TOTAL CASH OUTLAY', '$5,018'],
    ]
    body = []
    for i, r in enumerate(cap):
        if i == 0:
            body.append([P(r[0], st_th), P(r[1], st_th_r)])
        elif r[0].startswith('TOTAL'):
            body.append([P('<b>%s</b>' % r[0], st_cell_b), P('<b>%s</b>' % r[1], st_cell_b)])
        elif r[0] == 'Subtotal':
            body.append([P('<b>%s</b>' % r[0], st_cell_b), P('<b>%s</b>' % r[1], st_cell_b)])
        else:
            body.append([P(r[0], st_cell), P(r[1], st_cell_r)])
    t = Table(body, colWidths=[USABLE * 0.42, USABLE * 0.16])
    t.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, 0), FOREST),
                           ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                           ('LEFTPADDING', (0, 0), (-1, -1), 8),
                           ('RIGHTPADDING', (0, 0), (-1, -1), 8),
                           ('TOPPADDING', (0, 0), (-1, -1), 4.4),
                           ('BOTTOMPADDING', (0, 0), (-1, -1), 4.4),
                           ('LINEBELOW', (0, 0), (-1, -1), 0.35, RULE),
                           ('BACKGROUND', (0, 7), (-1, 7), TINT),
                           ('BACKGROUND', (0, 9), (-1, 9), colors.HexColor('#E8EDE4')),
                           ('LINEABOVE', (0, 9), (-1, 9), 1.0, FOREST)]))

    ret = [
        ['100% sell-through', 'Value'],
        ['Gross revenue (500 units)', '$14,995'],
        ['Total landed cost of goods', '$8,650'],
        ['Gross profit', '$6,258'],
        ['Less one-time costs', '$1,055'],
        ['Net profit on the test', '~$5,200'],
        ['Blended ROI on cash', '~104%'],
    ]
    rb = []
    for i, r in enumerate(ret):
        if i == 0:
            rb.append([P(r[0], st_th), P(r[1], st_th_r)])
        else:
            rb.append([P(r[0], st_cell), P(r[1], st_cell_r)])
    rt = Table(rb, colWidths=[USABLE * 0.26, USABLE * 0.14])
    rt.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, 0), COFFEE),
                            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                            ('LEFTPADDING', (0, 0), (-1, -1), 8),
                            ('RIGHTPADDING', (0, 0), (-1, -1), 8),
                            ('TOPPADDING', (0, 0), (-1, -1), 4.4),
                            ('BOTTOMPADDING', (0, 0), (-1, -1), 4.4),
                            ('LINEBELOW', (0, 0), (-1, -1), 0.35, RULE),
                            ('BACKGROUND', (0, 6), (-1, 6), colors.HexColor('#F0E8DC'))]))

    pair = Table([[t, rt]], colWidths=[USABLE * 0.62, USABLE * 0.38])
    pair.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'TOP'),
                              ('LEFTPADDING', (0, 0), (-1, -1), 0),
                              ('RIGHTPADDING', (0, 0), (0, 0), 0.20 * inch),
                              ('RIGHTPADDING', (1, 0), (1, 0), 0)]))
    F.append(pair)
    F.append(Spacer(1, 0.18 * inch))
    F.append(P('<b>Downside case:</b> at 50% sell-through, revenue is $7,498 and gross profit '
               '~$3,129 \u2014 the cash outlay is still recovered. The 250-unit cap is what makes '
               'the downside survivable.', st_note))

    # ---------- P4 SKU 1 ----------
    F.append(PageBreak())
    F.append(P('SKU 1 \u2014 Mogro Organics', st_h1))
    F.append(Spacer(1, 0.02 * inch))
    F.append(P('Organic Herbal Tea Tin \u00b7 30 pyramid sachets, 6 oz steel tin \u00b7 '
               'Adagio XL, Berkeley CA \u00b7 5\u20137 days \u00b7 labels printed in-house', st_body))
    F.append(Spacer(1, 0.18 * inch))

    econ1 = [
        ['Line', 'Amount', '% retail'],
        ['Retail price', '$29.99', '100%'],
        ['\u2212 Wholesale', '$5.60', '18.7%'],
        ['\u2212 Label / prep', '$0.40', '1.3%'],
        ['\u2212 Inbound freight', '$0.30', '1.0%'],
        ['\u2212 Amazon referral (15%)', '$4.50', '15.0%'],
        ['\u2212 Amazon FBA (1.3 lb)', '$6.50', '21.7%'],
        ['= NET PROFIT', '$12.69', '42.3%'],
        ['ROI on cost', '73.4%', '\u2014'],
    ]
    eb = []
    for i, r in enumerate(econ1):
        if i == 0:
            eb.append([P(r[0], st_th), P(r[1], st_th_r), P(r[2], st_th_r)])
        elif r[0].startswith('='):
            eb.append([P('<b>%s</b>' % r[0], st_cell_b), P('<b>%s</b>' % r[1], st_cell_b),
                       P('<b>%s</b>' % r[2], st_cell_b)])
        else:
            eb.append([P(r[0], st_cell), P(r[1], st_cell_r), P(r[2], st_cell_r)])
    et = Table(eb, colWidths=[USABLE * 0.26, USABLE * 0.12, USABLE * 0.10])
    et.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, 0), FOREST),
                            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                            ('LEFTPADDING', (0, 0), (-1, -1), 7),
                            ('RIGHTPADDING', (0, 0), (-1, -1), 7),
                            ('TOPPADDING', (0, 0), (-1, -1), 3.8),
                            ('BOTTOMPADDING', (0, 0), (-1, -1), 3.8),
                            ('LINEBELOW', (0, 0), (-1, -1), 0.35, RULE),
                            ('BACKGROUND', (0, 7), (-1, 7), colors.HexColor('#E8EDE4')),
                            ('LINEABOVE', (0, 7), (-1, 7), 1.0, FOREST)]))

    segs = [('Wholesale', 5.60, SAGE), ('Prep', 0.40, CREAM),
            ('Freight', 0.30, KRAFT), ('Referral', 4.50, AMBER),
            ('FBA', 6.50, COFFEE), ('Net', 12.69, FOREST)]

    ev1 = [
        P('Demand evidence', st_h2),
        P('\u2022 Named in 2026 wellness gifting analysis as \u201cthe softer entry point '
          'with broad appeal\u201d', st_body_s),
        P('\u2022 \u201cRitual gifts, not gadget gifts\u201d \u2014 tea is the clearest example',
          st_body_s),
        P('\u2022 The $20\u2013$50 band holds 40% of the self-care gift assortment', st_body_s),
        Spacer(1, 0.14 * inch),
        P('Why it wins operationally', st_h2),
        P('Adagio prints our label themselves. That eliminates the 2\u20133 day label-transit '
          'leg that threatens every other SKU on this list \u2014 the shortest critical path '
          'we found.', st_body_s),
    ]
    pair1 = Table([[et, ev1]], colWidths=[USABLE * 0.52, USABLE * 0.48])
    pair1.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'TOP'),
                               ('LEFTPADDING', (0, 0), (-1, -1), 0),
                               ('RIGHTPADDING', (0, 0), (0, 0), 0.30 * inch),
                               ('RIGHTPADDING', (1, 0), (1, 0), 0)]))
    F.append(pair1)

    F.append(Spacer(1, 0.30 * inch))
    F.append(P('Where the $29.99 goes', st_h2))
    F.append(Spacer(1, 0.05 * inch))
    F.append(bridge(29.99, segs, USABLE, 0.72 * inch))
    F.append(legend([('Wholesale', SAGE), ('Prep', CREAM), ('Freight', KRAFT),
                     ('Referral', AMBER), ('FBA', COFFEE), ('Net profit', FOREST)],
                    USABLE))

    # ---------- P5 SKU 2 ----------
    F.append(PageBreak())
    F.append(P('SKU 2 \u2014 Word Coffee', st_h1))
    F.append(Spacer(1, 0.02 * inch))
    F.append(P('Hardcover Ruled Journal \u00b7 5.5" \u00d7 8.5", 160 pages, casebound \u00b7 '
               'USA Custom Pad, Sidney NY \u00b7 7 business days', st_body))
    F.append(Spacer(1, 0.18 * inch))

    econ2 = [
        ['Line', 'Amount', '% retail'],
        ['Retail price', '$29.99', '100%'],
        ['\u2212 Wholesale', '$7.25', '24.2%'],
        ['\u2212 Label / prep', '$0.45', '1.5%'],
        ['\u2212 Inbound freight', '$0.25', '0.8%'],
        ['\u2212 Amazon referral (15%)', '$4.50', '15.0%'],
        ['\u2212 Amazon FBA (0.8 lb)', '$5.20', '17.3%'],
        ['= NET PROFIT', '$12.34', '41.2%'],
        ['ROI on cost', '69.9%', '\u2014'],
    ]
    eb = []
    for i, r in enumerate(econ2):
        if i == 0:
            eb.append([P(r[0], st_th), P(r[1], st_th_r), P(r[2], st_th_r)])
        elif r[0].startswith('='):
            eb.append([P('<b>%s</b>' % r[0], st_cell_b), P('<b>%s</b>' % r[1], st_cell_b),
                       P('<b>%s</b>' % r[2], st_cell_b)])
        else:
            eb.append([P(r[0], st_cell), P(r[1], st_cell_r), P(r[2], st_cell_r)])
    et2 = Table(eb, colWidths=[USABLE * 0.26, USABLE * 0.12, USABLE * 0.10])
    et2.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, 0), COFFEE),
                             ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                             ('LEFTPADDING', (0, 0), (-1, -1), 7),
                             ('RIGHTPADDING', (0, 0), (-1, -1), 7),
                             ('TOPPADDING', (0, 0), (-1, -1), 3.8),
                             ('BOTTOMPADDING', (0, 0), (-1, -1), 3.8),
                             ('LINEBELOW', (0, 0), (-1, -1), 0.35, RULE),
                             ('BACKGROUND', (0, 7), (-1, 7), colors.HexColor('#E8EDE4')),
                             ('LINEABOVE', (0, 7), (-1, 7), 1.0, FOREST)]))
    segs2 = [('Wholesale', 7.25, SAGE), ('Prep', 0.45, CREAM),
             ('Freight', 0.25, KRAFT), ('Referral', 4.50, AMBER),
             ('FBA', 5.20, COFFEE), ('Net', 12.34, FOREST)]

    flag = Table([[
        P('<b>One flag for Tyler</b><br/><br/>'
          'USA Custom Pad quotes <b>7 business days</b> \u2014 exactly at the boundary of the '
          'under-7-day rule. If that is a hard gate, swap to:<br/><br/>'
          '<b>Desktop Calendar \u2014 PrintPPS, Albuquerque NM</b><br/>'
          '$11.26 net \u00b7 MOQ 1 \u00b7 <b>ships in 1 business day</b><br/><br/>'
          'Fastest supplier in the dataset, and still clears $11 net.', st_body_s)
    ]], colWidths=[USABLE * 0.44])
    flag.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, -1), WHITE),
                              ('LINEBEFORE', (0, 0), (0, 0), 3.0, AMBER),
                              ('LEFTPADDING', (0, 0), (-1, -1), 13),
                              ('RIGHTPADDING', (0, 0), (-1, -1), 13),
                              ('TOPPADDING', (0, 0), (-1, -1), 10),
                              ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
                              ('BOX', (0, 0), (-1, -1), 0.5, RULE)]))
    pair2 = Table([[et2, flag]], colWidths=[USABLE * 0.52, USABLE * 0.48])
    pair2.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'TOP'),
                               ('LEFTPADDING', (0, 0), (-1, -1), 0),
                               ('RIGHTPADDING', (0, 0), (0, 0), 0.30 * inch),
                               ('RIGHTPADDING', (1, 0), (1, 0), 0)]))
    F.append(pair2)

    F.append(Spacer(1, 0.30 * inch))
    F.append(P('Where the $29.99 goes', st_h2))
    F.append(Spacer(1, 0.05 * inch))
    F.append(bridge(29.99, segs2, USABLE, 0.72 * inch))
    F.append(legend([('Wholesale', SAGE), ('Prep', CREAM), ('Freight', KRAFT),
                     ('Referral', AMBER), ('FBA', COFFEE), ('Net profit', FOREST)],
                    USABLE))

    # ---------- P6 MOGRA TABLE ----------
    F.append(NextPageTemplate('mogra'))
    F.append(PageBreak())
    F.append(P('Mogro Organics \u2014 20 products', st_h1))
    F.append(Spacer(1, 0.04 * inch))
    F.append(P('Ranked by net profit per unit. Average net $7.24 \u00b7 top three average $10.51.', st_body))
    F.append(Spacer(1, 0.14 * inch))
    F.append(data_table(prod_rows(MOGRA), CW, HEAD, FOREST))
    F.append(Spacer(1, 0.10 * inch))
    F.append(P('Demand: HOT = documented velocity \u00b7 SEASONAL = holiday tailwind \u00b7 '
               'STEADY = unproven. Speed: FAST = supplier ships under 5 days. '
               'Eight bulk-only herb suppliers were excluded \u2014 they will not apply labels.', st_note))

    # ---------- P7 WC TABLE ----------
    F.append(NextPageTemplate('wc'))
    F.append(PageBreak())
    F.append(P('Word Coffee \u2014 20 products', st_h1))
    F.append(Spacer(1, 0.04 * inch))
    F.append(P('Ranked by net profit per unit. Average net $8.31 \u00b7 top three average $11.82 \u00b7 '
               'six SKUs clear $10.', st_body))
    F.append(Spacer(1, 0.14 * inch))
    F.append(data_table(prod_rows(WC), CW, HEAD, COFFEE))
    F.append(Spacer(1, 0.10 * inch))
    F.append(P('Six of the top ten paper SKUs come from a single supplier \u2014 USA Custom Pad, '
               'Sidney NY \u2014 at 40\u201360% below the print-on-demand players. That one '
               'relationship carries the paper margin.', st_note))

    # ---------- P8 RISK ----------
    F.append(NextPageTemplate('risk'))
    F.append(PageBreak())
    F.append(P('Risk and mitigation', st_h1))
    F.append(Spacer(1, 0.14 * inch))
    risks = [
        ('Gated Amazon data',
         'No BSR, review count or search volume. Demand is inferred.',
         'Cap initial inventory at 250 units per SKU. Lean on Etsy F/W 2026, Walmart Holiday '
         'Report and Faire velocity. Treat launch as a paid test, not a forecast.'),
        ('Label transit bottleneck',
         '2\u20133 days we do not have.',
         'Restrict vendor selection to suppliers with in-house or under-3-day printing: '
         'Adagio, PrintPPS, Vervante, Sugar \u2019N Spice. Reject any shipped-label vendor.'),
        ('Bulk-only suppliers',
         'Will sell material but not sticker it.',
         'Explicitly exclude Mountain Rose, Starwest, Frontier, Monterey Bay, SF Herb, '
         'Spicy Organic, Organic Spices and Vanns from the Q4 sprint.'),
        ('FNSKU barcode fails to scan',
         'We supply the barcode \u2014 its quality is our liability.',
         'Print one physical sample and scan it with a phone before ordering 550 labels. '
         'This is the cheapest possible insurance.'),
        ('Supplier refuses to sticker',
         'Expect roughly one in three to decline sealed retail units.',
         'Confirm in writing before ordering labels. Fallback: regional prep centre, '
         'adding 2 days and $0.60 per unit.'),
        ('Black Friday missed',
         'Amazon receiving runs 7\u201310 days in late November.',
         'Ship by 16 November. If a supplier slips past 6 November, switch supplier \u2014 '
         'not the date.'),
        ('Price position mismatch',
         'The 3-wick candle lists at $34.99 against a $19.95 market median.',
         'Do not lead with the candle. Lead with ritual gifts where our price sits at '
         'market, not above it.'),
        ('Organic claim unverifiable',
         'Applies to tea and spice specifically.',
         'Request the organic certificate and transaction certificate before listing.'),
    ]
    hdr = [P('Risk', st_th), P('Why it matters', st_th), P('Mitigation', st_th)]
    body = [hdr]
    for r in risks:
        body.append([P('<b>%s</b>' % r[0], st_cell_b), P(r[1], st_cell), P(r[2], st_cell)])
    t = Table(body, colWidths=[1.75 * inch, 2.55 * inch, USABLE - 4.30 * inch])
    t.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, 0), FOREST),
                           ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                           ('LEFTPADDING', (0, 0), (-1, -1), 7),
                           ('RIGHTPADDING', (0, 0), (-1, -1), 7),
                           ('TOPPADDING', (0, 0), (-1, -1), 5),
                           ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
                           ('LINEBELOW', (0, 0), (-1, -1), 0.35, RULE)] +
                          [('BACKGROUND', (0, r), (-1, r), TINT)
                           for r in range(2, len(body), 2)]))
    F.append(t)

    # ---------- P9 DECISION ----------
    F.append(PageBreak())
    F.append(P('Decision required today', st_h1))
    F.append(Spacer(1, 0.05 * inch))
    F.append(P('Three approvals unlock the entire critical path. Nothing downstream can '
               'start until all three are signed.', st_body))
    F.append(Spacer(1, 0.20 * inch))

    steps = [
        ('01', 'Authorise the two SKUs',
         'Organic Herbal Tea Tin (Adagio XL, CA) and Hardcover Ruled Journal (USA Custom Pad, NY). '
         'Or approve the Desktop Calendar swap if under-7-day turnaround is non-negotiable.'),
        ('02', 'Approve sample and PO wire spend',
         '$5,018 total cash outlay \u2014 500 units, labels, freight, GS1 registration and 15% contingency.'),
        ('03', 'Sign off on immediate listing creation',
         'FNSKU barcodes must exist before the label artwork is finalised. This is the hard '
         'dependency that gates everything else.'),
    ]
    for num, title, body in steps:
        blk = Table([[
            P(num, ParagraphStyle('z%s' % num, fontName='Times-Bold', fontSize=22,
                                  leading=25, textColor=KRAFT)),
            [P('<b>%s</b>' % title, st_cell_b), Spacer(1, 0.02 * inch), P(body, st_note)]]],
            colWidths=[0.62 * inch, USABLE - 0.62 * inch])
        blk.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'TOP'),
                                 ('LEFTPADDING', (0, 0), (-1, -1), 0),
                                 ('BOTTOMPADDING', (0, 0), (-1, 0), 9),
                                 ('LINEBELOW', (0, 0), (-1, 0), 0.35, RULE)]))
        F.append(blk)

    F.append(Spacer(1, 0.18 * inch))
    F.append(P('Critical path from approval', st_h2))
    F.append(Spacer(1, 0.06 * inch))

    tl = [('2\u20134 Nov', 'Lock SKUs\nCreate listings\nGenerate FNSKU'),
          ('5\u20136 Nov', 'Artwork +\nFNSKU to\nlabel vendor'),
          ('7\u20139 Nov', 'Labels\nprinted and\nshipped'),
          ('10\u201313 Nov', 'Supplier\napplies\nstickers'),
          ('14\u201316 Nov', 'Carrier\npickup,\nin transit'),
          ('17\u201320 Nov', 'Delivered\nto FC'),
          ('21\u201325 Nov', 'Receiving\ncomplete\nSELLABLE')]
    cells, style = [], [('VALIGN', (0, 0), (-1, -1), 'TOP'),
                        ('LEFTPADDING', (0, 0), (-1, -1), 7),
                        ('RIGHTPADDING', (0, 0), (-1, -1), 7),
                        ('TOPPADDING', (0, 0), (-1, -1), 8),
                        ('BOTTOMPADDING', (0, 0), (-1, -1), 9)]
    row = []
    for i, (date, txt) in enumerate(tl):
        col = FOREST if i == len(tl) - 1 else WHITE
        fg = WHITE if i == len(tl) - 1 else INK
        inner = [Paragraph('<font color="%s"><b>%s</b></font>' % (hexc(KRAFT if i < len(tl)-1 else OLIVE), date),
                           ParagraphStyle('d%d' % i, fontName='Helvetica-Bold', fontSize=7.2,
                                          leading=9)),
                 Spacer(1, 0.04 * inch),
                 Paragraph(txt.replace('\n', '<br/>'),
                           ParagraphStyle('t%d' % i, fontName='Helvetica', fontSize=7,
                                          leading=9.4, textColor=fg))]
        row.append(inner)
        style += [('BACKGROUND', (i, 0), (i, 0), col),
                  ('BOX', (i, 0), (i, 0), 0.5, RULE if i < len(tl)-1 else FOREST)]
    t = Table([row], colWidths=[USABLE / 7.0] * 7)
    t.setStyle(TableStyle(style))
    F.append(t)

    doc.build(F)
    print('PDF written.')


if __name__ == '__main__':
    build()
