"""S5 gate: a plate that is text-free but still smeared must be reported.

Run from the worktree root:
    python .spike_acceptance/s5_accept.py

The measurement is injected (the same shape text_fidelity plugs into), so the gate
tests the decision, not an OCR engine's opinion. Exit 0 only when every case
behaves as specified.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path.cwd()
sys.path.insert(0, str(ROOT / "Northstar_backend"))


def _detector(boxes_seq):
    calls = {"n": 0}

    def detect(_png):
        i = min(calls["n"], len(boxes_seq) - 1)
        calls["n"] += 1
        b = boxes_seq[i]
        return {"status": "ok", "boxes": b, "contains_text": b > 0}

    return detect


def main() -> int:
    out = {"gate": "S5", "checks": [], "ok": False}
    try:
        import render_text_guard as g

        threshold = getattr(g, "RESIDUAL_MARK_THRESHOLD", None)
        out["threshold"] = threshold
        checks = []

        def note(name, passed, **extra):
            checks.append({"name": name, "passed": bool(passed), **extra})
            return passed

        checks.append(note("RESIDUAL_MARK_THRESHOLD is a small positive fraction",
                           isinstance(threshold, (int, float)) and 0 < float(threshold) < 0.05,
                           value=threshold))

        clean_png = b"png"
        # 1. already clean, no marks: plate_clean True.
        r1 = g.ensure_text_free(clean_png, detect=_detector([0]),
                                clean=lambda _p: {"bytes": b"x"},
                                measure=lambda _p: {"residual_mark_fraction": 0.0})
        checks.append(note("clean plate is plate_clean True", r1.get("plate_clean") is True,
                           result={k: r1.get(k) for k in ("cleaned", "plate_clean")}))

        # 2. text cleaned (0 boxes after) but faint marks left: reported, not passed.
        r2 = g.ensure_text_free(b"png", detect=_detector([4, 0]),
                                clean=lambda _p: {"bytes": b"clean"},
                                measure=lambda _p: {"residual_mark_fraction": 0.010,
                                                    "marks": 3})
        checks.append(note("cleaned text + residual marks => plate_clean False",
                           r2.get("cleaned") is True and r2.get("plate_clean") is False,
                           result={k: r2.get(k) for k in ("cleaned", "plate_clean", "reason")}))
        checks.append(note("the reason names the residual marks",
                           "residual" in str(r2.get("reason") or "").lower(),
                           reason=r2.get("reason")))
        checks.append(note("residuals carry the measurement",
                           isinstance(r2.get("residuals"), dict)
                           and float((r2.get("residuals") or {}).get(
                               "residual_mark_fraction", 0)) > 0,
                           residuals=r2.get("residuals")))

        # 3. below threshold: clean.
        r3 = g.ensure_text_free(b"png", detect=_detector([2, 0]),
                                clean=lambda _p: {"bytes": b"clean"},
                                measure=lambda _p: {"residual_mark_fraction": 0.0005})
        checks.append(note("marks below the threshold are plate_clean True",
                           r3.get("plate_clean") is True,
                           result={k: r3.get(k) for k in ("cleaned", "plate_clean")}))

        # 4. no instrument: never a pass.
        r4 = g.ensure_text_free(b"png", detect=_detector([0]),
                                clean=lambda _p: {"bytes": b"x"},
                                measure=lambda _p: None)
        checks.append(note("an unavailable measurement is never reported clean",
                           r4.get("plate_clean") is not True,
                           result={"plate_clean": r4.get("plate_clean"),
                                   "residuals": r4.get("residuals")}))

        # 5. the original keys still mean what they meant.
        checks.append(note("existing keys unchanged",
                           r2.get("boxes_before") == 4 and r2.get("boxes_after") == 0
                           and r2.get("passes") == 1,
                           result={k: r2.get(k) for k in
                                   ("boxes_before", "boxes_after", "passes")}))

        # 6. an OCR failure stays an OCR failure, not a clean plate.
        r6 = g.ensure_text_free(b"png", detect=lambda _p: {"status": "error",
                                                           "error": "engine down"},
                                clean=lambda _p: {"bytes": b"x"},
                                measure=lambda _p: {"residual_mark_fraction": 0.0})
        checks.append(note("OCR failure is not a pass",
                           r6.get("cleaned") is False and r6.get("plate_clean") is not True,
                           result={k: r6.get(k) for k in ("cleaned", "plate_clean")}))

        out["checks"] = checks
        out["ok"] = all(c["passed"] for c in checks)
        if not out["ok"]:
            out["reason"] = "not every contract case behaved as specified"
    except Exception as exc:  # noqa: BLE001 - a raising gate is a failed gate
        out["ok"] = False
        out["reason"] = f"{type(exc).__name__}: {exc}"[:400]
    print(json.dumps(out, indent=2, default=str))
    return 0 if out["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
