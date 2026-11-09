"""Twenty-one held-out briefs across the three product lines the owner named.

Held-out means: none of these ids were used while the pipeline was being tuned, and the reference
for each is a real product photograph, not a render. Two lines have imagery on this machine —
Mogra Organics (Lion's Mane) and Word Coffee, whose photographs live in the owner's
`pictures for seller umbrella` folder. **Neck Nirvana has no imagery anywhere I can find** (the
brand folder exists and is empty), so its briefs are declared and left unscored rather than
invented.

    python tools/heldout_briefs.py --write
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "ty" / "seller_briefs.json"
OUT = ROOT / "ty" / "seller_briefs_heldout.json"

SITUATIONS = ("white_background_main", "lifestyle", "infographic", "scale_reference",
              "bundle_multipack", "packaging_mockup", "background_swap", "series_consistency",
              "packaging_mockup", "lifestyle", "white_background_main")

LIONS_MANE = [
    "renders/references/mogra/mogra_pair_main.png",
    "renders/references/mogra/mogra_pair_lifestyle.png",
    "renders/references/mogra/mogra_forest_dusk.png",
]
WORD_COFFEE = [
    "renders/references/word-coffee/word_coffee_moms_front.jpg",
    "renders/references/word-coffee/word_coffee_women_front.jpg",
    "renders/references/word-coffee/word_coffee_moms_20.png",
    "renders/references/word-coffee/word_coffee_logo.png",
]
CATEGORY = {"mogra": "supplement_pouch", "word-coffee": "coffee_box"}


def _constraints(template: Dict[str, Any], situation: str) -> Dict[str, Any]:
    base = dict(template.get("constraints") or {})
    base["dimensions"] = {"min_width": 1024, "min_height": 1024,
                          "max_width": 10000, "max_height": 10000}
    if situation in ("white_background_main", "packaging_mockup", "infographic"):
        base["background"] = {"value": 255, "tolerance": 10, "mode": "uniform"}
        base["text_rule"] = "expected" if situation == "infographic" else "no_text"
    else:
        base["background"] = {"value": None, "tolerance": 0, "mode": "free"}
        base["text_rule"] = "expected"
    base["fill_pct"] = {"min": 8, "max": 100, "distance": 40}
    return base


def build() -> Dict[str, Any]:
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    template = next((b for b in catalog["briefs"] if b.get("source_mode") != "prompt_only"),
                    catalog["briefs"][0])
    briefs: List[Dict[str, Any]] = []
    index = 0
    for line, refs in (("lions-mane", LIONS_MANE), ("word-coffee", WORD_COFFEE)):
        for n in range(11 if line == "word-coffee" else 10):
            index += 1
            situation = SITUATIONS[n % len(SITUATIONS)]
            reference = refs[n % len(refs)]
            briefs.append({
                "id": f"HO-{index:03d}",
                "category": CATEGORY.get(line, "supplement_pouch"),
                "product_line": line,
                "situation": situation,
                "difficulty": 1 + (n % 3),
                "source_mode": "uploaded_reference",
                "fidelity": "exact",
                "product_in_frame": True,
                "held_out": True,
                "reference": {
                    "kind": "uploaded_file",
                    "path": reference,
                    "descriptor": {"filename": Path(reference).name,
                                   "mime_type": ("image/png" if reference.endswith(".png")
                                                 else "image/jpeg"),
                                   "subject": line.replace("-", " ")},
                },
                "constraints": _constraints(template, situation),
                "note": ("Held-out: never used while tuning. A real product photograph is the "
                         "reference; the pipeline must composite it, not generate a lookalike."),
            })
    for n in range(3):
        index += 1
        briefs.append({
            "id": f"HO-{index:03d}",
            "category": "supplement_pouch",
            "product_line": "neck-nirvana",
            "situation": SITUATIONS[n],
            "difficulty": 1,
            "source_mode": "uploaded_reference",
            "fidelity": "exact",
            "product_in_frame": True,
            "held_out": True,
            "reference": {"kind": "uploaded_file", "path": None,
                          "descriptor": {"filename": "", "mime_type": "",
                                         "subject": "neck nirvana product"}},
            "constraints": _constraints(template, SITUATIONS[n]),
            "note": "No product imagery exists on this machine for this brand; unscored.",
        })
    payload = {"schema": "northstar.seller_briefs.heldout.v1",
               "note": ("21 held-out briefs plus 3 declared-but-unscorable Neck Nirvana ones. "
                        "The three are declared so the gap is visible, not so they can be scored."),
               "briefs": briefs}
    OUT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return payload


def append_to_catalog() -> Dict[str, Any]:
    """Make the held-out briefs runnable without making them part of the tuned catalogue."""
    payload = build()
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    ids = {b["id"] for b in payload["briefs"]}
    catalog["briefs"] = [b for b in catalog["briefs"] if b["id"] not in ids] + payload["briefs"]
    CATALOG.write_text(json.dumps(catalog, indent=2) + "\n", encoding="utf-8")
    return {"ok": True, "catalog": len(catalog["briefs"]), "held_out": len(ids)}


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Held-out briefs")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--append", action="store_true")
    ns = parser.parse_args(argv)
    result = append_to_catalog() if ns.append else build()
    print(json.dumps({"held_out": len(result["briefs"]),
                      "lines": sorted({b["product_line"] for b in result["briefs"]}),
                      "scorable": sum(1 for b in result["briefs"]
                                      if (b.get("reference") or {}).get("path"))}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
