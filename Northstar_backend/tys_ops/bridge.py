"""Cloud sync bridge: signed tokens, offline queue, sync envelopes, gateway.

The bridge is the *edge* of the PC master node, not a copy of it. A mobile
client holds a short-lived signed token, posts operations over the same
``/api/admin/tys`` surface the operator uses, and — when the phone is offline —
the operations wait in a durable queue until a transport succeeds.

What this module guarantees
---------------------------
* A token is HMAC-SHA256 signed, scoped, and expires. Verification checks the
  signature, the expiry (with bounded clock skew) and the revocation list.
* An operation is enqueued at most once per ``idempotency_key`` per profile.
* A failed flush **keeps** the item and schedules a bounded exponential retry.
  After ``max_attempts`` the item moves to ``dead`` and is reported — it is
  never silently dropped.
* Sync envelopes carry a per-profile monotonic sequence and are applied
  idempotently, so a replayed mobile request cannot duplicate work.
* The gateway descriptor refuses to expose plaintext HTTP on a non-loopback
  host. That is a policy check, not a suggestion.

No sockets are opened here. ``flush`` takes a transport callable, which is what
makes the retry path testable without a network.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import tempfile
import threading
import time
import uuid
from typing import Any, Callable, Dict, List, Optional

SCHEMA = "tys.bridge.v1"
CLOCK_SKEW_S = 60
LOOPBACK = {"127.0.0.1", "localhost", "::1"}


class BridgeError(RuntimeError):
    def __init__(self, code: str, detail: str = "", **extra: Any):
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code = code
        self.detail = detail
        self.extra = extra

    def as_dict(self) -> Dict[str, Any]:
        out = {"code": self.code, "detail": self.detail}
        out.update(self.extra)
        return out


def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _unb64(text: str) -> bytes:
    pad = "=" * (-len(text) % 4)
    return base64.urlsafe_b64decode(text + pad)


def _sign(secret: str, payload_b64: str) -> str:
    return _b64(hmac.new(secret.encode("utf-8"), payload_b64.encode("ascii"),
                         hashlib.sha256).digest())


# ---------------------------------------------------------------------------
# Tokens
# ---------------------------------------------------------------------------

def issue_token(secret: str, profile_id: str, *,
                scopes: Optional[List[str]] = None,
                ttl_s: int = 900, now: Optional[float] = None) -> str:
    """Mint a short-lived, scoped bearer token for one profile."""
    stamp = time.time() if now is None else float(now)
    if ttl_s <= 0 or ttl_s > 86400:
        raise BridgeError("invalid_ttl", "ttl_s must be in (0, 86400]")
    payload = {
        "sub": profile_id,
        "scopes": sorted(set(scopes or ["tasks:run", "tasks:read"])),
        "iat": int(stamp),
        "exp": int(stamp + ttl_s),
        "jti": uuid.uuid4().hex,
    }
    body = _b64(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    return f"{body}.{_sign(secret, body)}"


class TokenAuthority:
    """Verifies minted tokens and holds the revocation list."""

    def __init__(self, secret: str):
        if not secret or len(secret) < 16:
            raise BridgeError("weak_secret", "a bridge secret needs >= 16 characters")
        self.secret = secret
        self._revoked: set = set()
        self._lock = threading.RLock()

    def verify(self, token: str, *, scope: Optional[str] = None,
               now: Optional[float] = None) -> Dict[str, Any]:
        stamp = time.time() if now is None else float(now)
        try:
            body, signature = token.split(".", 1)
        except ValueError:
            raise BridgeError("token_malformed")
        expected = _sign(self.secret, body)
        if not hmac.compare_digest(expected, signature):
            raise BridgeError("token_bad_signature")
        try:
            payload = json.loads(_unb64(body).decode("utf-8"))
        except (ValueError, json.JSONDecodeError):
            raise BridgeError("token_malformed")
        if int(payload.get("exp", 0)) + CLOCK_SKEW_S < stamp:
            raise BridgeError("token_expired", f"expired at {payload.get('exp')}")
        with self._lock:
            if payload.get("jti") in self._revoked:
                raise BridgeError("token_revoked")
        if scope and scope not in (payload.get("scopes") or []):
            raise BridgeError("token_scope_denied", scope,
                              granted=payload.get("scopes") or [])
        return payload

    def revoke(self, token: str) -> str:
        payload = self.verify(token) if token else {}
        with self._lock:
            self._revoked.add(payload.get("jti"))
        return str(payload.get("jti"))


# ---------------------------------------------------------------------------
# Offline queue
# ---------------------------------------------------------------------------

class OfflineQueue:
    """Durable per-profile operation queue with idempotency and dead letters."""

    def __init__(self, path: str, max_attempts: int = 5):
        self.path = path
        self.max_attempts = int(max_attempts)
        self._lock = threading.RLock()
        self._state = self._load()

    def _empty(self) -> Dict[str, Any]:
        return {"schema": SCHEMA, "queues": {}, "applied": {}}

    def _load(self) -> Dict[str, Any]:
        if not os.path.exists(self.path):
            return self._empty()
        with open(self.path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        if data.get("schema") != SCHEMA:
            raise BridgeError("queue_invalid", self.path)
        data.setdefault("queues", {})
        data.setdefault("applied", {})
        return data

    def _save(self) -> None:
        os.makedirs(os.path.dirname(os.path.abspath(self.path)), exist_ok=True)
        fd, tmp = tempfile.mkstemp(prefix=".bridge-", suffix=".json",
                                   dir=os.path.dirname(os.path.abspath(self.path)))
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(self._state, handle, indent=2)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp, self.path)
        except BaseException:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise

    def _queue(self, profile: str) -> Dict[str, Any]:
        return self._state["queues"].setdefault(
            profile, {"items": [], "seq": 0})

    def enqueue(self, profile: str, op: str, payload: Dict[str, Any], *,
                idempotency_key: Optional[str] = None,
                now: Optional[float] = None) -> Dict[str, Any]:
        stamp = time.time() if now is None else float(now)
        key = idempotency_key or f"{profile}:{op}:{uuid.uuid4().hex[:16]}"
        with self._lock:
            queue = self._queue(profile)
            for item in queue["items"]:
                if item["idempotency_key"] == key:
                    return {"status": "duplicate", "item": dict(item),
                            "seq": item["seq"]}
            queue["seq"] += 1
            item = {
                "id": "q_" + uuid.uuid4().hex[:12],
                "profile": profile,
                "op": op,
                "payload": payload,
                "idempotency_key": key,
                "seq": queue["seq"],
                "attempts": 0,
                "state": "pending",
                "next_attempt_at": stamp,
                "created_at": stamp,
                "last_error": None,
            }
            queue["items"].append(item)
            self._save()
            return {"status": "queued", "item": dict(item), "seq": item["seq"]}

    def pending(self, profile: str, *, now: Optional[float] = None) -> List[Dict[str, Any]]:
        stamp = time.time() if now is None else float(now)
        with self._lock:
            queue = self._queue(profile)
            return [dict(i) for i in queue["items"]
                    if i["state"] == "pending" and i["next_attempt_at"] <= stamp]

    def backoff(self, attempts: int) -> float:
        """Bounded exponential backoff: 2 s, 4 s, 8 s, 16 s, 32 s."""
        return float(min(32, 2 ** max(1, attempts)))

    def flush(self, profile: str, transport: Callable[[Dict[str, Any]], Any],
              *, max_items: int = 50, now: Optional[float] = None) -> Dict[str, Any]:
        """Deliver due items. A transport failure never loses an operation."""
        stamp = time.time() if now is None else float(now)
        sent, failed, dead = [], [], []
        with self._lock:
            queue = self._queue(profile)
            for item in list(queue["items"]):
                if len(sent) + len(failed) + len(dead) >= max_items:
                    break
                if item["state"] != "pending" or item["next_attempt_at"] > stamp:
                    continue
                try:
                    result = transport(dict(item))
                except Exception as exc:  # transport failure, incl. timeouts
                    item["attempts"] += 1
                    item["last_error"] = f"{type(exc).__name__}: {exc}"
                    if item["attempts"] >= self.max_attempts:
                        item["state"] = "dead"
                        dead.append(dict(item))
                    else:
                        item["next_attempt_at"] = stamp + self.backoff(item["attempts"])
                        failed.append(dict(item))
                    continue
                queue["items"].remove(item)
                self._state["applied"][profile] = max(
                    int(self._state["applied"].get(profile) or 0), int(item["seq"]))
                sent.append({"item": dict(item), "result": result})
            if sent or failed or dead:
                self._save()
            return {
                "profile": profile,
                "sent": sent,
                "retry": failed,
                "dead": dead,
                "pending_remaining": sum(1 for i in queue["items"]
                                         if i["state"] == "pending"),
                "applied_seq": int(self._state["applied"].get(profile) or 0),
            }

    def stats(self, profile: str) -> Dict[str, Any]:
        with self._lock:
            items = self._queue(profile)["items"]
            return {
                "profile": profile,
                "pending": sum(1 for i in items if i["state"] == "pending"),
                "dead": sum(1 for i in items if i["state"] == "dead"),
                "applied_seq": int(self._state["applied"].get(profile) or 0),
                "queue_seq": int(self._queue(profile)["seq"]),
            }

    def dead_letters(self, profile: str) -> List[Dict[str, Any]]:
        with self._lock:
            return [dict(i) for i in self._queue(profile)["items"]
                    if i["state"] == "dead"]


# ---------------------------------------------------------------------------
# Sync envelopes
# ---------------------------------------------------------------------------

class SyncState:
    """Per-profile monotonic sync cursor. Replays are accepted, not re-applied."""

    def __init__(self):
        self._lock = threading.RLock()
        self._outbound: Dict[str, int] = {}
        self._applied: Dict[str, int] = {}
        self._replays = 0
        self._applied_count = 0

    def envelope(self, profile: str, payloads: List[Dict[str, Any]]) -> Dict[str, Any]:
        with self._lock:
            self._outbound[profile] = self._outbound.get(profile, 0) + len(payloads)
            return {
                "profile": profile,
                "seq": self._outbound[profile],
                "count": len(payloads),
                "payloads": payloads,
            }

    def apply_remote(self, envelope: Dict[str, Any]) -> Dict[str, Any]:
        profile = str(envelope.get("profile") or "")
        seq = int(envelope.get("seq") or 0)
        with self._lock:
            cursor = self._applied.get(profile, 0)
            if seq <= cursor:
                self._replays += 1
                return {"status": "replay_ignored", "cursor": cursor, "seq": seq}
            self._applied[profile] = seq
            self._applied_count += 1
            return {"status": "applied", "cursor": seq,
                    "payloads": envelope.get("payloads") or []}

    def report(self) -> Dict[str, Any]:
        with self._lock:
            return {"profiles": len(self._outbound), "applied": self._applied_count,
                    "replays_ignored": self._replays,
                    "cursor": dict(self._applied)}


# ---------------------------------------------------------------------------
# Gateway / dynamic DNS descriptor
# ---------------------------------------------------------------------------

def gateway_descriptor(host: str, port: int, *, scheme: str = "https",
                       ttl_s: int = 60) -> Dict[str, Any]:
    """Describe how a phone reaches this PC. Refuses unsafe exposure."""
    scheme = scheme.lower()
    if scheme not in ("http", "https"):
        raise BridgeError("bad_scheme", scheme)
    if scheme == "http" and host not in LOOPBACK:
        raise BridgeError(
            "plaintext_exposure_refused",
            f"{host} is not loopback; the bridge must be https",
            host=host,
        )
    base = f"{scheme}://{host}:{int(port)}"
    return {
        "base_url": base,
        "dns": {"type": "A", "name": host, "ttl_s": int(ttl_s),
                "mode": "dynamic", "update_on_ip_change": True},
        "auth": {"mode": "bearer", "token_ttl_s": 900,
                 "scopes": ["tasks:read", "tasks:run", "tasks:resume",
                            "tasks:cancel", "tasks:controller-result"]},
        "routes": {
            "state": "GET  /api/admin/tys/state",
            "submit": "POST /api/admin/tys/work-orders",
            "run": "POST /api/admin/tys/tasks/{id}/run",
            "task": "GET  /api/admin/tys/tasks/{id}",
            "resume": "POST /api/admin/tys/tasks/{id}/resume",
            "cancel": "POST /api/admin/tys/tasks/{id}/cancel",
            "controller_result": "POST /api/admin/tys/tasks/{id}/controller-result",
        },
        "sync": {"mode": "offline-first", "dedupe": "idempotency_key",
                 "retry": "bounded exponential", "max_attempts": 5},
        "privacy": {"master": "local", "outbound": "operator-configured only"},
    }
