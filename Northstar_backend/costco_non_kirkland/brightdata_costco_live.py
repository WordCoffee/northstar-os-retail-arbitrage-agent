"""Bright Data Costco collector — GATED live schema test (explicit approval only).

This module performs a live Bright Data request ONLY for an explicitly approved,
tiny URL set. It never prints secrets; it reads the API token from the
environment solely to build the Authorization header.

Endpoints (Bright Data Scraper Studio / "Collect by URL"):
  POST https://api.brightdata.com/datasets/v3/trigger?dataset_id=<collector_id>
  GET  https://api.brightdata.com/datasets/v3/progress/<snapshot_id>
  GET  https://api.brightdata.com/datasets/v3/snapshot/<snapshot_id>?format=json
"""
from __future__ import annotations

import hashlib
import json
import os
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import requests

from .brightdata_costco_enrichment import load_collector_config, sha256_file, map_provider_record

TOKEN_ENVS = ("BRIGHTDATA_API_TOKEN", "BRIGHTDATA_API_KEY")
TRIGGER = "https://api.brightdata.com/datasets/v3/trigger"
PROGRESS = "https://api.brightdata.com/datasets/v3/progress/{sid}?format=json"
SNAPSHOT = "https://api.brightdata.com/datasets/v3/snapshot/{sid}?format=json"
OUT_DIR = os.path.join("data", "brightdata-costco")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _token() -> Optional[str]:
    for n in TOKEN_ENVS:
        v = os.getenv(n)
        if v:
            return v
    return None


def run_schema_test(urls: List[str], *, collector_id: Optional[str] = None, approved: bool = False,
                    max_inputs: int = 0, spend_cap: Optional[float] = None,
                    hard_cap: int = 25,
                    poll_timeout_s: int = 900, poll_interval_s: int = 20) -> Dict[str, Any]:
    """Run the approved bounded collector test. Fails closed without all gates."""
    collector_id = collector_id or load_collector_config().get("source_id")
    gates = {
        "approved": bool(approved),
        "collector_id_present": bool(collector_id),
        "urls_present": bool(urls) and len(urls) <= hard_cap,
        "max_inputs_set": isinstance(max_inputs, int) and 0 < max_inputs <= hard_cap,
        "spend_cap_set": spend_cap is not None,
    }
    missing = [k for k, v in gates.items() if not v]
    if missing:
        return {"result_status": "requires_explicit_approval", "missing_gates": missing,
                "network_calls_made": 0}

    token = _token()
    if not token:
        return {"result_status": "provider_not_configured",
                "detail": "no Bright Data API token in environment", "network_calls_made": 0}

    # enforce the exact input cap
    urls = urls[:max_inputs]
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    body = [{"url": u} for u in urls]

    result: Dict[str, Any] = {
        "result_status": "unknown",
        "collector_id": collector_id,
        "input_urls": urls,
        "max_inputs": max_inputs,
        "spend_cap": spend_cap,
        "submitted_at": _now(),
        "network_calls_made": 0,
    }

    try:
        resp = requests.post(f"{TRIGGER}?dataset_id={collector_id}&include_errors=true",
                             headers=headers, json=body, timeout=60)
        result["network_calls_made"] += 1
        result["trigger_http_status"] = resp.status_code
        if resp.status_code == 401:
            result["result_status"] = "unauthorized"
            return result
        if resp.status_code == 404:
            result["result_status"] = "collector_not_found"
            return result
        if resp.status_code >= 400:
            result["result_status"] = "trigger_failed"
            result["trigger_body_head"] = resp.text[:300]
            return result
        jb = resp.json()
    except Exception as e:  # pragma: no cover - live
        result["result_status"] = "transport_error"
        result["detail"] = str(e)[:200]
        return result

    snapshot_id = jb.get("snapshot_id")
    result["snapshot_id"] = snapshot_id
    if not snapshot_id:
        result["result_status"] = "no_snapshot_id"
        result["trigger_body_head"] = json.dumps(jb)[:300]
        return result

    deadline = time.time() + poll_timeout_s
    status = None
    while time.time() < deadline:
        try:
            pr = requests.get(PROGRESS.format(sid=snapshot_id), headers=headers, timeout=30)
            result["network_calls_made"] += 1
            if pr.status_code == 200:
                pj = pr.json()
                status = pj.get("status") or pj.get("state")
                if pj.get("credits_used") is not None:
                    result["credits_used_reported"] = pj.get("credits_used")
                if status in ("ready", "completed", "success", "done"):
                    break
        except Exception:
            pass
        time.sleep(poll_interval_s)
    result["final_status"] = status
    if status not in ("ready", "completed", "success", "done"):
        result["result_status"] = "timeout"
        return result

    try:
        dr = requests.get(SNAPSHOT.format(sid=snapshot_id), headers=headers, timeout=60)
        result["network_calls_made"] += 1
        if dr.status_code != 200:
            result["result_status"] = "download_failed"
            result["download_http_status"] = dr.status_code
            return result
        data = dr.json()
    except Exception as e:  # pragma: no cover - live
        result["result_status"] = "download_error"
        result["detail"] = str(e)[:200]
        return result

    records = data if isinstance(data, list) else (data.get("results") or data.get("data") or [data])
    os.makedirs(OUT_DIR, exist_ok=True)
    raw_path = os.path.join(OUT_DIR, f"collector-{snapshot_id}.json")
    with open(raw_path, "w", encoding="utf-8") as fh:
        json.dump({"snapshot_id": snapshot_id, "collector_id": collector_id,
                   "captured_at": _now(), "records": records}, fh, indent=2)
    result.update({
        "result_status": "collected",
        "records_returned": len(records),
        "raw_response_path": raw_path,
        "raw_response_sha256": sha256_file(raw_path),
        "records": records,
    })
    return result


def import_collector_response(path: str, store, *, provider_snapshot_id: Optional[str] = None) -> Dict[str, Any]:
    """Import a collector response; key enrichment to the SUBMITTED source URL.

    The Bright Data collector may return an item_id that differs from the local
    Costco item number (legacy id -> canonical id redirect). We therefore match
    records back to the local source product by the input/source URL, and store
    the local item number on the enrichment record for correct merging.
    """
    with open(path, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    records = data.get("records", data if isinstance(data, list) else [])
    sha = sha256_file(path)
    src_by_url = {}
    for r in store.list_source_products(limit=1_000_000):
        if r.get("source_url"):
            src_by_url[str(r["source_url"]).strip()] = r
    imported = 0
    mapping = []
    for raw in records:
        inp_raw = raw.get("input") if raw.get("input") is not None else raw.get("url")
        if isinstance(inp_raw, dict):
            inp_raw = inp_raw.get("url") or inp_raw.get("input")
        inp = str(inp_raw or "").strip()
        s = src_by_url.get(inp) or src_by_url.get(str(raw.get("url") or "").strip())
        rec = map_provider_record(raw, snapshot_sha256=sha, provider_snapshot_id=provider_snapshot_id)
        if s:
            rec["costco_item_number"] = s.get("costco_item_number")
            rec["source_product_id"] = s.get("id")
        else:
            rec["source_product_id"] = None
        store.upsert_enrichment_record(rec)
        imported += 1
        mapping.append({
            "input_url": inp,
            "returned_item_id": raw.get("item_id"),
            "local_item_number": s.get("costco_item_number") if s else None,
            "matched_to_local": bool(s),
            "item_id_matches_local": bool(s and str(raw.get("item_id")) == str(s.get("costco_item_number"))),
        })
    return {"result_status": "imported", "records": imported, "snapshot_sha256": sha,
            "item_mapping": mapping, "network_calls_made": 0}
