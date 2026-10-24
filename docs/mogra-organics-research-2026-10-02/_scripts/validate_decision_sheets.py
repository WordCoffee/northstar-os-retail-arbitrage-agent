import os, re
from pypdf import PdfReader
BASE = os.path.join("docs", "mogra-organics-research-2026-10-02")
OUT = os.path.join(BASE, "review_packet")
SHEETS = os.path.join(OUT, "Mogra_Organics_Suppliers_Packagers_Shipping_Decision_Sheets.pdf")
CANON = os.path.join(OUT, "Mogra_Organics_Holiday_Amazon_Launch_Blueprint_2026-10-02.pdf")

REQUIRED = [
    "PRINTABLE DECISION SHEET 1", "PRINTABLE DECISION SHEET 2", "PRINTABLE DECISION SHEET 3",
    "OWNER / PARTNER DECISION", "Legend", "Prepared 2026-10-02",
    # distinct projects
    "HERBS/SPICES", "Lion", "separate",
    # supplier page
    "Turnkey finished-product providers", "Ingredient suppliers (supply-only)",
    "MOQ / price", "US arrival", "Priority",
    # packager page
    "Customer-supplied ingredients", "Whole / powder capability", "Stock jars / pouches",
    "Organic-handling capability and evidence", "Distance to us",
    "established as authorised to open",
    # shipping page
    "Apples-to-apples", "Declared value", "Incoterm", "Ready-for-pickup",
    "Amazon inbound transportation and placement charges",
    "DHL Express Worldwide", "FedEx International Priority", "UPS Worldwide Expedited",
    "DHL Global Forwarding", "Freightos",
    "Mode", "Customs brokerage", "Published transit indication", "Actual delivered estimate",
    "Cost coverage", "Suitability (small order)", "Next quote request",
    # speed-first
    "Complete-route speed ranking", "UNRANKED / CONFIRMATION REQUIRED",
    "planning allowances", "Earliest credible finished unit",
]

# claims that must NEVER appear
FORBIDDEN = [
    "lead-free", "lead free", "safer than", "FDA-approved", "FDA approved",
    "clinically proven", "cures", "treats disease", "best supplier", "cheapest route",
    "guaranteed delivery", "we guarantee", "certified organic by the USDA",
]

def norm(t):
    t = re.sub(r"<[^>]+>", " ", t)
    return re.sub(r"\s+", " ", t.replace("\u2014", "-").replace("\u2013", "-")).lower()


# A forbidden term is acceptable ONLY inside an explicit prohibition sentence.
PROHIBITED_SENTENCE = norm('Do NOT use "lead-free", "safer", or competitor-superiority language')


def scan_forbidden(flat_norm):
    """Return forbidden terms used as actual claims (i.e. outside a prohibition)."""
    hits = []
    for k in FORBIDDEN:
        for m in re.finditer(re.escape(k.lower()), flat_norm):
            window = flat_norm[max(0, m.start() - 200):m.end() + 200]
            if "do not use" in window or "without appropriate substantiation" in window:
                continue  # prohibition context, not a claim
            hits.append((k, window))
    return hits

fails = 0
for label, path in (("STANDALONE", SHEETS), ("CANONICAL", CANON)):
    r = PdfReader(path)
    pages = [p.extract_text() or "" for p in r.pages]
    full = " ".join(pages)
    n = norm(full)
    print("=== %s : %d pages, %d bytes, %d chars" % (label, len(pages), os.path.getsize(path), len(full)))
    miss = [k for k in REQUIRED if norm(k) not in n]
    if label == "STANDALONE":
        print("  required present: %d/%d" % (len(REQUIRED) - len(miss), len(REQUIRED)))
        if miss:
            print("  MISSING:", miss); fails += 1
    hits = scan_forbidden(n)
    if hits:
        print("  FORBIDDEN CLAIM HITS:", [(k, w[:120]) for k, w in hits]); fails += 1
    else:
        print("  forbidden claims used as actual claims: none")
    if "do not use" in n and "lead-free" in n:
        print("  note: 'lead-free' present only inside the explicit prohibition sentence")
    blanks = [i + 1 for i, t in enumerate(pages)
              if len(re.sub(r"MOGRA ORGANICS.*?Page \d+", "", t, flags=re.S).strip()) < 90]
    print("  near-blank pages:", blanks or "none")
    if blanks:
        fails += 1
    if label == "CANONICAL":
        land = [i + 1 for i, p in enumerate(r.pages) if float(p.mediabox.width) > float(p.mediabox.height)]
        port = [i + 1 for i, p in enumerate(r.pages) if float(p.mediabox.width) <= float(p.mediabox.height)]
        print("  portrait pages: %d  landscape pages: %s" % (len(port), land))

# canonical must still contain its original content
c = norm(" ".join((p.extract_text() or "") for p in PdfReader(CANON).pages))
for k in ["25 Nov 2026", "1 Dec 2026", "$1,500", "2-4 SKUs", "T2 Holdings"]:
    print("  canonical retains %-12s : %s" % (k, norm(k) in c))

print("FAILURES:", fails)