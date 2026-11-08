#!/usr/bin/env python3
"""Visual gate via local Qwen2.5-VL (Ollama): read the actual product images.

Downloads candidate images, runs the VL model on the main + label images, and
writes out_sb/vision_verdicts.json:
  {asin: {form, capsules_or_tablets_visible, liquid_or_dropper_visible,
          label_says_lions_mane, label_says_organic, usda_organic_seal_visible,
          other_ingredients_on_label, mentions_extract_or_mycelium,
          net_weight_on_label, net_weight_oz, images_checked, confidence, evidence,
          auditor: "moondream"|"qwen2.5vl"}}

Resumable: verdicts already present are skipped. Sequential (local model).
"""
import base64, io, json, re, sys, time
from pathlib import Path
import requests
from PIL import Image

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "out_sb"
IMG_DIR = OUT / "images"
MODEL = sys.argv[1] if len(sys.argv) > 1 else "qwen2.5vl:7b"
LIMIT = int(sys.argv[2]) if len(sys.argv) > 2 else 0
MAX_IMAGES = 4
RESIZE = 1024

PROMPT = """You are auditing Amazon product images for a strict sourcing filter.
Look ONLY at what is physically visible/printed in the images. Reply with ONLY a JSON object, no other text:
{"form":"powder_bag|powder_jar|powder_pouch|powder_bottle|capsules|tablets|liquid|gummies|cosmetic|whole_dried|other|unclear",
 "capsules_or_tablets_visible":true_or_false,
 "liquid_or_dropper_visible":true_or_false,
 "label_says_lions_mane":true_or_false,
 "label_says_organic":true_or_false,
 "usda_organic_seal_visible":true_or_false,
 "other_ingredients_on_label":[],
 "mentions_extract_or_mycelium":true_or_false,
 "net_weight_on_label":"verbatim text or null",
 "confidence":0.0,
 "evidence":"one or two sentences citing what you see"}"""

def hi_res(u):
    if not u:
        return u
    u = re.sub(r"\._(SX|SY|UX|UL|SR|SS|MN|SP|CR|SL)[A-Za-z0-9_,]*_\.", "._AC_SL1500_.", u)
    if "_AC_SL1500_" not in u and re.search(r"\.(jpg|jpeg|png|webp)$", u, re.I):
        base, ext = u.rsplit(".", 1)
        return f"{base}._AC_SL1500_.{ext}"
    return u

def download_images(asin, urls):
    d = IMG_DIR / asin
    d.mkdir(parents=True, exist_ok=True)
    saved = []
    for i, u in enumerate(urls[:MAX_IMAGES], 1):
        fp = d / f"{i:02d}.jpg"
        if fp.exists() and fp.stat().st_size > 1000:
            try:
                Image.open(fp).verify()  # catches truncated/corrupt downloads
                saved.append(fp); continue
            except Exception:
                fp.unlink(missing_ok=True)
        try:
            r = requests.get(hi_res(u), timeout=60)
            r.raise_for_status()
            fp.write_bytes(r.content)
            Image.open(fp).verify()
            saved.append(fp)
        except Exception as e:
            print(f"    img {i} fail: {str(e)[:80]}")
        time.sleep(0.2)
    return saved

def to_b64(path):
    img = Image.open(path).convert("RGB")
    img.thumbnail((RESIZE, RESIZE))
    buf = io.BytesIO(); img.save(buf, format="JPEG", quality=85)
    return base64.b64encode(buf.getvalue()).decode()

def ask_vision(b64, prompt):
    r = requests.post("http://localhost:11434/api/chat",
                      json={"model": MODEL, "stream": False,
                            "options": {"temperature": 0, "num_predict": 700},
                            "messages": [{"role": "user", "content": prompt, "images": [b64]}]},
                      timeout=600)
    r.raise_for_status()
    return r.json()["message"]["content"]

def parse_json(txt):
    m = re.search(r"\{.*\}", txt, re.S)
    if not m:
        return None
    t = m.group(0)
    try:
        return json.loads(t)
    except Exception:
        # tolerate true/false/None case issues
        t2 = re.sub(r"\bTrue\b", "true", t); t2 = re.sub(r"\bFalse\b", "false", t2)
        t2 = re.sub(r"\bNone\b", "null", t2)
        try:
            return json.loads(t2)
        except Exception:
            return None

def oz_from_text(s):
    if not s:
        return None, False
    totals, fluid = [], False
    for n, unit in re.findall(r"(\d+(?:\.\d+)?)\s*(fl\.?\s*oz|fluid\s*ounces?|oz|ounces?|lbs?|pounds?|kg|kilograms?|grams?|g)\b", s, re.I):
        u = unit.lower().replace(".", "")
        if u.startswith("fl") or u.startswith("fluid"):
            fluid = True; continue
        f = 1 if u in ("oz", "ounce", "ounces") else 16 if u in ("lb", "lbs", "pound", "pounds") else 35.274 if u in ("kg", "kilogram", "kilograms") else 0.035274
        totals.append(round(float(n) * f, 2))
    return (totals[0] if len(totals) == 1 else (max(totals) if totals else None)), fluid

def main():
    cands = json.loads((OUT / "candidates_visual.json").read_text(encoding="utf-8"))
    vp = OUT / "vision_verdicts.json"
    verdicts = json.loads(vp.read_text(encoding="utf-8")) if vp.exists() else {}
    print(f"{len(cands)} candidates; {len(verdicts)} already done; model={MODEL}")
    done = 0
    for i, c in enumerate(cands, 1):
        if LIMIT and done >= LIMIT:
            break
        asin = c["asin"]
        if asin in verdicts and verdicts[asin].get("auditor") == MODEL and not verdicts[asin].get("error"):
            continue
        urls = [c.get("main_image")] + [u for u in (c.get("images") or []) if u != c.get("main_image")]
        urls = [u for u in urls if u]
        files = download_images(asin, urls)
        if not files:
            verdicts[asin] = {"auditor": MODEL, "error": "no images", "confidence": 0}
            continue
        best = None
        for j, fp in enumerate(files[:3]):
            try:
                txt = ask_vision(to_b64(fp), PROMPT)
            except Exception as e:
                print(f"  {asin} img{j+1} error: {str(e)[:100]}"); continue
            v = parse_json(txt)
            if not v:
                # retry once with stricter instruction
                try:
                    txt = ask_vision(to_b64(fp), "Reply with ONLY the JSON object. " + PROMPT)
                    v = parse_json(txt)
                except Exception:
                    v = None
            if v:
                v["images_checked"] = j + 1
                if v.get("net_weight_on_label"):
                    nw, fluid = oz_from_text(str(v.get("net_weight_on_label")))
                    v["net_weight_oz"] = nw
                    if fluid:
                        v["liquid_or_dropper_visible"] = True
                    if nw is None:
                        v["net_weight_oz"] = None
                else:
                    v["net_weight_oz"] = None
                v["auditor"] = MODEL
                best = v
                # stop early when the verdict is already informative
                if v.get("net_weight_oz") and v.get("label_says_lions_mane"):
                    break
            time.sleep(0.2)
        if best:
            verdicts[asin] = best
            done += 1
            nw = best.get("net_weight_oz")
            print(f"[{i}/{len(cands)}] {asin}: form={best.get('form')} lm={best.get('label_says_lions_mane')} "
                  f"org={best.get('label_says_organic') or best.get('usda_organic_seal_visible')} nw={nw} "
                  f"conf={best.get('confidence')}")
        else:
            verdicts[asin] = {"auditor": MODEL, "error": "unparseable", "confidence": 0}
            print(f"[{i}/{len(cands)}] {asin}: UNPARSEABLE")
        if i % 5 == 0:
            vp.write_text(json.dumps(verdicts, indent=2, ensure_ascii=False), encoding="utf-8")
    vp.write_text(json.dumps(verdicts, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"done: {len(verdicts)} verdicts written to vision_verdicts.json")

if __name__ == "__main__":
    main()
