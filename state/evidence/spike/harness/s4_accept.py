"""S4 gate: the plate's own words must not contradict the copy above it.

Run from the worktree root:
    python .spike_acceptance/s4_accept.py

Exercises the contract given in the task, with no image decode and no OCR engine:
the OCR verdict is injected exactly as render_text_guard injects its detector.
Exit 0 only when every case behaves as specified.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path.cwd()
sys.path.insert(0, str(ROOT / "Northstar_backend"))


def _ocr(*words):
    return {"status": "ok", "boxes": len(words), "words": list(words)}


def main() -> int:
    out = {"gate": "S4", "checks": [], "ok": False}
    try:
        import aplus_render as ar

        fn = getattr(ar, "check_plate_agrees_with_copy", None)
        if not callable(fn):
            out["reason"] = "check_plate_agrees_with_copy is missing"
            print(json.dumps(out, indent=2))
            return 1

        def check(name, got, want_ok, *, needs=()):
            entry = {"name": name, "want_ok": want_ok, "got_ok": got.get("ok")}
            ok = got.get("ok") is want_ok
            text = json.dumps(got, default=str).lower()
            for needle in needs:
                if needle.lower() not in text:
                    ok = False
                    entry.setdefault("missing", []).append(needle)
            entry["passed"] = ok
            entry["result"] = got
            out["checks"].append(entry)
            return ok

        results = []
        # 1. the shipped bug: Shiitake plate under a Lion's Mane headline.
        results.append(check("shiitake plate, lion's mane copy",
                             fn("Organic Lion's Mane Mushroom Powder", _ocr("MOGRÆ", "SHIITAKE")),
                             False, needs=("shiitake",)))
        # 2. same species -> agreement.
        results.append(check("lion's mane plate, lion's mane copy",
                             fn("Organic Lion's Mane Mushroom Powder", _ocr("LIONS", "MANE")),
                             True))
        # 3. a plate naming no species cannot contradict.
        results.append(check("plain plate, lion's mane copy",
                             fn("Organic Lion's Mane Mushroom Powder", _ocr("ORGANIC", "30", "SERVINGS")),
                             True))
        # 4. punctuation/case blind: "Lion’s Mane" copy vs "LIONS MANE" plate.
        results.append(check("apostrophe and case",
                             fn("ORGANIC LION\u2019S MANE", _ocr("lions", "mane")), True))
        # 5. no OCR verdict and no detector -> not agreement.
        results.append(check("plate unreadable", fn("Organic Lion's Mane", None), False))
        # 6. a detector is used when the verdict is absent.
        used = {"n": 0}

        def detect(_png):
            used["n"] += 1
            return _ocr("SHIITAKE")

        results.append(check("detector supplies the verdict",
                             fn("Organic Lion's Mane", None, detect=detect), False,
                             needs=("shiitake",)))
        det_ok = used["n"] == 1
        out["checks"].append({"name": "detector called exactly once",
                              "passed": det_ok, "calls": used["n"]})
        results.append(det_ok)

        out["ok"] = all(results)
        if not out["ok"]:
            out["reason"] = "not every contract case behaved as specified"
    except Exception as exc:  # noqa: BLE001 - a raising gate is a failed gate
        out["ok"] = False
        out["reason"] = f"{type(exc).__name__}: {exc}"[:400]
    print(json.dumps(out, indent=2, default=str))
    return 0 if out["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
