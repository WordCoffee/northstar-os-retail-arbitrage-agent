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
    "renders/references/word-coffee/wc_moms_22.png",
    "renders/references/word-coffee/wc_moms_24.png",
    "renders/references/word-coffee/wc_moms_29.png",
    "renders/references/word-coffee/wc_moms_33.png",
    "renders/references/word-coffee/wc_women_37.png",
    "renders/references/word-coffee/wc_women_40.png",
    "renders/references/word-coffee/wc_women_45.png",
    "renders/references/word-coffee/wc_women_46.png",
]
# Deliberately not the brand wordmark: a logo is not a product, and two briefs that share one
# produced byte-identical composites in the first run. Eleven briefs, eleven distinct photographs.
# The validator's category vocabulary has no coffee box, so Word Coffee is filed as `food_jar`
# (a sealed retail food package). Filing it under the closest real category is honest; inventing
# a category to make the set look bespoke is not.
CATEGORY = {"lions-mane": "supplement_pouch", "word-coffee": "food_jar"}

# The eight situations, once each. Difficulty rises only where a situation repeats, so no
# (category, situation, difficulty, mode) pair is ever duplicated.
SITUATION_ORDER = ("white_background_main", "lifestyle", "infographic", "scale_reference",
                   "bundle_multipack", "packaging_mockup", "background_swap", "series_consistency")

#: The constraint profile for each situation is the tuned catalogue's own, copied straight across.
#: Taking one arbitrary brief's constraints and reusing them for every situation is what the first
#: held-out run did, and it put a required white matte on lifestyle and infographic briefs: 21 of 21
#: briefs then failed `alpha_matte` for a rule that was never about them. The held-out part of a
#: held-out brief is the **product photograph**, never the bar.
def _situation_profiles(catalog: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    profiles: Dict[str, Dict[str, Any]] = {}
    for brief in catalog.get("briefs") or []:
        if brief.get("source_mode") == "prompt_only":
            continue
        situation = brief.get("situation")
        constraints = brief.get("constraints")
        if situation and isinstance(constraints, dict) and situation not in profiles:
            profiles[situation] = json.loads(json.dumps(constraints))
    return profiles


def _constraints(profiles: Dict[str, Dict[str, Any]], situation: str) -> Dict[str, Any]:
    """The tuned constraints for this situation, unmodified. A missing one is a bug, not a guess."""
    if situation not in profiles:
        raise KeyError(f"the tuned catalogue has no non-prompt-only brief for {situation!r}, "
                       "so a held-out brief cannot inherit a fair bar for it")
    return json.loads(json.dumps(profiles[situation]))


def _difficulty(n: int) -> int:
    """1..3, rising only when the situation repeats, so pairs stay unique."""
    return 1 + (n // len(SITUATION_ORDER))


def _brief(index: int, line: str, situation: str, reference: str,
           profiles: Dict[str, Dict[str, Any]], difficulty: int) -> Dict[str, Any]:
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
        "constraints": _constraints(profiles, situation),
        "note": ("Held-out: never used while tuning. A real product photograph is the "
                 "reference; the pipeline must composite it, not generate a lookalike."),
    }


def build() -> Dict[str, Any]:
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    profiles = _situation_profiles(catalog)
    briefs: List[Dict[str, Any]] = []
    index = 0
    for line, refs, count in (("lions-mane", LIONS_MANE, 10), ("word-coffee", WORD_COFFEE, 11)):
        for n in range(count):
            index += 1
            briefs.append(_brief(index, line, SITUATION_ORDER[n % len(SITUATION_ORDER)],
                                 refs[n % len(refs)], profiles, _difficulty(n)))
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
            "constraints": _constraints(profiles, SITUATION_ORDER[n]),
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
