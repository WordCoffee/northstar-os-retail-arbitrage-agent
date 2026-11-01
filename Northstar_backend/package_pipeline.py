"""Complete package generation for pouch, box, bottle and tube.

The existing package designer was pouch-only: it built front/back/side panels and
a doypack dieline, and its mockup used the pouch compositor. This module keeps
that pouch path intact and extends the same contract to the other three formats
using the existing geometry profiles, dieline builder, measured surface and
format compositors:

    spec -> panels -> dieline (SVG/PDF) -> measured-quad mockup -> manifest

It is an orchestrator over existing components, not a second compositor. Every
artefact is deterministic and local; no model is called here.
"""
from __future__ import annotations

import json
import math
import uuid
from io import BytesIO
from pathlib import Path
from typing import Any, Dict, Optional

from PIL import Image

import design_studio_print as dsp
import dieline_art
import format_compositors
import geometry_profiles
import package_art
import package_designs as pdesigns
import pouch_label as pl
import print_prep
import surface_measure
import text_fidelity
from specialists import package_designer as pd
from specialists import panels as pnl

ROOT = Path(__file__).resolve().parent
_ASSETS: Optional[tuple] = None

FORMATS = ("pouch", "box", "bottle", "tube")
DIMS = {
    "pouch": ("width_mm", "height_mm", "gusset_mm"),
    "box": ("width_mm", "depth_mm", "height_mm"),
    "bottle": ("diameter", "height", "label_height", "label_top_offset"),
    "tube": ("diameter", "height"),
}


def _fmt(spec: Dict[str, Any], fmt: Optional[str] = None) -> str:
    value = str(fmt or spec.get("format") or "pouch").strip().lower()
    if value not in FORMATS:
        raise ValueError(f"unknown package format {value!r}; known: {', '.join(FORMATS)}")
    return value


def missing_inputs(spec: Dict[str, Any], fmt: Optional[str] = None) -> list:
    """Required facts, with format-specific dimensions."""
    kind = _fmt(spec, fmt)
    gaps = []
    for key, why in (("title", "the product name exactly as it must appear"),
                     ("weight", "the net weight line"),
                     ("company", "the company name for the back panel"),
                     ("address", "the company address for the back panel"),
                     ("country_of_origin", "the country of origin")):
        if not str(spec.get(key) or "").strip():
            gaps.append({"field": key, "question": why})
    dims = dict(spec.get("dims") or {})
    for key in DIMS[kind]:
        if not float(dims.get(key) or 0) > 0:
            gaps.append({"field": f"dims.{key}", "question": f"{key} is required for a {kind} package"})
    if kind in ("pouch", "box") and not spec.get("ingredients") and not spec.get("supplement_facts"):
        gaps.append({"field": "ingredients", "question": "the ingredient list OR a supplement facts block"})
    return gaps


def _dieline(kind: str, dims: Dict[str, Any]) -> Dict[str, Any]:
    if kind == "pouch":
        params = {k: v for k, v in dims.items()
                  if k in ("width_mm", "height_mm", "gusset_mm", "weld_mm",
                           "top_weld_mm", "zip_offset_mm", "bleed_mm", "safe_mm",
                           "fill_g")}
        build = dsp.build_from_template("doypack", params or None)
    elif kind == "box":
        build = dsp.build_carton(
            "tuck_end", dims["width_mm"], dims["depth_mm"], dims["height_mm"],
            bleed_mm=float(dims.get("bleed_mm") or 3.0))
    elif kind == "bottle":
        # A label wraps the circumference, not the visible diameter. Leave a
        # 3% seam gap; the converter supplies the final seam allowance.
        wrap_width = math.pi * float(dims["diameter"]) * 0.97
        build = dsp.build_label(
            "rounded_rectangle", wrap_width, dims["label_height"],
            bleed_mm=float(dims.get("bleed_mm") or 3.0))
    else:  # tube
        usable = float(dims.get("usable_height_mm")
                       or dims["height"] - 2 * float(dims.get("crimp_mm") or 8.0))
        wrap_width = math.pi * float(dims["diameter"]) * 0.97
        build = dsp.build_label(
            "rounded_rectangle", wrap_width, usable,
            bleed_mm=float(dims.get("bleed_mm") or 3.0))
    return {
        "svg": dsp.render_svg(build),
        "pdf": dsp.render_pdf(build),
        "title": build.get("title"),
        "flat_width_mm": build.get("width_mm"),
        "flat_height_mm": build.get("height_mm"),
        "meta": build.get("meta") or {},
    }


def _profile_dims(kind: str, dims: Dict[str, Any]) -> Dict[str, Any]:
    """Translate package-spec dimensions to geometry_profiles' field names."""
    if kind == "box":
        return {"width": dims["width_mm"], "depth": dims["depth_mm"],
                "height": dims["height_mm"]}
    if kind == "bottle":
        return {"diameter": dims["diameter"], "height": dims["height"],
                "label_height": dims["label_height"],
                "label_top_offset": dims["label_top_offset"]}
    if kind == "tube":
        return {"diameter": dims["diameter"], "height": dims["height"]}
    if kind == "pouch":
        return {"width": dims["width_mm"], "height": dims["height_mm"],
                "bottom_gusset": dims.get("gusset_mm", 30.0)}
    return dict(dims)


def _mogra_assets() -> tuple:
    """Load the brand lockup and the drawn botanical motif once."""
    global _ASSETS
    if _ASSETS is None:
        logo = pl.load_logo(ROOT / "assets" / "brand" / "mogra_logo.png")
        raw = Image.open(ROOT / "assets" / "brand" / "hericium_source.jpg").convert("RGB")
        motif = dieline_art.extract_ink_motif(raw, [198, 400, 438, 668])
        _ASSETS = (logo, motif)
    return _ASSETS


def _face_mm(kind: str, dims: Dict[str, Any]) -> tuple:
    """Width/height of the actual printable face in millimetres."""
    if kind == "pouch":
        return (float(dims["width_mm"]),
                max(20.0, float(dims["height_mm"]) - 12.0
                    - float(dims.get("gusset_mm") or 30.0)))
    if kind == "box":
        return float(dims["width_mm"]), float(dims["height_mm"])
    if kind == "bottle":
        return (max(10.0, float(dims["diameter"]) * 0.75),
                float(dims["label_height"]))
    usable = (float(dims["height"]) - 2 * float(dims.get("crimp_mm") or 8.0)
              - float(dims.get("cap_mm") or 20.0))
    return float(dims["diameter"]), max(20.0, usable)


def _target_ratio(kind: str, dims: Dict[str, Any]) -> float:
    width, height = _face_mm(kind, dims)
    return height / max(1.0, width)


def _fit_panel(img: Image.Image, ratio: float) -> Image.Image:
    """Crop/extend a design to the target face ratio without stretching type."""
    if ratio <= 0:
        return img
    native = img.width / max(1, img.height)
    if abs(native - ratio) < 0.015:
        return img
    if native > ratio:
        width = max(2, int(round(img.height * ratio)))
        left = max(0, (img.width - width) // 2)
        return img.crop((left, 0, left + width, img.height))
    width = max(2, int(round(img.height * ratio)))
    background = img.getpixel((0, 0))
    canvas = Image.new("RGB", (width, img.height), background)
    canvas.paste(img, (max(0, (width - img.width) // 2), 0))
    return canvas


def _front_panel(kind: str, spec: Dict[str, Any], dims: Dict[str, Any],
                 logo_path: Optional[Path]) -> Image.Image:
    """Use a catalogue design when asked; otherwise render dynamic brand art."""
    logo = pl.load_logo(Path(logo_path)) if logo_path else None
    motif = None
    brand = str(spec.get("brand") or "").strip().upper()
    theme = str(spec.get("theme") or "forest").strip().lower()
    # The supplied Mogra master carries a cream plaque. On a light stock that
    # reads as a label; on a dark ground it becomes a white sticker. Use it only
    # on light themes, or when the caller supplied their own transparent logo.
    if logo is None and brand.startswith("MOGRA") and theme in ("kraft", "bone", "sage"):
        logo, motif = _mogra_assets()
    elif logo is None and spec.get("motif"):
        _, motif = _mogra_assets()
    key = str(spec.get("design") or "").strip().lower()
    if key and key in pdesigns.BAG_FRONTS:
        catalog_logo, catalog_motif = _mogra_assets()
        front = pdesigns.BAG_FRONTS[key](catalog_logo, catalog_motif)
        front = pdesigns.apply_paper(front, seed=(sum(key.encode()) % 9001))
        front = _fit_panel(front, _target_ratio(kind, dims))
    else:
        width_mm, height_mm = _face_mm(kind, dims)
        front = package_art.render_front(
            spec, logo=logo, motif=motif,
            width_mm=width_mm, height_mm=height_mm)
    # `panels.panel_sheet` uses the image itself as a paste mask, so the front
    # must carry an explicit opaque alpha channel (catalogue art is RGB).
    return front.convert("RGBA")


def _mockup(kind: str, plate_path: Path, front: Image.Image, dims: Dict[str, Any],
            out_dir: Optional[Path], spec: Optional[Dict[str, Any]] = None,
            logo_path: Optional[Path] = None) -> Dict[str, Any]:
    plate_bytes = Path(plate_path).read_bytes()
    plate = Image.open(BytesIO(plate_bytes)).convert("RGB")
    if kind == "pouch":
        payload = dict(spec or {})
        composed = pl.compose(
            Path(plate_path), title=str(payload.get("title") or ""),
            subtitle=str(payload.get("subtitle") or ""),
            weight=str(payload.get("weight") or ""),
            bullets=[str(c) for c in (payload.get("claims") or [])][:4],
            logo_path=logo_path,
            icons=[str(i) for i in (payload.get("icons") or [])][:4],
            label_panel=front)
        measured = dict(composed.get("measured") or {})
        measured.update({"kind": "pouch", "method": "pouch-label-panel",
                         "confidence": 1.0 if not composed.get("geom_residual_px")
                         else max(0.0, 1.0 - float(composed["geom_residual_px"]) / 20.0)})
        composed_out = {"bytes": composed["bytes"]}
    else:
        wrap = 0.75 if kind == "bottle" else 0.92
        measured = surface_measure.measure_surface(plate, kind, wrap_fraction=wrap)
        kwargs: Dict[str, Any] = {}
        if kind == "bottle":
            kwargs["wrap_fraction"] = wrap
        elif kind == "tube":
            kwargs["crimp_top"] = 0
            kwargs["crimp_bottom"] = 0
        composed_out = format_compositors.composite(kind, plate_bytes, front,
                                                    measured["quad"], **kwargs)
    out: Dict[str, Any] = {
        "bytes": composed_out["bytes"],
        "quad": measured["quad"],
        "method": measured.get("method"),
        "geom_residual_px": measured.get("geom_residual_px"),
        "confidence": measured.get("confidence"),
        "surface": {k: measured.get(k) for k in
                    ("kind", "band", "taper", "crimp_top_px", "crimp_bottom_px",
                     "width_px", "warnings")},
    }
    if out_dir is not None:
        profile = geometry_profiles.profile(kind, **_profile_dims(kind, dims))
        sidecar = print_prep.emit_sidecar(
            Path(out_dir) / f"package_{kind}_dieline.json",
            kind=kind, profile=profile, image_size=plate.size, quad=measured["quad"],
            method=measured.get("method") or "", residual_px=measured.get("geom_residual_px"),
            source_plate=plate_path)
        out["sidecar"] = str(sidecar.get("asset", {}).get("image") or "")
        out["print_ready"] = sidecar.get("print_ready")
        out["dpi"] = sidecar.get("dpi", {}).get("worst")
    return out


def build_package(spec: Dict[str, Any], *, format: Optional[str] = None,
                  plate_path: Optional[Path] = None,
                  logo_path: Optional[Path] = None,
                  out_dir: Optional[Path] = None,
                  allow_incomplete: bool = False) -> Dict[str, Any]:
    """Build panels, dieline and a measured mockup for one package format."""
    kind = _fmt(spec, format)
    gaps = missing_inputs(spec, kind)
    if gaps and not allow_incomplete:
        return {"ok": False, "status": "needs_input", "format": kind,
                "summary": f"{len(gaps)} thing(s) must come from you first.",
                "questions": gaps, "assets": []}

    dims = dict(spec.get("dims") or {})
    title = str(spec.get("title") or "").strip()
    subtitle = str(spec.get("subtitle") or "").strip()
    weight = str(spec.get("weight") or "").strip()
    claims = [str(c) for c in (spec.get("claims") or [])][:4]
    icons = [str(i) for i in (spec.get("icons") or [])][:4]

    front = _front_panel(kind, spec, dims, logo_path)
    face_w, face_h = _face_mm(kind, dims)
    # The panel artwork is the print asset; render it at 300 dpi for the real
    # face. The mockup is a preview and may have less resolution than the art.
    panel_w = max(300, round(face_w * 300.0 / 25.4))
    panel_h = max(300, round(face_h * 300.0 / 25.4))
    side_w = max(220, round(face_w * 0.34 * 300.0 / 25.4))
    back = pnl.render_back_panel(
        size=(panel_w, panel_h),
        title=title,
        ingredients=[str(i) for i in (spec.get("ingredients") or [])],
        supplement_facts=[str(i) for i in (spec.get("supplement_facts") or [])],
        suggested_use=str(spec.get("suggested_use") or "") or None,
        warnings=[str(w) for w in (spec.get("warnings") or [])],
        company=str(spec.get("company") or "") or None,
        address=str(spec.get("address") or "") or None,
        country_of_origin=str(spec.get("country_of_origin") or "") or None,
        lot_code=str(spec.get("lot_code") or "") or None,
    )
    side = pnl.render_side_panel(
        size=(side_w, panel_h),
        title=title, subtitle=subtitle, weight=weight, claims=claims, icons=icons,
        company=(spec.get("company") or None),
    )
    sheet = pnl.panel_sheet({"front": front, "back": back, "side": side})
    dieline = _dieline(kind, dims)
    result: Dict[str, Any] = {
        "ok": True,
        "status": "built",
        "format": kind,
        "summary": (f"Built a complete {kind} package: designed front, back, side, "
                    f"a measured mockup and a print dieline (SVG + PDF). "
                    "Draft geometry — confirm with your converter before print."),
        "questions": gaps,
        "panels": {"front": pnl.png_bytes(front), "back": pnl.png_bytes(back),
                   "side": pnl.png_bytes(side), "sheet": pnl.png_bytes(sheet)},
        "dieline": dieline,
        "validation": pnl.validate_panels(spec),
        "design": {"theme": str(spec.get("theme") or "forest"),
                   "catalog": str(spec.get("design") or "") or None},
        "spec": {k: spec.get(k) for k in (
            "format", "brand", "theme", "design", "title", "subtitle", "weight",
            "servings", "claims", "icons", "ingredients", "supplement_facts",
            "suggested_use", "warnings", "company", "address",
            "country_of_origin", "lot_code", "organic_certified", "dims")
            if spec.get(k) not in (None, "", [])},
        "artwork": {
            "face_mm": [round(face_w, 2), round(face_h, 2)],
            "panel_px": [panel_w, panel_h],
            "dpi": round(min(panel_w / (face_w / 25.4),
                             panel_h / (face_h / 25.4)), 2),
        },
        "print_ready": (panel_w / (face_w / 25.4) >= 299.5
                        and panel_h / (face_h / 25.4) >= 299.5),
        "assets": [],
    }
    if plate_path and Path(plate_path).is_file():
        try:
            mock = _mockup(kind, Path(plate_path), front, dims, out_dir,
                           spec=spec, logo_path=logo_path)
            result["panels"]["mockup"] = mock["bytes"]
            result["mockup_quad"] = mock["quad"]
            result["mockup_method"] = mock["method"]
            result["geom_residual_px"] = mock["geom_residual_px"]
            result["surface"] = mock["surface"]
            result["dieline_sidecar"] = mock.get("sidecar")
            # The sidecar measures the rendered preview plate; it is not the
            # resolution of the 300 dpi label artwork above.
            result["mockup_print_ready"] = mock.get("print_ready")
            result["mockup_dpi"] = mock.get("dpi")
            result["quality"] = text_fidelity.verify_asset_text(
                mock["bytes"], brief=f"{title} {subtitle}", text_safe=True)
        except Exception as exc:  # noqa: BLE001 - panels/dieline must survive
            result.setdefault("warnings", []).append(f"mockup skipped: {exc}")
    return result


def save_package(result: Dict[str, Any], out_dir: Path) -> Dict[str, Any]:
    """Write panels/dieline plus a manifest; returns the file names."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    saved = pd.save_package(result, out_dir)
    files = dict(saved.get("files") or {})
    kind = str(result.get("format") or "pouch")
    manifest = {
        "schema": "northstar.package.v1",
        "format": kind,
        "status": result.get("status"),
        "dieline": {k: v for k, v in (result.get("dieline") or {}).items()
                    if k in ("title", "flat_width_mm", "flat_height_mm", "meta")},
        "spec": result.get("spec"),
        "design": result.get("design"),
        "artwork": result.get("artwork"),
        "print_ready": result.get("print_ready"),
        "dpi": (result.get("artwork") or {}).get("dpi"),
        "mockup_quad": result.get("mockup_quad"),
        "mockup_method": result.get("mockup_method"),
        "geom_residual_px": result.get("geom_residual_px"),
        "surface": result.get("surface"),
        "mockup_print_ready": result.get("mockup_print_ready"),
        "mockup_dpi": result.get("mockup_dpi"),
        "quality": result.get("quality"),
        "warnings": result.get("warnings") or [],
        "files": files,
    }
    path = out_dir / f"package_{kind}_manifest.json"
    path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    files["manifest"] = path.name
    return files


__all__ = ["FORMATS", "build_package", "save_package", "missing_inputs"]
