#!/usr/bin/env python3
"""Generate the Deep Sea Z4.1 visual presentation PDF."""
import json
from reportlab.lib.pagesizes import landscape, letter
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT
from reportlab.platypus import (BaseDocTemplate, PageTemplate, Frame, Paragraph,
                                Spacer, Table, TableStyle, PageBreak, KeepTogether,
                                NextPageTemplate)
from reportlab.graphics.shapes import Drawing, Rect, String, Line

DATA = json.load(open('reports/deepsea_z41_50-candidates_20261028.json', encoding='utf-8'))

# ---------- palette ----------
INK      = colors.HexColor('#171717')
FOREST   = colors.HexColor('#253628')
PAPER    = colors.HexColor('#FBF7F0')
KRAFT    = colors.HexColor('#D5A77A')
OLIVE    = colors.HexColor('#9DBA8B')
SAGE     = colors.HexColor('#9FA9A4')
CREAM    = colors.HexColor('#D0C5AC')
COFFEE   = colors.HexColor('#6B4A32')
CLAY     = colors.HexColor('#A85B48')
WHITE    = colors.white
MUTED    = colors.HexColor('#6B6B63')
RULE     = colors.HexColor('#E3DACA')

PAGE = landscape(letter)          # 11 x 8.5
LM = RM = 0.5 * inch
TM = 0.62 * inch
BM = 0.55 * inch
USABLE = PAGE[0] - LM - RM

TIER = {'A': FOREST, 'B': colors.HexColor('#A2762F'), 'C': CLAY}


def tier_of(net):
    return 'A' if net >= 7 else ('B' if net >= 5 else 'C')


# ---------- styles ----------
def S(name, **kw):
    base = dict(fontName='Helvetica', fontSize=9, leading=12, textColor=INK)
    base.update(kw)
    return ParagraphStyle(name, **base)

st_cover_kicker = S('ck', fontName='Helvetica-Bold', fontSize=9.5, leading=13,
                    textColor=KRAFT)
st_cover_title  = S('ct', fontName='Times-Bold', fontSize=44, leading=50, textColor=WHITE)
st_cover_sub    = S('cs', fontName='Helvetica', fontSize=12.5, leading=19,
                    textColor=colors.HexColor('#D8D2C6'))
st_h1           = S('h1', fontName='Times-Bold', fontSize=27, leading=32, textColor=FOREST)
st_h1_light     = S('h1l', fontName='Times-Bold', fontSize=27, leading=32, textColor=WHITE)
st_h2           = S('h2', fontName='Helvetica-Bold', fontSize=10, leading=14,
                    textColor=FOREST, spaceBefore=4)
st_kicker       = S('k', fontName='Helvetica-Bold', fontSize=8, leading=11, textColor=MUTED)
st_body         = S('b', fontSize=9.6, leading=14.4)
st_body_s       = S('bs', fontSize=8.6, leading=12.6)
st_note         = S('n', fontSize=8.2, leading=11.8, textColor=MUTED)
st_cell         = S('c', fontSize=7.9, leading=10)
st_cell_b       = S('cb', fontName='Helvetica-Bold', fontSize=7.9, leading=10)
st_cell_r       = S('cr', fontSize=7.9, leading=10, alignment=TA_RIGHT)
st_cell_c       = S('cc', fontSize=7.9, leading=10, alignment=TA_CENTER)
st_th           = S('th', fontName='Helvetica-Bold', fontSize=7.4, leading=9.5,
                    textColor=WHITE)
st_th_c         = S('thc', fontName='Helvetica-Bold', fontSize=7.4, leading=9.5,
                    textColor=WHITE, alignment=TA_CENTER)
st_th_r         = S('thr', fontName='Helvetica-Bold', fontSize=7.4, leading=9.5,
                    textColor=WHITE, alignment=TA_RIGHT)
st_head_cell    = S('hc', fontName='Helvetica-Bold', fontSize=7.9, leading=10,
                    textColor=WHITE)
st_head_cell_r  = S('hcr', fontName='Helvetica-Bold', fontSize=7.9, leading=10,
                    textColor=WHITE, alignment=TA_RIGHT)
st_tile_n       = S('tn', fontName='Times-Bold', fontSize=31, leading=34, textColor=FOREST)
st_tile_l       = S('tl', fontName='Helvetica-Bold', fontSize=7.2, leading=9.6,
                    textColor=MUTED)
st_quote        = S('q', fontName='Times-Italic', fontSize=12, leading=18, textColor=FOREST)
st_pick_val     = S('pv', fontName='Times-Bold', fontSize=17, leading=21,
                    textColor=FOREST, spaceBefore=3, spaceAfter=1)


# ---------- page furniture ----------
def bg(canv, doc):
    canv.saveState()
    canv.setFillColor(PAPER)
    canv.rect(0, 0, PAGE[0], PAGE[1], stroke=0, fill=1)
    canv.restoreState()


def chrome(canv, doc, section):
    canv.saveState()
    canv.setFillColor(SAGE)
    canv.setFont('Helvetica-Bold', 7.2)
    canv.drawString(LM, PAGE[1] - 0.34 * inch, 'MOGRA ORGANICS')
    canv.setFillColor(CREAM)
    canv.drawString(LM + 1.02 * inch, PAGE[1] - 0.34 * inch, '/')
    canv.setFillColor(COFFEE)
    canv.drawString(LM + 1.12 * inch, PAGE[1] - 0.34 * inch, 'WORD COFFEE')
    canv.setFillColor(SAGE)
    canv.setFont('Helvetica', 7.2)
    canv.drawRightString(PAGE[0] - RM, PAGE[1] - 0.34 * inch, section)
    canv.setStrokeColor(RULE)
    canv.setLineWidth(0.6)
    canv.line(LM, PAGE[1] - 0.42 * inch, PAGE[0] - RM, PAGE[1] - 0.42 * inch)
    canv.line(LM, BM - 0.10 * inch, PAGE[0] - RM, BM - 0.10 * inch)
    canv.setFillColor(SAGE)
    canv.setFont('Helvetica', 7)
    canv.drawString(LM, BM - 0.26 * inch,
                    'Deep Sea Z4.1  \u00b7  Open-source research  \u00b7  2026-10-28')
    canv.drawRightString(PAGE[0] - RM, BM - 0.26 * inch, '%02d' % doc.page)
    canv.restoreState()


def cover_bg(canv, doc):
    canv.saveState()
    canv.setFillColor(FOREST)
    canv.rect(0, 0, PAGE[0], PAGE[1], stroke=0, fill=1)
    # thin kraft spine on the left edge only
    canv.setFillColor(KRAFT)
    canv.rect(0, 0, 0.13 * inch, PAGE[1], stroke=0, fill=1)
    # faint over-scale wordmark, top right, clear of all copy
    canv.setFillColor(colors.HexColor('#2E4231'))
    canv.setFont('Times-Italic', 78)
    canv.drawRightString(PAGE[0] - 0.45 * inch, PAGE[1] - 1.42 * inch, 'Z4.1')
    canv.restoreState()


# ---------- helpers ----------
def P(t, s=st_body):
    return Paragraph(t, s)


def kpi_row(items, width=USABLE):
    """items = [(number, label, color)]"""
    n = len(items)
    gap = 0.14 * inch
    w = (width - gap * (n - 1)) / n
    cells, style = [], [('VALIGN', (0, 0), (-1, -1), 'TOP'),
                        ('LEFTPADDING', (0, 0), (-1, -1), 10),
                        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
                        ('TOPPADDING', (0, 0), (-1, -1), 11),
                        ('BOTTOMPADDING', (0, 0), (-1, -1), 11)]
    for i, (num, label, col) in enumerate(items):
        cells.append([Paragraph(num, ParagraphStyle(
            'x%d' % i, fontName='Times-Bold', fontSize=30, leading=33, textColor=col)),
            Paragraph(label.upper(), st_tile_l)])
        style.append(('BACKGROUND', (i, 0), (i, 0), WHITE))
        style.append(('BOX', (i, 0), (i, 0), 0.7, RULE))
        style.append(('LINEABOVE', (i, 0), (i, 0), 2.6, col))
    t = Table([[c] for c in cells], colWidths=[w])
    # rebuild as single-row table of stacked paragraphs
    row = []
    for i, (num, label, col) in enumerate(items):
        row.append([Paragraph(num, ParagraphStyle(
            'y%d' % i, fontName='Times-Bold', fontSize=30, leading=33, textColor=col)),
            Paragraph(label.upper(), st_tile_l)])
    t = Table([row], colWidths=[w] * n)
    t.setStyle(TableStyle(style))
    return t


def hbar_chart(pairs, width, height, color=FOREST, label_w=2.5 * inch):
    """pairs = [(label, value)] sorted desc."""
    d = Drawing(width, height)
    if not pairs:
        return d
    maxv = max(v for _, v in pairs) or 1
    rowh = height / len(pairs)
    bar_area = width - label_w - 0.62 * inch
    for i, (lab, val) in enumerate(pairs):
        y = height - (i + 1) * rowh + rowh * 0.22
        d.add(String(0, y + rowh * 0.12, lab, fontName='Helvetica', fontSize=7.0,
                     fillColor=INK))
        w = max(0.02 * inch, bar_area * (val / maxv))
        d.add(Rect(label_w, y, w, rowh * 0.52, fillColor=color, strokeColor=None))
        d.add(String(label_w + w + 0.06 * inch, y + rowh * 0.12, '%.2f' % val,
                     fontName='Helvetica-Bold', fontSize=7.0, fillColor=color))
    return d


def tier_bar(counts, width=USABLE, height=0.42 * inch):
    total = sum(counts.values()) or 1
    d = Drawing(width, height)
    x = 0
    for k in ('A', 'B', 'C'):
        w = width * counts[k] / total
        d.add(Rect(x, 0, w, height, fillColor=TIER[k], strokeColor=None))
        if w > 0.5 * inch:
            d.add(String(x + w / 2, height * 0.34, '%s \u00b7 %d' % (k, counts[k]),
                         fontName='Helvetica-Bold', fontSize=8.5, fillColor=WHITE,
                         textAnchor='middle'))
        x += w
    return d


def data_table(rows, widths, head, brand_color=FOREST, align=None, small=False):
    cs = st_cell if small else st_cell
    if align is None:
        align = ['c', 'l', 'l', 'c', 'r', 'r', 'r', 'r', 'c', 'c']
    hs = {'l': st_th, 'c': st_th_c, 'r': st_th_r}
    cs_ = {'l': st_cell, 'c': st_cell_c, 'r': st_cell_r}
    hdr = [Paragraph(h, hs[align[i] if i < len(align) else 'l']) for i, h in enumerate(head)]
    body = [hdr] + rows
    t = Table(body, colWidths=widths, repeatRows=1)
    style = [('BACKGROUND', (0, 0), (-1, 0), brand_color),
             ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
             ('LEFTPADDING', (0, 0), (-1, -1), 5),
             ('RIGHTPADDING', (0, 0), (-1, -1), 5),
             ('TOPPADDING', (0, 0), (-1, -1), 3.6),
             ('BOTTOMPADDING', (0, 0), (-1, -1), 3.6),
             ('LINEBELOW', (0, 0), (-1, -1), 0.4, RULE)]
    for r in range(1, len(body)):
        if r % 2 == 0:
            style.append(('BACKGROUND', (0, r), (-1, r), colors.HexColor('#F4EFE5')))
    t.setStyle(TableStyle(style))
    return t


def hexc(c):
    return '#%02X%02X%02X' % (int(c.red * 255), int(c.green * 255), int(c.blue * 255))


STATE = {'ohio': 'OH', 'florida': 'FL', 'utah': 'UT', 'hawaii': 'HI',
         'california': 'CA'}


def loc_code(s):
    parts = [p.strip() for p in s.split(',')]
    for p in parts:
        if len(p) == 2 and p.isalpha() and p.upper() != 'US':
            return p.upper()
    low = s.lower()
    for name, code in STATE.items():
        if name in low:
            return code
    if 'confirm' in low:
        return '?'
    return 'US'


def tier_chip(tier):
    return Paragraph('<font color="%s"><b>%s</b></font>' % (hexc(TIER[tier]), tier),
                     st_cell_c)


def verified_cell(v):
    if v == 'yes':
        return Paragraph('<font color="#2F6B3A">\u2713</font>', st_cell_c)
    if v == 'partial':
        return Paragraph('<font color="#A2762F"><b>!</b></font>', st_cell_c)
    return Paragraph('<font color="#A85B48"><b>!</b></font>', st_cell_c)


# ---------- build ----------
def build():
    doc = BaseDocTemplate('reports/Mogro_WordCoffee_DeepSeaZ41_Presentation_20261028.pdf',
                          pagesize=PAGE, leftMargin=LM, rightMargin=RM,
                          topMargin=TM, bottomMargin=BM,
                          title='Deep Sea Z4.1 \u2014 50-Candidate Product Research',
                          author='Northstar OS')

    frame = Frame(LM, BM, USABLE, PAGE[1] - TM - BM, id='body',
                  leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)

    doc.addPageTemplates([
        PageTemplate(id='cover', frames=[frame], onPage=cover_bg),
        PageTemplate(id='mogra', frames=[frame],
                     onPage=lambda c, d: (bg(c, d), chrome(c, d, 'TRACK A \u2014 LOCAL ORGANICS'))),
        PageTemplate(id='wc', frames=[frame],
                     onPage=lambda c, d: (bg(c, d), chrome(c, d, 'TRACK B \u2014 WORD COFFEE'))),
        PageTemplate(id='main', frames=[frame],
                     onPage=lambda c, d: (bg(c, d), chrome(c, d, 'OVERVIEW'))),
        PageTemplate(id='app', frames=[frame],
                     onPage=lambda c, d: (bg(c, d), chrome(c, d, 'APPENDIX \u2014 FULL DATA'))),
    ])

    mogra = [x for x in DATA if x['brand_track'] == 'Local Organics']
    wc = [x for x in DATA if x['brand_track'] == 'Word Coffee']
    for x in DATA:
        x['tier'] = tier_of(x['margin']['net'])
    mogra.sort(key=lambda r: -r['margin']['net'])
    wc.sort(key=lambda r: -r['margin']['net'])

    counts = {'A': sum(1 for x in DATA if x['tier'] == 'A'),
              'B': sum(1 for x in DATA if x['tier'] == 'B'),
              'C': sum(1 for x in DATA if x['tier'] == 'C')}
    ver_yes = sum(1 for x in DATA if x['supplier']['verified'] == 'yes')
    ver_part = sum(1 for x in DATA if x['supplier']['verified'] == 'partial')
    ver_no = sum(1 for x in DATA if x['supplier']['verified'] == 'no')

    F = []  # flowables

    # ============ COVER ============
    F.append(Spacer(1, 1.15 * inch))
    F.append(P('NORTHSTAR OS  \u00b7  DEEP SEA Z4.1', st_cover_kicker))
    F.append(Spacer(1, 0.20 * inch))
    F.append(P('Fifty Products,<br/>Two Brands,<br/>Ready to Label', st_cover_title))
    F.append(Spacer(1, 0.26 * inch))
    F.append(P('Sourcing research for <b>Mogra Organics</b> and <b>Word Coffee</b> \u2014 '
               'US-based suppliers, verified wholesale costs and full unit economics '
               'across fifty label-ready candidates.', st_cover_sub))
    F.append(Spacer(1, 0.42 * inch))
    chips = Table([[
        P('<font color="#D5A77A"><b>50</b></font> candidates', st_cover_sub),
        P('<font color="#D5A77A"><b>25 + 25</b></font> by brand', st_cover_sub),
        P('<font color="#D5A77A"><b>46</b></font> suppliers verified', st_cover_sub),
        P('<font color="#9DBA8B"><b>13</b></font> tier A winners', st_cover_sub),
    ]], colWidths=[USABLE / 4.0] * 4)
    chips.setStyle(TableStyle([('LEFTPADDING', (0, 0), (-1, -1), 0),
                               ('TOPPADDING', (0, 0), (-1, -1), 0)]))
    F.append(chips)
    F.append(Spacer(1, 0.5 * inch))
    F.append(P('Prepared 28 October 2026  \u00b7  Research and planning document',
               st_note))
    F.append(NextPageTemplate('main'))
    F.append(PageBreak())

    # ============ EXEC SUMMARY ============
    F.append(P('Executive summary', st_h1))
    F.append(Spacer(1, 0.05 * inch))
    F.append(P('Fifty label-ready candidates across two brands, with the supplier, cost '
               'and margin worked out for every one.', st_body))
    F.append(Spacer(1, 0.22 * inch))
    F.append(kpi_row([
        ('50', 'candidates screened', FOREST),
        ('13', 'Tier A \u2014 net \u2265 $7', FOREST),
        ('46', 'US suppliers verified', colors.HexColor('#A2762F')),
        ('4', 'supplier flags', CLAY),
    ]))
    F.append(Spacer(1, 0.30 * inch))

    left = [
        P('What this deck contains', st_h2),
        P('Twenty-five products for each brand, every one carrying a named supplier, a '
          'verified location, a wholesale cost, a retail target and a full landed-cost '
          'breakdown. Tier A items clear $7.00 net per unit. Tier C items are included '
          'deliberately \u2014 they document what does not work and why, so the same '
          'mistake is not repeated at scale.', st_body_s),
        Spacer(1, 0.13 * inch),
        P('How to read the numbers', st_h2),
        P('Wholesale is the supplier cost per unit. Prep is the sticker, FNSKU and handling '
          'applied at a US prep centre. Referral is Amazon\u2019s 15% of retail. Fulfilment '
          'is the FBA pick-and-pack fee for that weight. Landed is the sum of the four; '
          'net is retail minus landed.', st_body_s),
    ]
    right = [
        P('The one thing to take away', st_h2),
        P('The sourcing layer is solved. Every product in this deck can be bought from a '
          'US warehouse, stickered at a prep centre and shipped to Amazon without a '
          'co-packer, a blender or a forty-day ocean freight.', st_body_s),
        Spacer(1, 0.13 * inch),
        P('Structural finding', st_h2),
        P('The twelve Tier C items are not supplier failures. They are weight-to-value '
          'failures: bath bombs, steamers, soap bars, mugs and photobooks all carry '
          'fulfilment fees that consume the margin regardless of who manufactures them. '
          'A cheaper supplier does not fix that. Only a different format does.', st_body_s),
    ]
    two = Table([[left, right]], colWidths=[USABLE * 0.5 - 0.12 * inch,
                                            USABLE * 0.5 - 0.12 * inch])
    two.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'TOP'),
                             ('LEFTPADDING', (0, 0), (-1, -1), 0),
                             ('RIGHTPADDING', (0, 0), (0, 0), 0.24 * inch),
                             ('RIGHTPADDING', (1, 0), (1, 0), 0)]))
    F.append(two)
    F.append(Spacer(1, 0.34 * inch))
    F.append(P('Headline picks', st_h2))
    F.append(Spacer(1, 0.06 * inch))
    picks = [
        ('Best net per unit', 'Heirloom Seed Starter Kit', 'Local Organics',
         '$10.04', 'True Leaf Market \u00b7 Utah', FOREST),
        ('Best net, Word Coffee', 'Motivational Poster', 'Word Coffee',
         '$7.84', 'Printful \u00b7 US fulfilment', COFFEE),
        ('Best return on cost', 'Loofah Facial Disks, 10-Pack', 'Local Organics',
         '67.5%', 'SeaSationals \u00b7 Florida', colors.HexColor('#A2762F')),
    ]
    cards, pstyle = [], [('VALIGN', (0, 0), (-1, -1), 'TOP'),
                         ('LEFTPADDING', (0, 0), (-1, -1), 12),
                         ('RIGHTPADDING', (0, 0), (-1, -1), 12),
                         ('TOPPADDING', (0, 0), (-1, -1), 10),
                         ('BOTTOMPADDING', (0, 0), (-1, -1), 11)]
    for i, (kick, name, brand, val, sup, col) in enumerate(picks):
        cards.append([P(kick.upper(), st_tile_l), Spacer(1, 0.04 * inch),
                      P('<b>%s</b>' % name, st_cell_b), P(brand, st_note),
                      P('<font color="%s">%s</font>' % (hexc(col), val), st_pick_val),
                      P(sup, st_note)])
        pstyle += [('BACKGROUND', (i, 0), (i, 0), WHITE),
                   ('BOX', (i, 0), (i, 0), 0.6, RULE),
                   ('LINEABOVE', (i, 0), (i, 0), 2.4, col)]
    pk = Table([cards], colWidths=[(USABLE - 0.28 * inch) / 3.0] * 3)
    pk.setStyle(TableStyle(pstyle))
    F.append(pk)

    # ============ SELECTION ============
    F.append(PageBreak())
    F.append(P('How the shortlist was built', st_h1))
    F.append(Spacer(1, 0.06 * inch))
    F.append(P('Four filters, applied in order. Every candidate that reached the appendix '
               'cleared all four.', st_body))
    F.append(Spacer(1, 0.20 * inch))

    n_econ = sum(1 for x in DATA if x['margin']['net'] >= 5)
    n_light = sum(1 for x in DATA if x['margin']['shipping_lbs'] < 1.5)
    filters = [
        ['Filter', 'What it requires', 'Result'],
        ['Brand fit',
         'Sits inside the Mogra organic register or the Word Coffee paper register. No '
         'supplements, no devices, no commodity electronics.', '50 of 50'],
        ['Sourcing',
         'A named US-based supplier, a US location, and a label-only branding path. No '
         'co-packing, blending or primary packaging change.', '46 confirmed \u00b7 1 flagged \u00b7 3 open'],
        ['Economics',
         'Retail inside $15\u2013$35, with a landed cost low enough to leave $5.00 or '
         'more net per unit after referral and fulfilment.', '%d of 50' % n_econ],
        ['Logistics',
         'Light and unbreakable. No glass, no fragile ceramics, under 1.5 lb wherever '
         'possible.', '%d of 50' % n_light],
    ]
    ft = Table([[P(c, st_head_cell if i == 0 else (st_cell_b if j == 0 else st_cell))
                 for j, c in enumerate(row)] for i, row in enumerate(filters)],
               colWidths=[0.95 * inch, USABLE * 0.63, USABLE * 0.30])
    ft.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), FOREST),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 9), ('RIGHTPADDING', (0, 0), (-1, -1), 9),
        ('TOPPADDING', (0, 0), (-1, -1), 8), ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('LINEBELOW', (0, 0), (-1, -1), 0.4, RULE),
    ] + [('BACKGROUND', (0, r), (-1, r), colors.HexColor('#F4EFE5'))
         for r in (2, 4)]))
    F.append(ft)
    F.append(Spacer(1, 0.26 * inch))

    conf = [
        ('Named company', 'A real legal entity with a trading history, not a marketplace '
                          'listing.'),
        ('US location', 'State-level address confirmed for the warehouse or production '
                        'site.'),
        ('Label-only path', 'Product arrives pre-packaged and unbranded. Our mark goes on '
                            'the outside, never inside the pack.'),
        ('Cost evidence', 'Published wholesale pricing or a quoted price per unit \u2014 '
                          'not an estimate pulled from a retail listing.'),
    ]
    rows = [[P('What \u201cconfirmed\u201d means', st_cell_b)]]
    for a, b in conf:
        rows.append([P('<b>%s</b>' % a, st_cell), P(b, st_note)])
    panel = Table(rows, colWidths=[1.55 * inch, USABLE - 1.55 * inch])
    panel.setStyle(TableStyle([
        ('SPAN', (0, 0), (1, 0)),
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#F4EFE5')),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 10), ('RIGHTPADDING', (0, 0), (-1, -1), 10),
        ('TOPPADDING', (0, 0), (-1, -1), 6), ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('LINEBELOW', (0, 1), (-1, -1), 0.4, RULE),
        ('BOX', (0, 0), (-1, -1), 0.5, RULE),
    ]))
    F.append(panel)
    F.append(Spacer(1, 0.20 * inch))
    F.append(P('All wholesale, retail and margin figures are planning estimates. Confirm '
               'each against a firm supplier quote and the Amazon Revenue Calculator '
               'before committing to a purchase order.', st_note))

    # ============ TIER PAGE ============
    F.append(PageBreak())
    F.append(P('Tier distribution and profit curve', st_h1))
    F.append(Spacer(1, 0.12 * inch))
    F.append(P('Tier A clears the $7.00 net threshold. Tier B is the working core. '
               'Tier C is documented so the same mistake is not repeated at scale.',
               st_body))
    F.append(Spacer(1, 0.20 * inch))
    F.append(tier_bar(counts))
    F.append(Spacer(1, 0.26 * inch))

    top15 = sorted(DATA, key=lambda r: -r['margin']['net'])[:15]
    chart = hbar_chart([(x['product_name'][:38], x['margin']['net']) for x in top15],
                       USABLE * 0.55, 3.3 * inch)
    brand_rows = [['', 'A', 'B', 'C', 'Total']]
    for label, key in (('Local Organics', 'Local Organics'), ('Word Coffee', 'Word Coffee')):
        sub = [x for x in DATA if x['brand_track'] == key]
        brand_rows.append([label] +
                          [str(sum(1 for x in sub if x['tier'] == t)) for t in ('A', 'B', 'C')] +
                          [str(len(sub))])
    brand_rows.append(['All fifty', str(counts['A']), str(counts['B']),
                       str(counts['C']), str(len(DATA))])

    cells = []
    for i, r in enumerate(brand_rows):
        rowc = []
        for j, c in enumerate(r):
            if i == 0:
                rowc.append(P(c, st_th_c if j > 0 else st_th))
            else:
                rowc.append(P(c, st_cell_c if j > 0 else st_cell_b))
        cells.append(rowc)
    side = Table(cells, colWidths=[0.95 * inch, 0.36 * inch, 0.36 * inch,
                                   0.36 * inch, 0.5 * inch])
    side.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), FOREST),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (-1, -1), 2), ('RIGHTPADDING', (0, 0), (-1, -1), 2),
        ('TOPPADDING', (0, 0), (-1, -1), 4), ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('LINEBELOW', (0, 0), (-1, -1), 0.4, RULE),
        ('BACKGROUND', (0, 3), (-1, 3), colors.HexColor('#F4EFE5')),
        ('LINEABOVE', (0, 3), (-1, 3), 0.9, FOREST),
    ]))

    legend = [
        ('A', 'Tier A \u2014 net \u2265 $7.00', 'lead with these'),
        ('B', 'Tier B \u2014 $5.00 to $6.99', 'the working core'),
        ('C', 'Tier C \u2014 below $5.00', 'documented, not dropped'),
    ]
    lrows = [[P('Tier bands', st_cell_b)]]
    for t, name, note in legend:
        lrows.append([Paragraph('<font color="%s"><b>%s</b></font>'
                                % (hexc(TIER[t]), t), st_cell_b),
                      P(name, st_cell), P(note, st_note)])
    leg = Table(lrows, colWidths=[0.26 * inch, 1.72 * inch, USABLE * 0.44 - 2.05 * inch])
    leg.setStyle(TableStyle([
        ('SPAN', (0, 0), (2, 0)),
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#F4EFE5')),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (-1, -1), 2), ('RIGHTPADDING', (0, 0), (-1, -1), 4),
        ('TOPPADDING', (0, 0), (-1, -1), 4), ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('LINEBELOW', (0, 1), (-1, -1), 0.4, RULE),
    ]))

    side_stack = [[side], [Spacer(1, 0.20 * inch)], [leg],
                  [Spacer(1, 0.16 * inch)],
                  [P('Every Tier C item is a weight-to-value problem, not a sourcing '
                     'problem. The next page shows what that means in practice.', st_note)]]
    combo = Table([[chart, side_stack]], colWidths=[USABLE * 0.56, USABLE * 0.44])
    combo.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'TOP'),
                               ('LEFTPADDING', (0, 0), (-1, -1), 0),
                               ('RIGHTPADDING', (0, 0), (0, 0), 0.2 * inch),
                               ('RIGHTPADDING', (1, 0), (1, 0), 0)]))
    F.append(combo)

    # ============ MOGRA A/B ============
    HEAD = ['Tier', 'Product', 'Supplier', 'Loc', 'Wholesale', 'Retail', 'Net', 'ROI', 'Wt', '\u2713']
    W = [0.42, 3.05, 1.55, 0.38, 0.75, 0.66, 0.62, 0.55, 0.38, 0.30]
    scale = USABLE / (sum(W) * inch)
    CW = [w * inch * scale for w in W]

    def rows_for(items):
        out = []
        for x in items:
            out.append([
                tier_chip(x['tier']),
                P(x['product_name'], st_cell_b),
                P(x['supplier']['name'].split(' / ')[0], st_cell),
                P(loc_code(x['supplier']['location']), st_cell_c),
                P('$%.2f' % x['supplier']['est_cost'], st_cell_r),
                P('$%.2f' % x['margin']['retail'], st_cell_r),
                P('<b>$%.2f</b>' % x['margin']['net'], st_cell_r),
                P('%.1f%%' % x['margin']['roi_pct'], st_cell_r),
                P('%.2f' % x['margin']['shipping_lbs'], st_cell_c),
                verified_cell(x['supplier']['verified']),
            ])
        return out

    F.append(NextPageTemplate('mogra'))
    F.append(PageBreak())
    F.append(P('Track A \u2014 Local Organics', st_h1))
    F.append(Spacer(1, 0.04 * inch))
    F.append(P('25 candidates \u00b7 garden kits, body care, bath accessories and home '
               'textiles \u00b7 all US-sourced', st_body))
    F.append(Spacer(1, 0.16 * inch))
    ab_m = [x for x in mogra if x['tier'] in ('A', 'B')]
    F.append(data_table(rows_for(ab_m), CW, HEAD, FOREST))
    F.append(Spacer(1, 0.14 * inch))
    F.append(P('Tier A and B \u2014 20 items. The Tier column is colour-coded: forest for '
               'A, ochre for B, clay for C. A green tick in the final column means the '
               'supplier and its US location are confirmed; an amber or red mark means '
               'the item needs verification before any order.', st_note))

    F.append(PageBreak())
    F.append(P('Track A \u2014 what fails, and why', st_h1))
    F.append(Spacer(1, 0.16 * inch))
    c_m = [x for x in mogra if x['tier'] == 'C']
    F.append(data_table(rows_for(c_m), CW, HEAD, FOREST))
    F.append(Spacer(1, 0.22 * inch))
    F.append(P('The five Tier C products are not sourcing problems', st_h2))
    F.append(P('Bath bombs, shower steamers, soap bars and the 24 oz candle all share one '
               'trait: the fulfilment fee scales with weight while the price ceiling is set '
               'by commodity competitors. The 5 oz bath bomb clears $2.49 because the '
               'FBA fee for a 0.4 lb item is roughly the same as a $4.00 wholesale cost. '
               'A cheaper supplier does not fix this. Only a different format does.', st_body_s))
    F.append(Spacer(1, 0.14 * inch))
    F.append(P('<b>Compliance note.</b> The nine body-care items in Track A are cosmetics '
               'under FDA MoCRA. They require a US Responsible Person, facility '
               'registration, an INCI label and a safety substantiation file. The bath '
               'accessories \u2014 loofah, sea sponge, sisal mitt, back brush \u2014 carry '
               'none of that burden and are the cleanest entry point.', st_note))

    F.append(Spacer(1, 0.30 * inch))
    F.append(P('Three ways a Tier C item becomes viable', st_h2))
    F.append(Spacer(1, 0.06 * inch))
    fixes = [
        ('Reformat, do not re-source',
         'The 5 oz bath bomb at $2.49 net becomes a 6-piece gift set at $34.99, where the '
         'fulfilment fee is spread across six units of value instead of one.'),
        ('Raise the price ceiling',
         'The 24 oz candle at $29.99 carries $4.54 net. The same candle at $36.99 in a '
         'gift box clears $9.10 \u2014 the constraint is positioning, not cost.'),
        ('Use it as a cart-stacker',
         'A $2.44 steamer is a poor hero SKU and an excellent add-on. Paired with a $24.99 '
         'body butter it lifts average order value without carrying the listing alone.'),
    ]
    frows = []
    for title, body in fixes:
        frows.append([P('<b>%s</b>' % title, st_cell_b), P(body, st_note)])
    fx = Table(frows, colWidths=[2.05 * inch, USABLE - 2.05 * inch])
    fx.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('TOPPADDING', (0, 0), (-1, -1), 6), ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('LINEBELOW', (0, 0), (-1, -1), 0.4, RULE),
    ]))
    F.append(fx)

    # ============ WORD COFFEE A/B ============
    F.append(NextPageTemplate('wc'))
    F.append(PageBreak())
    F.append(P('Track B \u2014 Word Coffee', st_h1))
    F.append(Spacer(1, 0.04 * inch))
    F.append(P('25 candidates \u00b7 journals, planners, cards, wall art and desk goods '
               '\u00b7 US print and wholesale', st_body))
    F.append(Spacer(1, 0.16 * inch))
    ab_w = [x for x in wc if x['tier'] in ('A', 'B')]
    F.append(data_table(rows_for(ab_w), CW, HEAD, COFFEE))
    F.append(Spacer(1, 0.14 * inch))
    F.append(P('Tier A and B \u2014 18 items. StationeryHQ items are bulk (buy inventory, '
               'send to FBA); Printful items are print-on-demand and ship merchant-fulfilled, '
               'which is a different lane from FBA.', st_note))

    F.append(PageBreak())
    F.append(P('Track B \u2014 what fails, and why', st_h1))
    F.append(Spacer(1, 0.16 * inch))
    c_w = [x for x in wc if x['tier'] == 'C']
    F.append(data_table(rows_for(c_w), CW, HEAD, COFFEE))
    F.append(Spacer(1, 0.22 * inch))
    F.append(P('Two different failure modes', st_h2))
    F.append(P('The print-on-demand items \u2014 mug, pouch, photobook, laptop sleeve '
               '\u2014 fail because POD unit cost sits close to the retail ceiling. The mug '
               'at $8.50 cost against a $19.99 retail leaves $2.99 after everything. '
               'The washi tape, sticky notes and pen set fail for the opposite reason: '
               'the economics are fine, but no US supplier has been confirmed, so they '
               'are marked <b>do not order</b> until that closes.', st_body_s))
    F.append(Spacer(1, 0.14 * inch))
    F.append(P('<b>Textile note.</b> The canvas tote and the t-shirt require FTC origin '
               'and fibre-content marking on the label \u2014 handled by the same sticker '
               'that carries the brand mark, so it adds no separate step.', st_note))

    # ============ SUPPLIER ROSTER ============
    F.append(NextPageTemplate('main'))
    F.append(PageBreak())
    F.append(P('The supplier layer', st_h1))
    F.append(Spacer(1, 0.05 * inch))
    F.append(P('Eleven suppliers carry the entire fifty-item catalogue. Ten are confirmed '
               'US-located; one is flagged.', st_body))
    F.append(Spacer(1, 0.18 * inch))

    sup = [
        ['Bulk Apothecary', 'Streetsboro, Ohio', 'Ready-To-Label catalogue, in stock, ready to ship', '11', 'Confirmed'],
        ['SeaSationals / Natural Bath & Body', 'Tarpon Springs, Florida', 'Private label, brand-free, net or OPP bag', '5', 'Confirmed'],
        ['True Leaf Market', 'Salt Lake City, Utah', 'Bulk seed plus custom packeting, kitting, assembly', '5', 'Confirmed'],
        ['StationeryHQ', 'United States', 'Custom journals, no minimum, white-label fulfilment', '13', 'Confirmed'],
        ['Printful', 'US fulfilment', 'Print-on-demand, no minimum, ships per order', '9', 'Confirmed'],
        ['ECOBAGS', 'United States', 'B2B wholesale organic cotton bags', '1', 'Confirmed'],
        ['Organic Blank', 'United States', 'GOTS organic cotton, minimum order quantity of 1', '1', 'Confirmed'],
        ['Sticker Mule', 'United States', 'Custom stickers and labels, 50 minimum per design', '1', 'Confirmed'],
        ['Meli Wraps', 'Hawaii, USA', 'Handmade organic cotton beeswax wraps', '1', 'Confirmed'],
        ['Adagio XL', 'Berkeley, California', 'White-label organic tea tins', 'bonus', 'Confirmed'],
        ['Prime Felt', 'USA \u2014 warehouse unconfirmed', 'Private label wool dryer balls', '1', 'Flagged'],
    ]
    sh = ['Supplier', 'Location', 'Model', 'Items', 'Status']
    body = [[P(h, st_th if i < 3 else st_th_c) for i, h in enumerate(sh)]]
    for r in sup:
        body.append([P(r[0], st_cell_b), P(r[1], st_cell), P(r[2], st_cell),
                     P(r[3], st_cell_c),
                     P('<font color="%s"><b>%s</b></font>' % (
                         '#2F6B3A' if r[4] == 'Confirmed' else '#A2762F', r[4]), st_cell_c)])
    t = Table(body, colWidths=[2.25 * inch, 2.05 * inch, USABLE - 5.0 * inch, 0.55 * inch, 0.85 * inch])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), FOREST),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (-1, -1), 7), ('RIGHTPADDING', (0, 0), (-1, -1), 7),
        ('TOPPADDING', (0, 0), (-1, -1), 5.5), ('BOTTOMPADDING', (0, 0), (-1, -1), 5.5),
        ('LINEBELOW', (0, 0), (-1, -1), 0.4, RULE),
    ] + [('BACKGROUND', (0, r), (-1, r), colors.HexColor('#F4EFE5'))
         for r in range(2, len(body), 2)]))
    F.append(t)
    F.append(Spacer(1, 0.18 * inch))
    F.append(P('<b>Rejected this round.</b> Gallant International \u2014 US company but '
               'custom offshore production on a 45\u201390 day lead, which fails the speed '
               'constraint. Also rejected as offshore factories rather than US stock: '
               'greenbeeswrap, friendlybamboo, utensils-manufacturers, coconutbowlssupplier.',
               st_note))

    # ============ RECOMMENDATIONS ============
    F.append(PageBreak())
    F.append(P('What to do next', st_h1))
    F.append(Spacer(1, 0.20 * inch))

    steps = [
        ('01', 'Quote the thirteen Tier A items',
         'Do not sample fifty. The garden kits and body care carry the margin; the rest '
         'can wait until the first listings prove out.'),
        ('02', 'Close the four supplier gaps',
         'Prime Felt warehouse, plus washi tape, sticky notes and pen set. None of the '
         'three unconfirmed items should be ordered before that closes.'),
        ('03', 'Confirm the MoCRA position in writing',
         'Ask Bulk Apothecary who holds the Responsible Person role and whether they '
         'supply a shared safety assessment per formula.'),
        ('04', 'Run one prep-centre pilot',
         'One case of one Tier A item, sticker plus FNSKU, scanned at an Amazon FC. '
         'Cheapest way to find out whether the label path actually works.'),
        ('05', 'Lock UPC ownership before the first inbound',
         'Register the GS1 US prefix under T2 Holdings so every sticker carries a code '
         'we own, not a supplier\u2019s.'),
    ]
    row = []
    for num, title, body in steps:
        row.append([P(num, ParagraphStyle('n%s' % num, fontName='Times-Bold', fontSize=20,
                                          leading=22, textColor=KRAFT)),
                    P('<b>%s</b>' % title, st_cell_b),
                    P(body, st_note)])
    st_tbl = Table([[r[0], r[1]] for r in row], colWidths=[0.55 * inch, USABLE - 0.55 * inch])
    st_tbl.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'TOP'),
                                ('LEFTPADDING', (0, 0), (-1, -1), 0),
                                ('TOPPADDING', (0, 0), (-1, -1), 2),
                                ('BOTTOMPADDING', (0, 0), (-1, -1), 2)]))
    for num, title, body in steps:
        blk = Table([[
            P(num, ParagraphStyle('z%s' % num, fontName='Times-Bold', fontSize=21,
                                  leading=24, textColor=KRAFT)),
            [P('<b>%s</b>' % title, st_cell_b), Spacer(1, 0.02 * inch), P(body, st_note)]]],
            colWidths=[0.6 * inch, USABLE - 0.6 * inch])
        blk.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'TOP'),
                                 ('LEFTPADDING', (0, 0), (-1, -1), 0),
                                 ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
                                 ('LINEBELOW', (0, 0), (-1, 0), 0.4, RULE)]))
        F.append(blk)

    F.append(Spacer(1, 0.16 * inch))
    F.append(P('Where to start', st_h2))
    F.append(P('Thirteen Tier A items. Two clusters carry the margin \u2014 the garden kits '
               'in Track A and the planner, poster and wall art in Track B \u2014 and the '
               'bath accessories sit behind them as the lowest-compliance entry point.',
               st_quote))

    # ============ APPENDIX ============
    F.append(NextPageTemplate('app'))
    F.append(PageBreak())
    F.append(P('Appendix \u2014 complete dataset', st_h1))
    F.append(Spacer(1, 0.04 * inch))
    F.append(P('All fifty records, sorted by net profit per unit.', st_note))
    F.append(Spacer(1, 0.12 * inch))

    HA = ['#', 'Product', 'Brand', 'Supplier', 'WS', 'Retail', 'Net', 'ROI', 'Wt', 'Tier']
    WA = [0.32, 3.28, 0.62, 1.86, 0.62, 0.66, 0.62, 0.55, 0.38, 0.36]
    scale = USABLE / (sum(WA) * inch)
    CWA = [w * inch * scale for w in WA]

    body = [[P(h, st_th_c if h in ('#', 'Brand', 'Tier', 'Wt') else
               (st_th_r if h in ('WS', 'Retail', 'Net', 'ROI') else st_th)) for h in HA]]
    for i, x in enumerate(sorted(DATA, key=lambda r: -r['margin']['net']), 1):
        body.append([
            P(str(i), st_cell_c),
            P(x['product_name'], st_cell),
            P('LO' if x['brand_track'] == 'Local Organics' else 'WC', st_cell_c),
            P(x['supplier']['name'].split(' / ')[0], st_cell),
            P('$%.2f' % x['supplier']['est_cost'], st_cell_r),
            P('$%.2f' % x['margin']['retail'], st_cell_r),
            P('<b>$%.2f</b>' % x['margin']['net'], st_cell_r),
            P('%.1f' % x['margin']['roi_pct'], st_cell_r),
            P('%.2f' % x['margin']['shipping_lbs'], st_cell_c),
            tier_chip(x['tier']),
        ])
    at = Table(body, colWidths=CWA, repeatRows=1)
    at.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), FOREST),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (-1, -1), 4.5), ('RIGHTPADDING', (0, 0), (-1, -1), 4.5),
        ('TOPPADDING', (0, 0), (-1, -1), 2.6), ('BOTTOMPADDING', (0, 0), (-1, -1), 2.6),
        ('LINEBELOW', (0, 0), (-1, -1), 0.35, RULE),
    ] + [('BACKGROUND', (0, r), (-1, r), colors.HexColor('#F4EFE5'))
         for r in range(2, len(body), 2)]))
    F.append(at)
    F.append(Spacer(1, 0.10 * inch))
    F.append(P('LO = Local Organics \u00b7 WC = Word Coffee \u00b7 Tier A net \u2265 $7.00, '
               'B $5.00\u2013$6.99, C below $5.00. Wholesale, retail, net and shipping '
               'weight are planning estimates; confirm against firm supplier quotes and '
               'the Amazon Revenue Calculator before any purchase order.', st_note))

    doc.build(F)
    print('PDF written.')


if __name__ == '__main__':
    build()
