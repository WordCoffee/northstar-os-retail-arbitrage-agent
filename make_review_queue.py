import json
from pathlib import Path

out_dir = Path("out_lions_mane")
cands_file = out_dir / "candidates_visual.json"
manifest_file = out_dir / "images_manifest.json"

if not cands_file.exists():
    print("Run text-gate first to produce candidates_visual.json")
    exit(1)

cands = json.loads(cands_file.read_text(encoding="utf-8"))
manifest = json.loads(manifest_file.read_text(encoding="utf-8")) if manifest_file.exists() else {}

queue = []
for c in cands:
    asin = c["asin"]
    imginfo = manifest.get(asin, {})
    saved = imginfo.get("saved", [])
    image_paths = [s["file"] for s in saved]
    queue.append({
        "asin": asin,
        "title": c["title"],
        "brand": c.get("brand"),
        "price": c.get("price"),
        "size_oz": c.get("size_oz"),
        "images": image_paths,
        "text_flags": c.get("text_review", []),
        # fields for the reviewer to fill
        "visual_verdict": "",  # PASS, REVIEW, or REJECT
        "visual_reasons": "",
        "form": "",
        "label_says_lions_mane": "",
        "label_says_organic": "",
        "usda_organic_seal_visible": "",
        "other_ingredients_on_label": "",
        "mentions_extract_or_mycelium": "",
        "net_weight_on_label": "",
        "net_weight_oz": "",
        "confidence": "",
        "evidence": ""
    })

(out_dir / "image_review_queue.json").write_text(json.dumps(queue, indent=2), encoding="utf-8")
print(f"Wrote {len(queue)} candidates to image_review_queue.json")
print("Please review the images and fill in the visual_verdict and related fields.")
print("Then run: python lions_mane_pull.py finalize")