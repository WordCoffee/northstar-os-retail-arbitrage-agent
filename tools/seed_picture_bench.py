"""Seed the fixed product-picture bench: 60 cases, 20 per input mode.

The bench is data, not code. It is written once, deterministically, and then
left alone: the whole point of a held-out set is that it was fixed BEFORE the
work started. Regenerating it after a change would launder the measurement.

Three input modes, because those are the three ways a seller actually asks:

    from_scratch        only a prompt
    stored_reference    a picture this system generated earlier (the library)
    uploaded_reference  a real photo / logo / packaging the seller supplied

Twenty cases per mode, spread across the scenarios a listing needs. Every
fourth case is held out (so 5 per mode, 15 in total) and is not used for
tuning.

    python tools/seed_picture_bench.py            # write the two files
    python tools/seed_picture_bench.py --check    # verify they still match
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "eval" / "product_pictures"

# (scenario, surface, brief, expected terms)
SCENARIOS = [
    ("main_white", "main",
     "studio product photograph of a matte kraft stand-up coffee pouch with a cream label, "
     "centred on a pure white seamless background, soft shadow, packshot lighting", []),
    ("lifestyle_kitchen", "lifestyle",
     "lifestyle photograph of the same kraft coffee pouch on a wooden kitchen counter beside "
     "a ceramic mug, morning window light", []),
    ("infographic_callouts", "infographic",
     "clean infographic product image of the kraft coffee pouch with three callout panels "
     "listing 2000 mg lion's mane, 85 servings, 2 g per serving", ["2000 mg", "85 servings"]),
    ("scale_comparison", "scale",
     "product photograph of the kraft coffee pouch next to a standard 12 oz mug to show its "
     "size, plain background, even lighting", []),
    ("feature_closeup", "closeup",
     "macro photograph of the kraft pouch zip seal and the cream label edge, showing the "
     "material texture and print quality", []),
    ("multi_angle_set", "set",
     "three-quarter angle product photograph of the kraft coffee pouch, same lighting as the "
     "front shot, plain background", []),
    ("bundle_variety", "bundle",
     "product photograph of three flavours of the kraft coffee pouch standing together, "
     "variety pack, plain background, even lighting", []),
    ("before_after", "comparison",
     "split comparison image: left the plain kraft pouch, right the pouch with its designed "
     "cream label, same angle and lighting, thin divider", []),
    ("seasonal_variant", "promotional",
     "seasonal promotional photograph of the kraft coffee pouch with warm autumn leaves and a "
     "soft amber light, product unchanged", []),
    ("aplus_module", "aplus",
     "A+ content module image: the kraft pouch on the left, a short ingredient story panel on "
     "the right, cream and forest-green palette", []),
    ("packaging_pouch_front", "packaging",
     "packaging mockup of the stand-up pouch, front face, flat lay on a light surface, no text "
     "rendered by the model", []),
    ("packaging_box_rear", "packaging",
     "packaging mockup of the rear panel of a kraft box for the same product, flat lay, plain "
     "light surface", []),
    ("background_swap", "edit",
     "the same pouch re-shot on a pale linen backdrop instead of white, identical product, "
     "identical framing", []),
    ("consistent_series_1", "series",
     "product photograph of the kraft coffee pouch, front, on pure white, for a consistent "
     "series", []),
    ("consistent_series_2", "series",
     "product photograph of the kraft coffee pouch, back label, on pure white, same framing "
     "and lighting as the front shot of the series", []),
    ("oversize_export", "main",
     "high resolution packshot of the kraft coffee pouch on pure white, centred, at least "
     "2000 pixels on the longest side", []),
    ("ingredient_detail", "closeup",
     "close-up of a small pile of dried lion's mane mushroom beside the pouch, shallow depth "
     "of field", []),
    ("gift_pack", "bundle",
     "gift presentation of the kraft pouch inside an open kraft gift box with tissue paper, "
     "product fully visible", []),
    ("countertop_context", "lifestyle",
     "the kraft pouch on a cafe counter next to a barista tamping espresso, product in sharp "
     "focus in the foreground", []),
    ("secondary_benefit", "secondary",
     "secondary listing image of the kraft pouch with a clean right-hand panel for benefit "
     "copy, product on the left third", []),
]

MODES = ("from_scratch", "stored_reference", "uploaded_reference")


def build() -> dict:
    cases = []
    for mode in MODES:
        for i, (scenario, surface, brief, terms) in enumerate(SCENARIOS, start=1):
            case_id = f"{mode[:4]}-{i:02d}-{scenario}"
            case = {
                "id": case_id,
                "mode": mode,
                "scenario": scenario,
                "surface": surface,
                "brief": brief,
                "expected_terms": terms,
                "split": "held_out" if i % 4 == 0 else "dev",
                "width": 2000 if scenario == "oversize_export" else 1024,
                "height": 2000 if scenario == "oversize_export" else 1024,
            }
            if mode == "stored_reference":
                case["reference"] = {"brand": "mogra", "product": "lions_mane",
                                     "kind": "product_photo"}
            elif mode == "uploaded_reference":
                case["reference"] = {"file": "renders/mogra_lions_mane/product_front.png"}
            cases.append(case)
    return {
        "schema_version": 1,
        "frozen": True,
        "note": ("Fixed before tuning. Do not regenerate after a change: a held-out set "
                 "that moves is not held out. Split: dev for iteration, held_out for the bar."),
        "modes": list(MODES),
        "scenarios": [s[0] for s in SCENARIOS],
        "cases": cases,
    }


def write(force: bool = False) -> dict:
    OUT.mkdir(parents=True, exist_ok=True)
    data = build()
    path = OUT / "cases.json"
    if path.is_file() and not force:
        current = json.loads(path.read_text(encoding="utf-8"))
        return {"ok": current == data, "path": str(path),
                "note": "already seeded; pass --force only if it was never used for a run"}
    text = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
    path.write_text(text, encoding="utf-8")
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    (OUT / "cases.sha256").write_text(digest + "\n", encoding="utf-8")
    return {"ok": True, "path": str(path), "cases": len(data["cases"]), "sha256": digest}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Seed the fixed picture bench.")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--check", action="store_true")
    ns = parser.parse_args(argv)
    result = write(force=ns.force)
    print(json.dumps(result, indent=2))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
