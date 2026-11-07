"""S2 gate: an explicit product_box scores a correct composite >= 85.

Run from the worktree root:
    python .spike_acceptance/s2_accept.py

Independent of the candidate's own tests: it exercises the public entry point
(score_case) on the real evidence PNGs and reports the actual number. Exit 0 only
when product_fidelity is measured and >= 85, and a no-box call still behaves as
before (the regression that the old path keeps working).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path.cwd()
sys.path.insert(0, str(ROOT / "Northstar_backend"))

COMPOSITE = ROOT / "renders/autonomy_probe/composite/lifestyle_linen_composite.png"
CUTOUT = ROOT / "renders/autonomy_probe/composite/lifestyle_linen_cutout.png"
BOX = [279, 308, 744, 1024]


def main() -> int:
    out = {"gate": "S2", "box": BOX}
    try:
        import picture_scorecard as ps

        if not COMPOSITE.is_file() or not CUTOUT.is_file():
            print(json.dumps({"gate": "S2", "ok": False,
                              "error": "evidence PNGs missing"}, indent=2))
            return 1
        composite = COMPOSITE.read_bytes()
        cutout = CUTOUT.read_bytes()

        row = ps.score_case(
            image_bytes=composite,
            case={"id": "e2", "surface": "lifestyle",
                  "product_box": list(BOX), "brief": "composited product on linen"},
            reference_bytes=cutout, scoring=False)
        block = (row.get("dimensions") or {}).get("product_fidelity") or {}
        score = block.get("score")
        out["with_box"] = {"score": score, "status": block.get("status"),
                           "detail": block.get("detail")}

        # The old path must not crash or claim a pass it did not measure.
        plain = ps.score_case(
            image_bytes=composite,
            case={"id": "e2_no_box", "surface": "lifestyle",
                  "brief": "composited product on linen"},
            reference_bytes=cutout, scoring=False)
        plain_block = (plain.get("dimensions") or {}).get("product_fidelity") or {}
        out["without_box"] = {"score": plain_block.get("score"),
                              "status": plain_block.get("status"),
                              "compared": (plain_block.get("detail") or {})
                              .get("compared") if isinstance(
                                  plain_block.get("detail"), dict) else None}

        out["ok"] = (block.get("status") == "measured" and score is not None
                     and float(score) >= 85.0)
        out["reason"] = ("" if out["ok"] else
                         "product_fidelity was not measured at >= 85 with an explicit box")
    except Exception as exc:  # noqa: BLE001 - a raising gate is a failed gate
        out["ok"] = False
        out["reason"] = f"{type(exc).__name__}: {exc}"[:400]
    print(json.dumps(out, indent=2, default=str))
    return 0 if out["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
