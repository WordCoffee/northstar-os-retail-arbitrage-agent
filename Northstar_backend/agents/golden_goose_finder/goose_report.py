"""Golden Goose Finder — report generation and exports.

Builds the JSON report (v1.0 schema), a human-readable summary.txt,
a console table for terminal display, and the SourceScout UI row exports
from scored opportunities. Only :func:`save_report` writes files; every
other function here is pure.

Honesty rules (mirrored from the rest of the backend): absent values stay
null (never 0); fee components we do not have the breakdown for stay null
instead of being invented; gating status is a display heuristic derived
only from observed seller presence, never asserted as fact.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from .opportunity_scorer import (
    TIER_HIGH,
    TIER_LOW,
    TIER_MEDIUM,
    TIER_REJECT,
    ScoredOpportunity,
    _as_pct,
    estimate_demand_fields,
    get_scoring_summary,
)

REPORT_VERSION = "1.0"

# Reports land in <repo>/reports/golden_goose/<timestamp>/.
_REPORTS_ROOT = Path(__file__).resolve().parents[3] / "reports" / "golden_goose"


# ---------------------------------------------------------------------------
# Small helpers.
# ---------------------------------------------------------------------------


def _round2(value: Optional[float]) -> Optional[float]:
    if value is None:
        return None
    return round(float(value), 2)


def _pct2(value: Optional[float]) -> Optional[float]:
    pct = _as_pct(value)
    return _round2(pct)


def _ranked(scored: List[ScoredOpportunity]) -> List[ScoredOpportunity]:
    return sorted(scored, key=lambda o: o.composite_score, reverse=True)


def _sales_estimate(economics) -> Optional[int]:
    fields = estimate_demand_fields(economics)
    if not fields:
        return None
    return fields.get("estimated_monthly_sales")


def _gating_status(fba_sellers: Optional[int]) -> str:
    """Display heuristic only — never a gating assertion.

    A live FBA seller count > 0 means the listing is demonstrably being
    sold via FBA; 0 sellers means an ungated seller would need to get
    approval (CAN_APPLY); unknown data -> UNKNOWN.
    """
    if fba_sellers is None:
        return "UNKNOWN"
    if fba_sellers > 0:
        return "APPROVED"
    return "CAN_APPLY"


def _competition_label(fba_sellers: Optional[int]) -> str:
    if fba_sellers is None:
        return "Unknown"
    if fba_sellers <= 1:
        return "Low"
    if fba_sellers <= 3:
        return "Medium"
    return "High"


def _panel_tier(tier: str) -> str:
    return {
        TIER_HIGH: "Pass",
        TIER_MEDIUM: "Hold",
        TIER_LOW: "Reject",
        TIER_REJECT: "Reject",
    }.get(tier, "Unscored")


# ---------------------------------------------------------------------------
# JSON report.
# ---------------------------------------------------------------------------


def _opportunity_entry(o: ScoredOpportunity) -> Dict[str, Any]:
    """One report entry for a scored opportunity (the full v1.0 schema)."""
    eco = o.economics
    ind = eco.individual
    ws = eco.wholesale

    fees = eco.total_amazon_fees
    costs = None if (eco.unit_cogs is None or fees is None) else eco.unit_cogs + fees

    notes = list(eco.economics_notes or []) + list(o.scoring_notes or [])
    if costs is not None and fees is not None:
        notes.append("breakeven approximated at the current fee level (fee split not provided)")

    return {
        "asin": ind.asin,
        "product_title": ind.title,
        "brand": ws.brand,
        "category": ws.category_slug,
        "gating_status": _gating_status(ind.fba_sellers),
        "amazon_metrics": {
            "est_monthly_sales": _sales_estimate(eco),
            "review_rating": ind.review_rating,
            "review_count": ind.review_count,
            "current_fba_sellers": ind.fba_sellers,
            "buy_box_price": _round2(ind.amazon_price),
            "bsr": ind.bsr,
        },
        "sourcing_data": {
            "source_store": (getattr(ws, "source_store", None) or "Unknown"),
            "wholesale_pack_title": getattr(ws, "wholesale_pack_title", None) or ws.brand,
            "wholesale_cost": _round2(ws.wholesale_price),
            "pack_count": ws.pack_count,
            "unit_cogs": _round2(eco.unit_cogs),
        },
        "financial_breakdown": {
            "resale_price": _round2(ind.amazon_price),
            "referral_fee": None,
            "fulfillment_fee": None,
            "repackaging_cost": None,
            "total_fees": _round2(fees),
            "total_costs_per_unit": _round2(costs),
            "net_profit_per_unit": _round2(eco.net_profit_per_unit),
            "net_profit_per_costco_pack": _round2(eco.net_profit_per_costco_pack),
            "roi_percentage": _pct2(eco.roi_per_unit),
            "roi_per_costco_pack_pct": _pct2(eco.roi_per_costco_pack),
            "profit_margin_pct": _pct2(eco.profit_margin_pct),
            "breakeven_price": _round2(costs),
        },
        "scoring": {
            "composite_score": round(o.composite_score, 4),
            "profit_score": round(o.profit_score, 4),
            "demand_score": round(o.demand_score, 4),
            "competition_score": round(o.competition_score, 4),
            "listing_health_score": round(o.listing_health_score, 4),
            "tier": o.tier,
            "tags": list(o.opportunity_tags),
        },
        "economics_confidence": eco.economics_confidence,
        "notes": notes,
    }


def _discarded_entry(o: ScoredOpportunity) -> Dict[str, str]:
    failed = []
    if not o.passes_profit_floor:
        failed.append("profit")
    if not o.passes_demand_floor:
        failed.append("demand")
    if not o.passes_competition_ceiling:
        failed.append("competition")
    if not o.passes_listing_health:
        failed.append("listing_health")
    reason = "Failed filters: %s" % ", ".join(failed) if failed else "Composite %.2f below 0.25" % o.composite_score
    return {
        "asin": o.economics.individual.asin,
        "title": o.economics.individual.title,
        "reason": reason,
        "details": "; ".join(o.scoring_notes),
    }


def _summary_dict(scored: List[ScoredOpportunity]) -> Dict[str, Any]:
    """JSON-safe version of get_scoring_summary() (best -> full entry)."""
    raw = get_scoring_summary(scored)
    best = raw["best_opportunity"]
    return {
        "total_evaluated": raw["total_evaluated"],
        "high": raw["high"],
        "medium": raw["medium"],
        "low": raw["low"],
        "rejected": raw["rejected"],
        "avg_profit": raw["avg_profit"],
        "avg_roi": raw["avg_roi"],
        "best_opportunity": (_opportunity_entry(best) if best is not None else None),
        "top_tags": raw["top_tags"],
    }


def generate_json_report(
    scored_opportunities: List[ScoredOpportunity],
    run_metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Generate a full JSON report in the Golden Goose Finder output schema.

    REJECT-tier results are moved into ``discarded``; the actionable list
    in ``opportunities`` only contains HIGH / MEDIUM / LOW entries (sorted
    by composite score descending).
    """
    ranked = _ranked(scored_opportunities)
    return {
        "report_version": REPORT_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "run_metadata": run_metadata or {},
        "summary": _summary_dict(scored_opportunities),
        "opportunities": [_opportunity_entry(o) for o in ranked if o.tier != TIER_REJECT],
        "discarded": [_discarded_entry(o) for o in ranked if o.tier == TIER_REJECT],
    }


# ---------------------------------------------------------------------------
# File saving (the only writing function in this module).
# ---------------------------------------------------------------------------


def save_report(report: Dict[str, Any], output_dir: Optional[str] = None) -> str:
    """Save a JSON report to reports/golden_goose/<timestamp>/ by default.

    Writes report.json plus a human-readable summary.txt alongside it.
    Returns the report.json path.
    """
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    base = Path(output_dir) if output_dir else _REPORTS_ROOT / timestamp
    base.mkdir(parents=True, exist_ok=True)

    json_path = base / "report.json"
    json_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )

    summary_path = base / "summary.txt"
    summary_path.write_text(_build_summary_text(report), encoding="utf-8")

    return str(json_path)


def _build_summary_text(report: Dict[str, Any]) -> str:
    summary = report.get("summary") or {}
    lines = [
        "Golden Goose Finder Report",
        "=" * 40,
        "Generated: %s" % report.get("generated_at", "?"),
        "Report version: %s" % report.get("report_version", "?"),
        "",
        "Summary: %d evaluated | HIGH %d | MEDIUM %d | LOW %d | REJECTED %d"
        % (
            summary.get("total_evaluated", 0),
            summary.get("high", 0),
            summary.get("medium", 0),
            summary.get("low", 0),
            summary.get("rejected", 0),
        ),
        "Avg profit/unit: $%.2f | Avg ROI: %.1f%%" % (summary.get("avg_profit", 0.0), summary.get("avg_roi", 0.0)),
    ]
    best = summary.get("best_opportunity")
    if isinstance(best, dict):
        lines.append(
            "Best: %s (%s) | tier %s | $%.2f/unit | composite %.4f"
            % (
                best.get("asin", "?"),
                best.get("product_title", "?")[:60],
                (best.get("scoring") or {}).get("tier", "?"),
                (best.get("financial_breakdown") or {}).get("net_profit_per_unit", 0.0),
                (best.get("scoring") or {}).get("composite_score", 0.0),
            )
        )
    if summary.get("top_tags"):
        tag_str = ", ".join("%s x%d" % (k, v) for k, v in sorted(summary["top_tags"].items()))
        lines.append("Top tags: %s" % tag_str)

    opportunities = report.get("opportunities") or []
    lines += ["", "--- Ranked opportunities (%d) ---" % len(opportunities)]
    for i, entry in enumerate(opportunities, start=1):
        eco = entry.get("financial_breakdown") or {}
        metrics = entry.get("amazon_metrics") or {}
        net_val = eco.get("net_profit_per_unit")
        roi_val = eco.get("roi_percentage")
        net_str = "%.2f" % net_val if isinstance(net_val, (int, float)) else str(net_val)
        roi_str = "%.1f" % roi_val if isinstance(roi_val, (int, float)) else str(roi_val)
        lines.append(
            "%d. %s | %s | %s | $%s net/unit | ROI %s%% | ~%s/mo | %s FBA"
            % (
                i,
                entry.get("asin", "?"),
                (entry.get("scoring") or {}).get("tier", "?"),
                (entry.get("product_title") or "?")[:60],
                net_str,
                roi_str,
                metrics.get("est_monthly_sales", "?"),
                metrics.get("current_fba_sellers", "?"),
            )
        )

    discarded = report.get("discarded") or []
    if discarded:
        lines += ["", "--- Discarded (%d) ---" % len(discarded)]
        for d in discarded:
            lines.append("- %s | %s | %s" % (d.get("asin", "?"), d.get("reason", "?"), d.get("title", "?")))

    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Console display.
# ---------------------------------------------------------------------------

_TIER_COLORS = {
    TIER_HIGH: "\x1b[32m",   # green
    TIER_MEDIUM: "\x1b[33m",  # yellow
    TIER_LOW: "\x1b[35m",     # magenta
    TIER_REJECT: "\x1b[31m",  # red
}
_RESET = "\x1b[0m"

_COLUMNS = ["Rank", "ASIN", "Brand", "Product", "Profit", "ROI", "Score", "Tier", "Monthly", "FBA"]
_RIGHT_ALIGN = {0, 4, 5, 6, 8, 9}  # numeric columns


def _cell(text: str, width: int, right: bool) -> str:
    if right:
        return text.rjust(width)
    return text.ljust(width)


def generate_console_display(scored: List[ScoredOpportunity]) -> str:
    """Formatted text table for terminal display, ranked by composite score.

    Tiers are color-coded with ANSI escape codes only when stdout is a
    real terminal, so piped/CI output stays clean.
    """
    use_color = bool(getattr(sys.stdout, "isatty", lambda: False)())
    ranked = _ranked(scored)

    rows: List[List[str]] = []
    for i, o in enumerate(ranked, start=1):
        eco = o.economics
        ind = eco.individual
        ws = eco.wholesale
        sales = _sales_estimate(eco)
        rows.append([
            str(i),
            (ind.asin or "N/A")[:12],
            (ws.brand or "Unknown")[:16],
            ((ind.title or "")[:26] or "Untitled"),
            "$%.2f" % eco.net_profit_per_unit if eco.net_profit_per_unit is not None else "-",
            "%.1f%%" % _as_pct(eco.roi_per_unit) if eco.roi_per_unit is not None else "-",
            "%.2f" % o.composite_score,
            o.tier,
            "%d" % sales if sales is not None else "-",
            "%d" % ind.fba_sellers if ind.fba_sellers is not None else "-",
        ])

    if not rows:
        return " | ".join(_COLUMNS) + "\n(no opportunities)\n"

    widths = [len(h) for h in _COLUMNS]
    for row in rows:
        for j, cell in enumerate(row):
            widths[j] = max(widths[j], len(cell))

    lines = [" | ".join(_cell(h, widths[j], False) for j, h in enumerate(_COLUMNS))]
    lines.append("-+-".join("-" * w for w in widths))
    for row in rows:
        cells = []
        for j, cell in enumerate(row):
            if j == 7 and use_color:  # tier column
                cell = "%s%s%s" % (_TIER_COLORS.get(cell, ""), cell, _RESET if _TIER_COLORS.get(cell) else "")
            cells.append(_cell(cell, widths[j], j in _RIGHT_ALIGN))
        lines.append(" | ".join(cells))
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# SourceScout UI panel export.
# ---------------------------------------------------------------------------


def export_to_scout_panel(scored: List[ScoredOpportunity]) -> List[Dict[str, Any]]:
    """Export scored opportunities to the SourceScout UI panel row model.

    Ranked by composite score descending. Reject-tier rows are included
    (mapped to tier "Reject") so the panel can show why they failed.
    """
    rows: List[Dict[str, Any]] = []
    for o in _ranked(scored):
        eco = o.economics
        ind = eco.individual
        ws = eco.wholesale
        rows.append({
            "id": ind.asin or "",
            "asin": ind.asin or "",
            "name": ind.title or "",
            "brand": ws.brand or "Unknown",
            "cost": _round2(eco.unit_cogs),
            "amazonPrice": _round2(ind.amazon_price),
            "fbaFee": _round2(eco.total_amazon_fees),
            "net": _round2(eco.net_profit_per_unit),
            "roi": _round2(_as_pct(eco.roi_per_unit)),
            "competition": _competition_label(ind.fba_sellers),
            "estMonthly": _sales_estimate(eco),
            "tier": _panel_tier(o.tier),
            "status": "scored",
            "sourceStore": getattr(ws, "source_store", None) or "Unknown",
            "wholesalePack": getattr(ws, "wholesale_pack_title", None) or ws.brand or "Unknown",
            "packCount": ws.pack_count,
            "tags": list(o.opportunity_tags),
        })
    return rows