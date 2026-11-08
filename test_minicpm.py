import base64, io, json
from pathlib import Path
from PIL import Image
import requests

PROMPT = '''You are auditing Amazon product images for a strict sourcing filter.
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
 "evidence":"one or two sentences citing what you see"}'''

def ask(model, b64, prompt, port=11434, npred=700):
    r = requests.post(f"http://localhost:{port}/api/chat",
        json={"model": model, "stream": False, "options": {"temperature": 0, "num_predict": npred},
              "messages": [{"role": "user", "content": prompt, "images": [b64]}]}, timeout=900)
    if r.status_code != 200:
        return f"HTTP {r.status_code}: {r.text[:200]}"
    return r.json().get("message", {}).get("content", "").strip()

def b64_of(path, size=1024):
    img = Image.open(path).convert("RGB"); img.thumbnail((size, size))
    buf = io.BytesIO(); img.save(buf, format="JPEG", quality=85)
    return base64.b64encode(buf.getvalue()).decode()

for asin in ["B0DQDM7HKD", "B07W8W2PS6"]:
    p = sorted(Path(f"out_sb/images/{asin}").glob("*.jpg"))[0]
    print("=" * 25, asin, p.name)
    out = ask("minicpm-v", b64_of(p), PROMPT)
    print(out[:700])
