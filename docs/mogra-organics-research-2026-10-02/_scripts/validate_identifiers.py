import os, re
from pypdf import PdfReader
OUT = os.path.join("docs", "mogra-organics-research-2026-10-02", "review_packet")
SH = os.path.join(OUT, "Mogra_Organics_Suppliers_Packagers_Shipping_Decision_Sheets.pdf")
CA = os.path.join(OUT, "Mogra_Organics_Holiday_Amazon_Launch_Blueprint_2026-10-02.pdf")

IDENTIFIERS = [
    "Pearl Group Corporation", "JAPC", "Spices Inc.", "Specialty Food Co-Packers",
    "Organic Spices Inc.", "Rocky Mountain Spice Company", "Spicy Organic",
    "Bata Food", "Prime Food Products",
    "DHL Express Worldwide", "FedEx International Priority", "UPS Worldwide Expedited",
    "DHL Global Forwarding", "Freightos", "Amazon Partner Carrier",
]

def flat(p):
    return re.sub(r"\s+", " ", " ".join((pg.extract_text() or "") for pg in PdfReader(p).pages))

s = flat(SH)
print("=== identifier integrity (standalone sheets) ===")
bad = 0
for i in IDENTIFIERS:
    ok = i in s
    if not ok:
        bad += 1
    print("  %-32s %s" % (i, "OK" if ok else "*** TRUNCATED/MISSING ***"))

print()
print("=== mid-word break scan (a lowercase run of 1-3 chars glued between words) ===")
sus = re.findall(r"[a-z]{2,}\s+[a-z]{1,3}\s+[a-z]{4,}", s)
print("  candidate fragments:", sorted(set(sus))[:12] if sus else "none")

print()
c = flat(CA)
print("=== canonical integrity ===")
for k in ["PRINTABLE DECISION SHEET 1", "PRINTABLE DECISION SHEET 2", "PRINTABLE DECISION SHEET 3",
          "Owner-supplied spelling", "T2 Holdings LLC"]:
    print("  %-34s %s" % (k, "OK" if k.lower() in c.lower() else "*** MISSING ***"))
print("  decision sheets appended:", "PRINTABLE DECISION SHEET 1" in c)
print("  blueprint body retained:", "HOLIDAY AMAZON LAUNCH BLUEPRINT" in c)
print("  TRUNCATION FAILURES:", bad)