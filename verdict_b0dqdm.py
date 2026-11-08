import base64, io, json, re
from pathlib import Path
from PIL import Image
import requests

OUT = Path("out_sb")
PROMPT = (Path("test_minicpm.py").read_text(encoding="utf-8").split("PROMPT = '''")[1].split("'''")[0])

def b64_of(path, size=1024):
    img = Image.open(path).convert("RGB"); img.thumbnail((size, size))
    buf = io.BytesIO(); img.save(buf, format="JPEG", quality=85)
    return base64.b64encode(buf.getvalue()).decode()

def ask(b64):
    r = requests.post("http://localhost:11434/api/chat",
        json={"model": "minicpm-v", "stream": False, "options": {"temperature": 0, "num_predict": 700},
              "messages": [{"role": "user", "content": PROMPT, "images": [b64]}]}, timeout=900)
    r.raise_for_status()
    return r.json()["message"]["content"]

def parse_json(txt):
    m = re.search(r"\{.*\}", txt, re.S)
    if not m:
        return None
    t = m.group(0)
    for rep in [("\bTrue\b", "true"), ("\bFalse\b", "false"), ("\bNone\b", "null")]:
        t = re.sub(rep[0], rep[1], t)
    try:
        return json.loads(t)
    except Exception:
        return None

asin = "B0DQDM7HKD"
vp = OUT / "vision_verdicts.json"
verdicts = json.loads(vp.read_text(encoding="utf-8"))
files = sorted((OUT / "images" / asin).glob("*.jpg"))
best = None
for i, fp in enumerate(files[:3], 1):
    try:
        v = parse_json(ask(b64_of(fp)))
        if v:
            v["images_checked"] = i
            v["auditor"] = "minicpm-v"
            # normalize object-valued net weight
            nwl = v.get("net_weight_on_label")
            if isinstance(nwl, dict):
                v["net_weight_on_label"] = nwl.get("verbatim_text") or nwl.get("text") or json.dumps(nwl)
            best = v
            if v.get("net_weight_on_label"):
                break
    except Exception as e:
        print(f"img{i} error: {str(e)[:120]}")
if best:
    verdicts[asin] = best
    vp.write_text(json.dumps(verdicts, indent=2, ensure_ascii=False), encoding="utf-8")
    print("saved verdict for", asin, "->", json.dumps(best)[:300])
else:
    print("FAILED for", asin)
