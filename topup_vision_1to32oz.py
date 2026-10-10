#!/usr/bin/env python3
"""Local-only vision top-up for records missing verdicts that are newly eligible
under the 1-32 oz rule. Writes a SEPARATE file (raw evidence untouched):
out_sb/rebuild_1to32oz/vision_verdicts_topup_1to32oz.json

Uses local Ollama only (no external/paid calls).
"""
import base64, io, json, re, sys
from pathlib import Path
import requests
from PIL import Image

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "out_sb"
RB = OUT / "rebuild_1to32oz"
RB.mkdir(exist_ok=True)
PORT = 11435
MODEL = "qwen2.5vl:7b"
PROMPT = (Path("run_vision_sb.py").read_text(encoding="utf-8").split('PROMPT = """')[1].split('"""')[0])

# enriched records missing a vision verdict that are newly re-evaluable under 1-32 oz
TARGETS = ["B01DKZZFCE", "B07MVRLJ91", "B0FY71CYK8", "B07YXFTZGW"]

def b64_of(path, size=1024):
    img = Image.open(path).convert("RGB"); img.thumbnail((size, size))
    buf = io.BytesIO(); img.save(buf, format="JPEG", quality=85)
    return base64.b64encode(buf.getvalue()).decode()

def ask(b64):
    r = requests.post(f"http://localhost:{PORT}/api/chat",
        json={"model": MODEL, "stream": False, "options": {"temperature": 0, "num_predict": 700},
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

def oz_from_text(s):
    if not s:
        return None
    vals = []
    for n, unit in re.findall(r"(\d+(?:\.\d+)?)\s*(fl\.?\s*oz|oz|ounces?|lbs?|pounds?|kg|kilograms?|grams?|g)\b", str(s), re.I):
        u = unit.lower().replace(".", "")
        if u.startswith("fl"):
            continue
        f = 1 if u in ("oz", "ounce", "ounces") else 16 if u in ("lb", "lbs", "pound", "pounds") else 35.274 if u in ("kg", "kilogram", "kilograms") else 0.035274
        vals.append(round(float(n) * f, 2))
    return max(vals) if vals else None

def main():
    details = json.loads((OUT / "details.json").read_text(encoding="utf-8"))
    topup = {}
    for asin in TARGETS:
        p = details.get(asin)
        if not p:
            print(asin, "no details"); continue
        urls = p.get("images") or []
        images_dir = OUT / "images" / asin
        files = sorted(images_dir.glob("*.jpg"))
        if not files:
            # download from cached image URLs (Amazon CDN, not a provider API call)
            import requests as rq
            d = OUT / "images" / asin
            d.mkdir(parents=True, exist_ok=True)
            for i, u in enumerate((urls or [])[:4], 1):
                try:
                    r = rq.get(u, timeout=60); r.raise_for_status()
                    (d / f"{i:02d}.jpg").write_bytes(r.content)
                except Exception as e:
                    print(f"  {asin} img {i}: {str(e)[:80]}")
            files = sorted(d.glob("*.jpg"))
        best = None
        for j, fp in enumerate(files[:3], 1):
            try:
                v = parse_json(ask(b64_of(fp)))
            except Exception as e:
                print(f"  {asin} img{j}: {str(e)[:90]}"); continue
            if v:
                v["images_checked"] = j
                v["auditor"] = MODEL
                nw_raw = v.get("net_weight_on_label")
                if isinstance(nw_raw, dict):
                    nw_raw = nw_raw.get("verbatim_text") or json.dumps(nw_raw)
                    v["net_weight_on_label"] = nw_raw
                v["net_weight_oz"] = oz_from_text(nw_raw)
                best = v
                if v.get("net_weight_oz"):
                    break
        if best:
            topup[asin] = best
            print(f"{asin}: form={best.get('form')} lm={best.get('label_says_lions_mane')} "
                  f"org={best.get('label_says_organic') or best.get('usda_organic_seal_visible')} "
                  f"nw={best.get('net_weight_on_label')} extract/myceli={best.get('mentions_extract_or_mycelium')}")
        else:
            print(asin, "FAILED")
    (RB / "vision_verdicts_topup_1to32oz.json").write_text(json.dumps(topup, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"saved {len(topup)} top-up verdicts")

if __name__ == "__main__":
    main()
