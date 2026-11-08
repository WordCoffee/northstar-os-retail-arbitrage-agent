import base64, io
from pathlib import Path
from PIL import Image
import requests

asin = "B077HH98NC"
d = Path("out_sb/images") / asin
files = sorted(d.glob("*.jpg"))
print("files:", [(f.name, f.stat().st_size) for f in files])
img = Image.open(files[0]).convert("RGB")
img.thumbnail((1024, 1024))
buf = io.BytesIO(); img.save(buf, format="JPEG", quality=85)
b64 = base64.b64encode(buf.getvalue()).decode()

PROMPT = '''You are auditing Amazon product images for a strict sourcing filter.
Look ONLY at what is physically visible/printed in the images. Reply with ONLY a JSON object, no other text:
{"form":"powder_bag|powder_jar|powder_pouch|powder_bottle|capsules|tablets|liquid|gummies|cosmetic|whole_dried|other|unclear",
 "label_says_lions_mane":true_or_false,
 "net_weight_on_label":"verbatim text or null"}'''

r = requests.post("http://localhost:11434/api/chat",
    json={"model": "qwen2.5vl:3b", "stream": False, "options": {"temperature": 0, "num_predict": 700},
          "messages": [{"role": "user", "content": PROMPT, "images": [b64]}]},
    timeout=600)
print("HTTP", r.status_code)
resp = r.json()
print("done_reason:", resp.get("done_reason"))
print("content:", repr(resp["message"]["content"][:800]))
