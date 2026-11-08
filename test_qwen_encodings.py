import base64, io
from pathlib import Path
from PIL import Image
import requests

def q(b64, prompt, model="qwen2.5vl:3b", npred=200):
    r = requests.post("http://localhost:11434/api/chat",
        json={"model": model, "stream": False, "options": {"temperature": 0, "num_predict": npred},
              "messages": [{"role": "user", "content": prompt, "images": [b64]}]}, timeout=600)
    return r.json().get("message", {}).get("content", "").strip()

tests = [
    ("original bytes B077HH98NC", base64.b64encode(Path("out_sb/images/B077HH98NC/01.jpg").read_bytes()).decode()),
    ("original bytes B07W8W2PS6", base64.b64encode(Path("out_sb/images/B07W8W2PS6/01.jpg").read_bytes()).decode()),
    ("resize 768 B077HH98NC", None),
]
img = Image.open("out_sb/images/B077HH98NC/01.jpg").convert("RGB"); img.thumbnail((768, 768))
buf = io.BytesIO(); img.save(buf, format="JPEG", quality=90)
tests[2] = ("resize 768 B077HH98NC", base64.b64encode(buf.getvalue()).decode())

for label, b64 in tests:
    print("=" * 20, label)
    print(repr(q(b64, "Describe this image in one sentence.")[:250]))
