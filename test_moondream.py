#!/usr/bin/env python3
"""Test moondream via Ollama's OpenAI-compatible endpoint on a local product image (base64)."""
import base64, json, sys
from pathlib import Path
import requests

IMG = Path(sys.argv[1] if len(sys.argv) > 1 else "out_lions_mane/images/B07W8W2PS6/01.jpg")
b64 = base64.b64encode(IMG.read_bytes()).decode()
prompt = ("Look at the product label in this image. Answer briefly: "
          "1) Is this a powder or capsules? 2) What product does the label say? "
          "3) Does it say organic? 4) What is the net weight printed on the label?")
r = requests.post("http://localhost:11434/v1/chat/completions",
                  headers={"Authorization": "Bearer ollama"},
                  json={"model": "moondream", "temperature": 0, "messages": [
                      {"role": "user", "content": [
                          {"type": "text", "text": prompt},
                          {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}}]}]},
                  timeout=300)
print("HTTP", r.status_code)
d = r.json()
print(d["choices"][0]["message"]["content"])
