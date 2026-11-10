import json
c = json.load(open("shared/subscription-plans.json", encoding="utf-8-sig"))
for p in c.get("plans", []):
    print(p.get("id"), "|", p.get("name"), "| ui_gates:", p.get("ui_gates"), "| gates:", p.get("gates"))
