import base64, io, re
from pathlib import Path
from PIL import Image
import requests

PROMPT = """Look at this Amazon product photo. Answer with exactly these lines:
FORM: powder / capsules / tablets / liquid / other
LIONS_MANE: yes / no / not visible
ORGANIC: yes / no / not visible
NET_WEIGHT: the net weight text printed on the label (like "16 oz" or "454 g"), or unknown
OTHER_INGREDIENTS: yes / no / unknown"""

def ask(model, b64, prompt):
    r = requests.post("http://localhost:11434/api/chat",
        json={"model": model, "stream": False, "options": {"temperature": 0, "num_predict": 300},
              "messages": [{"role": "user", "content": prompt, "images": [b64]}]}, timeout=600)
    return r.json().get("message", {}).get("content", "")

tests = [
    ("B077HH98NC", 0), ("B0GPY6GTK2", 0), ("B0C7LSXBH7", 0), ("B09TFZ39J1", 0),
]
for asin, idx in tests:
    d = Path("out_sb/images") / asin
    files = sorted(d.glob("*.jpg"))
    if not files:
        print(asin, "no images"); continue
    f = files[idx]
    img = Image.open(f).convert("RGB"); img.thumbnail((1024, 1024))
    buf = io.BytesIO(); img.save(buf, format="JPEG", quality=85)
    b64 = base64.b64encode(buf.getvalue()).decode()
    out = ask("moondream", b64, PROMPT)
    print("=" * 30, asin, f.name)
    print(out)
