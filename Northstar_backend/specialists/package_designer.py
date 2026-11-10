"""Package Designer — the complete-package agent.

Studied behaviour (see specs/package_designer.md): Packify, Pacdora, Cubit,
Mockey and Artboard Studio all collect DIMENSIONS + PANEL CONTENT before they
render, and they all produce more than one image: a dieline plus per-panel
artwork plus a mockup. Northstar previously produced one blankish pouch.

This agent forces that order:

    inputs -> gaps -> panel spec -> three panels -> dieline -> mockup -> validate

and it refuses to guess. Every fact it cannot find in the request or the brand
kit is returned as a question, and (if the operator proceeds anyway) rendered as
a visible `[MISSING: field]` marker on the artwork.

Northstar's stated improvement over the studied tools:
  • panel content is driven by the Brand Kit and the keyword set, so the pack
    ships with the SEO terms that matter for the listing;
  • the same facts feed the listing and A+ agents (one source of truth),
  • and every run is local and free.
"""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from PIL import Image

import design_studio_print as dsp
import pouch_label as pl
from specialists import panels as pnl

NAME = "package_designer"

#: What a print-ready stand-up pouch cannot be built without. Ordered by how
#: often it is the thing the operator forgot.
REQUIRED = [
    ("title", "the product name exactly as it must appear"),
    ("weight", "the net weight line, e.g. 'NET WT 6 OZ (170 g)'"),
    ("dims", "the pouch size in mm (width_mm, height_mm, gusset_mm)"),
    ("ingredients", "the ingredient list OR a supplement facts block"),
    ("company", "the company name for the back panel"),
    ("address", "the company address for the back panel"),
    ("country_of_origin", "the country of origin"),
]
OPTIONAL = [
    ("subtitle", "a supporting line, e.g. 'Organic Mushroom Powder'"),
    ("claims", "short claim lines for the front/side panels"),
    ("icons", "certification marks to draw: organic_sprout, non_gmo, gluten_free, fruiting_body"),
    ("suggested_use", "the suggested-use line"),
    ("warnings", "any required warning text"),
    ("supplement_facts", "the supplement facts block, one line per row"),
    ("lot_code", "a lot code pattern, or leave blank for 'supply at print'"),
    ("keywords", "target keywords to bias the copy (from the SEO layer)"),
]


def missing_inputs(spec: Dict[str, Any]) -> List[Dict[str, str]]:
    """Return the questions to ask, in the order they matter."""
    out: List[Dict[str, str]] = []
    for key, why in REQUIRED:
        value = spec.get(key)
        if key == "dims":
            d = value or {}
            if not (d.get("width_mm") and d.get("height_mm") and d.get("gusset_mm")):
                out.append({"field": key, "question": why})
            continue
        if key == "ingredients":
            if not spec.get("ingredients") and not spec.get("supplement_facts"):
                out.append({"field": key, "question": why})
            continue
        if not value:
            out.append({"field": key, "question": why})
    return out


def build_package(spec: Dict[str, Any], *, plate_path: Optional[Path] = None,
                  logo_path: Optional[Path] = None,
                  out_dir: Optional[Path] = None,
                  allow_incomplete: bool = False) -> Dict[str, Any]:
    """Build every panel + the dieline + a mockup.

    `allow_incomplete=False` (default) refuses when a required fact is missing and
    returns the questions instead — the behaviour the vague-request test checks.
    """
    gaps = missing_inputs(spec)
    if gaps and not allow_incomplete:
        return {
            "ok": False,
            "status": "needs_input",
            "summary": (f"I can build the whole package, but {len(gaps)} thing(s) must come "
                        f"from you first so nothing is invented."),
            "questions": gaps,
            "assets": [],
        }

    dims = dict(spec.get("dims") or {})
    title = str(spec.get("title") or "").strip() or pnl._missing("product name")
    subtitle = str(spec.get("subtitle") or "").strip()
    weight = str(spec.get("weight") or "").strip()
    claims = [str(c) for c in (spec.get("claims") or [])][:4]
    icons = [str(i) for i in (spec.get("icons") or [])][:4]
    logo = pl.load_logo(Path(logo_path)) if logo_path else None

    front = pl.render_label(
        title=title, subtitle=subtitle, weight=weight, bullets=claims,
        logo=logo, icons=icons,
        field=tuple(spec.get("field") or pl.FIELD),
        ink=tuple(spec.get("ink") or pl.INK),
        accent=tuple(spec.get("accent") or pl.ACCENT),
    )
    back = pnl.render_back_panel(
        title=title or "",
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
        title=title if title != pnl._missing("product name") else "",
        subtitle=subtitle, weight=weight, claims=claims, icons=icons,
        company=(spec.get("company") or None),
    )

    sheet = pnl.panel_sheet({"front": front, "back": back, "side": side})

    # ── dieline, from the same dimensions the panels were drawn for ──────────
    dparams = {k: v for k, v in dims.items()
               if k in ("width_mm", "height_mm", "gusset_mm", "weld_mm",
                        "top_weld_mm", "zip_offset_mm", "bleed_mm", "safe_mm",
                        "fill_g")}
    build = dsp.build_from_template("doypack", dparams or None)
    dieline_svg = dsp.render_svg(build)
    dieline_pdf = dsp.render_pdf(build)

    out: Dict[str, Any] = {
        "ok": True,
        "status": "built",
        "summary": (
            f"Built a complete {build.get('title')} package: front, back and side panels, "
            f"a print dieline (SVG + PDF) and a flat panel sheet. "
            f"Draft geometry — confirm with your converter before print."),
        "questions": gaps,
        "panels": {"front": pnl.png_bytes(front), "back": pnl.png_bytes(back),
                   "side": pnl.png_bytes(side), "sheet": pnl.png_bytes(sheet)},
        "dieline": {"svg": dieline_svg, "pdf": dieline_pdf,
                    "title": build.get("title"),
                    # `width_mm`/`height_mm` at the top of a build are the FLAT
                    # sheet, not the pouch. Keep both so nobody compares a fin to
                    # a flat sheet by accident.
                    "flat_width_mm": build.get("width_mm"),
                    "flat_height_mm": build.get("height_mm"),
                    "pouch": (build.get("meta") or {}).get("panels") or {},
                    "meta": build.get("meta") or {}},
        "validation": pnl.validate_panels(spec),
        "assets": [],
    }

    # ── mockup: the same deterministic face fit used by apply_label ──────────
    if plate_path and Path(plate_path).is_file():
        try:
            composed = pl.compose(
                Path(plate_path), title=title, subtitle=subtitle, weight=weight,
                bullets=claims, logo_path=logo_path, icons=icons,
                field=spec.get("field"), ink=spec.get("ink"),
                accent=spec.get("accent"))
            out["panels"]["mockup"] = composed["bytes"]
            out["mockup_quad"] = composed["quad"]
        except Exception as exc:  # noqa: BLE001 - a missing mockup must not lose the panels
            out.setdefault("warnings", []).append(f"mockup skipped: {exc}")
    return out


def save_package(result: Dict[str, Any], out_dir: Path) -> Dict[str, Any]:
    """Write every panel/dieline to disk and return the file names."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    tag = uuid.uuid4().hex[:12]
    files: Dict[str, str] = {}
    for key, payload in (result.get("panels") or {}).items():
        path = out_dir / f"package_{tag}_{key}.png"
        path.write_bytes(payload)
        files[key] = path.name
    dieline = result.get("dieline") or {}
    if dieline.get("svg"):
        name = f"package_{tag}_dieline.svg"
        (out_dir / name).write_text(dieline["svg"], encoding="utf-8")
        files["dieline_svg"] = name
    if dieline.get("pdf"):
        name = f"package_{tag}_dieline.pdf"
        (out_dir / name).write_bytes(dieline["pdf"])
        files["dieline_pdf"] = name
    result["files"] = files
    return result
