"""Brief catalog loading and validation.

A brief is one product-picture request a seller would plausibly make: category,
product situation, the input it starts from, and the hard constraints an
Amazon-ready image must satisfy.

The product-picture service has exactly three inputs (ty/MANDATE.md): the
prompt alone, stored references from earlier generations, and references the
user uploads. `source_mode` names which one a brief uses, and every reference
mode carries a `reference` object describing that input. A brief may not claim
a reference it does not name.

The catalog is data (`ty/seller_briefs.json`), not code. Nothing here calls a
model or the network.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Iterable, List

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CATALOG_PATH = REPO_ROOT / "ty" / "seller_briefs.json"

SOURCE_MODES = ("prompt_only", "stored_reference", "uploaded_reference")
REFERENCE_MODES = ("stored_reference", "uploaded_reference")
REFERENCE_KINDS = {"stored_reference": "stored_asset", "uploaded_reference": "uploaded_file"}
MIN_PER_MODE = 12

CATEGORIES = (
    "supplement_pouch",
    "ceramic_mug",
    "apparel",
    "skincare_bottle",
    "small_appliance",
    "pet_product",
    "tool",
    "food_jar",
)

SITUATIONS = (
    "white_background_main",
    "lifestyle",
    "infographic",
    "scale_reference",
    "bundle_multipack",
    "packaging_mockup",
    "background_swap",
    "series_consistency",
)

TEXT_RULES = ("no_text", "allowed", "text_expected")

REQUIRED_CONSTRAINTS = ("dimensions", "aspect", "background", "fill_pct")


def load_catalog(path: str | Path | None = None) -> Dict[str, Any]:
    """Read the catalog JSON. Raises FileNotFoundError/ValueError, never guesses."""
    target = Path(path) if path is not None else DEFAULT_CATALOG_PATH
    with open(target, "r", encoding="utf-8") as fh:
        payload = json.load(fh)
    if not isinstance(payload, dict) or not isinstance(payload.get("briefs"), list):
        raise ValueError("catalog must be an object with a 'briefs' list")
    return payload


def _check_dimensions(brief_id: str, spec: Any, errors: List[str]) -> None:
    if not isinstance(spec, dict):
        errors.append(f"{brief_id}: dimensions must be an object")
        return
    for key in ("min_width", "min_height"):
        value = spec.get(key)
        if not isinstance(value, int) or value < 200:
            errors.append(f"{brief_id}: dimensions.{key} must be an int >= 200")
    max_w = spec.get("max_width", 10000)
    max_h = spec.get("max_height", 10000)
    if not isinstance(max_w, int) or max_w < spec.get("min_width", 0):
        errors.append(f"{brief_id}: dimensions.max_width invalid")
    if not isinstance(max_h, int) or max_h < spec.get("min_height", 0):
        errors.append(f"{brief_id}: dimensions.max_height invalid")


def _check_background(brief_id: str, spec: Any, errors: List[str]) -> None:
    if not isinstance(spec, dict):
        errors.append(f"{brief_id}: background must be an object")
        return
    value = spec.get("value")
    if not isinstance(value, int) or not 0 <= value <= 255:
        errors.append(f"{brief_id}: background.value must be 0..255")
    mode = spec.get("mode", "uniform")
    if mode not in ("uniform", "free"):
        errors.append(f"{brief_id}: background.mode must be uniform|free")
    tol = spec.get("tolerance", 6)
    if not isinstance(tol, int) or not 0 <= tol <= 60:
        errors.append(f"{brief_id}: background.tolerance must be 0..60")


def _check_fill(brief_id: str, spec: Any, errors: List[str]) -> None:
    if not isinstance(spec, dict):
        errors.append(f"{brief_id}: fill_pct must be an object")
        return
    low, high = spec.get("min"), spec.get("max")
    if not isinstance(low, (int, float)) or not isinstance(high, (int, float)):
        errors.append(f"{brief_id}: fill_pct.min/max must be numbers")
    elif not 0 <= low < high <= 100:
        errors.append(f"{brief_id}: fill_pct must satisfy 0 <= min < max <= 100")


def _check_reference(brief_id: str, mode: Any, reference: Any, errors: List[str]) -> None:
    """A reference mode must name its reference; a prompt-only brief must not."""
    if mode == "prompt_only":
        if reference is not None:
            errors.append(f"{brief_id}: prompt_only brief must not declare a reference")
        return
    if mode not in REFERENCE_MODES:
        return  # the mode error is already reported
    if not isinstance(reference, dict):
        errors.append(f"{brief_id}: {mode} brief needs a reference object")
        return
    expected_kind = REFERENCE_KINDS[mode]
    kind = reference.get("kind")
    if kind != expected_kind:
        errors.append(f"{brief_id}: reference.kind must be {expected_kind!r} for {mode}, got {kind!r}")
        return
    path = reference.get("path")
    if kind == "stored_asset":
        if not isinstance(path, str) or not path.strip():
            errors.append(f"{brief_id}: stored reference needs a repo-relative path")
        elif path.startswith("/") or ":" in path or ".." in Path(path.replace("\\", "/")).parts:
            errors.append(f"{brief_id}: stored reference path must be repo-relative, no '..'")
        elif not any(path.replace("\\", "/").startswith(root) for root in (
                "renders/", "generated_images/", "Northstar_backend/data/studio_generated/")):
            errors.append(f"{brief_id}: stored reference must live under renders/, "
                          "generated_images/ or Northstar_backend/data/studio_generated/")
    else:  # uploaded_file
        descriptor = reference.get("descriptor")
        if not isinstance(descriptor, dict):
            errors.append(f"{brief_id}: uploaded reference needs a descriptor object")
        else:
            filename = descriptor.get("filename")
            if not isinstance(filename, str) or not filename.strip():
                errors.append(f"{brief_id}: uploaded reference descriptor needs a filename")
            mime = descriptor.get("mime_type")
            if not isinstance(mime, str) or not mime.startswith("image/"):
                errors.append(f"{brief_id}: uploaded reference descriptor mime_type must be image/*")
            subject = descriptor.get("subject")
            if not isinstance(subject, str) or not subject.strip():
                errors.append(f"{brief_id}: uploaded reference descriptor needs a subject")
        if path is not None and not isinstance(path, str):
            errors.append(f"{brief_id}: uploaded reference path must be a string or null")
    spec = reference.get("check")
    if spec is not None:
        if not isinstance(spec, dict):
            errors.append(f"{brief_id}: reference.check must be an object")
        else:
            colour = spec.get("min_colour_agreement", 0.62)
            aspect = spec.get("max_aspect_ratio", 1.6)
            if not isinstance(colour, (int, float)) or not 0 < colour <= 1:
                errors.append(f"{brief_id}: reference.check.min_colour_agreement must be 0..1")
            if not isinstance(aspect, (int, float)) or aspect < 1:
                errors.append(f"{brief_id}: reference.check.max_aspect_ratio must be >= 1")


def validate_catalog(payload: Dict[str, Any]) -> List[str]:
    """Return a list of human-readable problems. Empty list means valid."""
    errors: List[str] = []
    briefs = payload.get("briefs") if isinstance(payload, dict) else None
    if not isinstance(briefs, list):
        return ["catalog has no briefs list"]
    if len(briefs) < 24:
        errors.append(f"catalog has {len(briefs)} briefs, need at least 24")

    seen_ids = set()
    seen_pairs = set()
    situations = set()
    categories = set()
    tiers = set()
    modes = {mode: 0 for mode in SOURCE_MODES}

    for index, brief in enumerate(briefs):
        if not isinstance(brief, dict):
            errors.append(f"brief[{index}] is not an object")
            continue
        brief_id = brief.get("id")
        if not isinstance(brief_id, str) or not brief_id.strip():
            errors.append(f"brief[{index}] has no id")
            continue
        if brief_id in seen_ids:
            errors.append(f"{brief_id}: duplicate id")
        seen_ids.add(brief_id)

        category = brief.get("category")
        situation = brief.get("situation")
        if category not in CATEGORIES:
            errors.append(f"{brief_id}: unknown category {category!r}")
        else:
            categories.add(category)
        if situation not in SITUATIONS:
            errors.append(f"{brief_id}: unknown situation {situation!r}")
        else:
            situations.add(situation)

        mode = brief.get("source_mode")
        if mode not in SOURCE_MODES:
            errors.append(f"{brief_id}: unknown source_mode {mode!r} "
                          f"(must be one of {SOURCE_MODES})")
        else:
            modes[mode] += 1
        _check_reference(brief_id, mode, brief.get("reference"), errors)

        pair = (category, situation, brief.get("difficulty"), mode)
        if pair in seen_pairs:
            errors.append(f"{brief_id}: duplicate (category, situation, difficulty, mode) {pair}")
        seen_pairs.add(pair)

        tier = brief.get("difficulty")
        if not isinstance(tier, int) or tier not in (1, 2, 3):
            errors.append(f"{brief_id}: difficulty must be int 1..3")
        else:
            tiers.add(tier)

        constraints = brief.get("constraints")
        if not isinstance(constraints, dict):
            errors.append(f"{brief_id}: constraints must be an object")
            continue
        for key in REQUIRED_CONSTRAINTS:
            if key not in constraints:
                errors.append(f"{brief_id}: constraints missing {key}")
        if "dimensions" in constraints:
            _check_dimensions(brief_id, constraints["dimensions"], errors)
        if "aspect" in constraints:
            aspect = constraints["aspect"]
            if not isinstance(aspect, dict) or not isinstance(aspect.get("ratio"), (int, float)):
                errors.append(f"{brief_id}: aspect.ratio must be a number")
            elif not 0.2 <= float(aspect["ratio"]) <= 5:
                errors.append(f"{brief_id}: aspect.ratio must be 0.2..5")
            tol = aspect.get("tolerance", 0.02) if isinstance(aspect, dict) else None
            if not isinstance(tol, (int, float)) or not 0 <= tol <= 0.5:
                errors.append(f"{brief_id}: aspect.tolerance must be 0..0.5")
        if "background" in constraints:
            _check_background(brief_id, constraints["background"], errors)
        if "fill_pct" in constraints:
            _check_fill(brief_id, constraints["fill_pct"], errors)

        rule = constraints.get("text_rule")
        if rule not in TEXT_RULES:
            errors.append(f"{brief_id}: text_rule must be one of {TEXT_RULES}")
        matte = constraints.get("matte", {})
        if not isinstance(matte, dict) or matte.get("mode", "any") not in ("any", "white_matte", "alpha"):
            errors.append(f"{brief_id}: matte.mode invalid")
        size = constraints.get("file_size", {})
        if not isinstance(size, dict):
            errors.append(f"{brief_id}: file_size must be an object")
        else:
            low_bytes = size.get("min_bytes", 20000)
            high_bytes = size.get("max_bytes", 20_000_000)
            if not isinstance(low_bytes, int) or low_bytes < 0:
                errors.append(f"{brief_id}: file_size.min_bytes invalid")
            if not isinstance(high_bytes, int) or high_bytes <= low_bytes:
                errors.append(f"{brief_id}: file_size.max_bytes invalid")
        pass_score = brief.get("pass_score", 70)
        if not isinstance(pass_score, (int, float)) or not 0 <= pass_score <= 100:
            errors.append(f"{brief_id}: pass_score must be 0..100")
        critical = brief.get("critical", ["dimensions", "aspect", "background"])
        if not isinstance(critical, list) or any(not isinstance(c, str) for c in critical):
            errors.append(f"{brief_id}: critical must be a list of check names")

    for name in SITUATIONS:
        if name not in situations:
            errors.append(f"catalog does not cover situation {name!r}")
    for name in CATEGORIES:
        if name not in categories:
            errors.append(f"catalog does not cover category {name!r}")
    for tier in (1, 2, 3):
        if tier not in tiers:
            errors.append(f"catalog has no difficulty tier {tier}")
    for mode, count in modes.items():
        if count < MIN_PER_MODE:
            errors.append(f"catalog has {count} {mode} briefs, need at least {MIN_PER_MODE}")
    return errors


def brief_mode(brief: Dict[str, Any]) -> str:
    """The brief's input mode, or `unclassified` when it declares none.

    `unclassified` is deliberate: a brief that forgets its mode shows up as its
    own bucket in the summary instead of being silently folded into prompt_only.
    """
    mode = brief.get("source_mode") if isinstance(brief, dict) else None
    return str(mode) if mode in SOURCE_MODES else "unclassified"


def briefs_by_mode(payload: Dict[str, Any]) -> Dict[str, List[Dict[str, Any]]]:
    out: Dict[str, List[Dict[str, Any]]] = {name: [] for name in SOURCE_MODES}
    for brief in payload.get("briefs", []):
        out.setdefault(brief_mode(brief), []).append(brief)
    return out


def mode_counts(payload: Dict[str, Any]) -> Dict[str, int]:
    """Declared brief count per mode, always including the three known modes."""
    counts = {name: 0 for name in SOURCE_MODES}
    for brief in payload.get("briefs", []):
        key = brief_mode(brief)
        counts[key] = counts.get(key, 0) + 1
    return counts


def briefs_by_situation(payload: Dict[str, Any]) -> Dict[str, List[Dict[str, Any]]]:
    out: Dict[str, List[Dict[str, Any]]] = {name: [] for name in SITUATIONS}
    for brief in payload.get("briefs", []):
        out.setdefault(brief.get("situation"), []).append(brief)
    return out


def iter_briefs(payload: Dict[str, Any]) -> Iterable[Dict[str, Any]]:
    return list(payload.get("briefs", []))
