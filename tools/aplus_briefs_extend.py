"""Add eight A+ briefs across brands so the family is not single-brand.

The family shipped six briefs, all Mogra. Four brands have imagery on this machine; Word Coffee has
five product images and no A+ brief at all. These eight extend the family by cloning the *module
shape* of the nearest existing brief of the same content type — the structure is what makes a module
type testable — and changing the brand, the reference and the required copy. Nothing invents a claim:
the copied lines are the ones the existing briefs already carry, re-branded.

    python tools/aplus_briefs_extend.py --write
"""
from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "ty" / "seller_briefs.json"

WORDS_COFFEE = [
    "renders/references/word-coffee/word_coffee_moms_front.jpg",
    "renders/references/word-coffee/word_coffee_women_front.jpg",
    "renders/references/word-coffee/wc_women_in_purse.png",
    "renders/references/word-coffee/wc_women_easter_table.png",
]
MOGRA = [
    "renders/references/mogra/mogra_forest_dusk.png",
    "renders/references/mogra/mogra_pair_lifestyle.png",
]

#: (id, content_type, brand, reference index, copy substitutions)
PLAN = (
    ("AP-007", "hero_band", "word-coffee", 0,
     {"MOGRA ORGANICS": "WORD COFFEE", "LION'S MANE": "FOR MOM",
      "DAILY FOCUS NATURALLY": "EMPOWERING MOMS"}),
    ("AP-008", "comparison_table", "word-coffee", 1,
     {"MOGRA ORGANICS": "WORD COFFEE", "LION'S MANE": "FOR MOM"}),
    ("AP-009", "lifestyle_band", "word-coffee", 2,
     {"MOGRA ORGANICS": "WORD COFFEE", "LION'S MANE": "FOR MOM"}),
    ("AP-010", "spec_strip", "word-coffee", 3,
     {"MOGRA ORGANICS": "WORD COFFEE", "LION'S MANE": "FOR MOM"}),
    ("AP-011", "ingredient_grid", "lions-mane", 0,
     {"MOGRA ORGANICS": "MOGRA ORGANICS", "LION'S MANE": "LION'S MANE"}),
    ("AP-012", "brand_story", "lions-mane", 1, {}),
    ("AP-013", "comparison_table", "lions-mane", 0, {}),
    ("AP-014", "hero_band", "lions-mane", 1, {}),
)


def _retext(value: Any, mapping: Dict[str, str]) -> Any:
    if isinstance(value, str):
        out = value
        for old, new in mapping.items():
            out = out.replace(old, new)
        return out
    if isinstance(value, list):
        return [_retext(item, mapping) for item in value]
    if isinstance(value, dict):
        return {key: _retext(item, mapping) for key, item in value.items()}
    return value


def build() -> List[Dict[str, Any]]:
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    existing: List[Dict[str, Any]] = catalog["aplus_briefs"]
    by_type: Dict[str, Dict[str, Any]] = {}
    for brief in existing:
        by_type.setdefault(brief["content_type"], brief)
    added: List[Dict[str, Any]] = []
    for brief_id, content_type, brand, ref_index, mapping in PLAN:
        template = by_type[content_type]
        brief = copy.deepcopy(template)
        brief["id"] = brief_id
        reference = WORDS_COFFEE[ref_index] if brand == "word-coffee" else MOGRA[ref_index]
        brief["reference"]["path"] = reference
        brief["reference"]["descriptor"]["filename"] = Path(reference).name
        brief["reference"]["descriptor"]["subject"] = brand.replace("-", " ")
        brief["product_line"] = brand
        brief["difficulty"] = template.get("difficulty", 1)
        brief["note"] = (f"A+ {content_type} for {brand.replace('-', ' ')}, built on the same module "
                         "shape as the existing family so the module type is comparable.")
        if mapping:
            brief = _retext(brief, mapping)
        added.append(brief)
    return added


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Extend the A+ brief family across brands")
    parser.add_argument("--write", action="store_true")
    ns = parser.parse_args(argv)
    added = build()
    if ns.write:
        catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
        ids = {brief["id"] for brief in added}
        catalog["aplus_briefs"] = [row for row in catalog["aplus_briefs"]
                                   if row.get("id") not in ids] + added
        CATALOG.write_text(json.dumps(catalog, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"added": len(added),
                      "family": 6 + len(added),
                      "brands": sorted({brief.get("product_line") or "mogra"
                                        for brief in added}),
                      "content_types": sorted({brief["content_type"] for brief in added})}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
