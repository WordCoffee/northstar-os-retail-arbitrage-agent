"""Product pictures: a designed panel on a photographed package, gated.

This is the lane the owner asked for on 2026-11-03: a *product picture* of a
6 oz stand-up pouch — front and back — carrying the designed panels in correct
perspective, produced by the service rather than by a human at a shell prompt.

The division of labour is deliberate and is what makes the copy exact:

* the image model (FLUX 3, local ComfyUI) supplies the PHOTOGRAPH: a blank,
  unprinted pouch on a studio sweep. It runs through the text-safe lane, so any
  lettering it invents is detected, retried, reconstructed, or refused;
* the panels come from `mogra_label_art` at print resolution — real fonts,
  drawn artwork, OCR-checkable text, never diffusion;
* `find_panel_quad` measures the package face in the plate and refuses a plate
  that has no package in it;
* `composite_panel_onto_quad` warps the panel onto that face with a homography
  and the surface-realism pass, painting nothing outside the face;
* `assert_legible` OCRs the result and refuses it when the wordmark or net
  weight cannot be read or the type is soft.

A failure returns the reason and the rejected candidate instead of a picture
that looks finished. Local compute only. No provider call, no network, no cost.
"""
from __future__ import annotations

import io
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Optional, Sequence

from PIL import Image

import mockup_compositor as mc
import mockup_quality as mq
import brand_art as art
import text_fidelity as tf

ROOT = Path(__file__).resolve().parents[1]
RENDERS = ROOT / "renders"

PLATE_BRIEFS: Dict[str, str] = {
    "front": (
        "a photograph of one blank unprinted kraft stand-up pouch standing upright "
        "on a pale seamless studio sweep, its front face square to the camera, soft "
        "diffused key light from the upper left, a gentle contact shadow, subtle "
        "paper grain, photoreal commercial product photography, sharp focus on the "
        "pouch"),
    "back": (
        "a photograph of one blank unprinted kraft stand-up pouch standing upright "
        "on a pale seamless studio sweep, turned around so its back face is square "
        "to the camera, soft diffused key light from the upper left, a gentle "
        "contact shadow, subtle paper grain, photoreal commercial product "
        "photography, sharp focus on the pouch"),
}

#: The folding-carton form. A gift box is not a pouch: the plate must be a box,
#: or the measured face and the warp would print a box design onto a bag.
BOX_PLATE_BRIEFS: Dict[str, str] = {
    "front": (
        "a photograph of one blank unprinted slim folding gift box standing upright "
        "on a pale seamless studio sweep, its front face square to the camera, matte "
        "card stock, a gentle contact shadow, soft diffused key light from the upper "
        "left, photoreal commercial product photography, sharp focus on the box"),
    "back": (
        "a photograph of one blank unprinted slim folding gift box standing upright "
        "on a pale seamless studio sweep, turned around so its back face is square "
        "to the camera, matte card stock, a gentle contact shadow, soft diffused key "
        "light from the upper left, photoreal commercial product photography, sharp "
        "focus on the box"),
}

#: Print-area insets per form. The pouch insets skip the top weld and the base
#: gusset; a folding carton has neither, so its panel runs near the trim.
FORM_PLATE_BRIEFS: Dict[str, Dict[str, str]] = {
    art.POUCH: PLATE_BRIEFS,
    art.GIFT_BOX: BOX_PLATE_BRIEFS,
}
FORM_INSETS: Dict[str, Dict[str, float]] = {
    art.POUCH: {"inset_x": 0.075, "inset_top": 0.20, "inset_bottom": 0.10},
    art.GIFT_BOX: {"inset_x": 0.055, "inset_top": 0.055, "inset_bottom": 0.055},
}

#: The print should follow the pouch surface, not sit on it as a sticker. Measured
#: on the first real FLUX plate: the fold-shadow recipe from `pouch_label` (0.35 at
#: a 0.05 threshold) treated ordinary kraft shading as a crease and multiplied the
#: cream label down to 169/255 — three quarters of its value. These are tuned so a
#: crease darkens the ink and a lit face keeps its stock colour.
REALISM: Dict[str, float] = {
    "displacement_k": 1.5, "softlight_strength": 0.20, "specular_cap": 0.0,
    "grain_sync": 0.18, "tonal_match": 0.10, "fold_shadow": 0.12,
    "fold_threshold": 0.10, "ao_rim_px": 4, "ao_strength": 0.03,
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def resolve_out_dir(out_dir: Optional[str], *, base: Optional[str] = None) -> Path:
    """Resolve a requested output directory, confined to a base (renders/).

    ``base`` exists for tests, which must write into a temporary directory; the
    API never passes it, so a request cannot write outside ``renders/``.
    """
    base_dir = (Path(base) if base else RENDERS).resolve()
    target = Path(out_dir) if out_dir else (base_dir / "mogra_lions_mane")
    if not target.is_absolute():
        # A caller says `--out renders/mogra_lions_mane`, i.e. repo-relative.
        # Resolving that against renders/ produced renders/renders/... .
        target = ROOT / target
    target = target.resolve()
    if target != base_dir and base_dir not in target.parents:
        raise ValueError(f"out_dir must be inside {base_dir}, got {target}")
    return target


def plate_brief(face: str, form: str = art.POUCH) -> str:
    briefs = FORM_PLATE_BRIEFS.get(form)
    if briefs is None:
        raise ValueError(f"unknown form {form!r}; known: {', '.join(FORM_PLATE_BRIEFS)}")
    if face not in briefs:
        raise ValueError(f"unknown face {face!r}; known: front, back")
    return briefs[face]


def _guarded_plate(brief: str, *, width: int, height: int, tier: str,
                   seed: Optional[int], reference: Optional[bytes] = None
                   ) -> Dict[str, Any]:
    """Render a plate; never a raw model call.

    Text-safe is the default: the model is asked for a blank package and the
    lettering is drawn by the vector compositor. When a real product photo is
    supplied the plate is reference-conditioned instead - identity comes from
    the photo, and the designed panel still replaces the label area afterwards.
    A reference plate is expected to contain lettering (the reference has it),
    so it is not rejected by the text-free check; the composite + legibility
    gate is what decides.
    """
    import studio_generation as sg

    if reference is not None:
        out = sg.generate_reference(brief, reference, width=width, height=height,
                                    tier=tier, seed=seed)
        return {
            "bytes": out["bytes"], "seed": out.get("seed"), "model": out.get("model"),
            "width": out.get("width"), "height": out.get("height"),
            "duration_seconds": out.get("duration_seconds"),
            "used_brief": brief, "text_fidelity": None, "contains_text": None,
            "mode": "reference",
        }

    def _render(prompt: str) -> Dict[str, Any]:
        return sg.generate_image(prompt, width=width, height=height, tier=tier,
                                 seed=seed)

    result = tf.render_with_text_guard(render_fn=_render, brief=brief, text_safe=True)
    check = (result.get("text_fidelity") or {}).get("check") or {}
    return {
        "bytes": result["out"]["bytes"],
        "seed": result["out"].get("seed"),
        "model": result["out"].get("model"),
        "width": result["out"].get("width"),
        "height": result["out"].get("height"),
        "duration_seconds": result["out"].get("duration_seconds"),
        "used_brief": result.get("used_brief"),
        "text_fidelity": result.get("text_fidelity"),
        "contains_text": check.get("contains_text"),
        "mode": "text_safe",
    }


def compose_face(plate: Image.Image, design: Dict[str, Any], face: str, *,
                 shading: float = 0.45, feather: Optional[float] = 2.2,
                 form: Optional[str] = None, quad: Optional[Sequence] = None,
                 units: int = 1) -> Dict[str, Any]:
    """Measure the face(s), warp the declared panel onto each, OCR the result.

    Returns ``{image, quad, quads, units_found, panel, legibility, gate_ok, reason}``.
    A photograph with no measurable package raises ``ValueError('plate_face_not_found:
    …')``; with ``units > 1`` a plate that shows fewer units than asked for raises
    ``ValueError('units_not_found: …')`` — a bundle that shows one unit is not a
    bundle, and printing one panel on one of three boxes is a false picture. A
    picture whose copy cannot be read returns ``gate_ok=False`` with the reason
    instead of passing silently. The print-area insets come from the design's form,
    so a carton face is not inset like a pouch weld.
    """
    form = form or art.form_of(design)
    insets = FORM_INSETS.get(form, FORM_INSETS[art.POUCH])
    if quad is not None:
        quads = [quad]
    else:
        quads = mc.find_panel_quads(plate, count=max(1, int(units)), **insets)
    if len(quads) < max(1, int(units)):
        raise ValueError(
            f"units_not_found: measured {len(quads)} of {int(units)} requested")
    panel = (art.front_panel(design) if face == "front" else art.back_panel(design))

    maps = None
    composed_img = plate.convert("RGB")
    if shading:
        import compositor_realism as cr
        # Measure the surface BEFORE flattening the label target: the crease
        # field is what makes the print ride the pouch. Flatten AFTER, so a
        # specular patch in the photograph cannot wash out the design.
        maps = cr.build_surface_maps(composed_img)
        composed_img, _neutralized = mc.neutralize_quad(composed_img, quads[0], feather=10)
    for index, measured in enumerate(quads):
        if shading and index:
            composed_img, _neutralized = mc.neutralize_quad(composed_img, measured,
                                                            feather=10)
        composed_img = mc.composite_panel_onto_quad(
            composed_img, panel, measured, feather=feather, shading=shading,
            realism=dict(REALISM), maps=maps)

    gate = mq.assert_legible(composed_img, wordmark=str(design["brand"]),
                             net_weight=str(design.get("net_weight") or "") or None)
    return {
        "image": composed_img,
        "quad": [[round(float(x), 2), round(float(y), 2)] for x, y in quads[0]],
        "quads": [[[round(float(x), 2), round(float(y), 2)] for x, y in measured]
                  for measured in quads],
        "units_found": len(quads),
        "panel": panel,
        "legibility": gate,
        "gate_ok": bool(gate.get("ok")),
        "reason": "" if gate.get("ok") else str(gate.get("reason") or "not legible"),
    }


def _reference_for(reference: Any, face: str) -> Optional[bytes]:
    """A single reference applies to every face; a mapping is per face."""
    if reference is None:
        return None
    if isinstance(reference, dict):
        value = reference.get(face)
        return value if isinstance(value, (bytes, bytearray)) else None
    return reference if isinstance(reference, (bytes, bytearray)) else None


def build(design: Optional[Dict[str, Any]] = None, *,
          out_dir: Optional[str] = None,
          faces: Sequence[str] = ("front", "back"),
          width: int = 1024, height: int = 1536, tier: str = "final",
          seed: Optional[int] = None,
          generator: Optional[Callable[..., Dict[str, Any]]] = None,
          shading: float = 0.45,
          out_root: Optional[str] = None,
          reference: Optional[bytes] = None,
          units: int = 1) -> Dict[str, Any]:
    """Render the plates, compose the panels and gate every picture.

    ``generator(brief, width=…, height=…, tier=…, seed=…)`` is injectable so the
    composition and the gate can be tested without the image engine; the default
    is the real FLUX 3 text-safe lane. ``units`` is how many packages the picture
    must show: a bundle plate that measures fewer is refused with the count, never
    captioned as a bundle. The function never claims a pass it did not measure:
    every face carries its own OCR report and refusal reason.
    """
    dsn = design or art.design_for("mogra-lions-mane")
    form = art.form_of(dsn)
    units = max(1, int(units or 1))
    out = resolve_out_dir(out_dir, base=out_root)
    out.mkdir(parents=True, exist_ok=True)
    rejected = out / "_rejected"
    rejected.mkdir(parents=True, exist_ok=True)

    base_seed = int(seed) if seed is not None else None
    records: list = []
    ok = True
    for offset, face in enumerate(faces):
        if face not in ("front", "back"):
            raise ValueError(f"unknown face {face!r}; known: front, back")
        face_seed = None if base_seed is None else base_seed + offset
        brief = plate_brief(face, form)
        plate_record: Dict[str, Any] = {}
        try:
            if generator is not None:
                plate_record = generator(brief, width=width, height=height,
                                         tier=tier, seed=face_seed)
            else:
                plate_record = _guarded_plate(
                    brief, width=width, height=height, tier=tier, seed=face_seed,
                    reference=_reference_for(reference, face))
        except Exception as exc:  # noqa: BLE001 - the engine state is the reason
            records.append({
                "face": face, "ok": False, "stage": "plate",
                "reason": f"image_lane_unavailable: {exc}",
                "brief": brief, "seed": face_seed,
            })
            ok = False
            continue

        plate_bytes = plate_record.get("bytes") or b""
        if not plate_bytes:
            records.append({"face": face, "ok": False, "stage": "plate",
                            "reason": "image_lane_returned_no_bytes",
                            "brief": brief, "seed": face_seed})
            ok = False
            continue
        try:
            plate = Image.open(io.BytesIO(plate_bytes)).convert("RGB")
        except Exception as exc:  # noqa: BLE001
            records.append({"face": face, "ok": False, "stage": "plate",
                            "reason": f"plate_not_decodable: {exc}",
                            "brief": brief, "seed": face_seed})
            ok = False
            continue

        record: Dict[str, Any] = {
            "face": face,
            "brief": brief,
            "used_brief": plate_record.get("used_brief"),
            "seed": plate_record.get("seed", face_seed),
            "model": plate_record.get("model"),
            "plate_mode": plate_record.get("mode"),
            "plate_size": list(plate.size),
            "plate_text": {
                "contains_text": plate_record.get("contains_text"),
                "check": ((plate_record.get("text_fidelity") or {}).get("check") or {}),
                "attempts": (plate_record.get("text_fidelity") or {}).get("attempts"),
                "cleanup": (plate_record.get("text_fidelity") or {}).get("text_cleanup"),
            },
        }

        if plate_record.get("contains_text") is True:
            # A blank pouch must be blank. Painting the label over one face does
            # not remove invented lettering anywhere else in the frame.
            record.update({"ok": False, "stage": "plate",
                           "reason": "plate_has_lettering: the text-safe lane could "
                                     "not produce a lettering-free plate"})
            plate.save(rejected / f"{face}_plate.png")
            records.append(record)
            ok = False
            continue

        try:
            composed = compose_face(plate, dsn, face, shading=shading, form=form,
                                    units=units)
        except ValueError as exc:
            record.update({"ok": False, "stage": "compose", "reason": str(exc)})
            plate.save(rejected / f"{face}_plate.png")
            records.append(record)
            ok = False
            continue

        record.update({
            "quad": composed["quad"],
            "quads": composed["quads"],
            "units_requested": units,
            "units_found": composed["units_found"],
            "legibility": composed["legibility"],
            "gate_ok": composed["gate_ok"],
            "stage": "done" if composed["gate_ok"] else "legibility",
            "reason": composed["reason"],
            "ok": composed["gate_ok"],
        })
        if composed["gate_ok"]:
            path = out / f"product_{face}.png"
            composed["image"].save(path, dpi=(300, 300))
            record["file"] = str(path)
            record["bytes"] = path.stat().st_size
        else:
            rejected.mkdir(parents=True, exist_ok=True)
            path = rejected / f"product_{face}.png"
            composed["image"].save(path, dpi=(300, 300))
            record["rejected_file"] = str(path)
            ok = False
        records.append(record)

    manifest = {
        "schema": "northstar.product_picture.v1",
        "created_at": _now(),
        "ok": bool(ok and all(r.get("ok") for r in records) and len(records) == len(faces)),
        "product": {"brand": dsn["brand"], "product": dsn["product"],
                    "form": form, "net_weight": dsn["net_weight"],
                    "units": units},
        "out_dir": str(out),
        "faces": records,
        "engine": {"lane": "flux3-comfyui", "armed": _engine_armed(),
                   "model": (records[0].get("model") if records else None),
                   "tier": tier},
        "checks": {
            "plate_face_measured": all(bool(r.get("quad")) for r in records),
            "units": {r["face"]: r.get("units_found") for r in records},
            "units_complete": all(r.get("units_found") == units for r in records),
            "panel_gate": {r["face"]: r.get("gate_ok") for r in records},
            "legible": all(r.get("gate_ok") for r in records),
            "files": sorted(p.name for p in out.glob("product_*.png")),
        },
        "note": ("Panel artwork is deterministic vector text; FLUX supplied only the "
                 "photograph. A picture is written only after the OCR gate passes; "
                 "rejected candidates are kept in _rejected/ with their reason."),
    }
    (out / "product_picture_manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def _engine_armed() -> Optional[bool]:
    try:
        import studio_generation as sg
        return bool(sg.engine_status().get("armed"))
    except Exception:  # noqa: BLE001 - status unknown is not a pass
        return None


__all__ = ["build", "compose_face", "plate_brief", "resolve_out_dir",
           "PLATE_BRIEFS", "BOX_PLATE_BRIEFS", "FORM_PLATE_BRIEFS", "FORM_INSETS",
           "RENDERS"]
