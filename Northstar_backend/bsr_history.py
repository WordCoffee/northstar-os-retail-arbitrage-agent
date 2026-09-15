"""BSR & Price Snapshot Store — Keepa-style historical tracking.

Stores daily BSR, price, seller count, and review count snapshots
per ASIN. Enables trend analysis, volatility scoring, and historical
charts for the SourceScout dashboard.

Schema (stored as JSON with SQLite backing):
    {
        "<asin>": {
            "snapshots": [
                {"date": "2026-09-15", "bsr": 1234, "price": 19.99,
                 "seller_count": 5, "review_count": 142, "rating": 4.5,
                 "source": "bright_data"}
            ],
            "last_updated": "2026-09-15T16:00:00Z"
        }
    }
"""

import json
import os
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple
from pathlib import Path

_BACKEND_DIR = Path(__file__).resolve().parent
_DEFAULT_STORE = _BACKEND_DIR / "data" / "bsr_price_history.json"

# How many days of history to retain (rolling window)
RETENTION_DAYS = 365


def _store_path() -> str:
    raw = os.getenv("BSR_HISTORY_PATH")
    if raw:
        return raw if os.path.isabs(raw) else str(_BACKEND_DIR / raw)
    return str(_DEFAULT_STORE)


def _load_store() -> Dict[str, Any]:
    path = _store_path()
    if not os.path.isfile(path):
        return {"schema_version": 1, "generated_at": None, "asins": {}}
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        if "asins" not in data:
            data["asins"] = {}
        return data
    except (json.JSONDecodeError, OSError, ValueError):
        return {"schema_version": 1, "generated_at": None, "asins": {}}


def _save_store(data: Dict[str, Any]) -> None:
    path = _store_path()
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    data["generated_at"] = datetime.now(timezone.utc).isoformat()
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    os.replace(tmp, path)


def record_snapshot(
    asin: str,
    bsr: Optional[int] = None,
    price: Optional[float] = None,
    seller_count: Optional[int] = None,
    review_count: Optional[int] = None,
    rating: Optional[float] = None,
    source: str = "unknown",
    date: Optional[str] = None,
) -> Dict[str, Any]:
    """Record a daily snapshot for an ASIN. Idempotent per date —
    a second call for the same ASIN+date overwrites the previous."""
    if not asin:
        raise ValueError("asin is required")

    date = date or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    store = _load_store()
    asins = store.setdefault("asins", {})
    entry = asins.setdefault(asin, {"snapshots": [], "last_updated": None})

    # Replace existing snapshot for same date
    snapshots = entry["snapshots"]
    replaced = False
    for i, snap in enumerate(snapshots):
        if snap.get("date") == date:
            snapshots[i] = {
                "date": date,
                "bsr": bsr,
                "price": price,
                "seller_count": seller_count,
                "review_count": review_count,
                "rating": rating,
                "source": source,
            }
            replaced = True
            break

    if not replaced:
        snapshots.append({
            "date": date,
            "bsr": bsr,
            "price": price,
            "seller_count": seller_count,
            "review_count": review_count,
            "rating": rating,
            "source": source,
        })

    # Sort by date and prune old entries
    snapshots.sort(key=lambda s: s.get("date", ""))
    cutoff = (datetime.now(timezone.utc) - timedelta(days=RETENTION_DAYS)).strftime("%Y-%m-%d")
    entry["snapshots"] = [s for s in snapshots if s.get("date", "") >= cutoff]
    entry["last_updated"] = datetime.now(timezone.utc).isoformat()

    _save_store(store)
    return {"asin": asin, "date": date, "recorded": True}


def get_history(asin: str, days: int = 90) -> List[Dict[str, Any]]:
    """Get snapshot history for an ASIN, most recent first."""
    store = _load_store()
    entry = store.get("asins", {}).get(asin, {})
    snapshots = entry.get("snapshots", [])

    if days > 0:
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d")
        snapshots = [s for s in snapshots if s.get("date", "") >= cutoff]

    return list(reversed(snapshots))


def get_latest(asin: str) -> Optional[Dict[str, Any]]:
    """Get the most recent snapshot for an ASIN."""
    history = get_history(asin, days=7)
    return history[0] if history else None


def compute_volatility(asin: str, days: int = 90) -> Dict[str, Any]:
    """Compute price and BSR volatility metrics for an ASIN.

    Returns:
        price_volatility: std_dev / mean of daily prices (coefficient of variation)
        bsr_volatility: std_dev / mean of daily BSR ranks
        price_range: (min, max) over the period
        bsr_range: (min, max) over the period
        trend: "rising", "falling", "stable", or "insufficient_data"
        data_points: number of snapshots analyzed
    """
    history = get_history(asin, days=days)
    if len(history) < 2:
        return {
            "price_volatility": None,
            "bsr_volatility": None,
            "price_range": None,
            "bsr_range": None,
            "trend": "insufficient_data",
            "data_points": len(history),
        }

    prices = [s["price"] for s in history if s.get("price") is not None]
    bsrs = [s["bsr"] for s in history if s.get("bsr") is not None]

    def _cv(values: List[float]) -> Optional[float]:
        if len(values) < 2:
            return None
        mean = sum(values) / len(values)
        if mean == 0:
            return None
        variance = sum((x - mean) ** 2 for x in values) / (len(values) - 1)
        return (variance ** 0.5) / mean

    def _range(values: List[float]) -> Optional[Tuple[float, float]]:
        if not values:
            return None
        return (min(values), max(values))

    def _trend(values: List[float]) -> str:
        if len(values) < 3:
            return "insufficient_data"
        # Simple linear regression slope
        n = len(values)
        x_mean = (n - 1) / 2
        y_mean = sum(values) / n
        numerator = sum((i - x_mean) * (values[i] - y_mean) for i in range(n))
        denominator = sum((i - x_mean) ** 2 for i in range(n))
        if denominator == 0:
            return "stable"
        slope = numerator / denominator
        # Normalize slope relative to mean
        if abs(slope) < abs(y_mean) * 0.01:
            return "stable"
        return "rising" if slope > 0 else "falling"

    return {
        "price_volatility": round(_cv(prices), 4) if prices else None,
        "bsr_volatility": round(_cv(bsrs), 4) if bsrs else None,
        "price_range": _range(prices),
        "bsr_range": _range(bsrs),
        "trend": _trend(bsrs) if bsrs else "insufficient_data",
        "data_points": len(history),
    }


def batch_record(snapshots: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Record multiple snapshots at once. Each dict must have 'asin' key."""
    recorded = 0
    errors = 0
    for snap in snapshots:
        try:
            record_snapshot(
                asin=snap["asin"],
                bsr=snap.get("bsr"),
                price=snap.get("price"),
                seller_count=snap.get("seller_count"),
                review_count=snap.get("review_count"),
                rating=snap.get("rating"),
                source=snap.get("source", "batch"),
                date=snap.get("date"),
            )
            recorded += 1
        except Exception:
            errors += 1
    return {"recorded": recorded, "errors": errors, "total": len(snapshots)}


def summary() -> Dict[str, Any]:
    """Summary statistics for the snapshot store."""
    store = _load_store()
    asins = store.get("asins", {})
    total_snapshots = sum(len(a.get("snapshots", [])) for a in asins.values())
    return {
        "total_asins": len(asins),
        "total_snapshots": total_snapshots,
        "store_path": _store_path(),
        "last_updated": store.get("generated_at"),
    }
