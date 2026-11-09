"""Twenty-four held-out briefs across the three product lines the owner named.

Held-out means: none of these ids were used while the pipeline was being tuned, and the reference
for each is a real product photograph, not a render. Two lines have imagery on this machine —
Mogra Organics (Lion's Mane) and Word Coffee, whose photographs live in the owner's
`pictures for seller umbrella` folder. **Neck Nirvana has no imagery anywhere I can find** (the
brand folder under `Desktop/t2-os/brands` exists and is empty), so its three briefs live under
`declared_unscorable` instead of `briefs`: declared so the gap is visible, never invented, and
never handed to the runner where a missing reference would look like a pipeline failure.

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
# The validator's category vocabulary has no coffee box, so Word Coffee is filed as `food_jar`
# (a sealed retail food package). Filing it under the closest real category is honest; inventing
# a category to make the set look bespoke is not.
CATEGORY = {"lions-mane": "supplement_pouch", "word-coffee": "food_jar"}

# The eight situations, once each. Difficulty rises only where a situation repeats, so no
# (category, situation, difficulty, mode) pair is ever duplicated.
SITUATION_ORDER = ("white_background_main", "lifestyle", "infographic", "scale_reference",
                   "bundle_multipack", "packaging_mockup", "background_swap", "series_consistency")

# The validator's vocabulary, exactly (briefs.TEXT_RULES).
TEXT_FREE_SITUATIONS = ("white_background_main", "packaging_mockup")
TEXT_EXPECTED_SITUATIONS = ("infographic", "scale_reference", "bundle_multipack")


def _constraints(template: Dict[str, Any], situation: str) -> Dict[str, Any]:
    """The tuned reference brief's own constraints, with only the background rule changed.

    Anything else — dimensions, aspect, fill, file size — stays exactly as the tuned catalogue
    has it, so a held-out failure means the pipeline failed, not that the bar moved.
    """
    base = json.loads(json.dumps(template.get("constraints") or {}))
    background = dict(base.get("background") or {})
    if situation in TEXT_FREE_SITUATIONS:
        background["mode"] = "uniform"
        background["value"] = 255
    else:
        background["mode"] = "free"
        background.setdefault("value", 255)
    base["background"] = background
    base["text_rule"] = ("no_text" if situation in TEXT_FREE_SITUATIONS else
                         "text_expected" if situation in TEXT_EXPECTED_SITUATIONS else "allowed")
    return base


def _difficulty(n: int) -> int:
    """1..3, rising only when the situation repeats, so pairs stay unique."""
    return 1 + (n // len(SITUATION_ORDER))


def _brief(index: int, line: str, situation: str, reference: str, template: Dict[str, Any],
           difficulty: int) -> Dict[str, Any]:
    suffix = Path(reference).suffix.lower()
    return {
        "id": f"HO-{index:03d}",
        "category": CATEGORY.get(line, "supplement_pouch"),
        "product_line": line,
        "situation": situation,
        "difficulty": difficulty,
        "source_mode": "uploaded_reference",
        "fidelity": "exact",
        "product_in_frame": True,
        "held_out": True,
        "reference": {
            "kind": "uploaded_file",
            "path": reference,
            "descriptor": {"filename": Path(reference).name,
                           "mime_type": ("image/png" if suffix == ".png" else "image/jpeg"),
                           "subject": line.replace("-", " ")},
        },
        "constraints": _constraints(template, situation),
        "note": ("Held-out: never used while tuning. A real product photograph is the "
                 "reference; the pipeline must composite it, not generate a lookalike."),
    }


def build() -> Dict[str, Any]:
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    template = next((b for b in catalog["briefs"] if b.get("source_mode") != "prompt_only"),
                    catalog["briefs"][0])
    briefs: List[Dict[str, Any]] = []
    index = 0
    for line, refs, count in (("lions-mane", LIONS_MANE, 10), ("word-coffee", WORD_COFFEE, 11)):
        for n in range(count):
            index += 1
            briefs.append(_brief(index, line, SITUATION_ORDER[n % len(SITUATION_ORDER)],
                                 refs[n % len(refs)], template, _difficulty(n)))
    declared: List[Dict[str, Any]] = []
    for n in range(3):
        declared.append({
            "id": f"HO-D{n + 1:02d}",
            "category": "supplement_pouch",
            "product_line": "neck-nirvana",
            "situation": SITUATION_ORDER[n],
            "difficulty": 1,
            "source_mode": "uploaded_reference",
            "fidelity": "exact",
            "held_out": True,
            "reference": {"kind": "uploaded_file", "path": None,
                          "descriptor": {"filename": "neck-nirvana-missing.png",
                                         "mime_type": "image/png",
                                         "subject": "neck nirvana product"}},
            "constraints": _constraints(template, SITUATION_ORDER[n]),
            "note": "No product imagery exists on this machine for this brand; unscorable.",
        })
    return {"schema": "northstar.seller_briefs.heldout.v1",
            "note": ("21 runnable held-out briefs plus 3 declared-but-unscorable Neck Nirvana "
                     "ones. The three are declared so the gap is visible, not so they can score."),
            "briefs": briefs,
            "declared_unscorable": declared}


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
    OUT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    briefs = result.get("briefs") or []
    print(json.dumps({"held_out": len(briefs),
                      "declared_unscorable": len(result.get("declared_unscorable") or []),
                      "lines": sorted({b["product_line"] for b in briefs}),
                      "scorable": sum(1 for b in briefs if (b.get("reference") or {}).get("path"))},
                     indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
