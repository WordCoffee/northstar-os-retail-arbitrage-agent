"""Service contracts: prove every registry service's primary action actually works.

The registry (`ty/service_registry.json`) says what each service can do. It does
not prove that any of it happens. This tool calls each service's primary action
against a real backend, checks the response is substantive rather than a stub,
and - for a write - reads the value back through a *different* endpoint. A
service that cannot do that fails with the reason named.

Contract for one service
------------------------
1. `pass`  - the primary action reached a mounted endpoint, returned a
             substantive payload, and (write) the value was read back.
2. `fail`  - any of those is false; `verdict` names which and `reason` says why.
3. `gap`   - there is no primary action in the registry (`no_primary_action`).

Primary action selection is deterministic:

* effects rank `delete > write/create/update > external > read`, registry order
  breaks ties;
* an `external` action is **never called**: the standing gate forbids spending
  money or paid credits, and these routes call a metered model provider;
* the selected action must have a probe in this file. If a higher-effect action
  has no probe (because it needs an item nobody ingested, or has no read-back
  route) it is listed in `skipped_actions` with the reason, and the highest
  **provable** action is used instead. Hiding that would make "pass" mean
  "passed the easy one", so the skipped list is part of every row.

Modes
-----
    python tools/contract_check.py                 # live HTTP to 127.0.0.1:8000
    python tools/contract_check.py --in-process    # fresh TestClient + temp DB
    python tools/contract_check.py --json          # machine output only
    python tools/contract_check.py --service jobs  # one service

Both modes use the dev-loopback identity shim (X-User-Id/X-Org-Id/X-Role) that
the capsule's DEV-ONLY LOCALHOST EXCEPTION allows. Nothing here touches Amazon,
a paid provider, or a shared server other than the one being probed.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "ty" / "service_registry.json"
OUT = ROOT / "state" / "contracts" / "service_contracts.json"
BASE_URL = os.environ.get("NORTHSTAR_BASE_URL", "http://127.0.0.1:8000").rstrip("/")

DEV_HEADERS = {
    "X-User-Id": "demo-t2",
    "X-Org-Id": "org-t2",
    "X-Role": "operator",
}

EFFECT_RANK = {
    "delete": 5,
    "write": 4,
    "create": 4,
    "update": 4,
    "external": 3,
    "read": 1,
    "analysis": 1,
}

#: Endpoints a contract cannot execute without a prerequisite nobody has
#: produced, or whose write has no read-back surface. Named so the skip is
#: visible in the artefact instead of being silently dropped.
SKIP_REASONS = {
    "/api/v1/foundation/golden-goose/{item_id}/decision": (
        "write persists into a decisions table that has no read endpoint; the "
        "item detail route 404s until an opportunity is ingested, so persistence "
        "cannot be demonstrated"
    ),
}

#: The product-finder registry entry used to have `actions: []`. It now declares the
#: finder read (`fix-product-finder-wiring`, 2026-11-11), so that override was removed
#: rather than left shadowing the registry it was written to compensate for.
OVERRIDES: Dict[str, Dict[str, Any]] = {
    # AdPilot's registry entry lists three reads and one external action, so its contract could
    # never show a *persisted* primary action: there was nothing to persist into (adpilot `contract`
    # = 0, `complete` = 0). A campaign plan is the thing a seller returns to, so it is saved as a
    # durable job through the foundation store — the same store and the same read-back the `jobs`
    # service is proved with. The registry entry should carry this write; until it does, the override
    # names it here rather than reporting a gap that is no longer true.
    "adpilot": {
        "name": "save a campaign plan",
        "effect": "write",
        "endpoint": "/api/v1/foundation/jobs-durable",
        "method": "POST",
        "source": "Northstar_backend/foundation/api/jobs.py",
        "note": ("a campaign plan is persisted as a durable job and read back by id; the registry "
                 "entry lists reads only (2026-11-10)"),
    },
}

#: How to execute each endpoint. `fn` entries are built at run time so every
#: probe carries a unique idempotency key / upload name.
REQUESTS: Dict[str, Dict[str, Any]] = {
    "/api/sourcescout/summary": {"method": "GET"},
    "/api/sourcescout/matches": {"method": "GET"},
    "/api/sourcescout": {"method": "GET"},
    "/api/kirkland/scanner": {"method": "GET"},
    "/api/v1/models": {"method": "GET"},
    "/api/v1/credits/me": {"method": "GET"},
    "/api/products/finder": {"method": "GET", "params": {"limit": 100}},
    "/api/autothink/models": {"method": "GET"},
    "/api/v1/foundation/entitlements": {"method": "GET"},
    "/api/v1/foundation/plan-usage": {"method": "GET"},
    "/api/v1/foundation/providers": {"method": "GET"},
    "/api/v1/foundation/marketplaces": {"method": "GET"},
    "/api/v1/foundation/approvals": {"method": "GET"},
    "/api/v1/foundation/identity/conflicts": {"method": "GET"},
    "/api/v1/foundation/usage/summary": {"method": "GET"},
    "/api/v1/foundation/jobs-durable/queue-posture": {"method": "GET"},
    "/api/v1/foundation/schedules/posture": {"method": "GET"},
    "/api/v1/foundation/audit": {"method": "GET"},
    "/api/v1/foundation/environment": {"method": "GET"},
    "/api/v1/foundation/products": {"method": "GET"},
    "/api/v1/foundation/identity/candidates": {"method": "GET"},
    "/api/v1/foundation/keywords/imports": {"method": "GET"},
    "/api/v1/foundation/admin/dashboard": {"method": "GET"},
    "/api/v1/noncreative/accounts": {"method": "GET"},
    "/api/v1/noncreative/listings/health": {"method": "GET"},
    "/api/v1/noncreative/keywords": {"method": "GET"},
    "/api/v1/noncreative/competitor/observations": {"method": "GET"},
    "/api/design-studio/projects": {"method": "GET"},
    "/api/design-studio/assets": {"method": "GET"},
    "/api/design-studio/amazon-files": {"method": "GET"},
    "/api/design-studio/terms": {"method": "GET"},
    "/api/design-studio/dashboard/packages": {"method": "GET"},
    "/api/design-studio/listing-records": {"method": "GET"},
    "/api/v1/foundation/golden-goose/evaluate": {
        "method": "POST",
        "json": {
            "item_id": "contract-probe",
            "gate_inputs": {},
            "economics_readiness": "READY",
        },
    },
    "/api/v1/foundation/economics/compute": {
        "method": "POST",
        "json": {"input": {
            "selling_price": 29.99,
            "acquisition_cost": 10.0,
            "amazon_price": 29.99,
            "supplier_cost": 10.0,
            "weight_lbs": 1.0,
        }},
    },
    "/api/v1/foundation/economics/contract": {"method": "GET"},
    "/api/v1/foundation/jobs-durable": {"method": "POST", "fn": "_job_body"},
    "/api/v1/foundation/keywords/imports": {"method": "POST", "fn": "_keyword_body"},
    "/api/v1/foundation/signup": {"method": "POST", "fn": "_signup_body"},
    "/api/design-studio/assets/upload": {"method": "POST", "fn": "_upload_body"},
    "/api/design-studio/listing-records": {"method": "POST", "fn": "_listing_body"},
}

#: Keys that describe a response rather than measure anything. A payload with
#: only these is a stub, not evidence.
_IGNORED_KEYS = {
    "contract", "request_id", "meta", "count", "total", "kind", "schema_version",
    "generated_at", "status", "ok", "basis", "note", "notes", "error", "detail",
    "details", "message", "unavailable", "items", "rows", "data", "result",
    "type", "version", "timestamp", "created_at", "updated_at",
}
_PLACEHOLDER_STRINGS = {
    "", "ok", "unknown", "unverified", "unavailable", "none", "null", "n/a",
    "not available", "not calculated", "unmeasured", "incomplete",
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def registry_services(path: Path = REGISTRY) -> List[Dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return data.get("services") or []


def _is_callable(action: Dict[str, Any]) -> bool:
    endpoint = str(action.get("endpoint") or "")
    return endpoint in REQUESTS and action.get("effect") != "external"


def select_primary(service: Dict[str, Any]) -> Tuple[Optional[Dict[str, Any]],
                                                     List[Dict[str, Any]], str]:
    """Return (primary, skipped_actions, reason_if_none)."""
    override = OVERRIDES.get(service["id"])
    actions = list(service.get("actions") or [])
    if override:
        # The override only stands in where the registry itself has no action.
        if not actions:
            return override, [], ""
    if not actions:
        return None, [], "registry records no actions for this service"

    ranked = sorted(
        enumerate(actions),
        key=lambda pair: (-EFFECT_RANK.get(str(pair[1].get("effect") or "read"), 1),
                          pair[0]),
    )
    skipped: List[Dict[str, Any]] = []
    skipped_ids: set = set()
    chosen: Optional[Dict[str, Any]] = None
    for _, action in ranked:
        if action.get("effect") == "external":
            skipped.append({**action, "skipped_because": (
                "standing gate (a): this route spends paid model credits, so the "
                "contract never calls it")})
            skipped_ids.add(id(action))
            continue
        if not _is_callable(action):
            skipped.append({**action, "skipped_because": (
                SKIP_REASONS.get(str(action.get("endpoint")))
                or "no contract probe can exercise this action")})
            skipped_ids.add(id(action))
            continue
        chosen = action
        break

    if chosen is None:
        if skipped and all(s.get("effect") == "external" for s in skipped):
            return None, skipped, "every action is an external paid-model call"
        return None, skipped, "no action is provable by a contract probe"

    # Anything ranked above the chosen action is a skip worth stating.
    for _, action in ranked:
        if action is chosen:
            break
        if id(action) not in skipped_ids:
            skipped.append({**action, "skipped_because": "cannot be proven"})
            skipped_ids.add(id(action))
    return chosen, skipped, ""


def _recursive_informative(value: Any, depth: int = 0) -> int:
    """Count measured leaves in a payload, ignoring envelopes and prose."""
    if depth > 4:
        return 0
    if isinstance(value, bool):
        return 1 if value else 0
    if isinstance(value, (int, float)):
        return 1 if value not in (0, 0.0) else 0
    if isinstance(value, str):
        return 0 if value.strip().lower() in _PLACEHOLDER_STRINGS else 1
    if isinstance(value, list):
        rows = [v for v in value if isinstance(v, dict) and v]
        if rows:
            return max(2, len(rows))
        return min(2, sum(1 for v in value if _recursive_informative(v, depth + 1)))
    if isinstance(value, dict):
        total = 0
        for key, item in value.items():
            if str(key).lower() in _IGNORED_KEYS:
                continue
            total += _recursive_informative(item, depth + 1)
        return total
    return 0


def substance(payload: Any) -> Tuple[bool, str]:
    """Is this a real observation, or a stub with only envelope keys?"""
    if payload is None:
        return False, "empty body"
    if isinstance(payload, list):
        rows = [row for row in payload if isinstance(row, dict) and row]
        if not rows:
            return False, "no rows"
        return True, f"{len(rows)} row(s)"
    if not isinstance(payload, dict):
        return True, f"scalar {type(payload).__name__}"

    # A non-empty list of objects anywhere is real rows, whatever the envelope.
    for key, value in payload.items():
        if isinstance(value, list) and value and isinstance(value[0], dict):
            return True, f"{len(value)} row(s) under {key!r}"

    informative = _recursive_informative(payload)
    if informative >= 3:
        keys = ",".join(list(payload)[:8])
        return True, f"{informative} measured field(s) ({keys})"
    if informative >= 1 and len(payload) >= 3:
        keys = ",".join(list(payload)[:8])
        return True, f"{informative} measured field(s) ({keys})"
    return False, (f"payload has no measured rows or fields (keys: "
                   f"{','.join(list(payload)[:8]) or 'none'})")


def _job_body() -> Dict[str, Any]:
    return {"json": {
        "job_type": "immediate_success",
        "payload": {},
        "idempotency_key": f"contract-probe-{uuid.uuid4().hex[:12]}",
        "reason": "service contract probe",
    }}


def _keyword_body() -> Dict[str, Any]:
    return {"json": {
        "file_name": "search_term_report_sample.csv",
        "idempotency_key": f"contract-probe-{uuid.uuid4().hex[:12]}",
    }}


def _signup_body() -> Dict[str, Any]:
    return {"json": {
        "email": f"contract-probe-{uuid.uuid4().hex[:10]}@northstar.local",
        "invite_code": "CONTRACT-PROBE-NOT-A-REAL-INVITE",
        "display_name": "Contract Probe",
    }}


def _upload_body() -> Dict[str, Any]:
    name = f"contract-probe-{uuid.uuid4().hex[:10]}.txt"
    return {"files": {"file": (name, b"service contract probe\n", "text/plain")}}


def _listing_body() -> Dict[str, Any]:
    return {"json": {
        "asin": f"B0CON{uuid.uuid4().hex[:6].upper()}",
        "title": "service contract probe",
        "source": "contract-check",
    }}


_BODY_FNS = {
    "_job_body": _job_body,
    "_keyword_body": _keyword_body,
    "_signup_body": _signup_body,
    "_upload_body": _upload_body,
    "_listing_body": _listing_body,
}


def build_request(spec: Dict[str, Any]) -> Dict[str, Any]:
    if spec.get("fn"):
        return _BODY_FNS[spec["fn"]]()
    return {key: spec[key] for key in ("json", "params", "files") if key in spec}


def unwrap(payload: Any) -> Any:
    """Strip the bff/v1 envelope so validation sees the service's own data."""
    if isinstance(payload, dict) and payload.get("contract") == "bff/v1":
        return payload.get("data")
    return payload


def _find_row(payload: Any, key_path: List[str], wanted_id: str) -> Optional[Dict[str, Any]]:
    node: Any = payload
    for key in key_path:
        if not isinstance(node, dict):
            return None
        node = node.get(key)
    if not isinstance(node, list):
        return None
    for row in node:
        if isinstance(row, dict) and str(row.get("id") or "") == wanted_id:
            return row
    return None


#: How to read a write back through a *different* endpoint.
READBACK = {
    "/api/v1/foundation/jobs-durable": {
        "endpoint": "/api/v1/foundation/jobs-durable/{id}",
        "id_key": "id",
        "check": "id",
    },
    "/api/v1/foundation/keywords/imports": {
        "endpoint": "/api/v1/foundation/jobs-durable/{id}",
        "id_key": "job_id",
        "check": "id",
    },
    "/api/design-studio/assets/upload": {
        "endpoint": "/api/design-studio/assets",
        "id_key": "id",
        "check": "row",
        "rows_key": "assets",
    },
    "/api/design-studio/listing-records": {
        "endpoint": "/api/design-studio/listing-records",
        "id_key": "id",
        "check": "row",
        "rows_key": "records",
    },
}


def _request(client: Any, method: str, endpoint: str, kwargs: Dict[str, Any]) -> Any:
    headers = dict(DEV_HEADERS)
    if "files" in kwargs:
        # Let the multipart boundary be generated; the dev headers still ride along.
        return client.request(method, endpoint, headers=headers, **kwargs)
    headers["Content-Type"] = "application/json"
    return client.request(method, endpoint, headers=headers, **kwargs)


def probe_service(client: Any, service: Dict[str, Any]) -> Dict[str, Any]:
    sid = service["id"]
    primary, skipped, no_reason = select_primary(service)
    row: Dict[str, Any] = {
        "id": sid,
        "label": service.get("label"),
        "group": service.get("group"),
        "primary_action": None,
        "endpoint": None,
        "method": None,
        "effect": None,
        "status": None,
        "persisted": None,
        "evidence": "",
        "verdict": "fail",
        "reason": no_reason or "not probed",
        "skipped_actions": [
            {"name": s.get("name"), "endpoint": s.get("endpoint"),
             "effect": s.get("effect"), "why": s.get("skipped_because")}
            for s in skipped
        ],
    }
    if primary is None:
        row["verdict"] = "no_primary_action" if not skipped else "fail"
        if row["verdict"] == "fail":
            row["reason"] = no_reason
        return row

    endpoint = str(primary["endpoint"])
    method = str(primary.get("method") or "GET").upper()
    row.update({
        "primary_action": primary.get("name"),
        "endpoint": endpoint,
        "method": method,
        "effect": primary.get("effect"),
    })
    spec = REQUESTS[endpoint]
    kwargs = build_request(spec)

    try:
        response = _request(client, method, endpoint, kwargs)
    except Exception as exc:  # noqa: BLE001 - a transport failure is a failed contract
        row["reason"] = f"request failed: {type(exc).__name__}: {exc}"
        return row

    row["status"] = int(getattr(response, "status_code", 0))
    try:
        payload = response.json()
    except Exception:  # noqa: BLE001 - non-JSON body cannot be validated
        payload = None

    if row["status"] in (404, 405, 501):
        row["verdict"] = "endpoint_missing"
        row["reason"] = f"HTTP {row['status']} - endpoint is not mounted"
        row["evidence"] = _snippet(payload, response)
        return row
    if row["status"] == 403:
        row["verdict"] = "permission_denied"
        row["reason"] = f"HTTP 403 - {_error_text(payload) or 'identity refused'}"
        row["evidence"] = _snippet(payload, response)
        return row
    if not 200 <= row["status"] < 300:
        row["verdict"] = "http_error"
        row["reason"] = f"HTTP {row['status']} - {_error_text(payload) or 'no detail'}"
        row["evidence"] = _snippet(payload, response)
        return row

    data = unwrap(payload)
    ok, detail = substance(data)
    row["evidence"] = detail
    if not ok:
        row["verdict"] = "empty_payload"
        row["reason"] = detail
        return row

    if primary.get("effect") in ("write", "create", "update", "delete"):
        readback = READBACK.get(endpoint)
        if not readback:
            row["verdict"] = "persist_unproven"
            row["reason"] = "write succeeded but no read-back endpoint is known"
            return row
        persisted, detail2 = _read_back(client, readback, data)
        row["persisted"] = persisted
        if not persisted:
            row["verdict"] = "persist_failed"
            row["reason"] = detail2
            row["evidence"] = f"{detail}; read-back failed: {detail2}"
            return row
        row["evidence"] = f"{detail}; {detail2}"
    else:
        row["persisted"] = None

    row["verdict"] = "pass"
    row["reason"] = ""
    return row


def _read_back(client: Any, readback: Dict[str, Any],
               created: Any) -> Tuple[bool, str]:
    if not isinstance(created, dict):
        return False, "write response was not an object"
    wanted = str(created.get(readback["id_key"]) or "")
    if not wanted:
        return False, f"write response has no {readback['id_key']!r}"
    endpoint = readback["endpoint"].replace("{id}", wanted)
    try:
        response = _request(client, "GET", endpoint, {})
    except Exception as exc:  # noqa: BLE001
        return False, f"{endpoint}: {type(exc).__name__}: {exc}"
    if not 200 <= int(response.status_code) < 300:
        return False, f"{endpoint} returned HTTP {response.status_code}"
    try:
        payload = unwrap(response.json())
    except Exception:  # noqa: BLE001
        return False, f"{endpoint} did not return JSON"
    if readback["check"] == "id":
        found = isinstance(payload, dict) and str(payload.get("id") or "") == wanted
        return (True, f"read back {wanted} via {endpoint}") if found else (
            False, f"{endpoint} did not return id {wanted}")
    row = _find_row(payload, [readback["rows_key"]], wanted)
    return (True, f"read back {wanted} via {endpoint}") if row else (
        False, f"{endpoint} did not list {wanted}")


def _error_text(payload: Any) -> str:
    if isinstance(payload, dict):
        detail = payload.get("detail")
        if isinstance(detail, dict):
            return str(detail.get("message") or detail.get("code") or "")
        if detail:
            return str(detail)
        if payload.get("error"):
            return str(payload["error"])
    return ""


def _snippet(payload: Any, response: Any) -> str:
    if payload is None:
        return f"HTTP {response.status_code}"
    text = json.dumps(payload, default=str)
    return text[:300]


def make_client(mode: str, db_dir: Optional[Path] = None) -> Any:
    if mode == "live":
        import httpx  # noqa: PLC0415

        return httpx.Client(base_url=BASE_URL, timeout=60.0,
                            follow_redirects=False)
    return _in_process_client(db_dir)


def _in_process_client(db_dir: Optional[Path]) -> Any:
    os.environ.setdefault("ENVIRONMENT", "development")
    backend = ROOT / "Northstar_backend"
    if str(backend) not in sys.path:
        sys.path.insert(0, str(backend))
    workdir = Path(db_dir or tempfile.mkdtemp(prefix="contract-check-"))
    workdir.mkdir(parents=True, exist_ok=True)

    import data_layer  # noqa: PLC0415

    data_layer._SQLITE_PATH = workdir / "northstar.db"  # noqa: SLF001
    data_layer._db_instance = None  # noqa: SLF001

    import main  # noqa: PLC0415
    from fastapi.testclient import TestClient  # noqa: PLC0415
    from foundation.api.state import FoundationState  # noqa: PLC0415
    from foundation.dev_identity import ensure_dev_identity  # noqa: PLC0415

    main.app.state.foundation = FoundationState.build(str(workdir / "foundation.db"))
    ensure_dev_identity(main.app.state.foundation)
    main.app.state.dev_auto_session = True
    # A loopback peer keeps every dev-shim guard true; the default "testclient"
    # host is deliberately not loopback, so it must be stated.
    return TestClient(main.app, client=("127.0.0.1", 51234), raise_server_exceptions=False)


def run(mode: str = "live", db_dir: Optional[Path] = None,
        only: Optional[str] = None) -> Dict[str, Any]:
    services = registry_services()
    if only:
        services = [s for s in services if s["id"] == only]
    client = make_client(mode, db_dir)
    try:
        rows = [probe_service(client, service) for service in services]
    finally:
        close = getattr(client, "close", None)
        if callable(close):
            close()
    passed = [row for row in rows if row["verdict"] == "pass"]
    persisted = [row for row in rows if row.get("persisted") is True]
    gaps = [row for row in rows if row["verdict"] == "no_primary_action"]
    return {
        "schema": "contracts/v1",
        "generated": _now(),
        "mode": mode,
        "base_url": BASE_URL if mode == "live" else "in-process TestClient",
        "rule": ("primary action must reach a mounted endpoint, return a "
                 "substantive payload, and (write) read back through another "
                 "endpoint"),
        "count": len(rows),
        "passed": len(passed),
        "persisted": len(persisted),
        "gaps": len(gaps),
        "services": rows,
    }


def write(result: Dict[str, Any], path: Path = OUT) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return path


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Service contract check")
    parser.add_argument("--in-process", action="store_true",
                        help="fresh TestClient with a temp DB instead of live HTTP")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--service", default=None)
    parser.add_argument("--out", default=None,
                        help=("artefact path; defaults to state/contracts/service_contracts.json "
                              "for a full probe. A --service probe writes nothing unless --out is "
                              "given: a one-service measurement must not overwrite the published set"))
    parser.add_argument("--db-dir", default=None)
    ns = parser.parse_args(argv)

    mode = "in_process" if ns.in_process else "live"
    result = run(mode=mode,
                 db_dir=Path(ns.db_dir) if ns.db_dir else None,
                 only=ns.service)
    path = None
    if ns.out or not ns.service:
        path = write(result, Path(ns.out or OUT))
    if ns.json:
        print(json.dumps(result, indent=2))
    else:
        print(json.dumps({
            "services": result["count"],
            "passed": result["passed"],
            "persisted": result["persisted"],
            "gaps": result["gaps"],
            "artefact": str(path) if path else None,
            "partial_probe_not_written": path is None,
            "failed": [{"id": row["id"], "verdict": row["verdict"],
                        "reason": row["reason"]}
                       for row in result["services"]
                       if row["verdict"] != "pass"],
        }, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
