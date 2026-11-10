"""Session journal + checkpoints.

The journal is append-only and is the replay source. Replay re-renders state; it
never re-executes a side effect. Checkpoints snapshot only files the kernel wrote
through its own file tools — the documented reference has the same blind spot for
Bash-only changes, and ours is stated in the spec rather than hidden.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from .model import Checkpoint, Event

MAX_CHECKPOINTS_PER_SESSION = 100
RETENTION_S = 30 * 24 * 3600


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


class Journal:
    def __init__(self, path: Optional[os.PathLike | str] = None):
        self.path = Path(path) if path else None
        self.events: List[Event] = []
        self._seq = 0
        if self.path and self.path.exists():
            for line in self.path.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                raw = json.loads(line)
                ev = Event(**raw)
                self.events.append(ev)
                self._seq = max(self._seq, int(ev.seq))

    def append(self, session_id: str, type_: str, *,
               node_id: Optional[str] = None, payload: Optional[Dict[str, Any]] = None,
               policy_fingerprint: str = "") -> Event:
        self._seq += 1
        ev = Event(self._seq, session_id, type_, node_id=node_id,
                   payload=dict(payload or {}),
                   policy_fingerprint=policy_fingerprint)
        self.events.append(ev)
        if self.path:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(ev.to_dict(), sort_keys=True) + "\n")
        return ev

    def read(self, session_id: Optional[str] = None) -> List[Event]:
        if session_id is None:
            return list(self.events)
        return [e for e in self.events if e.session_id == session_id]

    def replay(self, session_id: str) -> Dict[str, Any]:
        """State derived from the journal. No callbacks, no side effects."""
        nodes: Dict[str, str] = {}
        evidence = 0
        checkpoints = 0
        errors: List[str] = []
        for e in self.read(session_id):
            if e.type == "node_started":
                nodes[str(e.node_id)] = "running"
            elif e.type == "node_finished":
                nodes[str(e.node_id)] = str(e.payload.get("state") or "done")
            elif e.type == "evidence":
                evidence += 1
            elif e.type == "checkpoint":
                checkpoints += 1
            elif e.type == "error":
                errors.append(str(e.payload.get("error") or "unknown"))
        return {"session_id": session_id, "nodes": nodes,
                "evidence_rows": evidence, "checkpoints": checkpoints,
                "errors": errors,
                "events": len(self.read(session_id))}


class CheckpointStore:
    """File snapshots with an explicit, inspectable scope."""

    def __init__(self, root: Optional[os.PathLike | str] = None):
        self.root = Path(root) if root else None
        self._items: Dict[str, List[Checkpoint]] = {}
        self._index: Dict[str, Checkpoint] = {}

    def create(self, session_id: str, plan_version: int,
               node_states: Dict[str, str], files: Iterable[os.PathLike | str] = (),
               conversation_seq: int = 0, restore_scope: str = "both",
               now: Optional[float] = None) -> Checkpoint:
        ts = time.time() if now is None else now
        ckpt_id = f"ckpt_{session_id}_{int(ts * 1000)}_{len(self._items.get(session_id, []))}"
        snapshot: List[Dict[str, Any]] = []
        copies: Dict[str, str] = {}
        for raw in files:
            p = Path(raw)
            if not p.exists() or not p.is_file():
                continue
            # Symlinks/hardlinks are skipped: restoring them is how a rewind
            # silently writes outside the workspace.
            if p.is_symlink():
                snapshot.append({"path": str(p), "skipped": "symlink"})
                continue
            try:
                st = p.stat()
                if getattr(st, "st_nlink", 1) > 1:
                    snapshot.append({"path": str(p), "skipped": "hardlink"})
                    continue
            except OSError:
                continue
            digest = _sha256(p)
            entry = {"path": str(p), "sha256": digest, "bytes": p.stat().st_size}
            if self.root:
                dest = self.root / ckpt_id / "files" / f"{digest[:16]}{p.suffix}"
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(p, dest)
                copies[str(p)] = str(dest)
                entry["snapshot"] = str(dest)
            snapshot.append(entry)
        ckpt = Checkpoint(ckpt_id, session_id, plan_version,
                          node_states=dict(node_states),
                          conversation_seq=int(conversation_seq),
                          file_snapshot=snapshot, restore_scope=restore_scope)
        ckpt._copies = copies  # type: ignore[attr-defined]
        self._items.setdefault(session_id, []).append(ckpt)
        self._index[ckpt_id] = ckpt
        self._prune(session_id, now=ts)
        return ckpt

    def _prune(self, session_id: str, *, now: float) -> None:
        items = self._items.get(session_id, [])
        # 100 most recent, and nothing older than the retention window.
        keep = [c for c in items
                if now - _parse_ts(c.created_at) <= RETENTION_S]
        self._items[session_id] = keep[-MAX_CHECKPOINTS_PER_SESSION:]

    def get(self, checkpoint_id: str) -> Optional[Checkpoint]:
        return self._index.get(checkpoint_id)

    def list(self, session_id: str) -> List[Checkpoint]:
        return list(self._items.get(session_id, []))

    def restore(self, checkpoint_id: str, *, scope: str = "both",
                now: Optional[float] = None) -> Dict[str, Any]:
        ckpt = self.get(checkpoint_id)
        if ckpt is None:
            raise KeyError(checkpoint_id)
        restored: List[str] = []
        skipped: List[Dict[str, str]] = []
        if scope in ("files", "both"):
            copies = getattr(ckpt, "_copies", {})
            for entry in ckpt.file_snapshot:
                if "skipped" in entry:
                    skipped.append({"path": entry["path"], "reason": entry["skipped"]})
                    continue
                src = copies.get(entry["path"])
                if not src or not Path(src).exists():
                    skipped.append({"path": entry["path"], "reason": "no snapshot"})
                    continue
                dest = Path(entry["path"])
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dest)
                restored.append(str(dest))
        return {"checkpoint_id": checkpoint_id,
                "scope": scope,
                "restored": restored,
                "skipped": skipped,
                "conversation_seq": ckpt.conversation_seq if scope in
                ("conversation", "both") else None,
                "limits": "file-tool writes only; browser state is not snapshotted"}


def _parse_ts(iso: str) -> float:
    try:
        return time.mktime(time.strptime(iso, "%Y-%m-%dT%H:%M:%SZ")) - time.timezone
    except Exception:  # noqa: BLE001
        return time.time()
