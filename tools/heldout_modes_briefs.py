"""Held-out briefs for the two input modes that had never been scored.

The published held-out run covers **uploaded-reference** only, and the capability label said so. This
builds the other two:

* **prompt-only** (12 briefs) — no reference image at all. The pipeline has to generate the picture
  from the brief's own description, so fidelity is `tolerant` and the route is `full_generation`.
  This mode is the one a seller uses when they have no photograph yet, and it was never measured.
* **stored-reference** (12 briefs) — the reference lives in the repo under `renders/`, fidelity is
  `exact`, so the composite route must preserve the seller's pixels.

Both sets use the tuned catalogue's constraint profile for their situation, and both draw on the
products that actually have imagery on this machine (Mogra Lion's Mane / Shiitake, Word Coffee).

    python tools/heldout_modes_briefs.py --write
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "ty" / "seller_briefs.json"
OUT = ROOT / "ty" / "seller_briefs_heldout_modes.json"

SITUATIONS = ("white_background_main", "lifestyle", "scale_reference", "bundle_multipack",
              "background_swap", "series_consistency", "infographic", "packaging_mockup")

LIONS_MANE = [
    "renders/references/mogra/mogra_pair_main.png",
    "renders/references/mogra/mogra_pair_lifestyle.png",
    "renders/references/mogra/mogra_forest_dusk.png",
]
WORD_COFFEE = [
    "renders/references/word-coffee/word_coffee_moms_front.jpg",
    "renders/references/word-coffee/word_coffee_women_front.jpg",
    "renders/references/word-coffee/wc_women_pic_box.jpg",
    "renders/references/word-coffee/wc_women_easter_table.png",
    "renders/references/word-coffee/wc_women_in_purse.png",
]

#: Prompt-only needs words, not a file: the description is the product specification the seller
#: would type. Nothing here claims a benefit; it describes what to show.
PROMPT_PRODUCT = {
    "lions-mane": ("a matte forest-green stand-up pouch with a white round label reading "
                   "MOGRA ORGANICS and ORGANIC LION'S MANE MUSHROOM POWDER, gold mushroom line art, "
                   "6 oz (170 g) printed at the base"),
    "word-coffee": ("a slim pale-pink and cream gift box printed Word Coffee, the words "
                    "For Mom in large lilac script, and the line Empowering Moms, One Message "
                    "at a Time"),
}
CATEGORY = {"lions-mane": "supplement_pouch", "word-coffee": "food_jar"}
SCENE = {
    "white_background_main": "on a seamless white studio background, product centred, no props",
    "lifestyle": "on a light oak kitchen counter in morning light, shallow depth of field",
    "scale_reference": "standing beside a coffee cup for scale, white background",
    "bundle_multipack": "three identical units arranged as a bundle, white background",
    "background_swap": "floating against a soft sage-green gradient, studio lighting",
    "series_consistency": "in the same lighting and framing as the rest of the range, grey backdrop",
    "infographic": "centred on a clean page with generous white margins, room for callouts",
    "packaging_mockup": "on a matte studio surface under a soft key light, slight perspective",
}


def _profiles(catalog: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    out: Dict[str, Dict[str, Any]] = {}
    for brief in catalog.get("briefs") or []:
        if brief.get("source_mode") == "prompt_only":
            continue
        out.setdefault(brief["situation"], json.loads(json.dumps(brief["constraints"])))
    return out


def _prompt_only(index: int, line: str, situation: str, difficulty: int,
                 profiles: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    product = PROMPT_PRODUCT[line]
    scene = SCENE[situation]
    return {
        "id": f"PO-{index:03d}",
        "category": CATEGORY[line],
        "product_line": line,
        "situation": situation,
        "difficulty": difficulty,
        "source_mode": "prompt_only",
        "fidelity": "tolerant",
        "product_in_frame": True,
        "held_out": True,
        "prompt": f"Product photograph of {product}, {scene}. Photorealistic, no text overlay.",
        "constraints": json.loads(json.dumps(profiles[situation])),
        "note": ("Held-out, prompt-only: no reference image exists for this brief, so the pipeline "
                 "generates the product from the description. Fidelity is tolerant by definition."),
    }


def _stored(index: int, line: str, situation: str, difficulty: int, path: str,
            profiles: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    suffix = Path(path).suffix.lower()
    return {
        "id": f"SR-{index:03d}",
        "category": CATEGORY[line],
        "product_line": line,
        "situation": situation,
        "difficulty": difficulty,
        "source_mode": "stored_reference",
        "fidelity": "exact",
        "product_in_frame": True,
        "held_out": True,
        "reference": {
            "kind": "stored_asset",
            "path": path,
            "descriptor": {"filename": Path(path).name,
                           "mime_type": "image/png" if suffix == ".png" else "image/jpeg",
                           "subject": line.replace("-", " ")},
        },
        "constraints": json.loads(json.dumps(profiles[situation])),
        "note": ("Held-out, stored-reference: the reference is a committed product image, so the "
                 "composite route must keep the seller's pixels."),
    }


def build() -> Dict[str, Any]:
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    profiles = _profiles(catalog)
    briefs: List[Dict[str, Any]] = []
    for n in range(12):
        line = "lions-mane" if n % 2 == 0 else "word-coffee"
        situation = SITUATIONS[n % len(SITUATIONS)]
        briefs.append(_prompt_only(n + 1, line, situation, 1 + (n // len(SITUATIONS)), profiles))
    for n in range(12):
        line = "lions-mane" if n % 2 == 0 else "word-coffee"
        situation = SITUATIONS[n % len(SITUATIONS)]
        pool = LIONS_MANE if line == "lions-mane" else WORD_COFFEE
        briefs.append(_stored(n + 1, line, situation, 1 + (n // len(SITUATIONS)),
                              pool[(n // 2) % len(pool)], profiles))
    return {
        "schema": "northstar.seller_briefs.heldout_modes.v1",
        "note": ("Twelve prompt-only and twelve stored-reference held-out briefs, so every input "
                 "mode carries at least ten scored outputs and the capability label can name the "
                 "modes that are actually measured."),
        "briefs": briefs,
    }


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Held-out briefs for prompt-only and stored-reference")
    parser.add_argument("--write", action="store_true")
    ns = parser.parse_args(argv)
    payload = build()
    if ns.write:
        OUT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    by_mode: Dict[str, int] = {}
    for brief in payload["briefs"]:
        by_mode[brief["source_mode"]] = by_mode.get(brief["source_mode"], 0) + 1
    print(json.dumps({"briefs": len(payload["briefs"]), "by_mode": by_mode,
                      "path": str(OUT.relative_to(ROOT))}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
