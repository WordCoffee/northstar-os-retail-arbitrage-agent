# Builds the standalone printable landscape decision sheets PDF.
# Reusable build: run after build_decision_sheets.py regenerates the CSVs.
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from reportlab.platypus import BaseDocTemplate, PageTemplate, Frame
from reportlab.lib.pagesizes import letter, landscape
from reportlab.lib.units import inch
from decision_sheet_pages import build_pages, PAPER, BODY, BODY_I, MUTED, CLAY, RULE, TODAY

BASE = os.path.join("docs", "mogra-organics-research-2026-10-02")
OUT  = os.path.join(BASE, "review_packet")
SPDF = os.path.join(OUT, "Mogra_Organics_Suppliers_Packagers_Shipping_Decision_Sheets.pdf")
W, H = landscape(letter)
M = 0.5 * inch


class DS(BaseDocTemplate):
    def __init__(self, fn, **k):
        super().__init__(fn, **k)
        self.addPageTemplates([PageTemplate(
            id="land", pagesize=(W, H),
            frames=[Frame(M, M, W - 2 * M, H - 2 * M, id="lm")],
            onPage=self.deco)])

    def deco(self, c, d):
        c.saveState()
        c.setFillColor(PAPER); c.rect(0, 0, W, H, stroke=0, fill=1)
        c.setFont(BODY, 7.2); c.setFillColor(MUTED)
        c.drawString(M, H - 0.42 * inch, "MOGRA ORGANICS - SUPPLIER / PACKAGER / SHIPPING DECISION SHEETS")
        c.setFont(BODY_I, 7.2); c.setFillColor(CLAY)
        c.drawRightString(W - M, H - 0.42 * inch, "HERBS/SPICES PROJECT - NOT SENT - NO QUOTES OBTAINED")
        c.setStrokeColor(RULE); c.setLineWidth(0.5)
        c.line(M, H - 0.49 * inch, W - M, H - 0.49 * inch)
        c.line(M, 0.42 * inch, W - M, 0.42 * inch)
        c.setFont(BODY, 7.2); c.setFillColor(MUTED)
        c.drawString(M, 0.30 * inch, "Prepared %s - timing fields are UNKNOWN until providers respond" % TODAY)
        c.drawRightString(W - M, 0.30 * inch, "Page %d" % d.page)
        c.restoreState()


DS(SPDF, pagesize=(W, H)).build(build_pages(W - 2 * M))
print("STANDALONE WRITTEN:", SPDF)
print("SIZE:", os.path.getsize(SPDF))