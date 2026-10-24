import csv, os, glob
ROOT="docs/mogra-organics-research-2026-10-02"
bad=0; total=0
for p in sorted(glob.glob(os.path.join(ROOT,"*.csv"))):
    with open(p,newline="",encoding="utf-8") as f:
        rows=list(csv.reader(f))
    if not rows: print("EMPTY",p); continue
    n=len(rows[0]); mism=[i for i,r in enumerate(rows[1:],2) if len(r)!=n]
    total+=len(rows)-1
    status="OK" if not mism else f"MISMATCH rows {mism[:5]}"
    if mism: bad+=1
    print(f"{os.path.basename(p):<40} rows={len(rows)-1:<4} cols={n:<3} {status}")
print("files with mismatch:",bad,"| total data rows:",total)
