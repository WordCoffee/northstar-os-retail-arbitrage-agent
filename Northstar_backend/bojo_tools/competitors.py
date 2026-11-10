"""Competitor tools for Bojo — the Competitor Monitor's snapshot store.

``watch_competitor`` wraps ``market_snapshot_store``: the per-ASIN market
snapshot store the Product Scout writes (buy box, returned offers, observed
seller counts, data status, per-stage freshness). Reading it is zero network —
it is the local file the enrichment run already persisted — and the honesty
rules are the store's own: a field the provider never returned stays absent,
observed counts are kept distinct from the claimed count, and a snapshot older
than its freshness window is reported ``stale`` rather than silently trusted.

Nothing is re-implemented here: ``get_snapshot`` validates the ASIN pattern,
``snapshot_freshness_status`` reads the per-stage deadline and
``is_fresh_success`` decides what counts as a successful observation.

Contract::

    {"ok": True,  "tool": "<name>", "data": {...}}
    {"ok": False, "tool": "<name>", "reason": "<reason string>"}

Business failures — no stored observation for any requested ASIN, or a store
that cannot be read — return ``ok=False``. Programmer errors in the argument
contract raise ``TypeError``/``ValueError``.
"""

from __future__ import annotations

import os
import sys
from functools import lru_cache
from typing import Any, Dict, List, Mapping, Optional

from ._coerce import text

TOOL_WATCH_COMPETITOR = "watch_competitor"

#: Freshness stages the store keeps a separate deadline for.
STAGES = ("offers", "sales", "identity")


def _backend_root() -> str:
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _ensure_backend_on_path() -> None:
    root = _backend_root()
    if root not in sys.path:
        sys.path.insert(0, root)


@lru_cache(maxsize=1)
def _default_store() -> Any:
    """The real snapshot store (local file, zero network)."""
    _ensure_backend_on_path()
    import market_snapshot_store

    return market_snapshot_store


def _bad(reason: str) -> Dict[str, Any]:
    return {"ok": False, "tool": TOOL_WATCH_COMPETITOR, "reason": reason}


def _asins(value: Any) -> List[str]:
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, (list, tuple)):
        raise TypeError("asins must be a string or a list of strings")
    out: List[str] = []
    for item in value:
        if not isinstance(item, str):
            raise TypeError("asins entries must be strings")
        written = item.strip()
        if written and written not in out:
            out.append(written)
    return out


def _observation(store: Any, asin: str, stage: str) -> Dict[str, Any]:
    snapshot = store.get_snapshot(asin)
    if not isinstance(snapshot, Mapping):
        return {"asin": asin, "observed": False}
    seller_counts = snapshot.get("seller_counts")
    return {
        "asin": asin,
        "observed": True,
        "title": snapshot.get("title"),
        "data_status": snapshot.get("data_status"),
        "freshness": store.snapshot_freshness_status(dict(snapshot), stage),
        "fresh_success": bool(store.is_fresh_success(dict(snapshot))),
        "observed_at": snapshot.get("observed_at"),
        "fetched_at": snapshot.get("fetched_at"),
        "buy_box": snapshot.get("buy_box") if isinstance(snapshot.get("buy_box"), Mapping) else None,
        "seller_counts": dict(seller_counts) if isinstance(seller_counts, Mapping) else None,
        "offers_returned": snapshot.get("offers_returned"),
        "offers_complete": snapshot.get("offers_complete"),
        "stages": snapshot.get("stages") if isinstance(snapshot.get("stages"), Mapping) else None,
        "data_gaps": [str(g) for g in (snapshot.get("data_gaps") or [])],
        "last_error": snapshot.get("last_error"),
    }


def watch_competitor(
    asins: Any,
    stage: str = "offers",
    store: Optional[Any] = None,
) -> Dict[str, Any]:
    """Report the stored competitor observation for each ASIN.

    ``asins`` is one ASIN string or a list of them. ``stage`` selects which
    freshness deadline decides fresh vs stale (``offers``, ``sales`` or
    ``identity``).

    ``store`` is an injectable dependency: anything exposing
    ``get_snapshot(asin)``, ``snapshot_freshness_status(snapshot, stage)`` and
    ``is_fresh_success(snapshot)``. It defaults to the real
    ``market_snapshot_store`` module, so a test never touches disk.
    """
    if not isinstance(stage, str):
        raise TypeError("stage must be a string")
    written_stage = stage.strip().lower()
    if written_stage not in STAGES:
        raise ValueError("stage must be one of %s" % ", ".join(STAGES))
    wanted = _asins(asins)
    if not wanted:
        return _bad("no ASINs supplied")

    client = store if store is not None else _default_store()
    observations: List[Dict[str, Any]] = []
    for asin in wanted:
        try:
            observations.append(_observation(client, asin, written_stage))
        except Exception as exc:  # noqa: BLE001 - store failure, surfaced honestly
            return _bad(
                "competitor snapshot read failed for %s: %s: %s"
                % (asin, type(exc).__name__, exc)
            )

    found = [o for o in observations if o.get("observed")]
    if not found:
        return _bad(
            "no stored competitor observation for %s"
            % ", ".join(wanted)
        )

    fresh = [o for o in found if o.get("freshness") == "fresh"]
    stale = [o for o in found if o.get("freshness") == "stale"]
    unknown = [o for o in found if o.get("freshness") == "unknown"]
    missing = [text(o.get("asin")) for o in observations if not o.get("observed")]

    return {
        "ok": True,
        "tool": TOOL_WATCH_COMPETITOR,
        "data": {
            "stage": written_stage,
            "watched": len(wanted),
            "found": len(found),
            "fresh": len(fresh),
            "stale": len(stale),
            "freshness_unknown": len(unknown),
            "missing": missing,
            "observations": observations,
        },
    }


TOOLS = {TOOL_WATCH_COMPETITOR: watch_competitor}
