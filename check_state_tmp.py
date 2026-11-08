import json
s = json.load(open("00_STATE.json", encoding="utf-8"))
print(json.dumps(s, indent=2))
