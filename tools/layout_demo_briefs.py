"""Build the four-brief layout bench for the Lion's Mane pouch.

The demo briefs are **not** held-out: they exist so the deterministic infographic and packaging
stages can be looked at on the real pouch, source next to output. Each one inherits the tuned
catalogue's constraint profile for its situation, exactly like a held-out brief, so a failure here
means the stage failed rather than the bar moving.

    python tools/layout_demo_briefs.py --write
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "ty" / "seller_briefs.json"
OUT = ROOT / "ty" / "seller_briefs_layout_demo.json"

REFERENCES = [
    "renders/references/mogra/mogra_pair_main.png",
    "renders/references/mogra/mogra_pair_lifestyle.png",
    "renders/references/mogra/mogra_forest_dusk.png",
]

# (id, situation, reference index, difficulty) — pairs are unique on
# (category, situation, difficulty, mode), which the validator enforces.
PLAN = (
    ("LM-DET-01", "infographic", 0, 1),
    ("LM-DET-02", "infographic", 1, 2),
    ("LM-DET-03", "packaging_mockup", 0, 1),
    ("LM-DET-04", "packaging_mockup", 2, 2),
)


def _profiles(catalog: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    out: Dict[str, Dict[str, Any]] = {}
    for brief in catalog.get("briefs") or []:
        if brief.get("source_mode") == "prompt_only":
            continue
        out.setdefault(brief["situation"], json.loads(json.dumps(brief["constraints"])))
    return out


def build() -> Dict[str, Any]:
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    profiles = _profiles(catalog)
    briefs: List[Dict[str, Any]] = []
    for brief_id, situation, reference_index, difficulty in PLAN:
        reference = REFERENCES[reference_index]
        suffix = Path(reference).suffix.lower()
        briefs.append({
            "id": brief_id,
            "category": "supplement_pouch",
            "product_line": "lions-mane",
            "situation": situation,
            "difficulty": difficulty,
            "source_mode": "uploaded_reference",
            "fidelity": "exact",
            "product_in_frame": True,
            "held_out": False,
            "demo": True,
            "reference": {
                "kind": "uploaded_file",
                "path": reference,
                "descriptor": {"filename": Path(reference).name,
                               "mime_type": "image/png" if suffix == ".png" else "image/jpeg",
                               "subject": "mogra organics lions mane"},
            },
            "constraints": json.loads(json.dumps(profiles[situation])),
            "note": ("Layout demonstration, not held-out: the deterministic infographic and "
                     "packaging stages on the real Lion's Mane pouch."),
        })
    return {"schema": "northstar.seller_briefs.layout_demo.v1",
            "note": ("Four demonstration briefs for the deterministic layout stages. They are "
                     "not part of the held-out set and their scores are not published as one."),
            "briefs": briefs}


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Layout demo briefs")
    parser.add_argument("--write", action="store_true")
    ns = parser.parse_args(argv)
    payload = build()
    if ns.write:
        OUT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"briefs": len(payload["briefs"]),
                      "situations": sorted({b["situation"] for b in payload["briefs"]}),
                      "path": str(OUT.relative_to(ROOT))}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
