"""Tamper-evident audit log (Phase 2).

Append-only, hash-chained (each entry commits to the previous entry's hash).
There are no update/delete APIs. ``detail`` passes through the Phase 1
redaction layer, so credential shapes never reach even the audit trail.
Sinks are optional callables (e.g. a JSONL file writer) — a failing sink must
never break the chain.
"""
from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Sequence

from northstar.security.redaction import redact_text

GENESIS_HASH = "0" * 64


@dataclass(frozen=True)
class AuditEntry:
    seq: int
    ts: float
    actor: str
    action: str
    decision: str
    reason: str
    detail: str
    prev_hash: str
    entry_hash: str


def _entry_hash(
    seq: int,
    ts: float,
    actor: str,
    action: str,
    decision: str,
    reason: str,
    detail: str,
    prev_hash: str,
) -> str:
    payload = json.dumps(
        [seq, repr(ts), actor, action, decision, reason, detail, prev_hash],
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class AuditLog:
    def __init__(
        self,
        *,
        clock: Callable[[], float] = time.time,
        sinks: Sequence[Callable[[AuditEntry], None]] = (),
    ) -> None:
        self.clock = clock
        self.sinks = list(sinks)
        self._entries: list[AuditEntry] = []

    def append(
        self, *, actor: str, action: str, decision: str, reason: str = "", detail: str = ""
    ) -> AuditEntry:
        seq = len(self._entries) + 1
        prev_hash = self._entries[-1].entry_hash if self._entries else GENESIS_HASH
        ts = float(self.clock())
        detail = redact_text(detail)
        entry = AuditEntry(
            seq=seq,
            ts=ts,
            actor=actor,
            action=action,
            decision=decision,
            reason=reason,
            detail=detail,
            prev_hash=prev_hash,
            entry_hash=_entry_hash(seq, ts, actor, action, decision, reason, detail, prev_hash),
        )
        self._entries.append(entry)
        for sink in self.sinks:
            try:
                sink(entry)
            except Exception:
                pass  # sinks are best-effort; the chain itself never breaks
        return entry

    @property
    def entries(self) -> tuple[AuditEntry, ...]:
        return tuple(self._entries)

    def verify(self) -> bool:
        prev = GENESIS_HASH
        for expected_seq, entry in enumerate(self._entries, start=1):
            if entry.seq != expected_seq or entry.prev_hash != prev:
                return False
            if (
                _entry_hash(
                    entry.seq,
                    entry.ts,
                    entry.actor,
                    entry.action,
                    entry.decision,
                    entry.reason,
                    entry.detail,
                    entry.prev_hash,
                )
                != entry.entry_hash
            ):
                return False
            prev = entry.entry_hash
        return True


class JsonlSink:
    """Append-only JSONL writer (one line per entry; opens per append)."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def __call__(self, entry: AuditEntry) -> None:
        line = json.dumps(
            {
                "seq": entry.seq,
                "ts": entry.ts,
                "actor": entry.actor,
                "action": entry.action,
                "decision": entry.decision,
                "reason": entry.reason,
                "detail": entry.detail,
                "prev_hash": entry.prev_hash,
                "entry_hash": entry.entry_hash,
            },
            separators=(",", ":"),
        )
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")
