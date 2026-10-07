"""Write-action approval workflow (social publishing / ad spend) — local queue.

Every write action requires a **recorded human approval** *and* its write flag to
be armed (``NORTHSTAR_SOCIAL_PUBLISH_ARMED`` / ``NORTHSTAR_ADS_WRITE_ARMED``).
Execution never posts publicly or spends money unless both hold; otherwise it
returns exactly why (never a fake success). Every transition is audit-logged.

Queue file: ``approvals.json`` in the media root (``NORTHSTAR_APPROVALS_INDEX``
overrides). No database.
"""

from __future__ import annotations

import json
import os
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from . import providers, storage

WRITE_KINDS: Dict[str, Dict[str, Any]] = {
    "social_publish": {
        "flag": "NORTHSTAR_SOCIAL_PUBLISH_ARMED",
        "approval_kind": "public_exposure",
        "live_client": False,
        "label": "Publish social post",
    },
    "ads_write": {
        "flag": "NORTHSTAR_ADS_WRITE_ARMED",
        "approval_kind": "real_money",
        "live_client": False,
        "label": "Apply ad change (spend)",
    },
}


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _path() -> Path:
    env = os.environ.get("NORTHSTAR_APPROVALS_INDEX")
    if env:
        return Path(env)
    return storage._local_root() / "approvals.json"


def _load() -> Dict[str, Any]:
    p = _path()
    if p.exists():
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
            if isinstance(d, dict) and isinstance(d.get("requests"), list):
                return d
        except Exception:
            pass
    return {"version": 1, "requests": []}


def _save(d: Dict[str, Any]) -> None:
    p = _path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(d, indent=2, ensure_ascii=False), encoding="utf-8")


def request(kind: str, payload: Dict[str, Any], *, requested_by: str = "operator",
            note: str = "") -> Dict[str, Any]:
    if kind not in WRITE_KINDS:
        raise ValueError(f"unknown write kind '{kind}'")
    d = _load()
    rec = {
        "id": f"WA-{uuid.uuid4().hex[:8].upper()}",
        "kind": kind,
        "label": WRITE_KINDS[kind]["label"],
        "approval_kind": WRITE_KINDS[kind]["approval_kind"],
        "payload": payload or {},
        "status": "pending",
        "requested_by": requested_by,
        "note": note,
        "armed": providers.flag(WRITE_KINDS[kind]["flag"]),
        "audit": [{"ts": _now(), "event": "requested", "by": requested_by}],
        "created_at": _now(),
        "updated_at": _now(),
    }
    d["requests"].append(rec)
    _save(d)
    return rec


def list_requests(status: Optional[str] = None) -> List[Dict[str, Any]]:
    rows = _load()["requests"]
    if status:
        rows = [r for r in rows if r.get("status") == status]
    return sorted(rows, key=lambda r: r.get("created_at", ""), reverse=True)


def get(rid: str) -> Optional[Dict[str, Any]]:
    return next((r for r in _load()["requests"] if r.get("id") == rid), None)


def _update(rid: str, **fields: Any) -> Optional[Dict[str, Any]]:
    d = _load()
    for r in d["requests"]:
        if r.get("id") == rid:
            r.update(fields)
            r["updated_at"] = _now()
            _save(d)
            return r
    return None


def decide(rid: str, *, approve: bool, by: str = "operator", note: str = "") -> Dict[str, Any]:
    rec = get(rid)
    if not rec:
        raise ValueError("approval not found")
    status = "approved" if approve else "rejected"
    audit = rec.get("audit", []) + [{"ts": _now(), "event": status, "by": by, "note": note}]
    return _update(rid, status=status, audit=audit, decided_by=by) or rec


def execute(rid: str) -> Dict[str, Any]:
    """Attempt to execute an approved write action. Honest about every gate."""
    rec = get(rid)
    if not rec:
        return {"ok": False, "executed": False, "reason": "not_found"}
    cfg = WRITE_KINDS.get(rec["kind"], {})
    armed = providers.flag(cfg.get("flag", ""))
    audit = rec.get("audit", [])

    if rec.get("status") != "approved":
        audit = audit + [{"ts": _now(), "event": "execute_blocked", "reason": "not_approved"}]
        _update(rid, audit=audit)
        return {"ok": True, "executed": False, "reason": "not_approved", "status": rec.get("status")}

    if not armed:
        audit = audit + [{"ts": _now(), "event": "execute_blocked", "reason": "write_actions_disarmed"}]
        _update(rid, audit=audit)
        return {"ok": True, "executed": False, "reason": "write_actions_disarmed",
                "arm_env": cfg.get("flag"), "approval_kind": rec.get("approval_kind")}

    if not cfg.get("live_client"):
        audit = audit + [{"ts": _now(), "event": "execute_blocked", "reason": "no_live_client"}]
        _update(rid, audit=audit, status="armed_no_client")
        return {"ok": True, "executed": False, "reason": "no_live_client",
                "note": "write path is armed and approved; the live provider client is not enabled"}

    # A real live client would run here (not present on this box).
    audit = audit + [{"ts": _now(), "event": "execute_blocked", "reason": "no_live_client"}]
    _update(rid, audit=audit)
    return {"ok": True, "executed": False, "reason": "no_live_client"}


def posture() -> Dict[str, Any]:
    return {
        "kinds": {k: {"label": v["label"], "approval_kind": v["approval_kind"],
                      "armed": providers.flag(v["flag"]), "arm_env": v["flag"],
                      "live_client": v["live_client"]} for k, v in WRITE_KINDS.items()},
        "pending": len(list_requests("pending")),
        "note": "write actions require an approved request AND an armed flag; no fake success",
    }
