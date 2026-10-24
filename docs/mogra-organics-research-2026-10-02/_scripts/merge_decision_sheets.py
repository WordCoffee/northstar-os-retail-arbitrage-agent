# Appends the finished landscape decision-sheet pages to the canonical
# partner-review PDF using pypdf, preserving per-page orientation.
import os
from pypdf import PdfWriter, PdfReader

BASE = os.path.join("docs", "mogra-organics-research-2026-10-02")
OUT  = os.path.join(BASE, "review_packet")
CANON = os.path.join(OUT, "Mogra_Organics_Holiday_Amazon_Launch_Blueprint_2026-10-02.pdf")
SHEETS = os.path.join(OUT, "Mogra_Organics_Suppliers_Packagers_Shipping_Decision_Sheets.pdf")

# Guard against double-append.
marker = "PRINTABLE DECISION SHEET 1"
cur = PdfReader(CANON)
if any(marker in (p.extract_text() or "") for p in cur.pages):
    print("ALREADY MERGED - canonical already contains the decision sheets. No action.")
else:
    w = PdfWriter()
    n0 = 0
    for p in cur.pages:
        w.add_page(p); n0 += 1
    n1 = 0
    for p in PdfReader(SHEETS).pages:
        w.add_page(p); n1 += 1
    with open(CANON, "wb") as f:
        w.write(f)
    print("MERGED: %d blueprint pages + %d decision-sheet pages = %d" % (n0, n1, n0 + n1))
print("SIZE:", os.path.getsize(CANON))