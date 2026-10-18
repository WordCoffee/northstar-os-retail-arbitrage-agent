"""Operator-window REA capture harness (V4.1 Step 3) — read-only, operator-gated.

Harvests competitor / operator UI *states* — DOM outline, component inventory,
value-free JSON body shapes, WebSocket frame inventory — **through Chrome Connect**
and writes redacted snapshots into the agent memory bank.

This module is the "operator" half of an REA capture: it validates a live, per-task
operator authorization, builds a strictly read-only observation task, redacts the
result, and files it as memory. It is the seam the model drives with the
`chromeconnect_*` tools during an operator window.

Non-negotiables (AGENTS.md — do not loosen):
  • **Chrome Connect is the controller; Playwright is only its tool.** This module
    never drives a browser. It hands a task to the controller via
    `chromeconnect_guard.cc_call` (or returns a plan for the model's
    `chromeconnect_run`). Direct Playwright use is refused by the Python guard.
  • **Read-only.** No clicks, no input, no form submission, no `Runtime.evaluate`,
    never credentials, CAPTCHA or login. A capture stops at any such boundary.
  • **Operator-gated.** A capture needs a live, per-task operator authorization for
    the target host; authorizations expire in at most 24 hours.
  • **The operator owns the host allowlist.** This module NEVER edits it. An
    unauthorized host is refused with the real reason.
  • **Honest.** Missing controller, missing authorization or a missing policy yields
    a `BLOCKED` result with a concrete reason — never a simulated or faked capture.

Packify first. Note honestly: Packify.ai is a packaging-design tool (design chat,
photoshoot, mockup editor, layered deep-agents). Its surfaces are captured as UI
*structure*; "listing/inventory" style panels only exist if the operator's own
screen has them. A different host (e.g. an Amazon seller surface) needs its own
allowlist entry and is out of scope here.
"""

from __future__ import annotations

import json
import os
import re
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional
from urllib.parse import urlsplit, urlunsplit

_REPO_ROOT = Path(__file__).resolve().parent.parent
POLICY_PATH = _REPO_ROOT / "config" / "chromecontrol_policy_owner.json"

AUTH_TTL_SECONDS = 24 * 3600  # operator grants expire in at most 24h
_MAX_AUTH_TTL_SECONDS = 24 * 3600

_READ_ONLY_RULES = (
    "READ-ONLY passive observation: observe DOM structure (node names/roles, no "
    "values), build a component/element inventory, and record value-free JSON "
    "request/response body shapes and WebSocket frame inventory. Do NOT click, type, "
    "submit a form, evaluate scripts, or handle any credential/CAPTCHA/login. Stop and "
    "report at any login, consent, CAPTCHA or rate-limit boundary."
)

# ---------------------------------------------------------------------------
# Target catalog (Packify first). `capture` = the value-free facets to collect.
# ---------------------------------------------------------------------------

REA_TARGETS: List[Dict[str, Any]] = [
    {
        "id": "packify_app_shell",
        "label": "Packify app shell / saved designs (listing) + any inventory-style panels",
        "host": "www.packify.ai",
        "url": "https://www.packify.ai/",
        "capture": ["dom_outline", "component_inventory", "json_body_shapes"],
        "why": "Baseline signed-in app structure and navigation; anchors field names for the live windows.",
    },
    {
        "id": "packify_photoshoot",
        "label": "Packify photoshoot coordinates pipeline",
        "host": "www.packify.ai",
        "url": "https://www.packify.ai/photoshoot",
        "capture": ["dom_outline", "json_body_shapes", "websocket_frames", "screenshot"],
        "why": "The photo/scene compositing contract (coordinates[] / extracted_coordinates) our scene compositor mirrors.",
    },
    {
        "id": "packify_mockup",
        "label": "Packify mockup editor (erase + composite text v2)",
        "host": "www.packify.ai",
        "url": "https://www.packify.ai/",
        "capture": ["dom_outline", "json_body_shapes", "websocket_frames"],
        "why": "Server contracts for putting a design onto a product photo and overlaying text.",
    },
    {
        "id": "packify_deep_agents",
        "label": "Packify deep-agents layering (layered, pausable generation)",
        "host": "www.packify.ai",
        "url": "https://www.packify.ai/",
        "capture": ["dom_outline", "json_body_shapes", "websocket_frames"],
        "why": "Event grammar + per-layer artifact payloads for our own AutothinK layering variant.",
    },
]

_TARGET_BY_ID = {t["id"]: t for t in REA_TARGETS}


def target_by_id(target_id: Optional[str]) -> Optional[Dict[str, Any]]:
    return _TARGET_BY_ID.get(str(target_id or ""))


# ---------------------------------------------------------------------------
# Operator-owned policy (read-only)
# ---------------------------------------------------------------------------

def load_operator_policy(path: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Read the operator-owned allowlist. Returns None if it is not present.

    This module NEVER writes this file.
    """
    p = Path(path or POLICY_PATH)
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return None


def _allowed_hosts(policy: Optional[Dict[str, Any]]) -> List[str]:
    if not policy:
        return []
    for key in ("allowed_hosts", "allowedHosts", "host_allowlist", "hosts"):
        val = policy.get(key)
        if isinstance(val, list):
            return [str(x).lower() for x in val]
        if isinstance(val, dict):
            return [str(k).lower() for k in val]
    return []


def host_allowed(host: str, policy: Optional[Dict[str, Any]] = None,
                 *, _loaded: bool = False) -> str:
    """Return 'allowed' | 'refused' | 'unknown' for a host.

    'unknown' means the operator-owned policy file is not present on this machine,
    so nothing can be assumed to be permitted.
    """
    if policy is None and not _loaded:
        policy = load_operator_policy()
    if policy is None:
        return "unknown"
    h = str(host or "").lower()
    for a in _allowed_hosts(policy):
        bare = a.lstrip("*.")
        if h == bare or h == a or h.endswith("." + bare):
            return "allowed"
    return "refused"


# ---------------------------------------------------------------------------
# Authorization (per-task, expiring)
# ---------------------------------------------------------------------------

def authorize(target_id: str, operator: str = "operator", *,
              now: Optional[datetime] = None,
              ttl_seconds: int = AUTH_TTL_SECONDS) -> Dict[str, Any]:
    """Create a per-task operator authorization record for a target.

    No credential or secret is captured — only who authorized what host, and until when.
    """
    t = target_by_id(target_id)
    if not t:
        raise ValueError(f"unknown REA target: {target_id}")
    ttl = max(1, min(int(ttl_seconds), _MAX_AUTH_TTL_SECONDS))
    n = now or datetime.now(timezone.utc)
    return {
        "id": str(uuid.uuid4()),
        "target_id": t["id"],
        "host": t["host"],
        "operator": str(operator or "operator"),
        "issued_at": n.isoformat(),
        "expires_at": (n + timedelta(seconds=ttl)).isoformat(),
        "read_only": True,
    }


def auth_valid(authorization: Optional[Dict[str, Any]], target_id: str, *,
               now: Optional[datetime] = None) -> bool:
    if not authorization or authorization.get("target_id") != target_id:
        return False
    n = now or datetime.now(timezone.utc)
    try:
        exp = datetime.fromisoformat(str(authorization.get("expires_at")))
    except Exception:  # noqa: BLE001
        return False
    if exp.tzinfo is None:
        exp = exp.replace(tzinfo=timezone.utc)
    return n < exp


# ---------------------------------------------------------------------------
# Task builder + plan (the gate)
# ---------------------------------------------------------------------------

def build_task(target: Dict[str, Any]) -> str:
    host = target.get("host")
    url = target.get("url") or f"https://{host}/"
    facets = ", ".join(target.get("capture") or [])
    return (
        f"Chrome Connect read-only capture of {url} (host {host}). "
        f"Collect ONLY these value-free facets: {facets}. "
        f"Stay on host {host}. {_READ_ONLY_RULES}"
    )


def plan_capture(target_id: str, *, authorization: Optional[Dict[str, Any]] = None,
                 policy: Optional[Dict[str, Any]] = None,
                 now: Optional[datetime] = None) -> Dict[str, Any]:
    """Validate the operator gate + allowlist and return a READY plan or a BLOCKED result."""
    t = target_by_id(target_id)
    if not t:
        return {"ok": False, "status": "BLOCKED", "reason": "unknown_target",
                "detail": f"no REA target named '{target_id}'",
                "known_targets": [x["id"] for x in REA_TARGETS]}
    if not auth_valid(authorization, target_id, now=now):
        return {"ok": False, "status": "BLOCKED", "reason": "operator_authorization_required",
                "detail": ("a live, per-task operator authorization is required for this host; "
                           "captures are never run implicitly."),
                "target": t["id"], "host": t["host"]}
    allowed = host_allowed(t["host"], policy)
    if allowed != "allowed":
        detail = (f"host '{t['host']}' is '{allowed}' in the operator-owned policy. "
                  "The operator owns the allowlist and must authorize this host; this "
                  "module never edits it.")
        if allowed == "unknown":
            detail = (f"the operator-owned policy file was not found ({POLICY_PATH.name}); "
                      "no host may be assumed permitted. The operator must record the allowlist.")
        return {"ok": False, "status": "BLOCKED", "reason": "host_not_allowlisted",
                "detail": detail, "target": t["id"], "host": t["host"], "policy": allowed}
    return {"ok": True, "status": "READY", "target": t["id"], "host": t["host"],
            "url": t["url"], "capture": list(t.get("capture") or []),
            "task": build_task(t), "read_only": True}


def _default_controller() -> Optional[Callable[[str], Any]]:
    """Import the sanctioned controller hand-off (chromeconnect_guard.cc_call).

    Returns None if the guard is not importable — the caller then stays BLOCKED
    rather than reaching for a browser directly.
    """
    try:
        import sys
        guard_dir = str(_REPO_ROOT / "tools")
        if guard_dir not in sys.path:
            sys.path.insert(0, guard_dir)
        import chromeconnect_guard  # type: ignore
        return chromeconnect_guard.cc_call
    except Exception:  # noqa: BLE001
        return None


def run_capture(target_id: str, *, authorization: Optional[Dict[str, Any]] = None,
                policy: Optional[Dict[str, Any]] = None, dry_run: bool = True,
                controller: Optional[Callable[[str], Any]] = None,
                now: Optional[datetime] = None) -> Dict[str, Any]:
    """Plan, then (optionally) hand the read-only task to Chrome Connect.

    Safe default: dry_run=True → returns the READY plan and calls nothing. A live
    call happens only with dry_run=False AND a valid authorization + allowlisted
    host AND an available controller.
    """
    plan = plan_capture(target_id, authorization=authorization, policy=policy, now=now)
    if not plan.get("ok"):
        return plan
    if dry_run:
        return {**plan, "mode": "dry_run", "detail": "plan only; no controller call made"}

    ctrl = controller or _default_controller()
    if ctrl is None:
        return {"ok": False, "status": "BLOCKED", "reason": "controller_not_found",
                "detail": "Chrome Connect controller hand-off is unavailable; nothing was launched.",
                "target": target_id}
    try:
        result = ctrl(plan["task"])
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "status": "ERROR", "reason": "controller_error",
                "detail": str(exc)[:200], "target": target_id}
    return {"ok": True, "status": "CAPTURED", "target": target_id,
            "mode": "live", "result": result, "read_only": True}


# ---------------------------------------------------------------------------
# Redaction + memory ingestion (the "feed agent memory" hook)
# ---------------------------------------------------------------------------

# Secret-bearing key=value pairs, including AWS presign params and a bare Bearer token.
_KV_SECRET = re.compile(
    r"((?:X-Amz-[A-Za-z0-9_\-]+|Signature|token|api[_-]?key|access[_-]?token|"
    r"session[_-]?id|secret|password|passwd|pwd)=)([^&\s]+)",
    re.IGNORECASE)
_BEARER = re.compile(r"(Bearer\s+)\S+", re.IGNORECASE)
_TOKEN_HINT = re.compile(
    r"(X-Amz-|Signature=|token=|api[_-]?key|access[_-]?token|Bearer\s|session[_-]?id)",
    re.IGNORECASE)


def redact_url(url: str) -> str:
    """Return an absolute URL with userinfo and the entire query string removed."""
    try:
        p = urlsplit(str(url))
        host = p.hostname or ""
        netloc = f"{host}:{p.port}" if p.port else host
        return urlunsplit((p.scheme, netloc, p.path, "", ""))
    except Exception:  # noqa: BLE001
        return str(url)


def redact_text(text: str) -> str:
    """Replace token-shaped substrings AND their values. A blunt, safe scrub."""
    s = str(text or "")
    s = _KV_SECRET.sub(lambda m: f"{m.group(1)}<redacted>", s)
    s = _BEARER.sub(lambda m: f"{m.group(1)}<redacted>", s)
    return _TOKEN_HINT.sub("<redacted>", s)


def summarize_capture(payload: Any) -> str:
    """A compact, value-free summary of a Chrome Connect / REA capture payload."""
    if not isinstance(payload, dict):
        return "REA passive capture (unstructured payload; no values retained)."
    res = payload.get("normalized_result", payload)
    net = (res.get("network") or {}) if isinstance(res, dict) else {}
    reqs = net.get("requests") or []
    ws = net.get("websocket_frames") or []
    lines = [f"REA passive capture — {len(reqs)} request(s), {len(ws)} ws frame(s)."]
    eps: List[str] = []
    for r in reqs[:40]:
        if isinstance(r, dict):
            eps.append(f"{r.get('method') or '?'} {redact_url(r.get('url') or '')}")
    if eps:
        lines.append("Endpoints: " + "; ".join(eps))
    return redact_text("\n".join(lines))[:4000]


def ingest_capture(db: Any, *, target_id: str, payload: Any,
                   authorization: Dict[str, Any],
                   account_id: str = "operator") -> Dict[str, Any]:
    """File a redacted capture into the agent memory bank. Returns the memory id."""
    t = target_by_id(target_id) or {"id": target_id, "host": "?", "url": "?"}
    entry = {
        "account_id": account_id,
        "entry_type": "rea_capture",
        "content": summarize_capture(payload),
        "source": f"rea_capture:{target_id}",
        "confidence": 0.6,
        "tags": ["rea_capture", str(target_id), str(t.get("host") or "")],
        "provenance": {
            "target": target_id,
            "host": t.get("host"),
            "url": redact_url(t.get("url") or ""),
            "operator": (authorization or {}).get("operator"),
            "authorized_at": (authorization or {}).get("issued_at"),
            "read_only": True,
            "source_kind": "chrome_connect_passive",
        },
    }
    eid = db.memory.ingest(entry)
    return {"ok": True, "memory_id": eid, "target": target_id, "host": t.get("host")}


def list_captures(db: Any, account_id: str = "operator", limit: int = 50) -> List[Dict[str, Any]]:
    """List stored REA capture memory entries for an account."""
    rows = db.memory.list_by_account(account_id, limit=max(int(limit), 1))
    return [r for r in rows if r.get("entry_type") == "rea_capture"]


if __name__ == "__main__":  # operator self-service: show the plan for each target (dry-run)
    import sys as _sys
    policy = load_operator_policy()
    print(f"operator policy present: {policy is not None} "
          f"({'config/' + POLICY_PATH.name if policy is not None else 'MISSING'})")
    for t in REA_TARGETS:
        print(f"- {t['id']:22s} host={t['host']:16s} "
              f"allowlist={host_allowed(t['host'], policy)}")
    if len(_sys.argv) > 1:
        auth = authorize(_sys.argv[1])
        print(json.dumps(run_capture(_sys.argv[1], authorization=auth, policy=policy),
                         indent=2)[:1200])
