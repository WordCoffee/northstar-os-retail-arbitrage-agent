import base64, io
from pathlib import Path
from PIL import Image
import requests

def ask(model, b64, prompt):
    r = requests.post("http://localhost:11434/api/chat",
        json={"model": model, "stream": False, "options": {"temperature": 0, "num_predict": 400},
              "messages": [{"role": "user", "content": prompt, "images": [b64]}]}, timeout=600)
    return r.json().get("message", {}).get("content", "")[:300]

for asin in ["B077HH98NC", "B0GPY6GTK2"]:
    d = Path("out_sb/images") / asin
    for f in sorted(d.glob("*.jpg"))[:2]:
        img = Image.open(f).convert("RGB")
        print(f"{asin}/{f.name}: size={img.size} mode={img.mode}")
        img.thumbnail((1024, 1024))
        buf = io.BytesIO(); img.save(buf, format="JPEG", quality=85)
        b64 = base64.b64encode(buf.getvalue()).decode()
        print("  qwen describe:", repr(ask("qwen2.5vl:3b", b64, "Describe this image in one sentence.")[:200]))
        print("  moon describe:", repr(ask("moondream", b64, "Describe this image in one sentence.")[:200]))
