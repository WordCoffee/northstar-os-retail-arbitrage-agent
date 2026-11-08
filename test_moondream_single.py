import base64, io, re
from pathlib import Path
from PIL import Image
import requests

def ask(model, b64, prompt, npred=120):
    r = requests.post("http://localhost:11434/api/chat",
        json={"model": model, "stream": False, "options": {"temperature": 0, "num_predict": npred},
              "messages": [{"role": "user", "content": prompt, "images": [b64]}]}, timeout=600)
    return r.json().get("message", {}).get("content", "").strip()

def img_b64(path):
    img = Image.open(path).convert("RGB"); img.thumbnail((1024, 1024))
    buf = io.BytesIO(); img.save(buf, format="JPEG", quality=85)
    return base64.b64encode(buf.getvalue()).decode()

img = "out_sb/images/B07W8W2PS6/01.jpg"
b64 = img_b64(img)
questions = [
    ("form", "Is this product a powder, capsules, tablets, or a liquid? Answer with one word."),
    ("weight", "What is the net weight printed on this product label? Answer with only that text."),
    ("lm", "Does the product label say Lion's Mane? Answer yes or no."),
    ("organic", "Does the product label say Organic or USDA Organic? Answer yes or no."),
    ("caps", "Are there any capsules or tablets visible in this image? Answer yes or no."),
]
for name, q in questions:
    print(f"[{name}] -> {ask('moondream', b64, q)!r}")

# also test failing image
img2 = "out_sb/images/B077HH98NC/01.jpg"
b64b = img_b64(img2)
print("--- B077HH98NC")
for name, q in questions:
    print(f"[{name}] -> {ask('moondream', b64b, q)!r}")
