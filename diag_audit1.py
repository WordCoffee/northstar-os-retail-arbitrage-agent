import json
from pathlib import Path

d = json.loads(Path("out_sb/audit_results.json").read_text(encoding="utf-8"))
for x in d["pass_audit"]:
    if x["asin"] == "B0BWJW3SCZ":
        print("answers for", x["asin"], ":")
        for a in x["answers"]:
            print(" ", a)
print()
for x in d["rejected_audit"]:
    if x.get("result") == "CHECK":
        print("CHECK:", x["asin"], "| recorded:", str(x.get("recorded"))[:130])
