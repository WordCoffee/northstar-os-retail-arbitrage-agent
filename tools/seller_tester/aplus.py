"""A+ content modules: a page of modules, produced and scored as a page.

An A+ deliverable is not one square picture. It is an ordered stack of modules —
a hero band, a comparison table, an ingredient grid, a lifestyle band, a brand
story, a technical spec strip — each with its own declared pixel size and its own
required copy. A single-image scorer cannot say anything useful about that: the
product may be absent from a brand story band by design, and a module that
renders nothing is a failure even though the page still looks like a page.

So this module has its own brief family, its own producer and its own scorer:

* the **brief** declares the module grid (id, kind, width, height, order), the
  copy each module must show, and the product-in-frame rule per module;
* the **producer** composites the seller's real product pixels for modules that
  carry the product (the same cutout/composite path as the picture service) and
  typesets flat copy for modules that do not; a module that needs a generated
  scene asks the render lane, and a refused lane is `cannot_verify` with the
  reason, never a replayed file;
* the **scorer** measures the page: module count and order, each module's real
  pixels against its declared size, the required copy per module through OCR and
  the same fuzzy matcher the reference check uses, and the product region for
  every module that requires it. The page passes only when every required
  module passes.

`product_in_frame: true` is only lawful on `fidelity: exact` with a reference:
the seller's product must be their own pixels. `tolerant` exists for the one
text-only band that carries no product, and validation refuses the rest.

Nothing here calls the network, Amazon, or a paid API. GPU work goes through the
existing render lane, which owns its own lock and RAM floor.
"""
from __future__ import annotations

import difflib
import json
import re
import sys
from io import BytesIO
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[2]
for _extra in (str(REPO_ROOT), str(REPO_ROOT / "Northstar_backend")):
    if _extra not in sys.path:
        sys.path.insert(0, _extra)

from . import reference_check  # noqa: E402
from .briefs import (  # noqa: E402
    CATEGORIES,
    REFERENCE_MODES,
    SOURCE_MODES,
    brief_fidelity,
    brief_mode,
)
from .composite_check import check_composite, missing_cutout_verdict  # noqa: E402
from .scorers import load_image  # noqa: E402

APLUS_KEY = "aplus_briefs"
CONTENT_TYPES = (
    "hero_band",
    "comparison_table",
    "ingredient_grid",
    "lifestyle_band",
    "brand_story",
    "spec_strip",
)
MIN_APLUS_BRIEFS = 6

MODULE_SCENES = ("flat", "generated")
DEFAULT_PAGE_WIDTH = 970
DEFAULT_BACKGROUND = 248
DEFAULT_MIN_TEXT_RECALL = 0.60
DEFAULT_PASS_SCORE = 70

#: Fuzzy match ratio for OCR noise, the same bar as the reference check.
FUZZY_RATIO = 0.82
#: A module whose luminance barely varies rendered nothing. A flat canvas is 0.0.
BLANK_LUMINANCE_STD = 0.75

FONT_CANDIDATES = (
    r"C:\Windows\Fonts\arialbd.ttf",
    r"C:\Windows\Fonts\seguisb.ttf",
    r"C:\Windows\Fonts\calibrib.ttf",
    r"C:\Windows\Fonts\arial.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
)


# --------------------------------------------------------------------- loading
def load_aplus_briefs(payload: Optional[Dict[str, Any]] = None
                      ) -> List[Dict[str, Any]]:
    """The A+ family from a catalog payload (or the shipped catalog)."""
    if payload is None:
        from .briefs import DEFAULT_CATALOG_PATH

        with open(DEFAULT_CATALOG_PATH, "r", encoding="utf-8") as handle:
            payload = json.load(handle)
    rows = payload.get(APLUS_KEY) if isinstance(payload, dict) else None
    if not isinstance(rows, list):
        raise ValueError(f"catalog has no {APLUS_KEY!r} list")
    return [row for row in rows if isinstance(row, dict)]


def _module_rows(brief: Dict[str, Any]) -> List[Dict[str, Any]]:
    modules = brief.get("modules")
    return [row for row in modules if isinstance(row, dict)] if isinstance(modules, list) else []


def module_grid(brief: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Declared modules in order, with the defaults the producer and scorer use."""
    page = brief.get("page") if isinstance(brief.get("page"), dict) else {}
    page_background = page.get("background") if isinstance(page.get("background"), dict) else {}
    out: List[Dict[str, Any]] = []
    for row in _module_rows(brief):
        background = row.get("background") if isinstance(row.get("background"), dict) else {}
        value = background.get("value", page_background.get("value", DEFAULT_BACKGROUND))
        out.append({
            "id": str(row.get("id") or ""),
            "kind": str(row.get("kind") or ""),
            "width": int(row.get("width") or 0),
            "height": int(row.get("height") or 0),
            "background_value": int(value),
            "product_in_frame": bool(row.get("product_in_frame")),
            "product_anchor": list(row.get("product_anchor") or (0.68, 0.56)),
            "product_scale": float(row.get("product_scale") or 0.66),
            "text_required": [str(line) for line in (row.get("text_required") or [])],
            "text_box": list(row.get("text_box") or (0.06, 0.10, 0.52, 0.80)),
            "text_align": str(row.get("text_align") or "left"),
            "font_scale": float(row.get("font_scale") or 0.075),
            "rules": bool(row.get("rules")),
            "scene": str(row.get("scene") or "flat"),
            "min_text_recall": float(
                row.get("min_text_recall", brief.get("min_text_recall",
                                                     DEFAULT_MIN_TEXT_RECALL))),
        })
    return out


def declared_page_height(brief: Dict[str, Any]) -> int:
    """Sum of module heights plus the declared gaps."""
    page = brief.get("page") if isinstance(brief.get("page"), dict) else {}
    gap = int(page.get("gap_px") or 0)
    modules = module_grid(brief)
    if not modules:
        return 0
    return sum(row["height"] for row in modules) + gap * (len(modules) - 1)


# ------------------------------------------------------------------- validation
def _float01(value: Any) -> bool:
    return isinstance(value, (int, float)) and 0.0 <= float(value) <= 1.0


def validate_aplus_briefs(payload: Dict[str, Any]) -> List[str]:
    """Human-readable problems with the A+ family. Empty list means valid."""
    errors: List[str] = []
    rows = payload.get(APLUS_KEY) if isinstance(payload, dict) else None
    if not isinstance(rows, list):
        return [f"catalog has no {APLUS_KEY!r} list"]
    if len(rows) < MIN_APLUS_BRIEFS:
        errors.append(f"A+ family has {len(rows)} briefs, need at least {MIN_APLUS_BRIEFS}")

    seen_ids = set()
    content_types = set()
    for index, brief in enumerate(rows):
        if not isinstance(brief, dict):
            errors.append(f"aplus_briefs[{index}] is not an object")
            continue
        brief_id = brief.get("id")
        if not isinstance(brief_id, str) or not brief_id.strip():
            errors.append(f"aplus_briefs[{index}] has no id")
            continue
        if brief_id in seen_ids:
            errors.append(f"{brief_id}: duplicate id")
        seen_ids.add(brief_id)

        content_type = brief.get("content_type")
        if content_type not in CONTENT_TYPES:
            errors.append(f"{brief_id}: unknown content_type {content_type!r} "
                          f"(must be one of {CONTENT_TYPES})")
        else:
            content_types.add(content_type)
        if brief.get("category") not in CATEGORIES:
            errors.append(f"{brief_id}: unknown category {brief.get('category')!r}")
        tier = brief.get("difficulty")
        if not isinstance(tier, int) or tier not in (1, 2, 3):
            errors.append(f"{brief_id}: difficulty must be int 1..3")

        mode = brief.get("source_mode")
        if mode not in SOURCE_MODES:
            errors.append(f"{brief_id}: unknown source_mode {mode!r} "
                          f"(must be one of {SOURCE_MODES})")
        fidelity = brief.get("fidelity")
        if fidelity not in ("exact", "tolerant"):
            errors.append(f"{brief_id}: fidelity must be 'exact' or 'tolerant'")
        if mode in REFERENCE_MODES and not isinstance(brief.get("reference"), dict):
            errors.append(f"{brief_id}: {mode} brief needs a reference object")

        page = brief.get("page")
        page_width = DEFAULT_PAGE_WIDTH
        if not isinstance(page, dict):
            errors.append(f"{brief_id}: page must be an object")
        else:
            page_width = page.get("width", DEFAULT_PAGE_WIDTH)
            if not isinstance(page_width, int) or not 200 <= page_width <= 2400:
                errors.append(f"{brief_id}: page.width must be an int 200..2400")
                page_width = DEFAULT_PAGE_WIDTH
            gap = page.get("gap_px", 0)
            if not isinstance(gap, int) or not 0 <= gap <= 200:
                errors.append(f"{brief_id}: page.gap_px must be an int 0..200")
            background = page.get("background")
            if background is not None:
                if not isinstance(background, dict) or \
                        not isinstance(background.get("value"), int) or \
                        not 0 <= background["value"] <= 255:
                    errors.append(f"{brief_id}: page.background.value must be 0..255")

        modules = _module_rows(brief)
        if not modules:
            errors.append(f"{brief_id}: declares no modules")
            continue
        seen_modules = set()
        module_ids: List[str] = []
        product_modules = 0
        for position, module in enumerate(modules):
            label = f"{brief_id}.modules[{position}]"
            module_id = module.get("id")
            if not isinstance(module_id, str) or not module_id.strip():
                errors.append(f"{label}: has no id")
                continue
            if module_id in seen_modules:
                errors.append(f"{brief_id}: duplicate module id {module_id!r}")
            seen_modules.add(module_id)
            module_ids.append(module_id)
            if module.get("kind") not in CONTENT_TYPES:
                errors.append(f"{label}: unknown kind {module.get('kind')!r}")
            width, height = module.get("width"), module.get("height")
            if not isinstance(width, int) or not 100 <= width <= 2400:
                errors.append(f"{label}: width must be an int 100..2400")
            elif width != page_width:
                errors.append(f"{label}: width {width} does not match page width {page_width}")
            if not isinstance(height, int) or not 100 <= height <= 2400:
                errors.append(f"{label}: height must be an int 100..2400")

            background = module.get("background")
            if background is not None:
                if not isinstance(background, dict) or \
                        not isinstance(background.get("value"), int) or \
                        not 0 <= background["value"] <= 255:
                    errors.append(f"{label}: background.value must be 0..255")

            in_frame = module.get("product_in_frame")
            if not isinstance(in_frame, bool):
                errors.append(f"{label}: product_in_frame must be true or false")
            elif in_frame:
                product_modules += 1

            text = module.get("text_required")
            if not isinstance(text, list) or not text or \
                    any(not isinstance(line, str) or not line.strip() for line in text):
                errors.append(f"{label}: text_required must be a non-empty list of strings")
            elif not any(reference_check.key_tokens(line) for line in text):
                errors.append(f"{label}: text_required carries no matchable word")

            box = module.get("text_box")
            if box is not None and (not isinstance(box, list) or len(box) != 4
                                    or not all(_float01(v) for v in box)):
                errors.append(f"{label}: text_box must be four fractions 0..1")
            anchor = module.get("product_anchor")
            if anchor is not None and (not isinstance(anchor, list) or len(anchor) != 2
                                       or not all(_float01(v) for v in anchor)):
                errors.append(f"{label}: product_anchor must be two fractions 0..1")
            scale = module.get("product_scale")
            if scale is not None and (not isinstance(scale, (int, float))
                                      or not 0.05 <= float(scale) <= 1.0):
                errors.append(f"{label}: product_scale must be 0.05..1.0")
            scene = module.get("scene", "flat")
            if scene not in MODULE_SCENES:
                errors.append(f"{label}: scene must be one of {MODULE_SCENES}")

        brief_in_frame = brief.get("product_in_frame")
        if not isinstance(brief_in_frame, bool):
            errors.append(f"{brief_id}: product_in_frame must be true or false")
        elif brief_in_frame and not product_modules:
            errors.append(f"{brief_id}: product_in_frame is true but no module requires it")
        elif not brief_in_frame and product_modules:
            errors.append(f"{brief_id}: modules require the product but "
                          "the brief declares product_in_frame: false")

        # The product-in-frame rule: the seller's product means the seller's pixels.
        if brief_in_frame or product_modules:
            if brief_fidelity(brief) != "exact":
                errors.append(
                    f"{brief_id}: a module that requires the product must be fidelity "
                    f"'exact' with a reference; 'tolerant' is only lawful for a "
                    f"text-only band with product_in_frame: false")

        if isinstance(page, dict) and isinstance(page.get("height"), int):
            declared = declared_page_height(brief)
            if declared and page["height"] != declared:
                errors.append(f"{brief_id}: page.height {page['height']} does not match "
                              f"the module grid {declared}")

    for name in CONTENT_TYPES:
        if name not in content_types:
            errors.append(f"A+ family does not cover content_type {name!r}")
    return errors


# ------------------------------------------------------------------- production
def _relative(path: Optional[str | Path]) -> Optional[str]:
    if path is None:
        return None
    try:
        return Path(path).resolve().relative_to(REPO_ROOT).as_posix()
    except (ValueError, OSError):
        return str(path)


def _png_bytes(image: Any) -> bytes:
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def _font(size: int) -> Any:
    from PIL import ImageFont

    for candidate in FONT_CANDIDATES:
        try:
            if Path(candidate).is_file():
                return ImageFont.truetype(candidate, size)
        except OSError:
            continue
    try:
        return ImageFont.load_default(size=size)
    except TypeError:  # Pillow < 10.1
        return ImageFont.load_default()


def _draw_copy(image: Any, module: Dict[str, Any]) -> None:
    """Typeset a module's required copy inside its declared text box."""
    from PIL import ImageDraw

    width, height = image.size
    lines = module["text_required"]
    box = module["text_box"]
    left = int(width * float(box[0]))
    top = int(height * float(box[1]))
    box_width = max(1, int(width * float(box[2])))
    box_height = max(1, int(height * float(box[3])))
    size = max(18, int(height * module["font_scale"]))
    font = _font(size)
    draw = ImageDraw.Draw(image)
    count = max(1, len(lines))
    step = box_height / float(count)
    align = module["text_align"]
    for index, line in enumerate(lines):
        y = top + int(step * index + step * 0.5)
        text = str(line)
        try:
            bounds = draw.textbbox((0, 0), text, font=font)
            text_width = bounds[2] - bounds[0]
        except (AttributeError, ValueError):
            text_width = int(len(text) * size * 0.55)
        if align == "center":
            x = left + max(0, (box_width - text_width) // 2)
        elif align == "right":
            x = left + max(0, box_width - text_width)
        else:
            x = left
        draw.text((x, y - size // 2), text, font=font, fill=(28, 34, 30))
        if module.get("rules") and index < count - 1:
            rule_y = top + int(step * (index + 1))
            draw.line((left, rule_y, left + box_width, rule_y),
                      fill=(176, 176, 168), width=max(1, size // 24))


def _cutout_png(brief: Dict[str, Any], *, repo_root: Path, method: str
                ) -> Tuple[Optional[bytes], Optional[Any], Dict[str, Any]]:
    """Cut the seller's product out of the brief's reference, once per page."""
    import product_cutout as pc

    rgb, reason, resolved = reference_check.load_reference_rgb(
        brief.get("reference"), repo_root=repo_root)
    if rgb is None:
        return None, None, {"ok": False, "reason": reason, "reference_path": resolved}
    try:
        cut = pc.cutout(rgb, method)
    except Exception as exc:  # noqa: BLE001 - a refused cutout is a stated failure
        return None, None, {"ok": False, "reason": f"cutout failed: "
                             f"{type(exc).__name__}: {exc}",
                             "reference_path": resolved}
    metrics = pc.alpha_metrics(cut.alpha)
    if int(metrics.get("subject_px") or 0) == 0:
        return None, None, {"ok": False,
                            "reason": f"cutout method {method!r} found no product",
                            "reference_path": resolved}
    png = pc.rgba_png_bytes(cut.rgb, cut.alpha)
    rgba = np.dstack([cut.rgb, (np.asarray(cut.alpha) * 255).astype(np.uint8)])
    return png, rgba, {"ok": True, "method": method, "reference_path": resolved,
                       "metrics": metrics}


def _module_canvas(module: Dict[str, Any]) -> Any:
    from PIL import Image

    return Image.new("RGB", (module["width"], module["height"]),
                     (module["background_value"],) * 3)


def _place_and_copy(image: Any, module: Dict[str, Any], cut_png: bytes
                    ) -> Tuple[Any, List[int]]:
    """Composite the cutout onto a module image, then typeset the copy over it."""
    import product_composite as composite
    from PIL import Image

    placed = composite.place_product(
        _png_bytes(image), cut_png,
        scale=module["product_scale"],
        anchor=tuple(module["product_anchor"]),
        shadow=True)
    composed = Image.open(BytesIO(placed["bytes"])).convert("RGB")
    _draw_copy(composed, module)
    left, top, right, bottom = (int(v) for v in placed["product_box"])
    return composed, [left, top, right - left, bottom - top]


def produce_module(brief: Dict[str, Any], module: Dict[str, Any], *,
                   cutout_png: Optional[bytes] = None,
                   cutout_rgba: Optional[Any] = None,
                   renderer: Optional[Callable[..., Dict[str, Any]]] = None,
                   cutout_reason: str = "") -> Dict[str, Any]:
    """Produce one module honestly, or record why it could not be produced."""
    from PIL import Image

    record: Dict[str, Any] = {
        "id": module["id"], "kind": module["kind"],
        "width": module["width"], "height": module["height"],
        "product_in_frame": module["product_in_frame"],
        "text_required": list(module["text_required"]),
        "bytes": None, "path": None, "cutout": cutout_rgba,
        "product_box": None, "scene_source": "flat",
        "cannot_verify": False, "cannot_verify_reason": None,
    }
    try:
        if module["product_in_frame"] and cutout_png is None:
            raise _ModuleRefused(
                f"the product is required in module {module['id']!r} but no cutout "
                f"is available ({cutout_reason or 'no reason recorded'})")
        if module["scene"] == "generated":
            if renderer is None:
                raise _ModuleRefused("module needs a generated scene but no renderer "
                                     "was supplied")
            try:
                scene = renderer(brief, "scene")
            except Exception as exc:  # noqa: BLE001 - a refused lane is a stated failure
                raise _ModuleRefused(
                    f"render lane refused the scene: {type(exc).__name__}: {exc}")
            if not isinstance(scene, dict) or not scene.get("bytes"):
                raise _ModuleRefused("the scene renderer returned no image bytes")
            source = str(scene.get("source") or "")
            record["scene_source"] = source
            base = Image.open(BytesIO(scene["bytes"])).convert("RGB")
            base = base.resize((module["width"], module["height"]), Image.LANCZOS)
            if source != "generated":
                record["cannot_verify"] = True
                record["cannot_verify_reason"] = (
                    f"scene source {source!r} is not a render; the product pixels are "
                    "proved, the scene is not")
            if module["product_in_frame"]:
                image, box = _place_and_copy(base, module, cutout_png)
                record["product_box"] = box
            else:
                image = base
                _draw_copy(image, module)
        else:
            image = _module_canvas(module)
            if module["product_in_frame"]:
                image, box = _place_and_copy(image, module, cutout_png)
                record["product_box"] = box
            else:
                _draw_copy(image, module)
    except _ModuleRefused as exc:
        record["cannot_verify"] = True
        record["cannot_verify_reason"] = str(exc)
        return record

    record["bytes"] = _png_bytes(image)
    return record


class _ModuleRefused(RuntimeError):
    """One module could not be produced; the page reports it, it is never skipped."""


def produce_page(brief: Dict[str, Any], *, repo_root: str | Path = REPO_ROOT,
                 out_dir: Optional[str | Path] = None,
                 renderer: Optional[Callable[..., Dict[str, Any]]] = None,
                 method: str = "grabcut") -> Dict[str, Any]:
    """Produce every declared module and, when all exist, the page image."""
    from PIL import Image

    root = Path(repo_root)
    target_dir = Path(out_dir) if out_dir is not None else root / "renders" / "seller_aplus"
    target_dir.mkdir(parents=True, exist_ok=True)

    modules = module_grid(brief)
    brief_id = str(brief.get("id") or "aplus")
    page = brief.get("page") if isinstance(brief.get("page"), dict) else {}
    gap = int(page.get("gap_px") or 0)
    page_background = page.get("background") if isinstance(page.get("background"), dict) else {}
    background_value = int(page_background.get("value", DEFAULT_BACKGROUND))

    needs_product = any(row["product_in_frame"] for row in modules)
    cutout_png = cutout_rgba = None
    cutout_reason = "this page has no module that carries the product"
    cutout_record: Dict[str, Any] = {"ok": True, "skipped": "no product module"}
    if needs_product:
        cutout_png, cutout_rgba, cutout_record = _cutout_png(
            brief, repo_root=root, method=method)
        if not cutout_record.get("ok"):
            cutout_reason = str(cutout_record.get("reason") or "cutout refused")

    records: List[Dict[str, Any]] = []
    for module in modules:
        record = produce_module(
            brief, module, cutout_png=cutout_png, cutout_rgba=cutout_rgba,
            renderer=renderer, cutout_reason=cutout_reason)
        if record.get("bytes"):
            module_path = target_dir / f"{brief_id}__{module['id']}.png"
            module_path.write_bytes(record["bytes"])
            record["path"] = str(module_path)
        records.append(record)

    produced = [row for row in records if row.get("bytes")]
    page_path = None
    page_error = None
    if len(produced) != len(records):
        missing = [row["id"] for row in records if not row.get("bytes")]
        page_error = (f"page not assembled: {len(missing)} of {len(records)} modules "
                      f"were not produced ({', '.join(missing)})")
    else:
        height = sum(row["height"] for row in records) + gap * max(0, len(records) - 1)
        canvas = Image.new("RGB", (int(modules[0]["width"]), height),
                           (background_value,) * 3)
        top = 0
        for row in records:
            with Image.open(BytesIO(row["bytes"])) as opened:
                canvas.paste(opened.convert("RGB"), (0, top))
            top += row["height"] + gap
        page_path = target_dir / f"{brief_id}.png"
        canvas.save(page_path, format="PNG")

    return {
        "brief_id": brief_id,
        "content_type": brief.get("content_type"),
        "source_mode": brief_mode(brief),
        "fidelity": brief_fidelity(brief),
        "page": {
            "width": int(modules[0]["width"]) if modules else 0,
            "height": declared_page_height(brief),
            "path": str(page_path) if page_path else None,
            "error": page_error,
            "background": background_value,
            "gap_px": gap,
        },
        "modules": records,
        "cutout": cutout_record,
    }


# ---------------------------------------------------------------------- scoring
def _norm(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value or "").casefold())


def _fuzzy_recall(wanted: Sequence[str], ocr_text: str) -> Tuple[float, List[str], List[str]]:
    haystack = [_norm(chunk) for chunk in str(ocr_text or "").split()]
    haystack = [chunk for chunk in haystack if chunk]
    joined = "".join(haystack)
    matched: List[str] = []
    missing: List[str] = []
    for token in wanted:
        best = max((difflib.SequenceMatcher(None, token, chunk).ratio()
                    for chunk in haystack), default=0.0)
        if best >= FUZZY_RATIO or token in joined:
            matched.append(token)
        else:
            missing.append(token)
    recall = len(matched) / float(len(wanted)) if wanted else 0.0
    return recall, matched, missing


def _text_verdict(required: Sequence[str], ocr_text: str, min_recall: float
                  ) -> Dict[str, Any]:
    """Every required line must be present. Short lines match exactly after normalising."""
    lines: List[Dict[str, Any]] = []
    for line in required:
        tokens = reference_check.key_tokens(line)
        if tokens:
            recall, matched, missing = _fuzzy_recall(tokens, ocr_text)
            ok = recall >= float(min_recall)
            lines.append({"line": line, "ok": ok, "recall": round(recall, 3),
                          "matched": matched, "missing": missing})
        else:
            ok = _norm(line) in _norm(ocr_text)
            lines.append({"line": line, "ok": ok, "recall": None,
                          "matched": [_norm(line)] if ok else [],
                          "missing": [] if ok else [_norm(line)]})
    ok = bool(required) and all(row["ok"] for row in lines)
    missing = [row["line"] for row in lines if not row["ok"]]
    detail = ("all required lines present" if ok else
              f"missing copy: {', '.join(missing)}")
    return {"ok": ok, "skipped": False, "cannot_verify": False, "detail": detail,
            "lines": lines, "min_recall": float(min_recall),
            "ocr_text": str(ocr_text or "")[:600]}


def _present_verdict(rgb: Optional[np.ndarray], error: str) -> Dict[str, Any]:
    if rgb is None:
        return {"ok": False, "skipped": False, "cannot_verify": True,
                "detail": f"module rendered nothing: {error}"}
    luminance = rgb.astype(np.float32) @ np.array([0.299, 0.587, 0.114], dtype=np.float32)
    std = float(luminance.std())
    span = float(luminance.max() - luminance.min())
    ok = std >= BLANK_LUMINANCE_STD and span >= 8.0
    return {"ok": ok, "skipped": False, "cannot_verify": False,
            "detail": (f"luminance std {std:.2f}, span {span:.0f} "
                       f"({'content' if ok else 'blank'})"),
            "luminance_std": round(std, 3), "luminance_span": round(span, 2)}


def _size_verdict(loaded: Any, module: Dict[str, Any]) -> Dict[str, Any]:
    ok = loaded.width == module["width"] and loaded.height == module["height"]
    return {"ok": ok, "skipped": False, "cannot_verify": False,
            "detail": f"{loaded.width}x{loaded.height} vs declared "
                      f"{module['width']}x{module['height']}",
            "measured_size": [loaded.width, loaded.height],
            "declared_size": [module["width"], module["height"]]}


def _module_image(record: Optional[Dict[str, Any]]
                  ) -> Tuple[Optional[np.ndarray], str]:
    if not isinstance(record, dict):
        return None, "no module was produced"
    data = record.get("bytes")
    if not data and record.get("path"):
        try:
            data = Path(record["path"]).read_bytes()
        except OSError as exc:
            return None, f"module file unreadable: {type(exc).__name__}"
    if not data:
        return None, "module record has no image bytes"
    try:
        return load_image(data).rgb, ""
    except ValueError as exc:
        return None, str(exc)


def _score_module(module: Dict[str, Any], record: Optional[Dict[str, Any]], *,
                  ocr: Optional[Callable[[np.ndarray], Dict[str, Any]]],
                  ocr_error: str = "") -> Dict[str, Any]:
    rgb, error = _module_image(record)
    present = _present_verdict(rgb, error)
    result: Dict[str, Any] = {
        "id": module["id"], "kind": module["kind"],
        "declared_size": [module["width"], module["height"]],
        "measured_size": None,
        "product_required": bool(module["product_in_frame"]),
        "checks": {"present": present},
        "failed_checks": [], "score": 0.0, "passed": False,
        "cannot_verify": False, "cannot_verify_reason": None,
    }
    if record is not None and record.get("cannot_verify"):
        result["cannot_verify"] = True
        result["cannot_verify_reason"] = record.get("cannot_verify_reason")
    if rgb is not None:
        loaded_size = _size_verdict(load_image(record["bytes"] if record.get("bytes")
                                             else Path(record["path"]).read_bytes()),
                                    module)
        result["checks"]["size"] = loaded_size
        result["measured_size"] = loaded_size["measured_size"]
        text = {"ok": False, "skipped": False, "cannot_verify": True,
                "detail": ocr_error or "OCR did not run"}
        if ocr is not None and not ocr_error:
            try:
                raw = ocr(rgb)
                ocr_text = str((raw or {}).get("text") or "")
            except Exception as exc:  # noqa: BLE001 - unreadable text is a failure
                text = {"ok": False, "skipped": False, "cannot_verify": True,
                        "detail": f"OCR raised {type(exc).__name__}: {exc}"}
            else:
                text = _text_verdict(module["text_required"], ocr_text,
                                     module["min_text_recall"])
        result["checks"]["text"] = text
        if module["product_in_frame"]:
            placement = (record or {}).get("product_box")
            cutout = (record or {}).get("cutout")
            if cutout is None:
                product = missing_cutout_verdict(
                    "the module records no cutout for its product")
            else:
                product = check_composite(rgb, cutout, placement=placement)
            result["checks"]["product"] = product
    elif module["product_in_frame"]:
        result["checks"]["product"] = missing_cutout_verdict(
            "the module rendered nothing, so the product cannot be verified")

    weights = {"present": 0.10, "size": 0.15, "text": 0.40}
    if module["product_in_frame"]:
        weights["product"] = 0.35
    else:
        weights["text"] = 0.75
    graded = [name for name, check in result["checks"].items()
              if not check.get("skipped") and weights.get(name, 0) > 0]
    denominator = sum(weights[name] for name in graded)
    earned = sum(weights[name] * (1.0 if result["checks"][name]["ok"] else 0.0)
                 for name in graded)
    result["score"] = round(100.0 * earned / denominator, 1) if denominator else 0.0
    result["failed_checks"] = [name for name, check in result["checks"].items()
                               if not check.get("skipped") and not check["ok"]]
    result["passed"] = (not result["cannot_verify"] and not result["failed_checks"]
                        and bool(module["text_required"]))
    return result


def score_aplus_page(brief: Dict[str, Any], modules: Sequence[Dict[str, Any]], *,
                     page_bytes: Optional[bytes] = None,
                     ocr: Optional[Callable[[np.ndarray], Dict[str, Any]]] = None,
                     min_text_recall: Optional[float] = None
                     ) -> Dict[str, Any]:
    """Score an A+ page: count, order, module size, copy per module, product region.

    `modules` are the produced module records in production order, each with
    `id` and either `bytes` or `path`, and optionally `product_box`/`cutout`/
    `cannot_verify`. `ocr` takes a decoded RGB array and returns `{"text": ...}`;
    it defaults to the local OCR engine. A module that rendered nothing fails the
    page; it is never skipped.
    """
    declared = module_grid(brief)
    declared_ids = [row["id"] for row in declared]
    produced_ids = [str(row.get("id")) for row in modules]
    count_ok = len(produced_ids) == len(declared_ids)
    order_ok = produced_ids == declared_ids

    ocr_fn = ocr
    ocr_error = ""
    if ocr_fn is None:
        ocr_fn = reference_check.ocr_text

    page_verdict: Dict[str, Any] = {"ok": False, "skipped": False,
                                    "cannot_verify": True,
                                    "detail": "no page artefact was supplied"}
    if page_bytes:
        try:
            page_loaded = load_image(page_bytes)
        except ValueError as exc:
            page_verdict = {"ok": False, "skipped": False, "cannot_verify": True,
                            "detail": f"page artefact unreadable: {exc}"}
        else:
            expected_h = declared_page_height(brief)
            expected_w = int((brief.get("page") or {}).get("width", DEFAULT_PAGE_WIDTH))
            ok = page_loaded.width == expected_w and page_loaded.height == expected_h
            page_verdict = {
                "ok": ok, "skipped": False, "cannot_verify": False,
                "detail": (f"page {page_loaded.width}x{page_loaded.height} vs declared "
                           f"{expected_w}x{expected_h}"),
                "measured_size": [page_loaded.width, page_loaded.height],
                "declared_size": [expected_w, expected_h],
            }

    module_results: List[Dict[str, Any]] = []
    by_id = {str(row.get("id")): row for row in modules}
    for module in declared:
        if min_text_recall is not None:
            module = dict(module, min_text_recall=float(min_text_recall))
        record = by_id.get(module["id"])
        module_results.append(_score_module(module, record, ocr=ocr_fn,
                                            ocr_error=ocr_error))

    failed_modules = [row["id"] for row in module_results if not row["passed"]]
    reasons: List[str] = []
    if not count_ok:
        reasons.append(f"module count {len(produced_ids)} vs declared {len(declared_ids)}")
    if not order_ok:
        reasons.append(f"module order {produced_ids} vs declared {declared_ids}")
    if not page_verdict.get("ok"):
        reasons.append(f"page: {page_verdict.get('detail')}")
    for row in module_results:
        if row.get("cannot_verify"):
            reasons.append(f"module {row['id']}: cannot verify — "
                           f"{row.get('cannot_verify_reason')}")
            continue
        for name in row["failed_checks"]:
            detail = (row["checks"].get(name) or {}).get("detail") or ""
            reasons.append(f"module {row['id']}: {name} failed — {detail}")

    scores = [float(row["score"]) for row in module_results]
    passed = (count_ok and order_ok and bool(page_verdict.get("ok"))
              and not failed_modules and not any(row.get("cannot_verify")
                                                 for row in module_results))
    return {
        "brief_id": brief.get("id"),
        "content_type": brief.get("content_type"),
        "source_mode": brief_mode(brief),
        "fidelity": brief_fidelity(brief),
        "declared_modules": declared_ids,
        "produced_modules": produced_ids,
        "module_count": {"declared": len(declared_ids), "produced": len(produced_ids),
                         "ok": count_ok},
        "module_order": {"ok": order_ok, "declared": declared_ids,
                         "produced": produced_ids},
        "page": page_verdict,
        "modules": module_results,
        "module_pass_count": sum(1 for row in module_results if row["passed"]),
        "module_count_total": len(module_results),
        "pages": 1,
        "passed": bool(passed),
        "score": round(sum(scores) / len(scores), 1) if scores else 0.0,
        "failed_modules": failed_modules,
        "reasons": reasons,
        "failures": reasons,
    }


__all__ = [
    "APLUS_KEY",
    "CONTENT_TYPES",
    "MIN_APLUS_BRIEFS",
    "declared_page_height",
    "load_aplus_briefs",
    "module_grid",
    "produce_module",
    "produce_page",
    "score_aplus_page",
    "validate_aplus_briefs",
]
