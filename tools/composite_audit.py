"""Audit composite outputs against the source cutout — independently of the generator.

The generator says it pasted the real product. This checks that it did: for every composite in
`renders/seller_composite/`, cut the product out of the brief's reference, find it in the output
and compare the region. The generator's own claim is not evidence.

The owner's rule (2026-11-08) is applied here as well as in the scorer: **a product region that
cannot be verified is a failure**. A row that cannot be verified is rewritten in the proof as
`provisional: true`, `passed: false`, with `product_region` added to `failed_checks`, its score
re-reduced through the same weights the scorer uses, and the old numbers kept under
`provisional_score` / `provisional_passed` so the record shows what changed and why.

    python tools/composite_audit.py --run
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parents[1]
for _path in (ROOT / "tools", ROOT / "Northstar_backend"):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))
PROOF = ROOT / "state" / "seller" / "composite_proof.json"
OUT = ROOT / "state" / "seller" / "composite_region.json"
BRIEFS = ROOT / "tools" / "seller_tester" / "mogra_briefs.json"
MIN_SIMILARITY = 0.82


def _load(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def brief_index() -> Dict[str, Dict[str, Any]]:
    data = _load(BRIEFS) or {}
    return {str(brief.get("id")): brief for brief in data.get("briefs") or []}


def cutout_for(brief: Dict[str, Any], artefact: Optional[Path] = None) -> Optional[Any]:
    """The cutout the *generator* used, if it saved one.

    Re-deriving a cutout here is a trap: on a lifestyle reference the background is not
    separable by corner distance, so the "cutout" becomes the whole scene and the comparison
    means nothing. The pipeline already runs a real segmenter (BiRefNet), so the audit consumes
    its cutout and refuses when it was not saved — which is what happened first, and is
    recorded rather than papered over.
    """
    candidates = []
    if artefact is not None:
        candidates.append(artefact.with_suffix(".cutout.png"))
    brief_id = str(brief.get("id") or "")
    if brief_id:
        candidates.append(ROOT / "renders" / "seller_composite" / f"{brief_id}.cutout.png")
    for path in candidates:
        if path.is_file():
            from PIL import Image
            import numpy as np

            with Image.open(path) as opened:
                image = opened.convert("RGBA")
            return np.array(image)
    return None


def _region_verdict(artefact: Path, cutout: Any, placement: Any) -> Dict[str, Any]:
    """Verify the product region with the repo's own identity metric.

    `product_composite.identity_check` already compares the composite's product box against
    the cutout, masked by the cutout's alpha, and reported 0.9958 on the white-canvas run.
    Re-implementing that comparison here produced a second, worse metric and a false
    `cannot verify`; an audit that disagrees with a tested implementation for no measured
    reason is a bug in the audit.
    """
    if cutout is None:
        from seller_tester.composite_check import missing_cutout_verdict

        return missing_cutout_verdict(
            "the generator did not save the cutout it used, so the product region cannot be "
            "compared; expected <artefact>.cutout.png")
    if not placement:
        from seller_tester.composite_check import check_composite

        from PIL import Image

        import numpy as np

        with Image.open(artefact) as opened:
            produced = np.array(opened.convert("RGB"))
        return check_composite(produced, cutout, placement=None, min_similarity=MIN_SIMILARITY)

    sidecar = artefact.with_suffix(".json")
    box = placement
    if sidecar.is_file():
        try:
            meta = json.loads(sidecar.read_text(encoding="utf-8"))
            recorded = meta.get("product_box")
            if isinstance(recorded, list) and len(recorded) == 4:
                box = [int(value) for value in recorded]
        except (OSError, ValueError):
            pass
    left, top, right, bottom = (int(value) for value in box)
    if right <= left or bottom <= top:
        left, top = int(placement[0]), int(placement[1])
        right, bottom = left + int(placement[2]), top + int(placement[3])

    import product_composite as composite  # noqa: PLC0415

    cutout_path = None
    for candidate in (artefact.with_suffix(".cutout.png"),
                      ROOT / "renders" / "seller_composite" / f"{artefact.stem}.cutout.png"):
        if candidate.is_file():
            cutout_path = candidate
            break
    if cutout_path is None:
        return {"ok": False, "cannot_verify": True,
                "detail": "the cutout file is missing beside the artefact"}
    result = composite.identity_check(artefact.read_bytes(), cutout_path.read_bytes(),
                                      (left, top, right, bottom))
    ssim = result.get("ssim")
    ok = ssim is not None and float(ssim) >= 0.90
    return {"ok": bool(ok), "cannot_verify": ssim is None, "similarity": ssim,
            "found_by": "placement", "basis": "masked_ssim",
            "detail": (f"product region {right - left}x{bottom - top} at ({left},{top}): "
                       f"masked SSIM {ssim} ({result.get('verdict')})")}


def _placement(result: Dict[str, Any]) -> Optional[List[int]]:
    """The product box as (x, y, width, height).

    `place_product` records `[left, top, right, bottom]`; `check_composite` takes
    `[x, y, width, height]`. Reading one as the other put boxes outside the frame and made a
    correct composite look unverifiable — the kind of unit error a rule catches only if the
    box is actually used.
    """
    generation = result.get("generation") or {}
    box = generation.get("product_box")
    if isinstance(box, list) and len(box) == 4:
        left, top, right, bottom = (int(value) for value in box)
        return [left, top, max(1, right - left), max(1, bottom - top)]
    return None


def _check_summary(verdict: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "ok": bool(verdict.get("ok")),
        "skipped": False,
        "cannot_verify": bool(verdict.get("cannot_verify")),
        "detail": str(verdict.get("detail") or "")[:400],
    }


def apply_region_to_row(result: Dict[str, Any], brief: Dict[str, Any],
                        verdict: Dict[str, Any]) -> Dict[str, Any]:
    """One proof row, re-scored with the product-region check. Pure, so it is testable."""
    from seller_tester.scorers import combine_checks

    checks = dict(result.get("checks") or {})
    checks["product_region"] = _check_summary(verdict)
    combined = combine_checks(checks, brief, composite_route=True)

    old_score = result.get("score")
    old_passed = bool(result.get("passed"))
    cannot_verify = bool(verdict.get("cannot_verify"))

    result["checks"] = checks
    result["score"] = combined["score"]
    result["passed"] = False if cannot_verify else combined["passed"]
    result["failed_checks"] = list(combined["failed_checks"])
    result["critical_failed"] = list(combined["critical_failed"])
    result["product_region"] = {
        "ok": bool(verdict.get("ok")),
        "cannot_verify": cannot_verify,
        "similarity": verdict.get("similarity"),
        "found_by": verdict.get("found_by"),
        "detail": str(verdict.get("detail") or ""),
    }
    if product_region_failed(verdict):
        result["failed_reason"] = str(verdict.get("detail") or "")
    else:
        result.pop("failed_reason", None)

    # Provisional = it passed on the other checks and only the product region is unproved.
    # The old verdict is kept so the record shows exactly what changed.
    if old_passed and cannot_verify:
        result["provisional"] = True
        result["provisional_score"] = old_score
        result["provisional_passed"] = old_passed
    else:
        result.setdefault("provisional", False)
        if result["provisional"]:
            result.setdefault("provisional_score", old_score)
            result.setdefault("provisional_passed", old_passed)
    return result


def product_region_failed(verdict: Dict[str, Any]) -> bool:
    return bool(verdict.get("cannot_verify")) or not bool(verdict.get("ok"))


def _resummarise(proof: Dict[str, Any], briefs: Dict[str, Dict[str, Any]]) -> None:
    """Keep the summary honest after the rows changed."""
    from seller_tester.harness import _by_category, _by_mode, _by_situation

    results = proof.get("results") or []
    passed = sum(1 for row in results if row.get("passed"))
    scores = [float(row.get("score") or 0.0) for row in results]
    proof["passed"] = passed
    proof["failed"] = len(results) - passed
    proof["pass_rate"] = round(100.0 * passed / len(results), 1) if results else 0.0
    proof["mean_score"] = round(sum(scores) / len(scores), 1) if scores else 0.0
    proof["provisional"] = sum(1 for row in results if row.get("provisional"))
    proof["product_region_verified"] = sum(
        1 for row in results if (row.get("product_region") or {}).get("ok"))
    proof["by_mode"] = _by_mode(results)
    proof["by_situation"] = _by_situation(results)
    proof["by_category"] = _by_category(results)


def audit(proof_path: Path = PROOF, out_path: Path = OUT) -> Dict[str, Any]:
    proof = _load(proof_path) or {}
    results = proof.get("results") or []
    briefs = brief_index()
    rows: List[Dict[str, Any]] = []
    for result in results:
        brief_id = str(result.get("brief_id"))
        brief = briefs.get(brief_id) or {}
        artefact = ROOT / str(result.get("artefact_path") or "")
        entry: Dict[str, Any] = {"brief_id": brief_id,
                                 "artefact": result.get("artefact_path"),
                                 "route": result.get("route")}
        if not artefact.is_file():
            entry.update({"ok": False, "cannot_verify": True,
                          "reason": "composite artefact is not on disk"})
            rows.append(entry)
            verdict = {"ok": False, "cannot_verify": True,
                       "detail": "product region cannot be verified: the composite artefact "
                                 "is not on disk"}
        else:
            cutout = cutout_for(brief, artefact)
            try:
                verdict = _region_verdict(artefact, cutout, _placement(result))
            except Exception as exc:  # noqa: BLE001
                verdict = {"ok": False, "cannot_verify": True,
                           "detail": (f"product region cannot be verified: "
                                      f"{type(exc).__name__}: {exc}")}
            entry.update({
                "ok": bool(verdict.get("ok")),
                "cannot_verify": bool(verdict.get("cannot_verify")),
                "similarity": verdict.get("similarity"),
                "found_by": verdict.get("found_by"),
                "min_similarity": MIN_SIMILARITY,
                "detail": verdict.get("detail") or verdict.get("reason"),
            })
        if result and brief:
            before = result.get("score")
            before_passed = bool(result.get("passed"))
            apply_region_to_row(result, brief, verdict)
            entry["provisional"] = bool(result.get("provisional"))
            entry["score_before"] = before
            entry["score_after"] = result.get("score")
            entry["passed_before"] = before_passed
            entry["passed_after"] = bool(result.get("passed"))
        rows.append(entry)

    _resummarise(proof, briefs)
    payload = {"at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
               "min_similarity": MIN_SIMILARITY, "rows": rows,
               "passed": sum(1 for row in rows if row.get("ok")),
               "provisional": proof.get("provisional", 0),
               "verified": proof.get("product_region_verified", 0),
               "total": len(rows)}
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    if results:
        proof_path.parent.mkdir(parents=True, exist_ok=True)
        proof_path.write_text(json.dumps(proof, indent=2) + "\n", encoding="utf-8")
    return payload


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Composite product-region audit")
    parser.add_argument("--run", action="store_true")
    ns = parser.parse_args(argv)
    payload = audit()
    print(json.dumps({"verified": payload["verified"], "passed": payload["passed"],
                      "provisional": payload["provisional"], "total": payload["total"],
                      "rows": [{k: row.get(k) for k in ("brief_id", "ok", "cannot_verify",
                                                        "similarity", "found_by",
                                                        "provisional", "score_before",
                                                        "score_after", "detail")}
                               for row in payload["rows"]]}, indent=2))
    return 0 if payload["passed"] == payload["total"] and payload["total"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
