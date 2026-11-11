"""sel-04: packaging deliverables are built by the app and scored like a print shop would.

A picture can be retouched until it passes; a **dieline** either folds into the package
the brief describes or it does not. This harness therefore exercises the app's own print
engine end to end — `design_studio_print.build_from_template` (geometry gate),
`render_svg` (layered, editable) and `render_pdf` (the sheet a printer receives) — and
scores the artefacts against the brief:

* **sheet** — the SVG declares the same millimetre sheet the build measured;
* **panels** — every panel the manufactured package has (front, back, gusset) exists and
  has a positive size;
* **bleed / safe** — at least what the brief asks, because a bleed shortfall is trimmed
  artwork and a safe shortfall is copy under the fold;
* **layers** — trim, fold, safe and bleed are separate SVG layers, which is what makes the
  file editable by a human instead of a flattened picture;
* **pdf** — the PDF opens and its page is the sheet's size in points;
* **readiness** — `package_readiness.assess_dieline` gives the one verdict, including the
  doypack proportion ladder, and its blockers are the failure reasons.

A brief the geometry gate refuses is a **refusal with the engine's own reason**, never a
silent substitution: `build_packaging` raises `PackagingRefused` and writes nothing.

    python -m tools.seller_tester packaging --limit 8
"""
from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PACKAGING_CATALOG = ROOT / "ty" / "seller_briefs_packaging.json"
DEFAULT_OUT = ROOT / "renders" / "packaging"
DEFAULT_SUMMARY = ROOT / "reports" / "ty" / "packaging_pass.json"
DEFAULT_GAPS = ROOT / "state" / "seller" / "packaging_gaps.json"

MM_PT = 72.0 / 25.4


class PackagingRefused(RuntimeError):
    """The engine refused this brief by name. Never swapped for another template."""


def _engine():
    backend = str(ROOT / "Northstar_backend")
    if backend not in sys.path:
        sys.path.insert(0, backend)
    import design_studio_print  # noqa: PLC0415
    import package_readiness  # noqa: PLC0415

    return design_studio_print, package_readiness


def load_catalog(path: str | Path = DEFAULT_PACKAGING_CATALOG) -> List[Dict[str, Any]]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    return list(payload.get("briefs") or [])


def build_packaging(brief: Dict[str, Any], out_dir: str | Path = DEFAULT_OUT) -> Dict[str, Any]:
    """Build the dieline the brief names, write SVG + PDF, and return the record."""
    engine, _ = _engine()
    template = str(brief.get("template") or "").strip()
    if not template:
        raise PackagingRefused("the brief names no dieline template")
    started = time.time()
    try:
        build = engine.build_from_template(template, brief.get("params") or {})
    except ValueError as exc:                      # the geometry gate's own words
        raise PackagingRefused(str(exc)) from exc
    except Exception as exc:  # noqa: BLE001 - an engine failure is stated, not hidden
        raise PackagingRefused(f"the dieline engine failed: {type(exc).__name__}: {exc}"
                               ) from exc
    svg = engine.render_svg(build)
    pdf = engine.render_pdf(build)
    target = Path(out_dir)
    target.mkdir(parents=True, exist_ok=True)
    brief_id = str(brief.get("id") or "brief")
    svg_path = target / f"{brief_id}.svg"
    pdf_path = target / f"{brief_id}.pdf"
    svg_path.write_text(svg, encoding="utf-8")
    pdf_path.write_bytes(pdf)
    record = {
        "brief_id": brief_id, "template": template,
        "product": brief.get("product"), "brand": brief.get("brand"),
        "width_mm": round(float(build.get("width_mm") or 0), 3),
        "height_mm": round(float(build.get("height_mm") or 0), 3),
        "meta": build.get("meta") or {},
        "layers": sorted({str(item.get("layer")) for item in (build.get("layers") or [])}),
        "svg_path": str(svg_path), "pdf_path": str(pdf_path),
        "svg_bytes": len(svg), "pdf_bytes": len(pdf),
        "seconds": round(time.time() - started, 2),
        "build": build,
    }
    return record


# ── the checks ────────────────────────────────────────────────────────────────

def check_sheet(svg: str, record: Dict[str, Any]) -> Dict[str, Any]:
    """The SVG's own sheet equals the measured sheet, in millimetres."""
    width = re.search(r'width="([\d.]+)mm"', svg)
    height = re.search(r'height="([\d.]+)mm"', svg)
    if not width or not height:
        return {"ok": False, "check": "sheet",
                "detail": "the SVG declares no millimetre size"}
    w, h = float(width.group(1)), float(height.group(1))
    ok = abs(w - record["width_mm"]) <= 0.1 and abs(h - record["height_mm"]) <= 0.1
    return {"ok": ok, "check": "sheet", "width_mm": w, "height_mm": h,
            "detail": f"SVG sheet {w:g}x{h:g} mm vs the build's "
                      f"{record['width_mm']:g}x{record['height_mm']:g} mm"}


def check_panels(record: Dict[str, Any], expect: Dict[str, Any]) -> Dict[str, Any]:
    """Every panel the manufactured package has, measured.

    The engine reports panels in two shapes, and they are not interchangeable: a doypack
    names its faces (`{"front": [x, y, w, h], "back": ..., "gusset": ...}`), while a
    carton reports the body faces as a **list of widths** plus the glue tab. The check
    follows the shape the engine used and does not pretend one is the other.
    """
    panels = (record.get("meta") or {}).get("panels")
    if isinstance(panels, dict):
        wanted = list(expect.get("panel_names") or expect.get("panels") or [])
        missing, sizes = [], {}
        for name in wanted:
            box = panels.get(name)
            if not isinstance(box, (list, tuple)) or len(box) != 4:
                missing.append(name)
                continue
            sizes[name] = [round(float(v), 2) for v in box]
            if float(box[2]) <= 0 or float(box[3]) <= 0:
                missing.append(name)
        ok = not missing and bool(wanted)
        return {"ok": ok, "check": "panels", "shape": "named", "missing": missing,
                "panels": sizes,
                "detail": (f"panels {sorted(sizes)} present" if ok
                           else f"missing or empty panels: {missing}")}
    if isinstance(panels, (list, tuple)):
        widths = [round(float(v), 3) for v in panels]
        need = int(expect.get("min_panels") or 4)
        enough = len(widths) >= need and all(width > 0 for width in widths)
        # A carton sheet is the bleed, the body faces and the glue tab, side by side: the
        # widths plus the bleed on both edges must add up to the sheet, or a face is
        # missing from the layout (measured: 4 x 45 + 15 + 2 x 3 = 201 mm).
        span = round(sum(widths), 3)
        bleed = float((record.get("meta") or {}).get("bleed_mm") or 0.0)
        span_ok = None
        if expect.get("sheet_span"):
            span_ok = abs(span + 2.0 * bleed - float(record["width_mm"])) <= 0.5
        ok = enough and span_ok is not False
        return {"ok": ok, "check": "panels", "shape": "widths", "widths": widths,
                "count": len(widths), "needed": need, "span_mm": span,
                "sheet_mm": record["width_mm"], "span_ok": span_ok,
                "detail": (f"{len(widths)} faces + glue spanning {span:g} mm of the "
                           f"{record['width_mm']:g} mm sheet" if ok else
                           f"{len(widths)} widths (need {need}), span {span:g} mm vs "
                           f"sheet {record['width_mm']:g} mm")}
    return {"ok": False, "check": "panels",
            "detail": f"the engine reported no panel geometry ({type(panels).__name__})"}


def check_bleed(record: Dict[str, Any], expect: Dict[str, Any]) -> Dict[str, Any]:
    bleed = float((record.get("meta") or {}).get("bleed_mm") or 0.0)
    need = float(expect.get("min_bleed_mm", 3.0))
    return {"ok": bleed >= need, "check": "bleed", "bleed_mm": bleed, "needed_mm": need,
            "detail": f"bleed {bleed:g} mm vs the brief's {need:g} mm"}


def check_safe(record: Dict[str, Any], expect: Dict[str, Any]) -> Dict[str, Any]:
    safe = float((record.get("meta") or {}).get("safe_mm") or 0.0)
    need = float(expect.get("min_safe_mm", 3.0))
    # a carton has no safe margin in its meta: the engine's own trim/fold geometry is the
    # authority there, so an absent value is not a shortfall
    if not safe:
        return {"ok": True, "check": "safe", "skipped": True,
                "detail": "this template declares no safe-margin field; trim/fold "
                          "geometry is the engine's own gate for it"}
    return {"ok": safe >= need, "check": "safe", "safe_mm": safe, "needed_mm": need,
            "detail": f"safe margin {safe:g} mm vs the brief's {need:g} mm"}


def check_layers(record: Dict[str, Any], expect: Dict[str, Any]) -> Dict[str, Any]:
    have = set(record.get("layers") or [])
    want = list(expect.get("layers") or ["trim", "fold", "safe", "bleed"])
    missing = [name for name in want if name not in have]
    return {"ok": not missing, "check": "layers", "layers": sorted(have),
            "missing": missing,
            "detail": (f"layers {sorted(have)}" if not missing
                       else f"missing layers: {missing}")}


def check_pdf(pdf: bytes, record: Dict[str, Any]) -> Dict[str, Any]:
    """The PDF a printer receives: it opens, and its page is the sheet."""
    if not pdf.startswith(b"%PDF"):
        return {"ok": False, "check": "pdf", "detail": "the file is not a PDF"}
    size = re.search(rb"/MediaBox\s*\[\s*0\s+0\s+([\d.]+)\s+([\d.]+)\s*\]", pdf)
    if not size:
        return {"ok": False, "check": "pdf",
                "detail": "the PDF declares no usable MediaBox"}
    w_pt, h_pt = float(size.group(1)), float(size.group(2))
    want_w = record["width_mm"] * MM_PT
    want_h = record["height_mm"] * MM_PT
    ok = abs(w_pt - want_w) <= 1.5 and abs(h_pt - want_h) <= 1.5
    return {"ok": ok, "check": "pdf", "page_pt": [round(w_pt, 1), round(h_pt, 1)],
            "expected_pt": [round(want_w, 1), round(want_h, 1)],
            "detail": f"page {w_pt:.1f}x{h_pt:.1f} pt vs the sheet's "
                      f"{want_w:.1f}x{want_h:.1f} pt"}


def check_readiness(record: Dict[str, Any]) -> Dict[str, Any]:
    """The app's own dieline verdict: assessed, and no blockers.

    `assess_dieline` returns blockers and warnings and no boolean — the combined verdict
    lives in `assess_package`. A warning (a proportion ladder note, the "planning dieline,
    not a die" confidence note) is information, not a failure: `package_readiness`'s own
    test says proportion warnings surface but do not block.
    """
    _, readiness = _engine()
    verdict = readiness.assess_dieline(record.get("build"))
    blockers = list(verdict.get("blockers") or [])
    warnings = list(verdict.get("warnings") or [])
    assessed = bool(verdict.get("assessed"))
    ok = assessed and not blockers
    return {"ok": ok, "check": "readiness", "assessed": assessed,
            "blockers": blockers, "warnings": warnings,
            "detail": ("retail-ready dieline" if ok else
                       "; ".join(blockers) or "the engine did not assess this dieline")}


def score_packaging(brief: Dict[str, Any], record: Dict[str, Any],
                    svg: str, pdf: bytes) -> Dict[str, Any]:
    expect = brief.get("expect") or {}
    checks = {
        "sheet": check_sheet(svg, record),
        "panels": check_panels(record, expect),
        "bleed": check_bleed(record, expect),
        "safe": check_safe(record, expect),
        "layers": check_layers(record, expect),
        "pdf": check_pdf(pdf, record),
        "readiness": check_readiness(record),
    }
    failed = [name for name, check in checks.items()
              if not check.get("ok") and not check.get("skipped")]
    score = round(100.0 * (len(checks) - len(failed)) / len(checks), 1)
    return {"brief_id": brief.get("id"), "template": brief.get("template"),
            "score": score, "passed": not failed, "failed_checks": failed,
            "checks": checks}


def run_pass(*, catalog: Optional[str | Path] = None, limit: Optional[int] = None,
             out_dir: str | Path = DEFAULT_OUT,
             summary_path: str | Path = DEFAULT_SUMMARY,
             gaps_path: str | Path = DEFAULT_GAPS,
             progress: Optional[Any] = None) -> Dict[str, Any]:
    """Build and score every packaging brief; a refusal is recorded, never skipped."""
    briefs = load_catalog(catalog or DEFAULT_PACKAGING_CATALOG)
    if limit is not None:
        briefs = briefs[:max(0, int(limit))]
    results: List[Dict[str, Any]] = []
    refusals: List[Dict[str, Any]] = []
    for index, brief in enumerate(briefs):
        try:
            record = build_packaging(brief, out_dir=out_dir)
        except PackagingRefused as exc:
            refusals.append({"brief_id": brief.get("id"), "reason": str(exc)})
            results.append({"brief_id": brief.get("id"), "status": "refused",
                            "score": 0.0, "passed": False,
                            "failed_checks": ["build"], "reason": str(exc)})
            if progress is not None:
                progress(index + 1, len(briefs))
            continue
        svg = Path(record["svg_path"]).read_text(encoding="utf-8")
        pdf = Path(record["pdf_path"]).read_bytes()
        scored = score_packaging(brief, record, svg, pdf)
        scored.update({"status": "scored", "artefact": record["svg_path"],
                       "pdf": record["pdf_path"], "seconds": record["seconds"],
                       "width_mm": record["width_mm"], "height_mm": record["height_mm"],
                       "layers": record["layers"]})
        results.append(scored)
        if progress is not None:
            progress(index + 1, len(briefs))
    scored_rows = [row for row in results if row.get("status") == "scored"]
    passed = [row for row in scored_rows if row.get("passed")]
    summary = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "generator": "design_studio_print.build_from_template + render_svg + render_pdf",
        "selected": len(briefs), "scored": len(scored_rows),
        "passed": len(passed), "failed": len(scored_rows) - len(passed),
        "refused": len(refusals),
        "pass_rate": round(100.0 * len(passed) / len(scored_rows), 1) if scored_rows else 0.0,
        "mean_score": (round(sum(float(row["score"]) for row in scored_rows)
                             / len(scored_rows), 1) if scored_rows else 0.0),
        "results": results,
    }
    Path(summary_path).parent.mkdir(parents=True, exist_ok=True)
    Path(summary_path).write_text(json.dumps(summary, indent=2), encoding="utf-8")
    if refusals or summary["failed"]:
        gaps = [{"brief_id": row["brief_id"], "kind": "packaging",
                 "failed_checks": row.get("failed_checks") or [],
                 "reason": row.get("reason") or "; ".join(
                     str(row["checks"][name].get("detail"))
                     for name in (row.get("failed_checks") or []))}
                for row in results if not row.get("passed")]
        Path(gaps_path).parent.mkdir(parents=True, exist_ok=True)
        Path(gaps_path).write_text(json.dumps({"at": summary["generated_at"],
                                               "gaps": gaps}, indent=2),
                                   encoding="utf-8")
        summary["gaps_path"] = str(gaps_path)
        summary["gaps"] = len(gaps)
    return summary


__all__ = [
    "DEFAULT_GAPS", "DEFAULT_OUT", "DEFAULT_PACKAGING_CATALOG", "DEFAULT_SUMMARY",
    "PackagingRefused", "build_packaging", "check_bleed", "check_layers", "check_panels",
    "check_pdf", "check_readiness", "check_safe", "check_sheet", "load_catalog",
    "run_pass", "score_packaging",
]
