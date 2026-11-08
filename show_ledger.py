import json
from pathlib import Path
l = json.loads(Path("out_lions_mane/credit_ledger.json").read_text(encoding="utf-8"))
for r in l["requests"]:
    print(f"{r['ts']}  {str(r['type']):8s} used={r['credits_used']} rem={r['credits_remaining']}  {r['purpose'][:60]}")
print("total used:", l["credits_used"], "remaining:", l["credits_remaining"])
