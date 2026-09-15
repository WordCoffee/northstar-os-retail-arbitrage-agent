"""Competitor Crowding Detector — tracks seller count changes over time.

Detects when competitor activity increases (crowding) or decreases
(opening) for tracked ASINs. Uses BSR history data to identify
patterns that affect sourcing decisions.

Signals:
- seller_count_change: significant change in seller count
- new_fba_sellers: FBA sellers appearing (increased competition)
- price_war: multiple sellers dropping prices simultaneously
- buy_box_instability: frequent buy box changes
"""

import json
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple
from pathlib import Path

_BACKEND_DIR = Path(__file__).resolve().parent


def detect_crowding(asin: str, history_days: int = 30) -> Dict[str, Any]:
    """Analyze seller count trends for an ASIN.

    Returns crowding signal with severity and recommendation.
    """
    try:
        from bsr_history import get_history, compute_volatility
    except ImportError:
        return {"signal": "unavailable", "reason": "bsr_history module not found"}

    history = get_history(asin, days=history_days)
    if len(history) < 2:
        return {
            "signal": "insufficient_data",
            "data_points": len(history),
            "recommendation": "Need more data points to detect crowding",
        }

    # Analyze seller count changes
    seller_counts = [(s.get("date"), s.get("seller_count")) for s in history if s.get("seller_count") is not None]
    prices = [(s.get("date"), s.get("price")) for s in history if s.get("price") is not None]

    crowding_signals = []
    severity = "low"

    # Seller count trend
    if len(seller_counts) >= 2:
        recent_avg = sum(sc for _, sc in seller_counts[-5:]) / min(5, len(seller_counts[-5:]))
        older_avg = sum(sc for _, sc in seller_counts[:5]) / min(5, len(seller_counts[:5]))
        if older_avg > 0:
            change_pct = (recent_avg - older_avg) / older_avg * 100
            if change_pct > 50:
                crowding_signals.append({
                    "type": "seller_surge",
                    "change_pct": round(change_pct, 1),
                    "severity": "high",
                })
                severity = "high"
            elif change_pct > 20:
                crowding_signals.append({
                    "type": "seller_increase",
                    "change_pct": round(change_pct, 1),
                    "severity": "medium",
                })
                if severity != "high":
                    severity = "medium"
            elif change_pct < -30:
                crowding_signals.append({
                    "type": "seller_decrease",
                    "change_pct": round(change_pct, 1),
                    "severity": "opportunity",
                })

    # Price war detection (multiple price drops)
    if len(prices) >= 3:
        recent_prices = [p for _, p in prices[-3:]]
        if all(recent_prices[i] < recent_prices[i-1] for i in range(1, len(recent_prices))):
            crowding_signals.append({
                "type": "price_war",
                "recent_prices": recent_prices,
                "severity": "high",
            })
            severity = "high"

    # Volatility check
    vol = compute_volatility(asin, days=history_days)
    if vol.get("price_volatility") and vol["price_volatility"] > 0.15:
        crowding_signals.append({
            "type": "high_price_volatility",
            "volatility": vol["price_volatility"],
            "severity": "medium",
        })
        if severity != "high":
            severity = "medium"

    # Determine recommendation
    if severity == "high":
        recommendation = "HIGH COMPETITION — consider reducing order quantity or waiting for stabilization"
    elif severity == "medium":
        recommendation = "MODERATE COMPETITION — proceed with caution, monitor closely"
    elif severity == "opportunity":
        recommendation = "OPPORTUNITY — competitors leaving, consider increasing inventory"
    else:
        recommendation = "LOW COMPETITION — standard ordering recommended"

    return {
        "asin": asin,
        "signal": severity,
        "signals": crowding_signals,
        "recommendation": recommendation,
        "data_points": len(history),
        "history_days": history_days,
        "volatility": vol,
        "analyzed_at": datetime.now(timezone.utc).isoformat(),
    }


def batch_detect(asins: List[str], history_days: int = 30) -> Dict[str, Dict]:
    """Run crowding detection on multiple ASINs."""
    results = {}
    for asin in asins:
        results[asin] = detect_crowding(asin, history_days=history_days)
    return results
