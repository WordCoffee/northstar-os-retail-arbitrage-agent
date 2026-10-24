"""Autothink handoff transport — the part that actually carries the brief.

`specialists/router.py scope()` prices an engineering handoff and tells the
operator *"say 'send it to Autothink' to proceed"*. Until this module existed,
nothing carried it anywhere: the offer was real, the delivery was not.

Rules, in order of what they protect:

1. **No send without an explicit approval.** ``approved_by`` is required, by
   name. The router's ``requires_user_approval`` is not advisory.
2. **No send without an endpoint.** Unconfigured is a refusal that names what is
   missing — never a stub that reports success and moves on.
3. **One attempt, never a retry.** A failed send writes a receipt with the
   reason. Sending again is a second decision, not an automatic one.
4. **A charge ceiling is mandatory.** Autothink is priced on the cloud lane; if
   the estimate exceeds the ceiling, nothing leaves the machine.
5. **The token is never recorded.** Not in a receipt, not in an error string,
   not in a journal line.
6. **No double charge.** A packet id that already has a successful receipt is
   refused as ``already_sent``.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Mapping, Optional, Tuple

DEFAULT_TIMEOUT_S = 30.0
_DEFAULT_JOURNAL = Path(__file__).resolve().parent.parent / "data" / "autothink-handoffs.jsonl"

# transport(url, payload, headers, timeout) -> (http_status, body_text)
Transport = Callable[[str, Dict[str, Any], Dict[str, str], float], Tuple[int, str]]


class TransportError(RuntimeError):
    """A send attempt that never produced an HTTP response."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _env(env: Optional[Mapping[str, str]]) -> Mapping[str, str]:
    return os.environ if env is None else env


def redact(text: Any, token: Optional[str]) -> str:
    """Strip the bearer token out of anything that might be written or shown."""
    out = str(text if text is not None else "")
    if token and len(token) >= 6:
        out = out.replace(token, "***")
    return out


def status(env: Optional[Mapping[str, str]] = None) -> Dict[str, Any]:
    """Report whether a send could happen, and name every missing piece."""
    e = _env(env)
    endpoint = (e.get("AUTOTHINK_ENDPOINT") or "").strip()
    live = (e.get("AUTOTHINK_LIVE") or "").strip() == "1"
    token = (e.get("AUTOTHINK_TOKEN") or "").strip() or None
    blockers = []
    if not endpoint:
        blockers.append("AUTOTHINK_ENDPOINT is not set")
    if not live:
        blockers.append("AUTOTHINK_LIVE is not 1 (the premium lane is not armed)")
    return {
        "configured": not blockers,
        "endpoint_set": bool(endpoint),
        "endpoint_host": _host(endpoint) if endpoint else None,
        "lane_armed": live,
        "token_set": bool(token),
        "blockers": blockers,
        "note": ("Nothing is sent while any blocker is listed. A send also needs an "
                 "explicit approval and a charge ceiling, every time."),
    }


def _host(url: str) -> str:
    rest = str(url).split("://", 1)[-1]
    return rest.split("/", 1)[0]


def build_packet(request: str, env: Optional[Mapping[str, str]] = None) -> Dict[str, Any]:
    """Turn an engineering request into the exact brief that would be sent.

    The decision to hand off is NOT re-implemented here: it comes from
    `router.scope`, so there is one place that decides what is engineering work.
    """
    from specialists import router

    text = str(request or "").strip()
    if not text:
        return {"ok": False, "reason": "empty_request",
                "error": "There is no request to send."}

    decision = router.scope(text)
    if not decision.get("offer_handoff"):
        return {"ok": False, "reason": "not_engineering",
                "error": ("This is Bojo's own work, so there is nothing to hand off: "
                          + str(decision.get("reason") or ""))}

    handoff = decision.get("handoff") or {}
    packet_id = "ath_" + hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]
    return {
        "ok": True,
        "packet_id": packet_id,
        "request": text,
        "target": handoff.get("target") or "autothink",
        "why": handoff.get("why"),
        "acceptance": handoff.get("acceptance") or [],
        "estimated_tokens": handoff.get("estimated_tokens"),
        "estimated_cost_usd": handoff.get("estimated_cost_usd"),
        "estimated_charge_usd": handoff.get("estimated_charge_usd"),
        "priced_on": handoff.get("priced_on"),
        "status": status(env),
    }


def _journal_path(env: Optional[Mapping[str, str]] = None,
                  override: Optional[Path] = None) -> Path:
    if override is not None:
        return Path(override)
    raw = (_env(env).get("AUTOTHINK_JOURNAL") or "").strip()
    return Path(raw) if raw else _DEFAULT_JOURNAL


def _already_sent(packet_id: str, path: Path) -> Optional[Dict[str, Any]]:
    """True only for a *successful* prior receipt — a failure may be retried by hand."""
    if not path.exists():
        return None
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if row.get("packet_id") == packet_id and row.get("ok") is True:
            return row
    return None


def _write_receipt(path: Path, receipt: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(receipt, ensure_ascii=False, sort_keys=True) + "\n")


def _post_json(url: str, payload: Dict[str, Any], headers: Dict[str, str],
               timeout: float) -> Tuple[int, str]:
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 - endpoint is operator-configured
            return int(resp.status), resp.read(200_000).decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        return int(exc.code), (exc.read(20_000).decode("utf-8", "replace") if exc.fp else "")
    except Exception as exc:  # noqa: BLE001 - the message is scrubbed and reported, never swallowed
        raise TransportError(str(exc)) from exc


def send(packet: Dict[str, Any], *, approved_by: Optional[str],
         max_charge_usd: Optional[float], transport: Optional[Transport] = None,
         env: Optional[Mapping[str, str]] = None,
         journal_path: Optional[Path] = None,
         timeout: float = DEFAULT_TIMEOUT_S) -> Dict[str, Any]:
    """Send one packet, at most once.

    Every refusal returns before any network call. Failures return a receipt;
    neither case raises, because the caller has to be able to tell the operator
    what happened.
    """
    e = _env(env)
    token = (e.get("AUTOTHINK_TOKEN") or "").strip() or None
    path = _journal_path(e, journal_path)

    if not packet.get("ok"):
        return {"ok": False, "status": "refused", "reason": "bad_packet",
                "error": packet.get("error")}

    approval = str(approved_by or "").strip()
    if not approval:
        return {"ok": False, "status": "refused", "reason": "approval_required",
                "error": ("Nothing was sent. An Autothink handoff costs money, so it needs "
                          "an explicit approval naming who approved it.")}

    st = status(e)
    if not st["configured"]:
        return {"ok": False, "status": "refused", "reason": "not_configured",
                "error": "Nothing was sent: " + "; ".join(st["blockers"]),
                "blockers": st["blockers"]}

    charge = packet.get("estimated_charge_usd")
    if max_charge_usd is None:
        return {"ok": False, "status": "refused", "reason": "no_charge_ceiling",
                "error": ("Nothing was sent. Name a ceiling (max_charge_usd) so the "
                          f"estimated charge {charge} cannot be exceeded silently."),
                "estimated_charge_usd": charge}
    try:
        ceiling = float(max_charge_usd)
    except (TypeError, ValueError):
        return {"ok": False, "status": "refused", "reason": "bad_charge_ceiling",
                "error": f"max_charge_usd must be a number, got {max_charge_usd!r}."}
    if charge is not None and float(charge) > ceiling:
        return {"ok": False, "status": "refused", "reason": "charge_exceeds_ceiling",
                "error": (f"Nothing was sent: the estimate is {charge} and the ceiling is "
                          f"{ceiling}."),
                "estimated_charge_usd": charge, "max_charge_usd": ceiling}

    prior = _already_sent(str(packet.get("packet_id")), path)
    if prior is not None:
        return {"ok": False, "status": "refused", "reason": "already_sent",
                "error": ("This exact brief has already been accepted by Autothink; sending "
                          "it again would charge twice."),
                "prior_receipt": prior}

    url = str(e.get("AUTOTHINK_ENDPOINT")).strip()
    headers = {"Content-Type": "application/json", "Accept": "application/json",
               "User-Agent": "NorthstarOS-autothink/1.0"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    payload = {k: v for k, v in packet.items() if k != "status"}
    send_it = transport or _post_json
    receipt: Dict[str, Any] = {
        "ts": _now(), "packet_id": packet.get("packet_id"),
        "endpoint_host": _host(url), "approved_by": approval,
        "estimated_charge_usd": charge, "max_charge_usd": ceiling, "attempt": 1,
    }

    try:
        http_status, body = send_it(url, payload, headers, timeout)
    except Exception as exc:  # noqa: BLE001 - one attempt; the reason is recorded
        receipt.update({"ok": False, "status": "failed", "http_status": None,
                        "error": redact(exc, token)})
        _write_receipt(path, receipt)
        return {"ok": False, "status": "failed", "reason": "transport_error",
                "error": redact(exc, token), "receipt": receipt}

    ok = 200 <= int(http_status) < 300
    response_id = None
    try:
        parsed = json.loads(body) if body else {}
        if isinstance(parsed, dict):
            response_id = parsed.get("id") or parsed.get("job_id") or parsed.get("request_id")
    except ValueError:
        parsed = None

    receipt.update({"ok": ok, "status": "sent" if ok else "failed",
                    "http_status": int(http_status), "response_id": response_id,
                    "response_excerpt": redact(body[:500], token)})
    if not ok:
        receipt["error"] = f"endpoint returned HTTP {int(http_status)}"
    _write_receipt(path, receipt)

    return {"ok": ok, "status": "sent" if ok else "failed",
            "reason": None if ok else "http_error",
            "receipt": receipt,
            "error": None if ok else f"Autothink answered HTTP {int(http_status)}; nothing was retried.",
            "journal": str(path)}
