"""Non-creative read-only API surface.

Read-only projections over the existing local SQLite data (products, costco_*
pipeline tables, keywords, listings, memory, audit, refresh metadata). No writes,
no external calls, no secrets (password_hash is never selected). Every endpoint
degrades to an honest empty result if a table is missing.

Mounted additively from main.py under /api/v1/noncreative.
"""
from __future__ import annotations

import functools
import json
from typing import Any, Optional

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

router = APIRouter(prefix="/api/v1/noncreative", tags=["noncreative"])


class DataUnavailable(Exception):
    """A read failed. Never silently presented as an empty result.

    P1-01: the distinction between "no rows" and "the query failed" is the
    whole point — an unknown must never be reported as a confident zero.
    """


def _unavailable(kind: str, reason: str) -> JSONResponse:
    """The honest error envelope for a failed read."""
    return JSONResponse(
        status_code=503,
        content={
            "kind": kind,
            "status": "unavailable",
            "reason": reason,
            "count": None,
            "items": [],
            "note": (
                "This projection could not be read. The data is UNKNOWN, "
                "not empty. No value on this surface should be treated as a "
                "real zero."
            ),
        },
    )


def _db():
    from data_layer import get_db
    return get_db()


def _rows(sql: str, params: tuple = ()) -> list[dict]:
    """Run a read-only query and return list[dict].

    P1-01 (2026-10-09): this used to return ``[]`` on ANY failure, which is
    indistinguishable from "the table is genuinely empty" — an unknown became a
    confident zero. It now raises ``DataUnavailable`` so the caller can surface
    an honest error state instead of a fake empty list.
    """
    try:
        conn = _db()
        cur = conn.execute(sql, params)
        cols = [c[0] for c in cur.description] if cur.description else []
        return [dict(zip(cols, r)) for r in cur.fetchall()]
    except Exception as exc:
        raise DataUnavailable(f"noncreative read failed: {exc.__class__.__name__}") from exc


def _scalar(sql: str, params: tuple = ()) -> Optional[Any]:
    """Run a read-only scalar query.

    P1-01: same contract as :func:`_rows` — a failure raises
    ``DataUnavailable`` rather than masquerading as ``None``.
    """
    try:
        conn = _db()
        row = conn.execute(sql, params).fetchone()
        return row[0] if row else None
    except Exception as exc:
        raise DataUnavailable(f"noncreative scalar failed: {exc.__class__.__name__}") from exc


def _safe_rows(sql: str, params: tuple = ()) -> tuple[list[dict], Optional[str]]:
    """``(rows, None)`` on success or ``([], reason)`` on failure.

    For the OPTIONAL projections where an empty answer is a legitimate state
    (a table the operator never populated). The reason is carried out so the
    caller can still label it honestly.
    """
    try:
        return _rows(sql, params), None
    except DataUnavailable as exc:
        return [], str(exc)


def _loads(value, default):
    if value is None:
        return default
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(value)
    except (ValueError, TypeError):
        return default


def _env(kind: str, items: list, summary: dict) -> dict:
    return {"kind": kind, "count": len(items), "items": items, "summary": summary}


def _honest_read(kind: str):
    """Wrap a projection so a failed read is a 503, never a fake empty list.

    P1-01: ``_rows``/``_scalar`` now raise ``DataUnavailable``. This decorator
    turns that into an explicit ``unavailable`` envelope carrying the reason,
    so the UI can render an error state instead of a confident zero.
    """
    def _wrap(fn):
        @functools.wraps(fn)
        def _inner(*args, **kwargs):
            try:
                return fn(*args, **kwargs)
            except DataUnavailable as exc:
                return _unavailable(kind, str(exc))
        return _inner
    return _wrap

# ── Commerce Ops: identity / pack resolution workflow ────────────────────────
@router.get("/commerce-ops/queue")
@_honest_read('commerce_ops_queue')
def commerce_ops_queue(limit: int = Query(default=200, le=500)):
    q = _rows(
        "SELECT id, run_id, costco_item_number, missing_identity_fields, "
        "missing_physical_fields, possible_next_source, title_only_insufficient, "
        "physical_pack_missing, created_at FROM costco_identifier_resolution_queue "
        "ORDER BY created_at DESC LIMIT ?", (limit,))
    runs = _rows(
        "SELECT run_id, run_name, status, created_at, counts_json "
        "FROM costco_pipeline_runs ORDER BY created_at DESC LIMIT 20")
    for r in runs:
        c = _loads(r.pop("counts_json", None), {})
        r["discovered"] = c.get("discovered")
        r["eligible"] = c.get("eligible")
        r["manual_review_required"] = c.get("manual_review_required")
    summary = {
        "queue_total": len(q),
        "title_only_insufficient": sum(1 for r in q if r.get("title_only_insufficient")),
        "physical_pack_missing": sum(1 for r in q if r.get("physical_pack_missing")),
        "runs": len(runs),
    }
    return _env("commerce_ops_queue", q, {**summary, "recent_runs": runs})


# ── Listing Guardian: listing + identity-enrichment health ───────────────────
@router.get("/listings/health")
@_honest_read('listings_health')
def listings_health(limit: int = Query(default=200, le=500)):
    listings = _rows(
        "SELECT id, asin, version, title, status, overall_score, seo_score, "
        "conversion_score, compliance_score, visual_score, rufus_score, updated_at "
        "FROM listings ORDER BY updated_at DESC LIMIT ?", (limit,))
    enrich = _rows(
        "SELECT costco_item_number, source_product_id, provider_name, brand, "
        "identifier_capture_status, freshness_status, split_pack_status, captured_at "
        "FROM costco_identity_enrichment ORDER BY captured_at DESC LIMIT ?", (limit,))
    by_capture: dict = {}
    for e in enrich:
        k = e.get("identifier_capture_status") or "unknown"
        by_capture[k] = by_capture.get(k, 0) + 1
    by_fresh: dict = {}
    for e in enrich:
        k = e.get("freshness_status") or "unknown"
        by_fresh[k] = by_fresh.get(k, 0) + 1
    evidence = _scalar("SELECT COUNT(*) FROM costco_evidence")
    summary = {
        "listings": len(listings),
        "enrichment_records": len(enrich),
        "evidence_rows": evidence or 0,
        "identifier_capture": by_capture,
        "freshness": by_fresh,
    }
    return _env("listings_health", listings, {**summary, "enrichment": enrich})


# ── Competitor Monitor: catalog / market observations ────────────────────────
@router.get("/competitor/observations")
@_honest_read('competitor_observations')
def competitor_observations(limit: int = Query(default=200, le=500)):
    products = _rows(
        "SELECT asin, title, brand, category, marketplace, amazon_price, "
        "buy_box_price, costco_cost, bsr_rank, seller_count, net_profit, roi_pct, "
        "data_kind, fetched_at FROM products ORDER BY created_at DESC LIMIT ?", (limit,))
    source = _rows(
        "SELECT costco_item_number, title_normalized, brand_normalized, costco_price, "
        "currency, availability_status, freshness_status, identity_status, "
        "exclusion_reason, observed_at FROM costco_source_products "
        "ORDER BY imported_at DESC LIMIT ?", (limit,))
    priced = [s.get("costco_price") for s in source if isinstance(s.get("costco_price"), (int, float))]
    summary = {
        "products": len(products),
        "source_products": len(source),
        "source_with_price": len(priced),
        "source_avg_price": (round(sum(priced) / len(priced), 2) if priced else None),
        "distinct_brands": len({(s.get("brand_normalized") or "").lower() for s in source if s.get("brand_normalized")}),
    }
    return _env("competitor_observations", products, {**summary, "source_products": source})


# ── Command Center: real activity feed ───────────────────────────────────────
@router.get("/activity")
@_honest_read('activity')
def activity(limit: int = Query(default=50, le=200)):
    runs = _rows(
        "SELECT run_id, run_name, command, status, created_at, error_summary "
        "FROM costco_pipeline_runs ORDER BY created_at DESC LIMIT ?", (limit,))
    audit = _rows(
        "SELECT action, entity_type, entity_id, created_at FROM audit_log "
        "ORDER BY created_at DESC LIMIT ?", (limit,))
    campaigns = _rows(
        "SELECT campaign_name, campaign_type, status, spend, revenue, acos "
        "FROM campaigns ORDER BY updated_at DESC LIMIT ?", (limit,))
    summary = {"pipeline_runs": len(runs), "audit_entries": len(audit), "campaigns": len(campaigns)}
    return _env("activity", runs, {**summary, "audit": audit, "campaigns": campaigns})


# ── Keyword Tracker: real keyword sets + performance ─────────────────────────
@router.get("/keywords")
@_honest_read('keywords')
def keywords(limit: int = Query(default=200, le=500)):
    kws = _rows(
        "SELECT id, keyword, search_volume, relevance_score, trend_direction, "
        "competition_level, associated_asins, source, created_at FROM keywords "
        "ORDER BY search_volume DESC LIMIT ?", (limit,))
    perf = _rows(
        "SELECT keyword_id, asin, organic_rank, sponsored_rank, impressions, clicks, "
        "spend, orders, revenue, acos, tier, movement, days_in_tier, recorded_at "
        "FROM keyword_performance ORDER BY recorded_at DESC LIMIT ?", (limit,))
    rising = sum(1 for k in kws if (k.get("trend_direction") or "").lower() in ("rising", "up"))
    summary = {
        "keywords": len(kws),
        "performance_rows": len(perf),
        "rising": rising,
        "total_search_volume": sum(k.get("search_volume") or 0 for k in kws),
    }
    return _env("keywords", kws, {**summary, "performance": perf})


# ── Shared Data Layer: source freshness / refresh registry ───────────────────
@router.get("/sources")
@_honest_read('sources')
def sources(limit: int = Query(default=100, le=300)):
    refresh = _rows(
        "SELECT provider, refresh_type, status, started_at, finished_at, "
        "records_imported, records_updated, records_failed, credits_used, error_message "
        "FROM refresh_metadata ORDER BY started_at DESC LIMIT ?", (limit,))
    pulls = _rows(
        "SELECT query, task_type, provider_id, credits_used, rows_returned, ok, "
        "started_at, finished_at FROM live_pulls ORDER BY started_at DESC LIMIT ?", (limit,))
    runs = _rows(
        "SELECT run_id, run_name, status, created_at FROM costco_pipeline_runs "
        "ORDER BY created_at DESC LIMIT ?", (limit,))
    summary = {"refresh_records": len(refresh), "live_pulls": len(pulls), "pipeline_runs": len(runs)}
    return _env("sources", refresh, {**summary, "live_pulls": pulls, "pipeline_runs": runs})


# ── Master Brain: knowledge-plane sessions view ──────────────────────────────
@router.get("/sessions")
@_honest_read('sessions')
def sessions(limit: int = Query(default=100, le=300)):
    mem = _rows(
        "SELECT id, entry_type, content, source, confidence, created_at "
        "FROM memory_entries WHERE retired_at IS NULL ORDER BY created_at DESC LIMIT ?", (limit,))
    audit = _rows(
        "SELECT action, entity_type, created_at FROM audit_log "
        "ORDER BY created_at DESC LIMIT ?", (limit,))
    by_type: dict = {}
    for m in mem:
        k = m.get("entry_type") or "unknown"
        by_type[k] = by_type.get(k, 0) + 1
    summary = {"memory_entries": len(mem), "audit_entries": len(audit), "by_type": by_type}
    return _env("sessions", mem, {**summary, "audit": audit})


# ── Beta-Ops: real account/activity counts ───────────────────────────────────
@router.get("/accounts")
@_honest_read('accounts')
def accounts(limit: int = Query(default=100, le=300)):
    users = _rows(
        "SELECT id, email, plan, role, is_active, created_at, last_login_at "
        "FROM users ORDER BY created_at DESC LIMIT ?", (limit,))
    sessions_rows = _rows(
        "SELECT user_id, created_at, expires_at, revoked FROM sessions "
        "ORDER BY created_at DESC LIMIT ?", (limit,))
    invites = _rows(
        "SELECT code, cohort, email, created_at, expires_at, redeemed_at FROM invites "
        "ORDER BY created_at DESC LIMIT ?", (limit,))
    summary = {"users": len(users), "sessions": len(sessions_rows), "invites": len(invites)}
    return _env("accounts", users, {**summary, "sessions": sessions_rows, "invites": invites})
