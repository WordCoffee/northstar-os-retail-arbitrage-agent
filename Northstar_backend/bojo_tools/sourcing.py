"""Sourcing tools for Bojo — Prospector catalog pull and Golden Goose scan.

Both tools wrap EXISTING production code; neither re-implements the business
logic:

``catalog_pull``      -> ``live_catalog.get_or_pull``, the same function behind
                         ``GET /api/v1/catalog/pull`` in ``main.py``. Stock
                         first, then (only when ``live=True`` and the operator
                         envelope is armed) a fresh pull. The catalog client is
                         injectable so tests never touch a database or network.
``golden_goose_scan`` -> ``calculate_breakdown_economics`` + ``score_batch``
                         from ``agents/golden_goose_finder``: real fee maths,
                         real hard filters, real tiering and ranking. Pure and
                         offline.

Contract (every tool)::

    {"ok": True,  "tool": "<name>", "data": {...}}
    {"ok": False, "tool": "<name>", "reason": "<reason string>"}

Business failures — an empty catalog, nothing above threshold, a dependency
that errors — come back as ``ok=False`` and never raise. Programmer errors in
the tool's own argument contract (wrong type for a required argument) raise
``TypeError``/``ValueError`` so they surface during development instead of
being silently reported to the operator as a business failure.
"""

from __future__ import annotations

import os
import sys
from functools import lru_cache
from typing import Any, Dict, List, Mapping, Optional

TOOL_CATALOG_PULL = "catalog_pull"
TOOL_GOLDEN_GOOSE_SCAN = "golden_goose_scan"


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


def _default_catalog() -> Any:
    """The real catalog implementation behind ``GET /api/v1/catalog/pull``."""
    _ensure_backend_on_path()
    import live_catalog

    return live_catalog


@lru_cache(maxsize=1)
def _golden_goose() -> Any:
    """The real Golden Goose economics/scoring modules (imported once)."""
    _ensure_backend_on_path()
    from agents.golden_goose_finder.breakdown_economics import (
        IndividualListing,
        WholesalePack,
        calculate_breakdown_economics,
    )
    from agents.golden_goose_finder.opportunity_scorer import (
        get_scoring_summary,
        score_batch,
    )

    return {
        "WholesalePack": WholesalePack,
        "IndividualListing": IndividualListing,
        "calculate_breakdown_economics": calculate_breakdown_economics,
        "score_batch": score_batch,
        "get_scoring_summary": get_scoring_summary,
    }


# ---------------------------------------------------------------------------
# Small typed coercion helpers (JSON from the model may carry numeric strings).
# ---------------------------------------------------------------------------


def _num(value: Any) -> Optional[float]:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.strip())
        except ValueError:
            return None
    return None


def _int(value: Any) -> Optional[int]:
    number = _num(value)
    if number is None:
        return None
    return int(number)


# ---------------------------------------------------------------------------
# catalog_pull — Prospector.
# ---------------------------------------------------------------------------


def catalog_pull(
    query: str,
    limit: int = 50,
    category: Optional[str] = None,
    live: bool = False,
    catalog: Optional[Any] = None,
) -> Dict[str, Any]:
    """Read the Prospector catalog for ``query`` (stock first, pull on a miss).

    Mirrors ``GET /api/v1/catalog/pull``: ``live_catalog.get_or_pull`` returns
    ``{"source": "stock"|"empty"|"live"|"live_empty", "rows": [...],
    "pulled": {...}|None}``.

    ``catalog`` is an injectable dependency: anything exposing
    ``get_or_pull(query, category=..., limit=..., live=...)``. It defaults to
    the real ``live_catalog`` module. Tests pass a fake, so no DB or network is
    touched.

    Returns rows verbatim from the catalog (they are already JSON-shaped) plus
    the honest ``source`` state. An empty result is a business failure.
    """
    if not isinstance(query, str):
        raise TypeError("query must be a string")
    written_query = query.strip()
    if not written_query:
        return {
            "ok": False,
            "tool": TOOL_CATALOG_PULL,
            "reason": "query is empty",
        }
    if isinstance(limit, bool) or not isinstance(limit, int):
        raise TypeError("limit must be an integer")
    if limit < 1:
        return {
            "ok": False,
            "tool": TOOL_CATALOG_PULL,
            "reason": "limit must be >= 1",
        }
    if category is not None and not isinstance(category, str):
        raise TypeError("category must be a string or None")

    client = catalog if catalog is not None else _default_catalog()
    try:
        pulled = client.get_or_pull(
            written_query, category=category, limit=limit, live=bool(live)
        )
    except Exception as exc:  # noqa: BLE001 - dependency failure, surfaced honestly
        return {
            "ok": False,
            "tool": TOOL_CATALOG_PULL,
            "reason": "catalog pull failed: %s: %s" % (type(exc).__name__, exc),
        }

    if not isinstance(pulled, dict):
        return {
            "ok": False,
            "tool": TOOL_CATALOG_PULL,
            "reason": "catalog returned %s, expected a mapping" % type(pulled).__name__,
        }

    rows = pulled.get("rows") or []
    if not isinstance(rows, list):
        return {
            "ok": False,
            "tool": TOOL_CATALOG_PULL,
            "reason": "catalog rows must be a list",
        }
    rows = rows[:limit]
    source = str(pulled.get("source") or "unknown")

    if not rows:
        return {
            "ok": False,
            "tool": TOOL_CATALOG_PULL,
            "reason": "no catalog rows for %r (source=%s)" % (written_query, source),
        }

    return {
        "ok": True,
        "tool": TOOL_CATALOG_PULL,
        "data": {
            "query": written_query,
            "category": category,
            "live": bool(live),
            "source": source,
            "count": len(rows),
            "rows": rows,
            "pulled": pulled.get("pulled"),
        },
    }


# ---------------------------------------------------------------------------
# golden_goose_scan — Golden Goose.
# ---------------------------------------------------------------------------


def _economics_from_candidate(candidate: Mapping[str, Any]) -> Any:
    """Build the real WholesalePack/IndividualListing pair for one candidate.

    Missing numbers stay ``None``; the economics calculator and every hard
    filter fail closed on them (no invented values), so junk candidates are
    rejected by the real scorer instead of being pre-filtered here.
    """
    gg = _golden_goose()
    brand = str(candidate.get("brand") or "Unknown")
    title = str(candidate.get("title") or "")
    slug = candidate.get("category_slug")

    wholesale = gg["WholesalePack"](
        source_store=str(candidate.get("source_store") or "unknown"),
        product_title=title,
        brand=brand,
        category_slug=str(slug) if slug else None,
        pack_count=_int(candidate.get("pack_count")),
        wholesale_price=_num(candidate.get("wholesale_price")),
        pack_weight_lbs=_num(candidate.get("pack_weight_lbs")),
    )
    individual = gg["IndividualListing"](
        asin=str(candidate.get("asin") or ""),
        title=title,
        brand=brand,
        category_slug=str(slug) if slug else "",
        amazon_price=_num(candidate.get("amazon_price")),
        bsr=_int(candidate.get("bsr")),
        review_rating=_num(candidate.get("review_rating")),
        review_count=_int(candidate.get("review_count")),
        fba_sellers=_int(candidate.get("fba_sellers")),
        monthly_sales_estimate=_num(candidate.get("monthly_sales_estimate")),
        weight_oz=_num(candidate.get("weight_oz")),
        seller_name=candidate.get("seller_name"),
        is_brand_seller=candidate.get("is_brand_seller"),
        is_amazon_seller=candidate.get("is_amazon_seller"),
    )
    return gg["calculate_breakdown_economics"](wholesale, individual)


def _opportunity_dict(scored: Any) -> Dict[str, Any]:
    econ = scored.economics
    return {
        "asin": scored.asin,
        "title": econ.individual.title,
        "brand": econ.wholesale.brand,
        "tier": scored.tier,
        "composite_score": scored.composite_score,
        "scores": {
            "profit": scored.profit_score,
            "demand": scored.demand_score,
            "competition": scored.competition_score,
            "listing_health": scored.listing_health_score,
            "price_gap": scored.price_gap_score,
            "ad_feasibility": scored.ad_feasibility_score,
        },
        "filters": {
            "profit_floor": scored.passes_profit_floor,
            "demand_floor": scored.passes_demand_floor,
            "competition_ceiling": scored.passes_competition_ceiling,
            "listing_health": scored.passes_listing_health,
            "seller_identity": scored.passes_seller_identity,
            "size": scored.passes_size_filter,
            "all": scored.passes_all_filters,
        },
        "economics": {
            "amazon_price": _num(getattr(econ.individual, "amazon_price", None)),
            "unit_cogs": econ.unit_cogs,
            "total_costs_per_unit": econ.total_costs_per_unit,
            "net_profit_per_unit": econ.net_profit_per_unit,
            "net_profit_per_pack": econ.net_profit_per_costco_pack,
            "roi_per_unit": econ.roi_per_unit,
            "profit_margin_pct": econ.profit_margin_pct,
            "undercut_headroom": econ.undercut_headroom,
            "max_undercut_price": econ.max_undercut_price,
            "confidence": econ.economics_confidence,
        },
        "tags": list(scored.opportunity_tags),
        "notes": list(scored.scoring_notes),
    }


def golden_goose_scan(
    candidates: List[Mapping[str, Any]],
    roi_floor: float = 10.0,
    min_monthly_sales: int = 1000,
    include_rejected: bool = False,
    limit: Optional[int] = 10,
    scorer: Optional[Any] = None,
) -> Dict[str, Any]:
    """Score and rank wholesale->individual arbitrage candidates.

    Runs the real Golden Goose pipeline for each candidate:
    ``calculate_breakdown_economics`` (fee stack, COGS, ROI, undercut
    headroom) then ``score_batch`` (hard filters, 0-1 composite, HIGH /
    MEDIUM / LOW / REJECT tier, descending rank). REJECT-tier rows are dropped
    unless ``include_rejected=True`` — which is exactly the real
    ``score_batch`` behaviour.

    A candidate is a JSON object with::

        {"asin", "title", "brand", "category_slug",
         "amazon_price", "wholesale_price", "pack_count",
         "bsr", "review_rating", "review_count", "fba_sellers",
         "weight_oz", "monthly_sales_estimate",
         "seller_name", "is_brand_seller", "is_amazon_seller"}

    Only ``asin`` and the price/count fields matter structurally; every other
    field is optional and a missing value fails closed inside the scorer.

    ``scorer`` is an injection seam for tests; it defaults to the real
    ``score_batch``. It receives the economics list and the same threshold
    keyword arguments.
    """
    if not isinstance(candidates, (list, tuple)):
        raise TypeError("candidates must be a list")
    for index, candidate in enumerate(candidates):
        if not isinstance(candidate, Mapping):
            raise TypeError("candidates[%d] must be a mapping" % index)
    if isinstance(roi_floor, bool) or not isinstance(roi_floor, (int, float)):
        raise TypeError("roi_floor must be a number")
    if isinstance(min_monthly_sales, bool) or not isinstance(min_monthly_sales, int):
        raise TypeError("min_monthly_sales must be an integer")
    if limit is not None and (isinstance(limit, bool) or not isinstance(limit, int)):
        raise TypeError("limit must be an integer or None")
    if limit is not None and limit < 1:
        return {
            "ok": False,
            "tool": TOOL_GOLDEN_GOOSE_SCAN,
            "reason": "limit must be >= 1",
        }

    if not candidates:
        return {
            "ok": False,
            "tool": TOOL_GOLDEN_GOOSE_SCAN,
            "reason": "no candidates supplied",
        }

    gg = _golden_goose()
    economics = [_economics_from_candidate(c) for c in candidates]
    ranker = scorer if scorer is not None else gg["score_batch"]
    try:
        scored = ranker(
            economics,
            roi_floor=float(roi_floor),
            min_monthly_sales=min_monthly_sales,
            include_rejected=bool(include_rejected),
        )
    except Exception as exc:  # noqa: BLE001 - scorer failure, surfaced honestly
        return {
            "ok": False,
            "tool": TOOL_GOLDEN_GOOSE_SCAN,
            "reason": "scoring failed: %s: %s" % (type(exc).__name__, exc),
        }

    scored = list(scored or [])
    if not scored:
        return {
            "ok": False,
            "tool": TOOL_GOLDEN_GOOSE_SCAN,
            "reason": (
                "no candidates survived Golden Goose selection "
                "(all REJECT-tier; roi_floor=$%.2f, min_monthly_sales=%d)"
                % (float(roi_floor), min_monthly_sales)
            ),
        }

    if limit is not None:
        scored = scored[:limit]

    summary = gg["get_scoring_summary"](scored)
    best = summary.pop("best_opportunity", None)
    summary["best_asin"] = getattr(best, "asin", None)
    summary["best_composite_score"] = getattr(best, "composite_score", None)

    return {
        "ok": True,
        "tool": TOOL_GOLDEN_GOOSE_SCAN,
        "data": {
            "evaluated": len(candidates),
            "returned": len(scored),
            "roi_floor": float(roi_floor),
            "min_monthly_sales": min_monthly_sales,
            "include_rejected": bool(include_rejected),
            "summary": summary,
            "opportunities": [_opportunity_dict(s) for s in scored],
        },
    }


TOOLS = {
    TOOL_CATALOG_PULL: catalog_pull,
    TOOL_GOLDEN_GOOSE_SCAN: golden_goose_scan,
}
