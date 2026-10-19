"""Live package-readiness assessment on the real Mogra artifacts.

Runs the one-call verdict over the composed artwork, the framed MAIN image and a
doypack dieline, then writes the full report to renders/package_readiness_live.json.

Usage: python scripts/package_readiness_live.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "Northstar_backend"))

import design_studio_print as dp  # noqa: E402
import package_readiness as pr  # noqa: E402

ARTWORK = ROOT / "renders" / "ab_realism_real.png"
MAIN = ROOT / "renders" / "smoke_main_2000.png"
OUT = ROOT / "renders" / "package_readiness_live.json"

TERMS = ["MOGRA ORGANICS", "ORGANIC LION'S MANE", "MUSHROOM POWDER", "6 oz (170 g)"]


def main() -> int:
    artwork = ARTWORK.read_bytes() if ARTWORK.is_file() else None
    main_image = MAIN.read_bytes() if MAIN.is_file() else None
    dieline = dp.build_from_template("doypack", {
        "width_mm": 150, "height_mm": 210, "gusset_mm": 40, "fill_g": 227})

    out = pr.assess_package(artwork=artwork, main_image=main_image, dieline=dieline,
                            expected_terms=TERMS)
    OUT.write_text(json.dumps(out, indent=2), encoding="utf-8")

    print("VERDICT:", out["verdict"])
    print("BLOCKERS:")
    for b in out["blockers"]:
        print("  -", b)
    print("WARNINGS:")
    for w in out["warnings"]:
        print("  -", w)
    print("NOT ASSESSED:", out["not_assessed"])
    ev = out["evidence"]
    pp = ev["prepress"]
    if pp.get("assessed"):
        print(f"prepress: {pp['verdict']} | max TAC {pp['ink']['max_tac_pct']}% | "
              f"out-of-gamut {pp['gamut']['out_of_gamut_pct']}% | profile {pp['profile']}")
    cp = ev["copy"]
    print(f"copy: assessed={cp.get('assessed')} matched={cp.get('matched')} "
          f"missing={cp.get('missing')}")
    mn = ev["main"]
    print(f"main: {mn.get('verdict')} fill={mn.get('fill_longest_side')} "
          f"white={mn.get('background_white_frac')}")
    dl = ev["dieline"]
    print(f"dieline: {dl.get('template')} {dl.get('size_mm')}mm bleed={dl.get('bleed_mm')} "
          f"proportion={dl.get('proportion_status')}")
    print("sidecar:", OUT.relative_to(ROOT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
