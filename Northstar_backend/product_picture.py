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

#: The rigid-cylinder form. A jar, bottle, tube or canister is not a box and not
#: a pouch: the plate must be the round body the wrap-around label belongs on.
#: The plate is also a *measurement target*: a body the same colour as the sweep
#: has no measurable silhouette (measured 2026-11-11: a beige body on a beige
#: sweep left the right-hand edge undetectable), so the brief asks for contrast
#: and for the whole package in frame.
#:
#: A design may name its own body (`plate_subject`), because a mug with a handle
#: and a canister with a lid are not the same object even though both are
#: cylinders: a plate brief that says "cylindrical package" draws a plain tube.
CYLINDER_PLATE_TEMPLATE = (
    "a photograph of one blank unprinted {subject} standing upright on a pale grey "
    "seamless studio sweep, the whole package in frame with its silhouette clearly "
    "separated from the background, {turn}, no lettering and no label, a soft "
    "contact shadow, soft diffused key light from the upper left, photoreal "
    "commercial product photography, sharp focus on the body")

CYLINDER_PLATE_BRIEFS: Dict[str, str] = {
    "front": CYLINDER_PLATE_TEMPLATE.format(
        subject="rigid cylindrical package",
        turn="its front square to the camera"),
    "back": CYLINDER_PLATE_TEMPLATE.format(
        subject="rigid cylindrical package",
        turn="turned around so its back is square to the camera"),
}

#: Print-area insets per form. The pouch insets skip the top weld and the base
#: gusset; a folding carton has neither, so its panel runs near the trim.
FORM_PLATE_BRIEFS: Dict[str, Dict[str, str]] = {
    art.POUCH: PLATE_BRIEFS,
    art.GIFT_BOX: BOX_PLATE_BRIEFS,
    art.CYLINDER: CYLINDER_PLATE_BRIEFS,
}
FORM_INSETS: Dict[str, Dict[str, float]] = {
    art.POUCH: {"inset_x": 0.075, "inset_top": 0.20, "inset_bottom": 0.10},
    art.GIFT_BOX: {"inset_x": 0.055, "inset_top": 0.055, "inset_bottom": 0.055},
    # A cylinder's printable band sits below the shoulder/cap and above the base
    # curve, and runs nearly to the silhouette's sides: the label wraps, so the
    # side inset is small while the top inset carries the shoulder and the cap.
    art.CYLINDER: {"inset_x": 0.03, "inset_top": 0.26, "inset_bottom": 0.10},
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


def _shadow_phrase(brief: str, shadow: bool) -> str:
    """Ask for a contact shadow, or ask for its absence, in the same sentence position.

    D-021 (measured 2026-11-11): the plate prompts asked the model for "a gentle contact
    shadow" on every brief, including main images, where the shadow is exactly what the
    picture must not have. The plate is where it has to be prevented — once the cutout
    keeps it, the silhouette contains it and no downstream check can see it.
    """
    if shadow:
        return brief
    if "a gentle contact shadow" in brief:
        return brief.replace("a gentle contact shadow",
                             "even shadowless light, no shadow and no cast shadow")
    if "a soft contact shadow under each" in brief:
        return brief.replace("a soft contact shadow under each",
                             "no shadow and no cast shadow under any of them")
    if "a soft contact shadow" in brief:
        return brief.replace("a soft contact shadow",
                             "even shadowless light, no shadow and no cast shadow")
    return brief


def plate_brief(face: str, form: str = art.POUCH,
                design: Optional[Dict[str, Any]] = None,
                units: int = 1, shadow: bool = True) -> str:
    briefs = FORM_PLATE_BRIEFS.get(form)
    if briefs is None:
        raise ValueError(f"unknown form {form!r}; known: {', '.join(FORM_PLATE_BRIEFS)}")
    if face not in briefs:
        raise ValueError(f"unknown face {face!r}; known: front, back")
    subject = str((design or {}).get("plate_subject") or "").strip()
    if units and int(units) > 1:
        # A bundle plate must SHOW the units: a photograph of one package measured
        # against a three-unit request is refused (`units_not_found`), so the brief
        # asks for the bundle rather than letting the measurement fail.
        count = int(units)
        word = {2: "two", 3: "three", 4: "four"}.get(count, str(count))
        base = subject or "rigid cylindrical package" if form == art.CYLINDER else (
            "slim folding gift box" if form == art.GIFT_BOX else "kraft stand-up pouch")
        return _shadow_phrase(
            (f"a photograph of {word} identical blank unprinted {base}s standing "
             f"side by side in a row on a pale grey seamless studio sweep, every "
             f"package in frame and separated from its neighbours, no lettering and "
             f"no label, a soft contact shadow under each, soft diffused key light "
             f"from the upper left, photoreal commercial product photography, sharp "
             f"focus on the packages"), shadow)
    if subject and form == art.CYLINDER:
        # A design that names its own body gets a plate of that object; a plain
        # cylinder is only the default. Without this a mug was drawn as a tube.
        return _shadow_phrase(CYLINDER_PLATE_TEMPLATE.format(
            subject=subject,
            turn=("its front square to the camera" if face == "front" else
                  "turned around so its back is square to the camera")), shadow)
    return _shadow_phrase(briefs[face], shadow)


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


def _compose_cylinder(plate: Image.Image, design: Dict[str, Any], face: str,
                      insets: Dict[str, float], units: int,
                      *, shading: float) -> Dict[str, Any]:
    """Warp a wrap-around label onto each measured cylinder body, then gate it.

    A cylinder has no four-corner face: the label wraps the visible half of the
    tube. The label also has a *real size* — `face_mm` declares the visible-half
    width and the height — so the band is measured, not stretched: the body's
    measured width sets the picture's px-per-mm, the declared label height gives
    the band's height in pixels, and the label is centred on the body's printable
    area. A label that is taller than the body is refused by name rather than
    squeezed onto it.

    The body itself is measured by difference from the plate's own background
    (`find_cylinder_bands`), because chroma segmentation measured a patch of
    shadow on the first real FLUX plate of a beige cylinder on a beige sweep.

    The panel is drawn at the band's own pixel size, so its copy lands at the
    resolution the picture actually has instead of being resampled twice.
    """
    composed_img = plate.convert("RGB")
    width_mm, height_mm = art.face_mm(design, face)
    bodies = mc.find_cylinder_bands(plate, count=max(1, int(units)))
    bands: list = []
    panels: list = []
    for body in bodies:
        bx0, by0, bx1, by1 = body
        body_w = bx1 - bx0
        body_h = by1 - by0
        # the printable area: below the shoulder/cap and above the base curve,
        # and never to the very silhouette edge (the label wraps inside it)
        px0 = bx0 + body_w * float(insets.get("inset_x", 0.03))
        px1 = bx1 - body_w * float(insets.get("inset_x", 0.03))
        py0 = by0 + body_h * float(insets.get("inset_top", 0.26))
        py1 = by1 - body_h * float(insets.get("inset_bottom", 0.10))
        px_per_mm = (px1 - px0) / max(0.1, float(width_mm))
        label_h = float(height_mm) * px_per_mm
        if label_h > (py1 - py0):
            raise ValueError(
                f"label_too_tall_for_body: the declared label is {height_mm:.0f} mm "
                f"({label_h:.0f} px at this scale) and the printable body is "
                f"{py1 - py0:.0f} px tall")
        centre = (py0 + py1) / 2.0
        band = [px0, centre - label_h / 2.0, px1, centre + label_h / 2.0]
        bands.append(band)
        size = (max(64, int(band[2] - band[0])), max(64, int(band[3] - band[1])))
        panel = (art.front_panel(design, size=size) if face == "front"
                 else art.back_panel(design, size=size))
        panels.append(panel)
        composed_img = mc.warp_cylinder(composed_img, panel, band,
                                        shading=max(0.0, min(1.0, float(shading))))

    gate = mq.assert_legible(composed_img, wordmark=str(design["brand"]),
                             net_weight=str(design.get("net_weight") or "") or None)
    return {
        "image": composed_img,
        "quad": [[round(x, 2), round(y, 2)] for x, y in
                 ((bands[0][0], bands[0][1]), (bands[0][2], bands[0][1]),
                  (bands[0][2], bands[0][3]), (bands[0][0], bands[0][3]))],
        "quads": [[[round(x, 2), round(y, 2)] for x, y in
                   ((band[0], band[1]), (band[2], band[1]),
                    (band[2], band[3]), (band[0], band[3]))] for band in bands],
        "bands": [[round(value, 2) for value in band] for band in bands],
        "units_found": len(bands),
        "panel": panels[0],
        "legibility": gate,
        "gate_ok": bool(gate.get("ok")),
        "reason": "" if gate.get("ok") else str(gate.get("reason") or "not legible"),
    }


def _place_on_flat(composed: Image.Image, *, value: int = 255,
                   fill: float = 0.80, method: str = "background_distance",
                   matte: str = "auto", matte_url: Optional[str] = None
                   ) -> Dict[str, Any]:
    """Cut the product out of its plate and stand it on a flat white canvas.

    A main-image brief is not a photograph of a product on a sweep: it is the
    product alone on 255 white, at least 85 % of the frame's linear fill. The app
    composited the label onto the photograph and stopped there, so every
    white-background brief failed `background` and `alpha_matte` on a real plate
    (measured 2026-11-11: ST-001 at 70). This does the last step of the product
    picture: cut, scale, centre, paste.

    ``matte`` chooses the instrument (D-017):

    * ``"birefnet"`` — a real matte through the media lane. It **raises** when the
      lane cannot supply one; it never degrades into a colour cut quietly.
    * ``"auto"`` — the real matte when the lane answers, otherwise the colour cut,
      with the fallback and its reason recorded on the picture.
    * ``"none"`` — the colour cut alone. A plate's opaque contact shadow then
      survives, which is D-017; use it only where that is deliberate.
    """
    import time

    import numpy as np

    import product_cutout as pc

    rgb = np.asarray(composed.convert("RGB"))
    wanted = str(matte or "auto").strip().lower()
    if wanted not in ("auto", "birefnet", "none"):
        raise ValueError(f"unknown matte {matte!r}; known: auto, birefnet, none")
    matte_record: Dict[str, Any] = {"requested": wanted, "method": "none",
                                    "seconds": 0.0, "rejected_px": 0, "reason": ""}
    alpha = None
    if wanted in ("auto", "birefnet"):
        started = time.perf_counter()
        try:
            alpha = pc.matte_alpha(rgb, **({"url": matte_url} if matte_url else {}))
            matte_record.update(method="birefnet",
                                seconds=round(time.perf_counter() - started, 2))
        except pc.MatteUnavailable as exc:
            matte_record["reason"] = str(exc)
            if wanted == "birefnet":
                raise
    if alpha is None:
        try:
            alpha = pc.cutout(rgb, method).alpha
        except Exception:  # noqa: BLE001 - a cutout that cannot run is stated, not swapped
            alpha = pc.cutout(rgb, "grabcut").alpha
            method = "grabcut"
        matte_record["reason"] = matte_record["reason"] or "no real matte was requested"
    mask = np.asarray(alpha, dtype=np.uint8)
    if matte_record["method"] == "birefnet":
        # The measured statement of what the matte bought: the pixels the colour cut
        # had kept and the matte rejected. On a plate those are the contact shadow.
        kept = pc.background_distance_alpha(rgb) > 200
        matte_record["rejected_px"] = int((kept & (mask <= 8)).sum())
    # A studio plate carries a soft contact shadow. It is part of the same colour
    # difference as the product, so a colour cut keeps it; a real matte does not. The
    # solid pass below keeps the product and drops a *translucent* shadow, and never
    # widens what a matte already decided.
    solid = (mask > 200).astype(np.uint8)
    if solid.sum() > 0:
        import cv2

        count, labels, stats, _ = cv2.connectedComponentsWithStats(solid, connectivity=8)
        if count > 1:
            biggest = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
            solid = (labels == biggest).astype(np.uint8)
        solid = cv2.morphologyEx(solid, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
        solid = cv2.GaussianBlur(solid * 255, (3, 3), 0)
        # Keep the union: the solid pass restores any part of the product a soft
        # alpha lost, and never clips the product's own bright edge. On the colour
        # cut an opaque shadow attached to the product survives this pass — that is
        # D-017, and the cure is the real matte above, not a higher threshold.
        mask = np.maximum(mask, solid)
    ys, xs = np.nonzero(mask > 8)
    if xs.size < 16:
        raise ValueError("cutout_empty: the plate produced no product to stand on white")
    left, right = int(xs.min()), int(xs.max()) + 1
    top, bottom = int(ys.min()), int(ys.max()) + 1
    cut_rgba = Image.fromarray(
        np.dstack([rgb, mask]).astype(np.uint8), "RGBA").crop((left, top, right, bottom))

    canvas = Image.new("RGB", composed.size, (int(value), int(value), int(value)))
    # `fill` is the share of the CANVAS AREA the product should occupy: the briefs
    # state fill as an area percentage, and Amazon's 85 % linear guidance is about
    # 72 % area for a square subject. Scaling by area keeps every brief inside its
    # own band instead of overshooting the ones with an upper bound.
    target_area = max(0.02, min(0.72, float(fill)))
    scale = (target_area * canvas.width * canvas.height
             / max(1.0, float(cut_rgba.width * cut_rgba.height))) ** 0.5
    size = (max(1, int(cut_rgba.width * scale)), max(1, int(cut_rgba.height * scale)))
    if size[0] > canvas.width or size[1] > canvas.height:
        shrink = min(canvas.width / size[0], canvas.height / size[1])
        size = (max(1, int(size[0] * shrink)), max(1, int(size[1] * shrink)))
    scaled = cut_rgba.resize(size, Image.LANCZOS)
    position = ((canvas.width - size[0]) // 2, (canvas.height - size[1]) // 2)
    canvas.paste(scaled, position, scaled)
    buffer = io.BytesIO()
    cut_rgba.save(buffer, format="PNG")
    return {"image": canvas, "method": method, "matte": matte_record,
            "box": [position[0], position[1], position[0] + size[0], position[1] + size[1]],
            "fill": round(size[0] * size[1] / float(canvas.width * canvas.height), 4),
            "cutout": buffer.getvalue()}


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

    A rigid cylinder has no four-corner face: its label wraps the visible half of
    the tube, so the measured face becomes a *band* and the panel is warped round
    the arc by :func:`mockup_compositor.warp_cylinder` instead of homographed onto
    a quad. Printing a flat homography on a round body is what makes a label look
    like a sticker.
    """
    form = form or art.form_of(design)
    insets = FORM_INSETS.get(form, FORM_INSETS[art.POUCH])
    if form == art.CYLINDER:
        # A cylinder measures its own body (difference from the plate's own
        # background) and warps round the visible arc; there is no quad to take.
        return _compose_cylinder(plate, design, face, insets, units, shading=shading)
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
          units: int = 1,
          background: Optional[str] = None,
          background_value: int = 255,
          fill: float = 0.85,
          matte: str = "auto") -> Dict[str, Any]:
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
        # A main image is the product alone on a flat value, so its plate is asked for
        # no contact shadow (D-021). A free/scene brief keeps the shadow: a lifestyle
        # picture with the product floating above its own shadow would be the wrong
        # defect.
        wants_shadow = str(background or "").strip().lower() not in ("white", "flat")
        brief = plate_brief(face, form, dsn, units=units, shadow=wants_shadow)
        plate_record: Dict[str, Any] = {}
        cutout_bytes: Dict[str, Any] = {}
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

        placed: Optional[Dict[str, Any]] = None
        if str(background or "").strip().lower() in ("white", "flat"):
            # A main-image brief is the product alone on a flat canvas, not a
            # photograph of it on a sweep. The cutout happens on the PLATE, before
            # the label is composed: cutting the finished picture punches the
            # label's own light panel out of it (measured 2026-11-11 — the wordmark
            # went with it).
            try:
                placed = _place_on_flat(plate, value=background_value, fill=fill,
                                        matte=matte)
            except ValueError as exc:
                record.update({"ok": False, "stage": "background", "reason": str(exc)})
                plate.save(rejected / f"{face}_plate.png")
                records.append(record)
                ok = False
                continue
            plate = placed["image"]
            record["background"] = {"mode": "flat", "value": int(background_value),
                                    "method": placed["method"], "box": placed["box"],
                                    "fill": placed["fill"]}
            # D-017: a delivered main image states which matte produced it, and what
            # the matte rejected. "auto" on a cold lane is a colour cut, said plainly.
            record["matte"] = placed["matte"]
            record["product_box"] = list(placed["box"])
            cutout_bytes["png"] = placed.get("cutout")

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
            if cutout_bytes.get("png"):
                # D-018: keep the product's own silhouette beside the picture, so a
                # white product on a white canvas can be measured by its shape rather
                # than by a colour difference that is zero.
                cutout_path = path.with_suffix(".cutout.png")
                cutout_path.write_bytes(cutout_bytes["png"])
                record["cutout_path"] = str(cutout_path)
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
            "matte": {r["face"]: (r.get("matte") or {}).get("method", "none")
                      for r in records},
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
