import base64, io
from pathlib import Path
from PIL import Image
import requests

def q(b64, prompt, model="qwen2.5vl:7b", npred=400):
    r = requests.post("http://localhost:11434/api/chat",
        json={"model": model, "stream": False, "options": {"temperature": 0, "num_predict": npred},
              "messages": [{"role": "user", "content": prompt, "images": [b64]}]}, timeout=900)
    if r.status_code != 200:
        return f"HTTP {r.status_code}: {r.text[:200]}"
    return r.json().get("message", {}).get("content", "").strip()

def b64_of(path, size=1024):
    img = Image.open(path).convert("RGB"); img.thumbnail((size, size))
    buf = io.BytesIO(); img.save(buf, format="JPEG", quality=85)
    return base64.b64encode(buf.getvalue()).decode()

for asin, fname in [("B077HH98NC", "01.jpg"), ("B07W8W2PS6", "01.jpg"), ("B0GPY6GTK2", "01.jpg")]:
    p = f"out_sb/images/{asin}/{fname}"
    print("=" * 25, asin)
    print("desc:", repr(q(b64_of(p), "Describe this image in one sentence.")[:250]))
    print("form:", repr(q(b64_of(p), "Is this product a powder, capsules, tablets, or a liquid? Answer with one word.")[:80]))
    print("weight:", repr(q(b64_of(p), "What is the net weight printed on this product label? Answer with only that text.")[:100]))
