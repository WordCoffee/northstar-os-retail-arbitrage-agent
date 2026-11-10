"""Publishing tools for Bojo — ListingForge copy and Design Studio dielines.

Both tools wrap EXISTING production code; neither re-implements the logic:

``compose_listing`` -> ``reasoning_tasks.listing_proposal``, the same function
                       behind ``POST /api/v1/reasoning/listing-proposal`` in
                       ``main.py``: prompt -> provider -> deterministic
                       normalisation (length limits, prohibited words, copy
                       audit). The provider is injectable, so a test drives the
                       real normalisation with a fake model response and never
                       touches a model.
``build_dieline``   -> ``design_studio_print.build_from_template`` +
                       ``render_svg``/``render_pdf``. That builder already runs
                       ``dieline_geometry.require_valid`` before anything is
                       rendered, so the geometry gate is the production gate,
                       not a second one. Pure and offline.

Contract (every tool)::

    {"ok": True,  "tool": "<name>", "data": {...}}
    {"ok": False, "tool": "<name>", "reason": "<reason string>"}

Business failures — a provider that errors, copy that came back empty, a
template the engine rejects, a requested format that cannot render — come back
as ``ok=False`` and never raise. Programmer errors in the tool's own argument
contract raise ``TypeError``/``ValueError``.
"""

from __future__ import annotations

import os
import sys
from functools import lru_cache
from typing import Any, Dict, List, Mapping, Optional

from ._coerce import text

TOOL_COMPOSE_LISTING = "compose_listing"
TOOL_BUILD_DIELINE = "build_dieline"


# ---------------------------------------------------------------------------
# Backend import plumbing (the backend root is normally already on sys.path,
# but these tools must also work when imported from a plain `python -c`).
# ---------------------------------------------------------------------------


def _backend_root() -> str:
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _ensure_backend_on_path() -> None:
    root = _backend_root()
    if root not in sys.path:
        sys.path.insert(0, root)


@lru_cache(maxsize=1)
def _default_composer() -> Any:
    """The real listing composer behind the reasoning route."""
    _ensure_backend_on_path()
    import reasoning_tasks

    return reasoning_tasks


@lru_cache(maxsize=1)
def _default_printer() -> Any:
    """The real print engine (parametric dielines, layered SVG/PDF)."""
    _ensure_backend_on_path()
    import design_studio_print

    return design_studio_print


@lru_cache(maxsize=1)
def _default_geometry() -> Any:
    """The real dieline geometry auditor."""
    _ensure_backend_on_path()
    import dieline_geometry

    return dieline_geometry


def _bad(tool: str, reason: str) -> Dict[str, Any]:
    return {"ok": False, "tool": tool, "reason": reason}


# ---------------------------------------------------------------------------
# compose_listing — ListingForge.
# ---------------------------------------------------------------------------


def _string_list(value: Any, name: str) -> List[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value] if value.strip() else []
    if not isinstance(value, (list, tuple)):
        raise TypeError("%s must be a list of strings or None" % name)
    out: List[str] = []
    for item in value:
        if not isinstance(item, str):
            raise TypeError("%s entries must be strings" % name)
        if item.strip():
            out.append(item.strip())
    return out


def compose_listing(
    sku: str,
    title: str = "",
    bullets: Optional[List[str]] = None,
    description: str = "",
    attributes: Optional[Mapping[str, Any]] = None,
    keywords: Optional[List[str]] = None,
    brand: Optional[str] = None,
    model: Optional[str] = None,
    provider: Optional[Any] = None,
    composer: Optional[Any] = None,
) -> Dict[str, Any]:
    """Draft a listing revision proposal for one SKU.

    Wraps ``reasoning_tasks.listing_proposal``: it builds the prompt, calls the
    provider, then applies the deterministic validation that lives there (200
    char title, 500 char bullets, 2000 char description, prohibited phrases,
    copy audit). The proposal is never applied anywhere.

    ``composer`` is an injectable dependency: anything exposing
    ``listing_proposal(...)``. It defaults to the real ``reasoning_tasks``
    module. ``provider`` is passed straight through to the production function,
    which is the seam a test uses to supply a fake model response.
    """
    if not isinstance(sku, str):
        raise TypeError("sku must be a string")
    if not isinstance(title, str):
        raise TypeError("title must be a string")
    if not isinstance(description, str):
        raise TypeError("description must be a string")
    if attributes is not None and not isinstance(attributes, Mapping):
        raise TypeError("attributes must be a mapping or None")
    if brand is not None and not isinstance(brand, str):
        raise TypeError("brand must be a string or None")
    if model is not None and not isinstance(model, str):
        raise TypeError("model must be a string or None")

    written_sku = sku.strip()
    bullet_list = _string_list(bullets, "bullets")
    keyword_list = _string_list(keywords, "keywords")

    if not written_sku:
        return _bad(TOOL_COMPOSE_LISTING, "sku is empty")
    if not (title.strip() or bullet_list or description.strip()):
        return _bad(
            TOOL_COMPOSE_LISTING,
            "at least one of title, bullets or description is required",
        )

    engine = composer if composer is not None else _default_composer()
    try:
        proposal = engine.listing_proposal(
            sku=written_sku,
            title=title,
            bullets=bullet_list,
            description=description,
            attributes=dict(attributes or {}),
            keywords=keyword_list,
            brand=brand,
            model=model,
            provider=provider,
        )
    except Exception as exc:  # noqa: BLE001 - dependency failure, surfaced honestly
        return _bad(
            TOOL_COMPOSE_LISTING,
            "listing composer failed: %s: %s" % (type(exc).__name__, exc),
        )

    if not isinstance(proposal, Mapping):
        return _bad(
            TOOL_COMPOSE_LISTING,
            "composer returned %s, expected a mapping" % type(proposal).__name__,
        )
    if not proposal.get("ok"):
        reason = text(proposal.get("error")) or "; ".join(
            str(w) for w in (proposal.get("warnings") or [])
        ) or "the composer produced no proposal"
        return _bad(TOOL_COMPOSE_LISTING, "listing composer refused: " + reason)

    proposed = proposal.get("proposed") or {}
    if not isinstance(proposed, Mapping):
        return _bad(TOOL_COMPOSE_LISTING, "proposed copy must be a mapping")
    if not text(proposed.get("title")):
        return _bad(TOOL_COMPOSE_LISTING, "the proposal has no title")

    warnings = [str(w) for w in (proposal.get("warnings") or [])]
    return {
        "ok": True,
        "tool": TOOL_COMPOSE_LISTING,
        "data": {
            "sku": written_sku,
            "original": proposal.get("original") or {},
            "proposed": dict(proposed),
            "reasons": [str(r) for r in (proposal.get("reasons") or [])],
            "missing_evidence": [
                str(m) for m in (proposal.get("missing_evidence") or [])
            ],
            "warnings": warnings,
            "copy_audit": proposal.get("copy_audit"),
            "provenance": proposal.get("provenance"),
            "applied": False,
            "note": "Proposal only. Nothing was saved to a marketplace or an ad platform.",
        },
    }


# ---------------------------------------------------------------------------
# build_dieline — Design Studio.
# ---------------------------------------------------------------------------


def build_dieline(
    template_id: str,
    params: Optional[Mapping[str, Any]] = None,
    include_svg: bool = False,
    pdf: bool = False,
    printer: Optional[Any] = None,
    geometry: Optional[Any] = None,
) -> Dict[str, Any]:
    """Build a layered, print-ready dieline from a parametric template.

    Wraps ``design_studio_print.build_from_template`` (which sanitises and
    bounds every parameter, then refuses anything that fails
    ``dieline_geometry.require_valid``) plus ``render_svg`` / ``render_pdf``.
    The geometry is the already-proven production geometry; this tool adds no
    maths of its own.

    ``printer`` / ``geometry`` are injectable dependencies and default to the
    real modules. Both are pure and offline.
    """
    if not isinstance(template_id, str):
        raise TypeError("template_id must be a string")
    if params is not None and not isinstance(params, Mapping):
        raise TypeError("params must be a mapping or None")
    if not isinstance(include_svg, bool):
        raise TypeError("include_svg must be a boolean")
    if not isinstance(pdf, bool):
        raise TypeError("pdf must be a boolean")

    written_id = template_id.strip()
    if not written_id:
        return _bad(TOOL_BUILD_DIELINE, "template_id is empty")

    engine = printer if printer is not None else _default_printer()
    auditor = geometry if geometry is not None else _default_geometry()

    try:
        build = engine.build_from_template(written_id, dict(params or {}))
    except ValueError as exc:  # sanitisation / geometry gate refused the spec
        return _bad(TOOL_BUILD_DIELINE, "dieline rejected: %s" % exc)
    except Exception as exc:  # noqa: BLE001 - dependency failure, surfaced honestly
        return _bad(
            TOOL_BUILD_DIELINE,
            "dieline build failed: %s: %s" % (type(exc).__name__, exc),
        )

    if not isinstance(build, Mapping):
        return _bad(
            TOOL_BUILD_DIELINE,
            "print engine returned %s, expected a mapping" % type(build).__name__,
        )

    try:
        audit = auditor.audit(build)
    except Exception as exc:  # noqa: BLE001 - audit failure is reported, not raised
        return _bad(
            TOOL_BUILD_DIELINE,
            "geometry audit failed: %s: %s" % (type(exc).__name__, exc),
        )

    try:
        svg = engine.render_svg(build)
    except Exception as exc:  # noqa: BLE001
        return _bad(
            TOOL_BUILD_DIELINE,
            "SVG render failed: %s: %s" % (type(exc).__name__, exc),
        )

    pdf_bytes = None
    if pdf:
        try:
            pdf_bytes = engine.render_pdf(build)
        except Exception as exc:  # noqa: BLE001
            return _bad(
                TOOL_BUILD_DIELINE,
                "PDF render failed: %s: %s" % (type(exc).__name__, exc),
            )

    layers = build.get("layers") or []
    layer_kinds: List[str] = []
    for layer in layers:
        kind = text((layer or {}).get("layer"))
        if kind and kind not in layer_kinds:
            layer_kinds.append(kind)

    data: Dict[str, Any] = {
        "template_id": written_id,
        "title": build.get("title"),
        "width_mm": build.get("width_mm"),
        "height_mm": build.get("height_mm"),
        "meta": build.get("meta") or {},
        "elements": len(layers),
        "layers": layer_kinds,
        "audit": audit,
        "svg_bytes": len(svg.encode("utf-8")) if isinstance(svg, str) else None,
        "formats": ["svg"] + (["pdf"] if pdf_bytes is not None else []),
        "note": (
            "Draft geometry. Confirm every dimension with the manufacturer or "
            "converter before printing."
        ),
    }
    if include_svg:
        data["svg"] = svg
    if pdf_bytes is not None:
        data["pdf_bytes"] = len(pdf_bytes)

    return {"ok": True, "tool": TOOL_BUILD_DIELINE, "data": data}


TOOLS = {
    TOOL_COMPOSE_LISTING: compose_listing,
    TOOL_BUILD_DIELINE: build_dieline,
}
