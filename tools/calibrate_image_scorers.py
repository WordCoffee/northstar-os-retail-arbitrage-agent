"""Calibrate the two image scorers on this box's real outputs.

Writes one JSON record per image to state/evidence/image_review_calibration_20261104.json.
Text used for each row is the brief the surface was generated from.
"""
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "Northstar_backend"))

import image_review_scorers as s  # noqa: E402

OUT = ROOT / "state" / "evidence" / "image_review_calibration_20261104.json"

POUCH = ("a product photograph of a matte kraft stand-up coffee pouch with a cream "
         "label, lion's mane mushroom coffee, front facing")
BACK = ("a product photograph of the back of a matte kraft stand-up coffee pouch "
        "with a cream nutrition label")
TIKTOK = ("a vertical social frame of a kraft coffee pouch with the headline "
          "fuel your focus")
WHITE = ("a product photograph of a kraft coffee pouch on a pure white background, "
         "centred, soft shadow")
BLANK = ("a product photograph of a kraft coffee pouch with a cream label")

ROWS = [
    ("product_front", ROOT / "renders/mogra_lions_mane/product_front.png", POUCH),
    ("product_back", ROOT / "renders/mogra_lions_mane/product_back.png", BACK),
    ("tiktok_frame", ROOT / "Northstar_backend/data/studio_generated/tiktok_e445423614.png", TIKTOK),
    ("listing_white_bg", ROOT / "Northstar_backend/data/studio_generated/white-bg_67b967d23c.png", WHITE),
    ("rejected_white_bg_a", ROOT / "Northstar_backend/data/studio_generated/rejected_white-bg_2086282da3.png", WHITE),
    ("rejected_white_bg_b", ROOT / "Northstar_backend/data/studio_generated/rejected_white-bg_b5b819fb85.png", WHITE),
    ("flat_label_art", ROOT / "renders/mogra_lions_mane/mogra_lions_mane_front_label.png", BLANK),
]

rows = []
for name, path, text in ROWS:
    if not path.is_file():
        rows.append({"name": name, "skipped": "missing", "path": str(path)})
        continue
    png = path.read_bytes()
    record = {"name": name, "path": str(path.relative_to(ROOT)), "text": text}
    for axis in ("adherence", "preference"):
        started = time.time()
        result = s.score(axis, png, text)
        record[axis] = result.get("score")
        record[f"{axis}_error"] = result.get("error")
        record[f"{axis}_seconds"] = round(time.time() - started, 1)
    rows.append(record)
    print(json.dumps(record), flush=True)

OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(json.dumps({"calibrated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                           "available": s.available(), "rows": rows}, indent=2),
               encoding="utf-8")
print("wrote", OUT)
