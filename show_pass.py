import csv
from pathlib import Path

rows = list(csv.DictReader(open("out_sb/pass.csv", newline="", encoding="utf-8")))
print("PASS rows:", len(rows))
for r in rows:
    print(f"{r['asin']} | {r.get('size_oz'):>6} oz | ${r.get('price')} | rev={r.get('reviews')} | sales={r.get('sales_volume')} | "
          f"bsr={r.get('bsr_primary')} | est={r.get('bsr_est_monthly_sales')} | brand={(r.get('brand') or '')[:16]} | {(r.get('title') or '')[:45].encode('ascii','replace').decode()}")
