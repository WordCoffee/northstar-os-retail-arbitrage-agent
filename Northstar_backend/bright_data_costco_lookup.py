"""Bright Data Web Unlocker — Costco product-search lookup (slug/search fallback).

Resolves a product TITLE (e.g. a costco-items.csv row that the offline
resolver could not map to a Costco item number) to candidate item IDs by
fetching Costco's site search results page through the same gated Web
Unlocker transport as the detail adapter (bright_data_costco.py).

Solves the concrete blocker for the 180-product catalog test: 18/180 tracked
products have no id-bearing catalog row (apparel, laundry detergent, bath
tissue, paper towels, coffee K-cups, dog food, minoxidil, mattress). This is
the 'alternate slug/search lookup' path previously deferred; it is now built
end-to-end (code + tests with mocked responses) but NEVER executes a live
request unless the operator approves a run and the env gate is set.

Gating / discipline (mirrors the detail adapter exactly):
  - BRIGHTDATA_COSTCO_DETAIL_ENABLED=1 required for live calls. Default 0.
  - ONE request per search query, ZERO retries.
  - sequential pacing BRIGHTDATA_REQUEST_DELAY_SECONDS (default 2.0).
  - HARD failures (auth_error/http_error/transport_error/config_error) HALT
    the batch immediately (circuit breaker) — successes persisted first.
  - SOFT per-item outcomes keep the batch moving:
      lookup_no_results  — search page fetched but no .product.<id>.html links
      lookup_weak_match  — candidates found but none clears the match bar
    These record null-first fields, never fabricated ids.
  - evidence (raw + normalized, scrubbed, with the empty/short-body
    diagnostics from the detail adapter's convention) persisted under a
    caller-supplied run dir.

Lookup URL:  https://www.costco.com/search?query=<url-encoded title>
Candidates:  anchors/links whose href matches the Costco product URL pattern
             (a slug path ending in .product.<id>.html)
Ranking:     Jaccard overlap of title tokens with the query (brand tokens
             stripped on both sides). Exact item-id membership is not assumed
             — the returned candidate MUST be live-verified by a subsequent
             gated `details refresh` before it is trusted.

CLI:
  python bright_data_costco_lookup.py resolve \
      --title "Kirkland Signature Paper Towels, 2-Ply, 160 Sheets, 12 Rolls" \
      [--unresolved-from <prepared-manifest.json>] [--run-dir <dir>] [--delay N]
"""

from __future__ import annotations

import argparse
import html as html_module
import json
import os
import re
import sys
import time
import urllib.parse
from datetime import datetime, timezone
from typing import Dict, List, Optional

from dotenv import load_dotenv

load_dotenv()

import bright_data_client
import bright_data_costco as detail_adapter

GATE_ENV = detail_adapter.GATE_ENV
DELAY_ENV = detail_adapter.DELAY_ENV
DEFAULT_DELAY_SECONDS = detail_adapter.DEFAULT_DELAY_SECONDS
HEAD_CAP_CHARS = detail_adapter.HEAD_CAP_CHARS

COSTCO_SEARCH_URL_TEMPLATE = "https://www.costco.com/search?query={query}"

# Hard-failure vocabulary consistent with the detail adapter.
HARD_FAILURE_TYPES = detail_adapter.HARD_FAILURE_TYPES
SOFT_FAILURE_TYPES = ("lookup_no_results", "lookup_weak_match")

_PRODUCT_LINK_RE = re.compile(
    r'href=["\']([^"\']*?\.product\.\d+\.html)["\']', re.I
)
_HREF_ANCHOR_RE = re.compile(
    r'<a\s+[^>]*href=["\']([^"\']*?\.product\.\d+\.html)["\'][^>]*>(.*?)</a>',
    re.S | re.I,
)

# Search results on costco.com carry product titles in anchor text and in
# result-card headings; anchor text is the primary signal.
_CLEAN_TAG_RE = re.compile(r"<[^>]+>")


def _clean_text(raw: Optional[str]) -> Optional[str]:
    if raw is None:
        return None
    clean = html_module.unescape(re.sub(_CLEAN_TAG_RE, "", raw))
    return " ".join(clean.split()) or None


def _norm_tokens(text: Optional[str]) -> List[str]:
    """Brand-stopword-stripped token list for query/candidate comparison."""
    tokens = re.findall(r"[a-z0-9]+", (text or "").lower())
    stop = {
        "kirkland",
        "signature",
        "costco",
        "wholesale",
        "and",
        "the",
        "of",
        "for",
        "with",
        "de",
        "la",
        "amp",
    }
    return [t for t in tokens if t not in stop and len(t) > 2]


def _jaccard_score(a_tokens: List[str], b_tokens: List[str]) -> float:
    A, B = set(a_tokens), set(b_tokens)
    if not A or not B:
        return 0.0
    return len(A & B) / len(A | B)


def parse_costco_search_page(html: str, query: str) -> Dict:
    """Parse a Costco search-results page into ranked item-id candidates.

    Returns:
      {
        "status": "lookup_candidate" | "lookup_weak_match" | "lookup_no_results",
        "query": <original query>,
        "candidates": [ {item_id, title, url, score}, ... ] sorted desc,
        "best": top candidate dict or None,
        "notes": str,
      }
    """
    q_tokens = _norm_tokens(query)

    seen_ids = {}
    for m in _HREF_ANCHOR_RE.finditer(html or ""):
        href = m.group(1)
        anchor = _clean_text(m.group(2))
        iid = re.search(r"\.product\.(\d+)\.html\b", href, re.I)
        if not iid:
            continue
        item_id = iid.group(1)
        if item_id in seen_ids:
            if anchor and not seen_ids[item_id].get("title"):
                seen_ids[item_id]["title"] = anchor
            continue
        seen_ids[item_id] = {"item_id": item_id, "title": anchor or None, "url": href}

    # Also pick up bare .product.<id>.html links with no usable anchor text.
    for m in _PRODUCT_LINK_RE.finditer(html or ""):
        href = m.group(1)
        iid = re.search(r"\.product\.(\d+)\.html\b", href, re.I)
        if iid and iid.group(1) not in seen_ids:
            seen_ids[iid.group(1)] = {
                "item_id": iid.group(1),
                "title": None,
                "url": href,
            }

    candidates = []
    for rec in seen_ids.values():
        title = rec.get("title")
        title_tokens = _norm_tokens(title) if title else []
        score = _jaccard_score(q_tokens, title_tokens) if title_tokens else 0.0
        candidates.append(
            {
                "item_id": rec["item_id"],
                "title": title,
                "url": rec["url"],
                "score": round(score, 3),
            }
        )
    candidates.sort(key=lambda c: (-c["score"], c["item_id"]))

    if not candidates:
        return {
            "status": "lookup_no_results",
            "query": query,
            "candidates": [],
            "best": None,
            "notes": "no .product.<id>.html links found on the search page",
        }

    best = candidates[0]
    if best["score"] >= 0.50:
        status = "lookup_candidate"
        notes = f"top candidate '{best['title']}' (score {best['score']:.2f})"
    elif best["score"] >= 0.30:
        status = "lookup_weak_match"
        notes = f"no candidate clears 0.50; top '{best['title']}' at {best['score']:.2f}"
    else:
        status = "lookup_weak_match"
        notes = f"no candidate clears 0.30; top '{best['title']}' at {best['score']:.2f}"
    return {
        "status": status,
        "query": query,
        "candidates": candidates,
        "best": best,
        "notes": notes,
    }


def _body_diagnostic(html: Optional[str]) -> str:
    return detail_adapter._body_diagnostic(html)


def _classify_hard_failure(last_error, raise_exc) -> str:
    return detail_adapter._classify_hard_failure(last_error, raise_exc)


def _persist_evidence(run_dir, ts, key, raw_record, norm_record):
    raw_dir = os.path.join(run_dir, "raw")
    norm_dir = os.path.join(run_dir, "normalized")
    os.makedirs(raw_dir, exist_ok=True)
    os.makedirs(norm_dir, exist_ok=True)
    raw_path = os.path.join(raw_dir, f"lookup_{key}_{ts}.json")
    norm_path = os.path.join(norm_dir, f"lookup_{key}_{ts}.json")
    with open(raw_path, "w", encoding="utf-8") as fh:
        json.dump(raw_record, fh, indent=2, ensure_ascii=True)
    with open(norm_path, "w", encoding="utf-8") as fh:
        json.dump(norm_record, fh, indent=2, ensure_ascii=True)
    return raw_path, norm_path


def resolve_by_search(
    queries: List[str],
    run_dir: str,
    delay: Optional[float] = None,
) -> Dict:
    """Live slug/search lookup (GATED). One Web Unlocker request per query."""
    if not detail_adapter._gate_enabled():
        msg = (
            f"[BrightDataCostcoLookup] BLOCKED: {GATE_ENV} != '1'. "
            f"Set {GATE_ENV}=1 to enable live calls."
        )
        print(msg)
        return {
            "status": "blocked",
            "reason": f"{GATE_ENV} not enabled",
            "provider": "BRIGHTDATA_WEB_UNLOCKER",
            "items_requested": len(queries or []),
            "items_resolved": 0,
            "items": [],
            "failures": [],
            "evidence_paths": [],
        }

    run_dir = run_dir or f"data/costco-lookup-runs/{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
    delay = max(0.0, float(delay if delay is not None else DEFAULT_DELAY_SECONDS))
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    items: List[Dict] = []
    failures: List[Dict] = []
    evidence_paths: List[str] = []
    halted = False
    total = len(queries or [])

    for idx, query in enumerate(queries or []):
        if idx > 0:
            time.sleep(delay)

        query = (query or "").strip()
        url = COSTCO_SEARCH_URL_TEMPLATE.format(query=urllib.parse.quote(query))
        requested_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        html = None
        raise_exc = None
        try:
            html = bright_data_client._fetch(url)
        except ValueError as exc:
            raise_exc = exc
        except Exception as exc:  # noqa: BLE001 - persist then report
            raise_exc = exc

        http_status = bright_data_client.LAST_HTTP_STATUS
        last_error = bright_data_client.LAST_ERROR

        if html is None:
            failure_type = _classify_hard_failure(last_error, raise_exc)
            fail_rec = {
                "run_id": f"lookup_{ts}",
                "operation": "costco_search_lookup",
                "query": query,
                "requested_at": requested_at,
                "provider": "BRIGHTDATA_WEB_UNLOCKER",
                "endpoint": "https://api.brightdata.com/request",
                "url": url,
                "http_status": http_status if http_status is not None else 0,
                "failure_type": failure_type,
                "last_error": last_error or (str(raise_exc) if raise_exc else None),
                "response_headers": bright_data_client._scrub_response_headers(
                    bright_data_client.LAST_RESPONSE_HEADERS
                ),
                "reason": (
                    f"http_{http_status}" if http_status is not None else failure_type
                ),
                "retries": 0,
                "stop_on_block": "halted_run",
                "scrubbed": True,
            }
            failures.append(fail_rec)
            raw_path, norm_path = _persist_evidence(
                run_dir, ts, _key(query), fail_rec, fail_rec
            )
            evidence_paths.extend([raw_path, norm_path])
            print(
                f"[{idx + 1}/{total}] query '{query[:40]}' FAILED: {failure_type} "
                f"(http={http_status}) — halting batch (circuit breaker)."
            )
            halted = True
            break

        parsed = parse_costco_search_page(html, query)
        status = parsed["status"]

        norm_record = {
            "run_id": f"lookup_{ts}",
            "operation": "costco_search_lookup",
            "query": query,
            "requested_at": requested_at,
            "provider": "BRIGHTDATA_WEB_UNLOCKER",
            "url": url,
            "http_status": http_status,
            "identity_match_status": status,
            "notes": parsed["notes"],
            "best_candidate": parsed["best"],
            "candidate_count": len(parsed["candidates"]),
            "candidates": parsed["candidates"][:8],
            "retries": 0,
        }
        items.append(norm_record)

        raw_record = {
            "run_id": f"lookup_{ts}",
            "operation": "costco_search_lookup",
            "query": query,
            "requested_at": requested_at,
            "provider": "BRIGHTDATA_WEB_UNLOCKER",
            "platform": "web_unlocker_costco_search",
            "endpoint": "https://api.brightdata.com/request",
            "payload": {
                "zone": bright_data_client.BRIGHTDATA_UNLOCKER_ZONE,
                "url": url,
                "format": "raw",
            },
            "auth_header": "Bearer <redacted>",
            "http_status": http_status,
            "retries": 0,
            "scrubbed": True,
            "response_headers": bright_data_client._scrub_response_headers(
                bright_data_client.LAST_RESPONSE_HEADERS
            ),
            "response_body_bytes": len((html or "").encode("utf-8")),
            "response_body_diagnostic": _body_diagnostic(html),
            "response_html_head_capped": (html or "")[:HEAD_CAP_CHARS],
        }
        raw_path, norm_path = _persist_evidence(
            run_dir, ts, _key(query), raw_record, norm_record
        )
        evidence_paths.extend([raw_path, norm_path])

        marker = status
        print(
            f"[{idx + 1}/{total}] query '{query[:42]}' {marker} "
            f"candidates={len(parsed['candidates'])} "
            f"best={parsed['best']['item_id'] if parsed['best'] else None} "
            f"score={parsed['best']['score'] if parsed['best'] else None} "
            f"body={_body_diagnostic(html)}"
        )

    return {
        "status": "halted" if halted else "completed",
        "provider": "BRIGHTDATA_WEB_UNLOCKER",
        "run_id": f"lookup_{ts}",
        "items_requested": total,
        "items_resolved": sum(
            1 for it in items if it.get("identity_match_status") == "lookup_candidate"
        ),
        "items": items,
        "failures": failures,
        "evidence_paths": evidence_paths,
    }


def _key(query: str) -> str:
    """Filesystem-safe key for a query string."""
    out = re.sub(r"[^a-z0-9]+", "-", (query or "").lower()).strip("-")
    return out[:60] or "query"


def _load_unresolved_titles(manifest_path: str) -> List[Dict]:
    """Pull {title} rows whose offline resolution needs a live lookup."""
    with open(manifest_path, encoding="utf-8-sig") as fh:
        data = json.load(fh)
    rows = []
    for it in data.get("items", []):
        if it.get("resolution") == "unresolved_needs_lookup":
            rows.append(it)
    return rows


# --- CLI -------------------------------------------------------------------
def _cli(argv=None):
    parser = argparse.ArgumentParser(
        prog="bright_data_costco_lookup.py",
        description="Bright Data Web Unlocker Costco search lookup (gated).",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    resolve = sub.add_parser("resolve", help="resolve titles to Costco item ids")
    resolve.add_argument(
        "--title", action="append", default=None, help="product title to look up"
    )
    resolve.add_argument(
        "--unresolved-from",
        default=None,
        help="prepared manifest; every unresolved_needs_lookup title is looked up",
    )
    resolve.add_argument("--run-dir", default=None)
    resolve.add_argument("--delay", type=float, default=None)

    args = parser.parse_args(argv)

    if not args.command == "resolve":
        parser.error("only 'resolve' is implemented")

    queries = list(args.title or [])
    if args.unresolved_from:
        for row in _load_unresolved_titles(args.unresolved_from):
            queries.append(row["requested_title"])

    if not queries:
        parser.error("provide --title or --unresolved-from")

    if not detail_adapter._gate_enabled():
        print(
            f"[BrightDataCostcoLookup] BLOCKED: {GATE_ENV} != '1'. "
            f"Set {GATE_ENV}=1 to enable live calls."
        )
        return 2

    summary = resolve_by_search(queries, run_dir=args.run_dir, delay=args.delay)
    print("\n=== SUMMARY (LOOKUP) ===")
    print(f"status          : {summary['status']}")
    print(f"items_requested : {summary['items_requested']}")
    print(f"items_resolved  : {summary['items_resolved']}")
    return 0


if __name__ == "__main__":
    sys.exit(_cli())