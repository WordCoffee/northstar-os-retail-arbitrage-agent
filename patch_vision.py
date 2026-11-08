from pathlib import Path
import json

p = Path("run_vision_sb.py")
s = p.read_text(encoding="utf-8")
s = s.replace('if asin in verdicts and verdicts[asin].get("auditor") in ("qwen2.5vl", "moondream"):',
              'if asin in verdicts and verdicts[asin].get("auditor") == MODEL and not verdicts[asin].get("error"):')
s = s.replace('v["auditor"] = MODEL.split(":")[0]', 'v["auditor"] = MODEL')
s = s.replace('verdicts[asin] = {"auditor": MODEL.split(":")[0], "error": "no images", "confidence": 0}',
              'verdicts[asin] = {"auditor": MODEL, "error": "no images", "confidence": 0}')
s = s.replace('verdicts[asin] = {"auditor": MODEL.split(":")[0], "error": "unparseable", "confidence": 0}',
              'verdicts[asin] = {"auditor": MODEL, "error": "unparseable", "confidence": 0}')
p.write_text(s, encoding="utf-8")
print("patched run_vision_sb.py")

vp = Path("out_sb/vision_verdicts.json")
v = json.loads(vp.read_text(encoding="utf-8"))
clean = {k: x for k, x in v.items() if not x.get("error") and x.get("auditor") == "qwen2.5vl"}
vp.write_text(json.dumps(clean, indent=2, ensure_ascii=False), encoding="utf-8")
print("kept", len(clean), "of", len(v), "verdicts")
