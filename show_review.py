import csv
from pathlib import Path

rows = list(csv.DictReader(open("out_sb/review.csv", newline="", encoding="utf-8")))
print("REVIEW rows:", len(rows))
for r in rows:
    print(f"- {r['asin']} | {(r.get('title') or '')[:70]} | reasons: {str(r.get('reasons'))[:150]}")
