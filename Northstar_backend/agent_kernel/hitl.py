"""Human-in-the-loop approval gate (dependency-free).

Matrix / AgentTeams is the intended transport, but it is not installed on this
host. This module provides the durable part the transport needs: a request
record, an approve/deny transition, and a `require_approved` gate. A Matrix
bridge can call `approve()`/`deny()` from a room command; until then the operator
can use the CLI.

Requests are data, never credentials: callers must not put a secret value in the
payload. The gate is deny-by-default for any action that names an approval id.
"""
from __future__ import annotations

import json
import re
import secrets
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

_ID_RE = re.compile(r"^hitl_[0-9T:_-]+_[0-9a-f]{8}$")


class ApprovalRequired(RuntimeError):
    """The named request is missing, pending or denied."""


def _dir(root: Path | str) -> Path:
    path = Path(root).resolve() / "state" / "hitl"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _path(root: Path | str, request_id: str) -> Path:
    rid = str(request_id or "")
    if not _ID_RE.match(rid):
        raise ApprovalRequired(f"invalid approval id {request_id!r}")
    return _dir(root) / f"{rid}.json"


def request(action: str, *, root: Path | str, payload: Optional[Dict[str, Any]] = None,
            requested_by: str = "agent", transport: str = "local",
            publish: Optional[Callable[[Dict[str, Any]], Any]] = None) -> Dict[str, Any]:
    """Create a pending request. `publish` is the Matrix/AgentTeams hook."""
    if not str(action or "").strip():
        raise ValueError("an approval request needs an action")
    stamp = time.strftime("%Y%m%dT%H%M%S")
    rid = f"hitl_{stamp}_{secrets.token_hex(4)}"
    record = {
        "id": rid,
        "action": str(action)[:200],
        "payload": payload or {},
        "requested_by": str(requested_by)[:80],
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "status": "pending",
        "operator": None,
        "note": "",
        "transport": transport,
    }
    _path(root, rid).write_text(json.dumps(record, indent=2), encoding="utf-8")
    if publish is not None:
        try:
            result = publish(record)
            record["published"] = True
            record["publish_result"] = str(result)[:300]
        except Exception as exc:  # noqa: BLE001 - local record survives a bridge failure
            record["published"] = False
            record["publish_error"] = f"{type(exc).__name__}: {exc}"[:300]
        _path(root, rid).write_text(json.dumps(record, indent=2), encoding="utf-8")
    return record


def get(root: Path | str, request_id: str) -> Dict[str, Any]:
    path = _path(root, request_id)
    if not path.is_file():
        raise ApprovalRequired(f"approval request not found: {request_id}")
    return json.loads(path.read_text(encoding="utf-8"))


def _decide(root: Path | str, request_id: str, status: str, operator: str,
            note: str = "") -> Dict[str, Any]:
    record = get(root, request_id)
    if record.get("status") != "pending":
        raise ApprovalRequired(
            f"request {request_id} is already {record.get('status')}; "
            "a decision is final")
    record.update({"status": status, "operator": str(operator)[:80],
                   "note": str(note)[:500],
                   "decided_at": time.strftime("%Y-%m-%dT%H:%M:%S")})
    _path(root, request_id).write_text(json.dumps(record, indent=2), encoding="utf-8")
    return record


def approve(root: Path | str, request_id: str, operator: str,
            note: str = "") -> Dict[str, Any]:
    return _decide(root, request_id, "approved", operator, note)


def deny(root: Path | str, request_id: str, operator: str,
         note: str = "") -> Dict[str, Any]:
    return _decide(root, request_id, "denied", operator, note)


def pending(root: Path | str) -> List[Dict[str, Any]]:
    rows = []
    for path in sorted(_dir(root).glob("hitl_*.json")):
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if record.get("status") == "pending":
            rows.append(record)
    return rows


def require_approved(root: Path | str, request_id: str) -> Dict[str, Any]:
    record = get(root, request_id)
    if record.get("status") != "approved":
        raise ApprovalRequired(
            f"approval {request_id} is {record.get('status')}, not approved")
    return record


def main(argv: Optional[List[str]] = None) -> int:
    import argparse
    ap = argparse.ArgumentParser(description="Local HITL approval queue.")
    ap.add_argument("--root", default=".")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("pending")
    p_req = sub.add_parser("request")
    p_req.add_argument("--action", required=True)
    p_req.add_argument("--by", default="agent")
    p_req.add_argument("--payload", default="{}")
    p_yes = sub.add_parser("approve")
    p_yes.add_argument("id")
    p_yes.add_argument("--operator", default="operator")
    p_yes.add_argument("--note", default="")
    p_no = sub.add_parser("deny")
    p_no.add_argument("id")
    p_no.add_argument("--operator", default="operator")
    p_no.add_argument("--note", default="")
    args = ap.parse_args(argv)
    if args.cmd == "pending":
        print(json.dumps(pending(args.root), indent=2))
    elif args.cmd == "request":
        print(json.dumps(request(args.action, root=args.root, requested_by=args.by,
                                 payload=json.loads(args.payload or "{}")), indent=2))
    elif args.cmd == "approve":
        print(json.dumps(approve(args.root, args.id, args.operator, args.note), indent=2))
    else:
        print(json.dumps(deny(args.root, args.id, args.operator, args.note), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["ApprovalRequired", "request", "get", "approve", "deny", "pending",
           "require_approved"]
