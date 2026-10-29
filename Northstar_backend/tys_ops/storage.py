"""Hybrid storage: local master repository + tiered media quota.

The rule this module encodes: **the PC is the master**. Media written by a
seller's session lands in a local directory, is accounted for in a local
ledger, and only leaves the machine through a path the operator configured.
There is no implicit upload anywhere in this file.

Tiers
-----
``free``      1 GB of temporary image storage, **zero** video retention.
``paid_10gb`` 10 GB total, video retained for a configurable window (30 days
              by default) and still purged when the window closes.

Behaviour that is deliberately explicit rather than silent:

* a free-tier video is *not stored*. It comes back as
  ``status="not_stored"`` with ``retention_seconds=0`` and a download prompt.
  Nothing is quietly kept and nothing is quietly dropped.
* pushing past the image cap prunes the oldest **unprotected** images only.
  Downloaded or paid-retained media is never pruned to make room.
* if pruning cannot free enough, the call refuses with ``over_quota`` and the
  exact byte deficit. It never writes past the cap.
* a session end purges media that was never downloaded and returns the prompts
  the client must show.

The ledger is a single JSON document, rewritten atomically. It is small
(metadata only), so this is sufficient and keeps the module dependency-free.
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import threading
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional

GB = 1024 ** 3
DAY = 86400

MAX_PROFILES = 100

TIERS: Dict[str, Dict[str, Any]] = {
    "free": {
        "label": "included",
        "image_quota_bytes": 1 * GB,
        "total_quota_bytes": 1 * GB,
        "video_retention_s": 0,
        "price_note": "included",
    },
    "paid_10gb": {
        "label": "10 GB tier",
        "image_quota_bytes": 10 * GB,
        "total_quota_bytes": 10 * GB,
        "video_retention_s": 30 * DAY,
        "price_note": "explicit opt-in / paid tier",
    },
}

KINDS = ("image", "video")


class StorageError(RuntimeError):
    """Stable, machine-readable storage refusal."""

    def __init__(self, code: str, detail: str = "", **extra: Any):
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code = code
        self.detail = detail
        self.extra = extra

    def as_dict(self) -> Dict[str, Any]:
        out = {"code": self.code, "detail": self.detail}
        out.update(self.extra)
        return out


def _iso(ts: Optional[float] = None) -> str:
    return datetime.fromtimestamp(ts if ts is not None else time.time(),
                                  tz=timezone.utc).isoformat()


def _atomic_json(path: str, payload: Dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".storage-", suffix=".json",
                               dir=os.path.dirname(os.path.abspath(path)))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, sort_keys=False)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


class StorageLedger:
    """Per-profile media accounting with tier policy enforcement."""

    SCHEMA = "tys.storage.v1"

    def __init__(self, path: str, root: Optional[str] = None):
        self.path = path
        self.root = root or os.path.join(os.path.dirname(os.path.abspath(path)), "media")
        self._lock = threading.RLock()
        self._state = self._load()

    # -- persistence -------------------------------------------------------

    def _empty(self) -> Dict[str, Any]:
        return {"schema": self.SCHEMA, "profiles": {}, "media": [],
                "alerts": [], "download_prompts": [], "sessions": {}}

    def _load(self) -> Dict[str, Any]:
        if not os.path.exists(self.path):
            return self._empty()
        with open(self.path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        if not isinstance(data, dict) or data.get("schema") != self.SCHEMA:
            raise StorageError("ledger_invalid", f"{self.path} is not a {self.SCHEMA} ledger")
        for key, default in self._empty().items():
            data.setdefault(key, default)
        return data

    def _save(self) -> None:
        _atomic_json(self.path, self._state)

    # -- profiles ----------------------------------------------------------

    def register_profile(self, profile_id: str, tier: str = "free",
                         quota_bytes: Optional[int] = None) -> Dict[str, Any]:
        with self._lock:
            if tier not in TIERS:
                raise StorageError("unknown_tier", tier)
            existing = self._state["profiles"].get(profile_id)
            if existing:
                return dict(existing)
            if len(self._state["profiles"]) >= MAX_PROFILES:
                raise StorageError(
                    "profile_cap_reached",
                    f"{MAX_PROFILES} power-user profiles are already registered",
                    cap=MAX_PROFILES,
                )
            cfg = TIERS[tier]
            profile = {
                "id": profile_id,
                "tier": tier,
                "image_quota_bytes": int(quota_bytes or cfg["image_quota_bytes"]),
                "total_quota_bytes": int(cfg["total_quota_bytes"]),
                "video_retention_s": int(cfg["video_retention_s"]),
                "created_at": _iso(),
            }
            self._state["profiles"][profile_id] = profile
            self._state["sessions"].setdefault(profile_id, {"opened_at": _iso(),
                                                            "seq": 0})
            self._save()
            return dict(profile)

    def profile(self, profile_id: str) -> Dict[str, Any]:
        prof = self._state["profiles"].get(profile_id)
        if not prof:
            raise StorageError("unknown_profile", profile_id)
        return prof

    def upgrade_tier(self, profile_id: str, tier: str) -> Dict[str, Any]:
        with self._lock:
            prof = self.profile(profile_id)
            if tier not in TIERS:
                raise StorageError("unknown_tier", tier)
            cfg = TIERS[tier]
            prof["tier"] = tier
            prof["image_quota_bytes"] = int(cfg["image_quota_bytes"])
            prof["total_quota_bytes"] = int(cfg["total_quota_bytes"])
            prof["video_retention_s"] = int(cfg["video_retention_s"])
            prof["upgraded_at"] = _iso()
            self._save()
            return dict(prof)

    # -- accounting --------------------------------------------------------

    def _active(self, profile_id: str) -> List[Dict[str, Any]]:
        return [m for m in self._state["media"]
                if m["profile"] == profile_id and m["state"] == "active"]

    def media(self, profile_id: str, *, state: Optional[str] = "active") -> List[Dict[str, Any]]:
        """Read-only view of a profile's media, newest last."""
        with self._lock:
            return [dict(m) for m in self._state["media"]
                    if m["profile"] == profile_id
                    and (state is None or m["state"] == state)]

    def usage(self, profile_id: str) -> Dict[str, Any]:
        active = self._active(profile_id)
        images = sum(m["bytes"] for m in active if m["kind"] == "image")
        videos = sum(m["bytes"] for m in active if m["kind"] == "video")
        prof = self.profile(profile_id)
        return {
            "profile": profile_id,
            "tier": prof["tier"],
            "image_bytes": images,
            "video_bytes": videos,
            "total_bytes": images + videos,
            "image_quota_bytes": prof["image_quota_bytes"],
            "total_quota_bytes": prof["total_quota_bytes"],
            "image_free_bytes": max(0, prof["image_quota_bytes"] - images),
            "total_free_bytes": max(0, prof["total_quota_bytes"] - images - videos),
            "items": len(active),
        }

    # -- pruning -----------------------------------------------------------

    def _prunable(self, profile_id: str, kind: Optional[str] = None) -> List[Dict[str, Any]]:
        """Oldest first. Protected media is never a candidate."""
        candidates = [
            m for m in self._active(profile_id)
            if not m.get("downloaded") and not m.get("retained")
            and (kind is None or m["kind"] == kind)
        ]
        return sorted(candidates, key=lambda m: (m["stored_at"], m["id"]))

    def prune(self, profile_id: str, target_bytes: int, kind: Optional[str] = None,
              now: Optional[float] = None) -> Dict[str, Any]:
        """Purge unprotected media until usage is at or under ``target_bytes``."""
        with self._lock:
            removed: List[Dict[str, Any]] = []
            freed = 0
            # total usage matters for the total cap, kind usage for the image cap
            while True:
                usage = self.usage(profile_id)
                current = usage["image_bytes"] if kind == "image" else usage["total_bytes"]
                if current <= target_bytes:
                    break
                candidates = self._prunable(profile_id, kind)
                if not candidates:
                    break
                victim = candidates[0]
                victim["state"] = "pruned"
                victim["pruned_at"] = _iso(now)
                self._remove_file(victim)
                removed.append({k: victim[k] for k in ("id", "name", "kind", "bytes")})
                freed += victim["bytes"]
            if removed:
                self._state["alerts"].append({
                    "kind": "storage_pruned",
                    "profile": profile_id,
                    "items": len(removed),
                    "freed_bytes": freed,
                    "at": _iso(now),
                })
                self._save()
            return {"removed": removed, "freed_bytes": freed,
                    "usage": self.usage(profile_id)}

    def _remove_file(self, media: Dict[str, Any]) -> None:
        path = media.get("path")
        if path and os.path.exists(path):
            try:
                os.remove(path)
            except OSError:
                pass

    # -- writes ------------------------------------------------------------

    def store_media(self, profile_id: str, kind: str, nbytes: int, *,
                    name: str = "", data: Optional[bytes] = None,
                    now: Optional[float] = None) -> Dict[str, Any]:
        """Admit one media asset, or refuse with a stable code.

        ``data`` is optional: the ledger is authoritative, so accounting can be
        exercised without materialising gigabytes. When supplied it is written
        into the local root (the PC master) and removed on purge.
        """
        if kind not in KINDS:
            raise StorageError("unknown_kind", kind)
        nbytes = int(nbytes)
        if nbytes <= 0:
            raise StorageError("invalid_size", "nbytes must be positive")
        stamp = time.time() if now is None else float(now)
        with self._lock:
            prof = self.profile(profile_id)

            if kind == "video" and int(prof["video_retention_s"]) <= 0:
                prompt = {
                    "profile": profile_id,
                    "kind": "video",
                    "name": name,
                    "bytes": nbytes,
                    "reason": "free_tier_zero_video_retention",
                    "action": "download_now",
                    "message": ("Free tier keeps no video. Download this clip before "
                                "ending the session or it will be discarded."),
                    "at": _iso(now),
                }
                self._state["download_prompts"].append(prompt)
                session = self._state["sessions"].setdefault(
                    profile_id, {"opened_at": _iso(now), "seq": 0})
                session.setdefault("transient", []).append(
                    {"kind": "video", "name": name, "bytes": nbytes,
                     "at": _iso(now), "downloaded": False})
                self._save()
                return {
                    "status": "not_stored",
                    "reason": "free_tier_zero_video_retention",
                    "retention_seconds": 0,
                    "must_download": True,
                    "download_prompt": prompt,
                    "usage": self.usage(profile_id),
                }

            image_cap = int(prof["image_quota_bytes"])
            total_cap = int(prof["total_quota_bytes"])
            usage = self.usage(profile_id)

            def _effective(kind_: str, snapshot: Dict[str, Any]) -> tuple:
                """Bytes used and the cap that actually binds for this kind."""
                if kind_ == "image":
                    # images must fit both their own quota and what is left of
                    # the total after retained video is accounted for.
                    cap_ = max(0, min(image_cap, total_cap - snapshot["video_bytes"]))
                    return snapshot["image_bytes"], cap_
                return snapshot["total_bytes"], total_cap

            used, cap = _effective(kind, usage)

            pruned = {"removed": [], "freed_bytes": 0}
            if used + nbytes > cap:
                pruned = self.prune(profile_id, max(0, cap - nbytes),
                                    kind if kind == "image" else None, now=stamp)
                usage = self.usage(profile_id)
                used, cap = _effective(kind, usage)

            if used + nbytes > cap:
                return {
                    "status": "over_quota",
                    "code": "over_quota",
                    "kind": kind,
                    "needed_bytes": nbytes,
                    "deficit_bytes": used + nbytes - cap,
                    "used_bytes": used,
                    "cap_bytes": cap,
                    "pruned": pruned["removed"],
                    "tier": prof["tier"],
                }

            media_id = "m_" + uuid.uuid4().hex[:12]
            path = None
            if data is not None:
                os.makedirs(self.root, exist_ok=True)
                safe = "".join(c if c.isalnum() or c in "._-" else "_"
                               for c in (name or media_id))[:80]
                path = os.path.join(self.root, f"{media_id}_{safe}")
                with open(path, "wb") as handle:
                    handle.write(data)

            entry = {
                "id": media_id,
                "profile": profile_id,
                "kind": kind,
                "name": name or media_id,
                "bytes": nbytes,
                "path": path,
                "stored_at": _iso(stamp),
                "expires_at": (_iso(stamp + prof["video_retention_s"])
                               if kind == "video" and prof["video_retention_s"] else None),
                "downloaded": False,
                "retained": bool(prof["video_retention_s"] and kind == "video"),
                "state": "active",
            }
            self._state["media"].append(entry)
            self._save()
            return {"status": "stored", "media": entry,
                    "pruned": pruned["removed"], "usage": self.usage(profile_id)}

    def mark_downloaded(self, profile_id: str, media_id: str) -> Dict[str, Any]:
        with self._lock:
            for media in self._state["media"]:
                if media["id"] == media_id and media["profile"] == profile_id:
                    media["downloaded"] = True
                    media["downloaded_at"] = _iso()
                    self._save()
                    return dict(media)
            raise StorageError("media_not_found", media_id)

    # -- session end / expiry ---------------------------------------------

    def finalize_session(self, profile_id: str, now: Optional[float] = None) -> Dict[str, Any]:
        """Purge what the client never downloaded; return the prompts it owed."""
        with self._lock:
            purged: List[Dict[str, Any]] = []
            for media in self._active(profile_id):
                if media.get("downloaded") or media.get("retained"):
                    continue
                media["state"] = "purged"
                media["purged_at"] = _iso(now)
                self._remove_file(media)
                purged.append({"id": media["id"], "name": media["name"],
                               "kind": media["kind"], "bytes": media["bytes"]})

            session = self._state["sessions"].get(profile_id) or {}
            transient = session.get("transient") or []
            dropped = [t for t in transient if not t.get("downloaded")]
            session["transient"] = []
            session["closed_at"] = _iso(now)
            self._state["sessions"][profile_id] = session

            prompts = [p for p in self._state["download_prompts"]
                       if p["profile"] == profile_id]
            self._state["download_prompts"] = [
                p for p in self._state["download_prompts"] if p["profile"] != profile_id]

            if purged or dropped:
                self._state["alerts"].append({
                    "kind": "session_media_purged",
                    "profile": profile_id,
                    "items": len(purged) + len(dropped),
                    "at": _iso(now),
                })
            self._save()
            return {"profile": profile_id, "purged": purged,
                    "dropped_transient": dropped, "download_prompts": prompts,
                    "usage": self.usage(profile_id)}

    def sweep_expired(self, now: Optional[float] = None) -> Dict[str, Any]:
        """Purge media whose retention window closed. Safe to call at any time."""
        stamp = time.time() if now is None else now
        with self._lock:
            removed: List[Dict[str, Any]] = []
            for media in self._state["media"]:
                if media["state"] != "active" or not media.get("expires_at"):
                    continue
                try:
                    expires = datetime.fromisoformat(media["expires_at"]).timestamp()
                except ValueError:
                    continue
                if expires <= stamp:
                    media["state"] = "expired"
                    media["expired_at"] = _iso(stamp)
                    self._remove_file(media)
                    removed.append({"id": media["id"], "kind": media["kind"],
                                    "bytes": media["bytes"]})
            if removed:
                self._save()
            return {"expired": removed, "count": len(removed)}

    # -- reporting ---------------------------------------------------------

    def summary(self) -> Dict[str, Any]:
        with self._lock:
            profiles = len(self._state["profiles"])
            active = [m for m in self._state["media"] if m["state"] == "active"]
            return {
                "schema": self.SCHEMA,
                "profiles": profiles,
                "profile_cap": MAX_PROFILES,
                "active_items": len(active),
                "active_bytes": sum(m["bytes"] for m in active),
                "alerts": len(self._state["alerts"]),
                "pending_download_prompts": len(self._state["download_prompts"]),
                "by_tier": {
                    tier: sum(1 for p in self._state["profiles"].values()
                              if p["tier"] == tier)
                    for tier in TIERS
                },
            }


def disk_free_gb(path: str) -> float:
    usage = shutil.disk_usage(path)
    return round(usage.free / GB, 2)


def guard_disk(path: str, min_free_gb: float = 10.0) -> Dict[str, Any]:
    """The capsule's disk rule, as a checkable predicate."""
    free = disk_free_gb(path)
    ok = free >= min_free_gb
    return {
        "ok": ok,
        "free_gb": free,
        "min_free_gb": min_free_gb,
        "action": None if ok else "pause_gpu_and_downloads",
    }


def purge_unreferenced(root: str, keep: Iterable[str]) -> List[str]:
    """Delete files under ``root`` that the ledger no longer knows about."""
    keep_set = {os.path.abspath(p) for p in keep if p}
    removed: List[str] = []
    if not os.path.isdir(root):
        return removed
    for name in os.listdir(root):
        path = os.path.abspath(os.path.join(root, name))
        if os.path.isfile(path) and path not in keep_set:
            try:
                os.remove(path)
                removed.append(path)
            except OSError:
                pass
    return removed
