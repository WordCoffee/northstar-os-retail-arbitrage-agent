"""Run the fixed product-picture bench and score it.

This is the measuring instrument for the Product Pictures workstream. It runs
the same 60 fixed cases the plan froze, through the real service functions, and
writes one scorecard per case plus an aggregate.

    python tools/run_picture_bench.py --mode from_scratch --split dev --limit 3
    python tools/run_picture_bench.py --split held_out --models
    python tools/run_picture_bench.py --report          # last aggregate, no render

Design rules:

  * a case that cannot render is recorded as failed with the real error - it is
    never dropped from the denominator, because "it did not work" is a result;
  * `--retries N` regenerates a non-compliant main image and records whether the
    second attempt recovered (the failure-recovery dimension);
  * results are append-only JSON files under state/evidence/, so a run can be
    resumed and two runs can be compared by case id.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "Northstar_backend"
CASES = ROOT / "eval" / "product_pictures" / "cases.json"
OUT_DIR = ROOT / "state" / "evidence"
IMAGES = ROOT / "renders" / "autonomy_probe" / "bench"
sys.path.insert(0, str(BACKEND))


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _cases(mode: Optional[str], split: str, limit: int, only: str = "",
           per_mode: int = 0) -> List[Dict[str, Any]]:
    data = json.loads(CASES.read_text(encoding="utf-8"))
    rows = [c for c in data["cases"]
            if (not mode or c["mode"] == mode)
            and (split == "all" or c["split"] == split)
            and (not only or only in c["id"])]
    if per_mode:
        seen: Dict[str, int] = {}
        picked = []
        for row in rows:
            if seen.get(row["mode"], 0) >= per_mode:
                continue
            seen[row["mode"]] = seen.get(row["mode"], 0) + 1
            picked.append(row)
        rows = picked
    return rows[:limit] if limit else rows


def _reference_bytes(case: Dict[str, Any]) -> Optional[bytes]:
    ref = case.get("reference") or {}
    if not ref:
        return None
    if ref.get("file"):
        path = ROOT / ref["file"]
        return path.read_bytes() if path.is_file() else None
    try:
        import reference_library as rl

        rows = rl.find(brand=ref.get("brand", ""), product=ref.get("product", ""),
                       kind=ref.get("kind"), limit=1)
        if not rows:
            # The shelf is organised by brand/product; the kind is a preference,
            # not a requirement. Falling back keeps a case from failing only
            # because a reference was filed under a different kind.
            rows = rl.find(brand=ref.get("brand", ""), product=ref.get("product", ""),
                           limit=1)
        if not rows:
            return None
        return rl.resolve(rows[0]["id"])
    except Exception:  # noqa: BLE001
        return None


def _render(case: Dict[str, Any], *, seed: int) -> Dict[str, Any]:
    import studio_generation as sg

    mode = case["mode"]
    w, h = int(case.get("width") or 1024), int(case.get("height") or 1024)
    started = time.time()
    if mode == "from_scratch":
        result = sg.generate_image(case["brief"], width=w, height=h, seed=seed)
    else:
        ref = _reference_bytes(case)
        if not ref:
            raise RuntimeError(f"reference_missing: {case.get('reference')}")
        result = sg.generate_reference(case["brief"], ref, width=w, height=h, seed=seed)
    result["seconds"] = round(time.time() - started, 1)
    # A bare diffusion output is not a listing image. The production lane puts
    # the subject on pure white at the marketplace fill band with
    # listing_render.fit_main_image; measuring the raw render against a main-image
    # rule would score the wrong artifact and make the gate look broken.
    if str(case.get("surface")) in ("main", "main_image", "listing_image"):
        try:
            import listing_render as lr

            result["bytes"] = lr.fit_main_image(result["bytes"],
                                                target_fill=0.86, size=(w, h))
            result["main_fit_applied"] = True
        except Exception as exc:  # noqa: BLE001 - a failed fit is recorded
            result["main_fit_applied"] = False
            result["main_fit_error"] = f"{type(exc).__name__}: {exc}"
    return result


def run_one(case: Dict[str, Any], *, retries: int, models: bool) -> Dict[str, Any]:
    import picture_scorecard as ps

    IMAGES.mkdir(parents=True, exist_ok=True)
    attempts = 0
    last: Dict[str, Any] = {}
    recovered = False
    while attempts <= max(0, retries):
        attempts += 1
        try:
            rendered = _render(case, seed=4242 + attempts * 17)
        except Exception as exc:  # noqa: BLE001 - the failure is the measurement
            return {"case_id": case["id"], "mode": case["mode"],
                    "scenario": case["scenario"], "surface": case["surface"],
                    "split": case["split"], "ok": False,
                    "error": f"{type(exc).__name__}: {exc}", "attempts": attempts,
                    "at": _now()}
        target = IMAGES / f"{case['id']}_a{attempts}.png"
        target.write_bytes(rendered["bytes"])
        record = {"attempt": attempts,
                  "image": str(target.relative_to(ROOT)).replace("\\", "/"),
                  "seconds": rendered.get("seconds"),
                  "width": rendered.get("width"), "height": rendered.get("height")}
        scored = ps.score_case(
            image_bytes=rendered["bytes"], case=case,
            reference_bytes=_reference_bytes(case) if case["mode"] != "from_scratch" else None,
            seconds=rendered.get("seconds"), scoring=models)
        compliance = (scored.get("dimensions", {})
                      .get("marketplace_compliance", {}).get("score"))
        record["scorecard"] = scored
        last = record
        if compliance is None or compliance >= 100.0:
            break
        if attempts <= retries:
            continue
    if attempts > 1 and last.get("scorecard", {}).get("dimensions", {}) \
            .get("marketplace_compliance", {}).get("score", 0) == 100.0:
        recovered = True
    case_out = dict(case)
    case_out.update({"attempts": attempts, "recovered": recovered})
    return {"case_id": case["id"], "mode": case["mode"], "scenario": case["scenario"],
            "surface": case["surface"], "split": case["split"], "ok": True,
            "attempts": attempts, "recovered": recovered, "at": _now(),
            "image": last.get("image"), "seconds": last.get("seconds"),
            "scorecard": last.get("scorecard")}


def summarise(rows: List[Dict[str, Any]], *, models: bool) -> Dict[str, Any]:
    import picture_scorecard as ps

    scored = [r["scorecard"] for r in rows if r.get("scorecard")]
    agg = ps.aggregate(scored)
    errors = [{"case_id": r["case_id"], "error": r.get("error")}
              for r in rows if not r.get("ok")]
    agg["errors"] = errors
    agg["scoring_models"] = models
    agg["at"] = _now()
    return agg


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Run the fixed picture bench.")
    parser.add_argument("--mode", default=None,
                        choices=("from_scratch", "stored_reference", "uploaded_reference"))
    parser.add_argument("--split", default="dev", choices=("dev", "held_out", "all"))
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--per-mode", type=int, default=0,
                        help="take the first N dev cases of each input mode")
    parser.add_argument("--only", default="")
    parser.add_argument("--retries", type=int, default=0)
    parser.add_argument("--models", action="store_true",
                        help="also run HPSv2/PickScore and the vision model (slow)")
    parser.add_argument("--report", action="store_true")
    parser.add_argument("--out", default="")
    ns = parser.parse_args(argv)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    if ns.report:
        files = sorted(OUT_DIR.glob("picture_bench_*.json"))
        if not files:
            print(json.dumps({"ok": False, "error": "no bench run yet"}))
            return 1
        print(json.dumps(json.loads(files[-1].read_text(encoding="utf-8")), indent=2))
        return 0

    cases = _cases(ns.mode, ns.split, ns.limit, ns.only, ns.per_mode)
    rows = []
    for n, case in enumerate(cases, start=1):
        row = run_one(case, retries=ns.retries, models=ns.models)
        rows.append(row)
        print(f"[{n}/{len(cases)}] {case['id']} "
              f"{'ok' if row.get('ok') else 'FAILED: ' + str(row.get('error'))}",
              file=sys.stderr)

    summary = summarise(rows, models=ns.models)
    summary["selection"] = {"mode": ns.mode, "split": ns.split, "limit": ns.limit,
                            "retries": ns.retries}
    payload = {"rows": rows, "summary": summary}
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = Path(ns.out) if ns.out else OUT_DIR / f"picture_bench_{stamp}.json"
    out.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    print(json.dumps({"out": str(out), "summary": summary}, indent=2, default=str))
    return 0 if not summary["errors"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
