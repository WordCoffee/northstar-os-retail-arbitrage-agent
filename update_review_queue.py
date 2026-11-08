import json
from pathlib import Path

out_dir = Path("out_lions_mane")
verdicts_file = out_dir / "image_audit_verdicts.json"
queue_file = out_dir / "image_review_queue.json"

verdicts = {}
if verdicts_file.exists():
    verdicts = json.loads(verdicts_file.read_text(encoding="utf-8"))

cands_file = out_dir / "candidates_visual.json"
manifest_file = out_dir / "images_manifest.json"

cands = json.loads(cands_file.read_text(encoding="utf-8"))
manifest = json.loads(manifest_file.read_text(encoding="utf-8")) if manifest_file.exists() else {}

queue = []
for c in cands:
    asin = c["asin"]
    imginfo = manifest.get(asin, {})
    saved = imginfo.get("saved", [])
    image_paths = [s["file"] for s in saved]
    v = verdicts.get(asin, {})
    queue.append({
        "asin": asin,
        "title": c["title"],
        "brand": c.get("brand"),
        "price": c.get("price"),
        "size_oz": c.get("size_oz"),
        "images": image_paths,
        "text_flags": c.get("text_review", []),
        # pre-fill from existing verdicts if any
        "visual_verdict": v.get("auditor", ""),  # we will map auditor to PASS/REVIEW/REJECT? Actually we need to infer.
        # Better to leave visual_verdict empty and let user fill, but we can provide the evidence.
        "form": v.get("form", ""),
        "label_says_lions_mane": str(v.get("label_says_lions_mane", "")),
        "label_says_organic": str(v.get("label_says_organic", "")),
        "usda_organic_seal_visible": str(v.get("usda_organic_seal_visible", "")),
        "other_ingredients_on_label": v.get("other_ingredients_on_label", []),
        "mentions_extract_or_mycelium": v.get("mentions_extract_or_mycelium", ""),
        "net_weight_on_label": v.get("net_weight_on_label", ""),
        "net_weight_oz": v.get("net_weight_oz", ""),
        "confidence": v.get("confidence", ""),
        "evidence": v.get("evidence", ""),
    })

(queue_file).write_text(json.dumps(queue, indent=2, ensure_ascii=False), encoding="utf-8")
print(f"Wrote {len(queue)} candidates to image_review_queue.json")
print("Existing verdicts have been pre-filled where available.")
print("Please review the images and complete the visual_verdict field (PASS, REVIEW, or REJECT) and any missing details.")
print("Then run: python lions_mane_pull.py finalize")