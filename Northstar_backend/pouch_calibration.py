"""Pouch calibration — turn "measure a competitor pouch" into a recorded delta.

The packaging blueprint's biggest commercial risk is the gusset: the 8 oz spec's
40 mm is roughly half the published convention for that fill weight, and no
software can settle it. This module makes the tape-measure step produce an
artifact:

  * compare a SPEC against one or more MEASURED pouches (mm, true size)
  * report per-dimension deltas and the nearest published ladder row
  * give a plain verdict: spec_holds / spec_adjust / inconclusive
  * append the measurement to a durable JSON record the co-packer conversation
    can be built on

It never changes the spec and never guesses: a missing measurement is reported
as missing.

CLI (run from the repo root; the script's own folder is added to sys.path):
  python Northstar_backend/pouch_calibration.py \
      --spec 150x210+40 --fill 227 --measured 148x205+78 --source "BrandX 8 oz"
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from design_studio_print import DOYPACK_LADDER, _round

RECORD_PATH = Path(__file__).resolve().parent / "data" / "pouch_calibrations.json"

#: A measured dimension within this fraction of the spec is "the same pouch".
MATCH_TOLERANCE = 0.05
#: Beyond this the spec is materially different from what is on the shelf.
MISMATCH_THRESHOLD = 0.12


def parse_size(text: str) -> Dict[str, float]:
    """Parse ``150x210+40`` (mm) into width/height/gusset."""
    raw = str(text or "").strip().lower().replace(" ", "")
    if "x" not in raw:
        raise ValueError(f"expected WxH+G (e.g. 150x210+40), got {text!r}")
    body, _, gusset = raw.partition("+")
    w, _, h = body.partition("x")
    try:
        out = {"width_mm": float(w), "height_mm": float(h),
               "gusset_mm": float(gusset) if gusset else 0.0}
    except ValueError:
        raise ValueError(f"non-numeric size component in {text!r}")
    if out["width_mm"] <= 0 or out["height_mm"] <= 0 or out["gusset_mm"] < 0:
        raise ValueError(f"width/height must be positive and gusset >= 0, got {text!r}")
    return out


def _delta(spec: float, measured: float) -> Dict[str, Any]:
    diff = measured - spec
    pct = (diff / spec) if spec else 0.0
    state = ("match" if abs(pct) <= MATCH_TOLERANCE
             else "mismatch" if abs(pct) > MISMATCH_THRESHOLD else "near")
    return {"spec_mm": _round(spec), "measured_mm": _round(measured),
            "delta_mm": _round(diff), "delta_pct": _round(pct * 100, 1),
            "state": state}


def nearest_ladder_row(fill_g: Optional[float]) -> Optional[Dict[str, Any]]:
    if not fill_g:
        return None
    row = min(DOYPACK_LADDER, key=lambda r: abs(r[0] - float(fill_g)))
    return {"fill_g": row[0], "width_mm": row[1], "height_mm": row[2],
            "gusset_mm": row[3]}


def compare(*, spec: Dict[str, float], measured: Dict[str, float],
            fill_g: Optional[float] = None,
            source: Optional[str] = None) -> Dict[str, Any]:
    """Compare one measured pouch against the spec and the published ladder."""
    missing = [k for k in ("width_mm", "height_mm", "gusset_mm") if k not in measured]
    deltas = {k: _delta(spec[k], measured[k])
              for k in ("width_mm", "height_mm", "gusset_mm") if k in measured}
    ladder = nearest_ladder_row(fill_g)

    blockers: List[str] = []
    notes: List[str] = []
    gusset = deltas.get("gusset_mm")
    if gusset and gusset["state"] == "mismatch":
        direction = "bigger" if gusset["delta_mm"] > 0 else "smaller"
        blockers.append(
            f"measured gusset is {gusset['delta_mm']:+.1f}mm ({gusset['delta_pct']:+.1f}%) "
            f"vs the spec - the shelf pouch is materially {direction}")
    if ladder:
        measured_g = measured.get("gusset_mm")
        if measured_g and measured_g < ladder["gusset_mm"] * 0.75:
            notes.append(
                f"even the MEASURED gusset ({measured_g:g}mm) is well below the "
                f"published {ladder['gusset_mm']:g}mm for a {ladder['fill_g']:g}g pouch")
        elif measured_g and abs(measured_g - ladder["gusset_mm"]) / ladder["gusset_mm"] <= 0.15:
            notes.append(
                f"the measured gusset agrees with the published ladder "
                f"({ladder['gusset_mm']:g}mm for {ladder['fill_g']:g}g) - the SPEC is the "
                "outlier")
    if missing:
        blockers.append(f"measurement is incomplete (missing {', '.join(missing)})")

    states = [d["state"] for d in deltas.values()]
    if not missing and all(s == "match" for s in states):
        verdict = "spec_holds"
    elif any(s == "mismatch" for s in states):
        verdict = "spec_adjust"
    else:
        verdict = "inconclusive"

    return {
        "verdict": verdict, "source": source or "unnamed",
        "spec": {k: _round(v) for k, v in spec.items()},
        "measured": {k: _round(v) for k, v in measured.items()},
        "fill_g": fill_g, "ladder_row": ladder,
        "deltas": deltas, "blockers": blockers, "notes": notes,
        "tolerance": {"match": MATCH_TOLERANCE, "mismatch": MISMATCH_THRESHOLD},
        "note": ("A recorded delta, not a decision. The co-packer's die drawing (or "
                 "two or three measured competitor pouches) is the authority."),
    }


def record(result: Dict[str, Any], path: Optional[Path] = None) -> Dict[str, Any]:
    """Append a comparison to the durable calibration record."""
    target = Path(path) if path else RECORD_PATH
    data: Dict[str, Any] = {"version": 1, "entries": []}
    if target.is_file():
        try:
            data = json.loads(target.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001 - a corrupt record must not lose the new entry
            data = {"version": 1, "entries": [], "recovered_from_corrupt": True}
    entry = {"recorded_at": datetime.now(timezone.utc).isoformat(), **result}
    data.setdefault("entries", []).append(entry)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return {"path": str(target), "entries": len(data["entries"])}


def _main() -> int:
    ap = argparse.ArgumentParser(description="Record a measured pouch vs the spec")
    ap.add_argument("--spec", required=True, help="WxH+G in mm, e.g. 150x210+40")
    ap.add_argument("--measured", required=True, help="WxH+G in mm")
    ap.add_argument("--fill", type=float, default=None, help="fill weight in grams")
    ap.add_argument("--source", default=None, help="what was measured")
    ap.add_argument("--no-record", action="store_true")
    args = ap.parse_args()

    res = compare(spec=parse_size(args.spec), measured=parse_size(args.measured),
                  fill_g=args.fill, source=args.source)
    if not args.no_record:
        res["record"] = record(res)
    print(json.dumps(res, indent=2)[:3500])
    return 0 if res["verdict"] != "spec_adjust" else 2


if __name__ == "__main__":
    raise SystemExit(_main())
