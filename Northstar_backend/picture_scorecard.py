"""One numeric scorecard for product pictures, in eight dimensions.

The problem this solves: the box already measures a great deal - pHash/SSIM
identity, HPSv2 preference, PickScore adherence, OCR text presence, main-image
fill and purity, render seconds - but each one lives in its own module and
answers its own question. "Is the product-picture workstream production ready"
has never had a number, so it could never be compared across cycles.

This module is that number. It does not invent anything: every dimension is
computed from a measurement that already exists, and a dimension whose
instrument is missing reports ``unavailable`` with the reason instead of a
score. An unavailable dimension never counts as a pass.

Dimensions (0-100 each):

    instruction_fidelity   does the picture match the brief? (local vision model)
    product_fidelity       is it the same product? (pHash/SSIM against a reference)
    photographic_quality   artifacts, lighting, composition (HPSv2 + sharpness)
    marketplace_compliance white background, fill band, minimum size, no text
    text_accuracy          text-free where it must be, or the expected terms found
    set_consistency        the same product across a set (pHash spread)
    speed                  seconds to a delivered image
    failure_recovery       a bad render detected and regenerated, not shipped

The thresholds and the marketplace numbers are configurable in
``config/picture_scorecard.json`` because several of them are commonly cited
values rather than confirmed rules.
"""
from __future__ import annotations

import json
from io import BytesIO
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
CONFIG_PATH = ROOT / "config" / "picture_scorecard.json"

DIMENSIONS = ("instruction_fidelity", "product_fidelity", "photographic_quality",
              "marketplace_compliance", "text_accuracy", "set_consistency",
              "speed", "failure_recovery")

DEFAULTS: Dict[str, Any] = {
    "_doc": ("Commonly cited marketplace values, not confirmed rules. The main image "
             "is usually required to be on pure white, fill about 85 percent of the "
             "frame, have no text or badges, and be at least 1000 px on the longest "
             "side, with 2000 px preferred. Confirm these with the owner before "
             "treating a compliance score as a marketplace guarantee."),
    "marketplace": {
        "pure_white_rgb": [255, 255, 255],
        "white_tolerance": 2,
        "min_fill": 0.85,
        "fill_band": [0.80, 0.95],
        "min_side_px": 1000,
        "preferred_side_px": 2000,
        "allow_text_on_main": False,
    },
    "quality": {
        "preference_floor": 0.15,
        "preference_good": 0.30,
        "sharpness_floor": 40.0,
        "sharpness_good": 220.0,
    },
    "identity": {
        "max_phash_distance": 24,
        "good_ssim": 0.55,
        "min_ssim": 0.40,
    },
    "speed": {
        "good_seconds": 75.0,
        "fail_seconds": 300.0,
    },
    "bar": {
        "_doc": "The production bar the loop must clear on the held-out set twice.",
        "min_dimension": 85,
        "required_compliance": 100,
    },
}


def load_config(path: Optional[Path] = None) -> Dict[str, Any]:
    cfg = json.loads(json.dumps(DEFAULTS))
    p = Path(path) if path else CONFIG_PATH
    if p.is_file():
        try:
            overlay = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            overlay = {}
        for key, value in (overlay or {}).items():
            if isinstance(value, dict) and isinstance(cfg.get(key), dict):
                cfg[key].update(value)
            else:
                cfg[key] = value
    return cfg


def _dim(score: Optional[float], *, status: str = "measured",
         detail: Any = None) -> Dict[str, Any]:
    return {"score": None if score is None else round(float(score), 1),
            "status": status if score is not None else ("unavailable" if status == "measured" else status),
            "detail": detail}


def _clamp(value: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, value))


def _term_in(term: str, haystack: str) -> bool:
    """OCR is noisy, so a multi-word term matches on a majority of its words."""
    words = [w for w in "".join(ch.lower() if ch.isalnum() else " "
                                for ch in term).split() if len(w) > 2]
    if not words:
        return False
    found = sum(1 for w in words if w in haystack)
    return found / len(words) >= 0.6


def _scale(value: float, lo: float, hi: float) -> float:
    """Map lo..hi onto 0..100, clamped. A floor value scores 0, a good value 100."""
    if hi == lo:
        return 100.0 if value >= hi else 0.0
    return _clamp((value - lo) / (hi - lo) * 100.0)


def _sharpness(image_bytes: bytes) -> Optional[float]:
    try:
        import numpy as np
        from PIL import Image

        with Image.open(BytesIO(image_bytes)) as im:
            gray = np.asarray(im.convert("L"), dtype=np.float64)
        if gray.size < 9:
            return None
        lap = (gray[:-2, 1:-1] + gray[2:, 1:-1] + gray[1:-1, :-2]
               + gray[1:-1, 2:] - 4 * gray[1:-1, 1:-1])
        return float(lap.var())
    except Exception:  # noqa: BLE001 - an unavailable instrument is reported
        return None


def _ocr(image_bytes: bytes) -> Optional[Dict[str, Any]]:
    """The repo's own OCR verdict: status/contains_text/boxes/words, or None."""
    try:
        import text_fidelity as tf

        rep = tf.check_text_in_image(image_bytes)
        if not isinstance(rep, dict) or rep.get("status") != "ok":
            return None
        return rep
    except Exception:  # noqa: BLE001
        return None


def _vision_verdict(image_bytes: bytes, brief: str) -> Optional[Dict[str, Any]]:
    try:
        import local_vision as lv

        out = lv.qc_image(image_bytes, brief)
        return out if isinstance(out, dict) else None
    except Exception:  # noqa: BLE001
        return None


def score_case(*, image_bytes: bytes, case: Dict[str, Any],
               reference_bytes: Optional[bytes] = None,
               seconds: Optional[float] = None,
               cfg: Optional[Dict[str, Any]] = None,
               scoring: bool = True) -> Dict[str, Any]:
    """Score one delivered picture. ``scoring=False`` runs only the free programmatic axes.

    ``scoring=False`` is for fast loops and tests: it skips the two model scorers
    (HPSv2, PickScore) and the vision model, and marks those dimensions
    unavailable rather than guessing.
    """
    cfg = cfg or load_config()
    brief = str(case.get("brief") or case.get("prompt") or "")
    surface = str(case.get("surface") or "product_picture")
    out: Dict[str, Any] = {"case_id": case.get("id"), "surface": surface,
                           "scenario": case.get("scenario") or "",
                           "dimensions": {}}

    # ---- marketplace compliance (programmatic, always available) -------------
    if surface in ("main", "listing_image", "main_image"):
        try:
            import image_prep

            mk = cfg["marketplace"]
            rep = image_prep.check_main_compliance(
                image_bytes, min_fill=float(mk["min_fill"]),
                min_side=int(mk["min_side_px"]))
            passed = str(rep.get("verdict") or "").lower() == "compliant"
            out["compliance_detail"] = {k: rep.get(k) for k in
                                        ("verdict", "pixels", "background_white_frac",
                                         "fill_longest_side", "fill_area", "blockers")
                                        if k in rep}
            out["dimensions"]["marketplace_compliance"] = _dim(
                100.0 if passed else 0.0,
                detail=rep.get("blockers") or rep.get("verdict"))
        except Exception as exc:  # noqa: BLE001
            out["dimensions"]["marketplace_compliance"] = _dim(
                None, status="unavailable", detail=f"{type(exc).__name__}: {exc}")
    else:
        out["dimensions"]["marketplace_compliance"] = _dim(
            None, status="not_applicable",
            detail="compliance is only scored for a main/listing image")

    # ---- text accuracy (programmatic OCR) -----------------------------------
    ocr = _ocr(image_bytes)
    expected = [str(t) for t in (case.get("expected_terms") or []) if str(t).strip()]
    if ocr is None:
        out["dimensions"]["text_accuracy"] = _dim(
            None, status="unavailable", detail="OCR lane unavailable")
    elif surface in ("main", "listing_image", "main_image"):
        # A main image must carry no text at all.
        out["dimensions"]["text_accuracy"] = _dim(
            100.0 if ocr.get("boxes", 0) == 0 else 0.0,
            detail={"boxes": ocr.get("boxes"), "words": ocr.get("words"),
                    "rule": "main image must be text-free"})
    elif expected:
        words = " ".join(str(w).lower() for w in (ocr.get("words") or []))
        found = sum(1 for term in expected if _term_in(term, words))
        out["dimensions"]["text_accuracy"] = _dim(
            found / len(expected) * 100.0,
            detail={"expected": expected, "found": found,
                    "words": ocr.get("words")})
    else:
        out["dimensions"]["text_accuracy"] = _dim(
            None, status="not_applicable", detail="no text rule for this surface")

    # ---- product fidelity (identity against a reference) -------------------
    if reference_bytes:
        try:
            import ship_gate

            ident = ship_gate.review_image(
                image_bytes, brief=brief, reference=reference_bytes,
                surface=None, use_default_scorers=False)
            axis = (ident.get("axes") or {}).get("identity", {})
            distance = axis.get("phash_distance")
            ssim = axis.get("ssim")
            ik = cfg["identity"]
            if ssim is None and distance is None:
                out["dimensions"]["product_fidelity"] = _dim(
                    None, status="unavailable", detail=axis or ident)
            else:
                ssim = float(ssim or 0.0)
                score = _scale(ssim, float(ik["min_ssim"]), float(ik["good_ssim"]))
                if distance is not None and int(distance) > int(ik["max_phash_distance"]):
                    score = min(score, 40.0)
                out["dimensions"]["product_fidelity"] = _dim(
                    score, detail={"phash_distance": distance, "ssim": round(ssim, 4)})
        except Exception as exc:  # noqa: BLE001
            out["dimensions"]["product_fidelity"] = _dim(
                None, status="unavailable", detail=f"{type(exc).__name__}: {exc}")
    else:
        out["dimensions"]["product_fidelity"] = _dim(
            None, status="not_applicable", detail="no reference supplied")

    # ---- photographic quality (HPSv2 preference + sharpness) ---------------
    sharp = _sharpness(image_bytes)
    qk = cfg["quality"]
    if scoring:
        try:
            import image_review_scorers as irs

            pref = irs.score("preference", image_bytes, brief) or {}
            value = pref.get("score")
            if value is None:
                out["dimensions"]["photographic_quality"] = _dim(
                    None, status="unavailable", detail=pref.get("error") or "no score")
            else:
                base = _scale(float(value), float(qk["preference_floor"]),
                              float(qk["preference_good"]))
                if sharp is not None and sharp < float(qk["sharpness_floor"]):
                    base = min(base, 50.0)
                out["dimensions"]["photographic_quality"] = _dim(
                    base, detail={"preference": value, "sharpness": sharp})
        except Exception as exc:  # noqa: BLE001
            out["dimensions"]["photographic_quality"] = _dim(
                None, status="unavailable", detail=f"{type(exc).__name__}: {exc}")
    else:
        out["dimensions"]["photographic_quality"] = _dim(
            None, status="skipped", detail=f"scoring disabled; sharpness={sharp}")
    out["sharpness"] = sharp

    # ---- instruction fidelity (vision model against the brief) ------------
    if scoring and brief:
        verdict = _vision_verdict(image_bytes, brief)
        if not verdict or verdict.get("unparsed"):
            out["dimensions"]["instruction_fidelity"] = _dim(
                None, status="unavailable",
                detail=(verdict or {}).get("raw", "no verdict"))
        else:
            matches = bool(verdict.get("matches_brief"))
            confidence = float(verdict.get("confidence") or 0.0)
            issues = verdict.get("issues") or []
            score = (95.0 if matches else 35.0) - min(30.0, 5.0 * len(issues))
            score = _clamp(score * (0.7 + 0.3 * min(1.0, confidence)))
            out["dimensions"]["instruction_fidelity"] = _dim(
                score, detail={"matches_brief": matches, "issues": issues,
                               "model": verdict.get("model")})
    else:
        out["dimensions"]["instruction_fidelity"] = _dim(
            None, status="skipped" if scoring is False else "not_applicable",
            detail="no brief or scoring disabled")

    # ---- speed -------------------------------------------------------------
    if seconds is None:
        out["dimensions"]["speed"] = _dim(None, status="unavailable",
                                          detail="no render time recorded")
    else:
        sk = cfg["speed"]
        if seconds <= float(sk["good_seconds"]):
            score = 100.0
        elif seconds >= float(sk["fail_seconds"]):
            score = 0.0
        else:
            span = float(sk["fail_seconds"]) - float(sk["good_seconds"])
            score = 100.0 * (1.0 - (seconds - float(sk["good_seconds"])) / span)
        out["dimensions"]["speed"] = _dim(score, detail={"seconds": round(seconds, 1)})

    # ---- failure recovery --------------------------------------------------
    attempts = case.get("attempts")
    if attempts is None:
        out["dimensions"]["failure_recovery"] = _dim(
            None, status="not_applicable", detail="no regeneration attempts recorded")
    else:
        out["dimensions"]["failure_recovery"] = _dim(
            100.0 if case.get("recovered") else 0.0,
            detail={"attempts": attempts, "recovered": bool(case.get("recovered"))})

    out["dimensions"]["set_consistency"] = _dim(
        None, status="deferred", detail="scored across a set by aggregate()")
    out["phash"] = phash_of(image_bytes)
    return out


def aggregate(rows: Sequence[Dict[str, Any]], *, cfg: Optional[Dict[str, Any]] = None,
              set_size: int = 0) -> Dict[str, Any]:
    """Mean per dimension over cases, plus set consistency when a set is scored.

    A dimension with no measured cases is reported as unavailable, never as zero
    and never as a pass: "we could not measure it" and "it scored badly" are
    different facts and the bar checks both differently.
    """
    cfg = cfg or load_config()
    per_dim: Dict[str, List[float]] = {d: [] for d in DIMENSIONS}
    unavailable: Dict[str, int] = {d: 0 for d in DIMENSIONS}
    statuses: Dict[str, set[str]] = {d: set() for d in DIMENSIONS}
    compliance_pass = compliance_total = 0
    for row in rows:
        for dim, block in (row.get("dimensions") or {}).items():
            if dim not in per_dim:
                continue
            statuses[dim].add(str(block.get("status") or ""))
            score = block.get("score")
            if score is None:
                unavailable[dim] += 1
            else:
                per_dim[dim].append(float(score))
            if dim == "marketplace_compliance" and block.get("status") == "measured":
                compliance_total += 1
                if float(score) >= 100.0:
                    compliance_pass += 1

    summary: Dict[str, Any] = {"cases": len(rows), "dimensions": {}}
    for dim in DIMENSIONS:
        scores = per_dim[dim]
        summary["dimensions"][dim] = {
            "mean": round(sum(scores) / len(scores), 1) if scores else None,
            "measured": len(scores),
            "unavailable": unavailable[dim],
        }
    if compliance_total:
        summary["compliance_rate"] = round(compliance_pass / compliance_total, 4)
    else:
        summary["compliance_rate"] = None

    # Set consistency: pHash spread *within a set*, not across unrelated
    # scenarios. Comparing a lifestyle shot with a white packshot measures the
    # brief, not consistency; the same product photographed twice measures it.
    groups: Dict[str, List[int]] = {}
    for row in rows:
        if row.get("phash") is None:
            continue
        key = str(row.get("scenario") or row.get("case_id") or "default")
        groups.setdefault(key, []).append(int(row["phash"]))
    pairwise: List[int] = []
    groups_used = 0
    for key, hashes in groups.items():
        if len(hashes) < 2:
            continue
        groups_used += 1
        for i in range(len(hashes)):
            for j in range(i + 1, len(hashes)):
                pairwise.append(bin(hashes[i] ^ hashes[j]).count("1"))
    if pairwise:
        mean_distance = sum(pairwise) / len(pairwise)
        summary["dimensions"]["set_consistency"] = {
            "mean": round(_clamp(100.0 - mean_distance * 4.0), 1),
            "measured": len(pairwise), "unavailable": 0,
            "detail": {"mean_phash_distance": round(mean_distance, 2),
                       "sets_compared": groups_used},
        }
    else:
        summary["dimensions"]["set_consistency"] = {
            "mean": None, "measured": 0,
            "unavailable": sum(len(h) for h in groups.values()),
            "detail": "needs at least two images of the same scenario"}
    summary["sets"] = {k: len(v) for k, v in sorted(groups.items())}

    bar = cfg["bar"]
    passed = [d for d, block in summary["dimensions"].items()
              if block["mean"] is not None
              and block["mean"] >= float(bar["min_dimension"])]
    failed = [d for d, block in summary["dimensions"].items()
              if block["mean"] is not None
              and block["mean"] < float(bar["min_dimension"])]
    missing = [d for d, block in summary["dimensions"].items()
               if block["mean"] is None
               and d not in ("set_consistency",)
               # A dimension every case declared not_applicable is not a gap:
               # a from-scratch picture has no reference to be faithful to.
               and not (statuses[d] and statuses[d] <= {"not_applicable", "deferred"})]
    summary["bar"] = {
        "min_dimension": bar["min_dimension"],
        "required_compliance": bar["required_compliance"],
        "dimensions_passing": passed,
        "dimensions_below_bar": failed,
        "dimensions_unmeasured": missing,
        "compliance_ok": (summary["compliance_rate"] is not None
                          and summary["compliance_rate"] * 100.0
                          >= float(bar["required_compliance"])),
    }
    summary["production_ready"] = bool(
        not failed and not missing and summary["bar"]["compliance_ok"])
    return summary


def phash_of(image_bytes: Optional[bytes]) -> Optional[int]:
    if not image_bytes:
        return None
    try:
        from io import BytesIO as _B

        from PIL import Image

        import ship_gate

        with Image.open(_B(image_bytes)) as im:
            return int(ship_gate.phash(im.convert("RGB")))
    except Exception:  # noqa: BLE001
        return None
