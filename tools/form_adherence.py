"""Form adherence measurement: render four briefs, then ask a local vision model what
container actually appears. Compares requested vs observed; nothing is assumed.
"""
from __future__ import annotations

import base64
import io
import json
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = "http://127.0.0.1:8000"
OLLAMA = "http://127.0.0.1:11434"
VISION = "qwen3.5:4b"
OUT = ROOT / "state" / "evidence" / "form_adherence.json"

FORMS = {
    "pouch": "a 6 oz stand-up pouch",
    "box": "a rigid folding carton box",
    "bottle": "a 500 ml plastic bottle with a screw cap",
    "tube": "a squeeze tube",
}

BRIEF = ("{form} of organic lion's mane mushroom powder on a warm neutral background, "
         "soft studio light, premium packaging photography, no text, no lettering")

QUESTION = ("Look at the image. Which single container form is shown: stand-up pouch, "
            "rigid box, bottle, or squeeze tube? Answer with one word from that list.")

HEADERS = {"X-User-Id": "demo-t2", "Content-Type": "application/json"}


def post(url: str, payload: dict, timeout: float = 600.0, headers: dict | None = None):
    req = urllib.request.Request(url, data=json.dumps(payload).encode(),
                                 headers=headers or {"Content-Type": "application/json"},
                                 method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


def render(form_text: str, requested: str) -> dict:
    started = time.time()
    res = post(f"{BASE}/api/design-studio/generate",
               {"kind": "image", "brief": BRIEF.format(form=form_text), "tier": "draft",
                "text_safe": True, "form": requested}, headers=HEADERS)
    asset = (res or {}).get("asset") or {}
    aid = asset.get("id")
    data = b""
    if aid:
        req = urllib.request.Request(f"{BASE}/api/design-studio/assets/{aid}/file",
                                     headers={"X-User-Id": "demo-t2"})
        with urllib.request.urlopen(req, timeout=60) as r:
            data = r.read()
    return {"asset_id": aid, "bytes": len(data), "elapsed_s": round(time.time() - started, 1),
            "data": data}


def classify(png: bytes) -> str:
    b64 = base64.b64encode(png).decode()
    res = post(f"{OLLAMA}/api/generate",
               {"model": VISION, "prompt": QUESTION, "images": [b64], "stream": False,
                "think": False, "options": {"num_predict": 40, "temperature": 0.0}})
    return str(res.get("response") or "").strip().lower()


def main() -> int:
    rows = []
    for requested, text in FORMS.items():
        try:
            r = render(text, requested)
            observed = classify(r["data"]) if r["data"] else "no-image"
        except Exception as exc:  # noqa: BLE001
            rows.append({"requested": requested, "error": f"{type(exc).__name__}: {str(exc)[:120]}"})
            continue
        hit = requested in observed
        rows.append({"requested": requested, "observed": observed[:60], "match": hit,
                     "asset_id": r["asset_id"], "bytes": r["bytes"],
                     "render_s": r["elapsed_s"]})
    matched = sum(1 for r in rows if r.get("match"))
    record = {"model": VISION, "tier": "draft", "rows": rows,
              "matched": matched, "of": len(rows)}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(record, indent=2), encoding="utf-8")
    print(json.dumps(record, indent=2))
    return 0 if matched >= 3 else 1


if __name__ == "__main__":
    raise SystemExit(main())
