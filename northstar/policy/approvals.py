"""Approval queue + the SIMULATED snapshot guard (Phase 2).

Any live run, any spend, any side effect needs an explicit owner approval.
Structural rules: a requester can never approve its own request; decisions are
recorded with approver + timestamp. Simulated outputs can NEVER be written to
the snapshot store (``assert_snapshot_writable``).
"""
from __future__ import annotations

import itertools
import time
from dataclasses import dataclass
from typing import Callable

from .errors import PolicyConfigError, PolicyDenied

KINDS = ("live_fetch", "spend", "side_effect")

SIMULATED = "SIMULATED"


@dataclass
class ApprovalItem:
    id: str
    task_id: str
    kind: str
    reason: str
    requester: str
    created_at: float
    status: str = "pending"  # pending | approved | denied
    decided_by: str | None = None
    decided_at: float | None = None


class ApprovalQueue:
    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        self.clock = clock
        self._items: dict[str, ApprovalItem] = {}
        self._seq = itertools.count(1)

    def _get(self, item_id: str) -> ApprovalItem:
        item = self._items.get(item_id)
        if item is None:
            raise PolicyDenied("unknown_item", item_id)
        return item

    def request(self, *, task_id: str, kind: str, reason: str, requester: str) -> ApprovalItem:
        if kind not in KINDS:
            raise PolicyConfigError(f"unknown kind: {kind}")
        if not requester:
            raise PolicyConfigError("requester required")
        item = ApprovalItem(
            id=f"ap-{next(self._seq):04d}",
            task_id=task_id,
            kind=kind,
            reason=reason,
            requester=requester,
            created_at=self.clock(),
        )
        self._items[item.id] = item
        return item

    def _decide(self, item_id: str, approver: str, status: str) -> ApprovalItem:
        item = self._get(item_id)
        if item.status != "pending":
            raise PolicyDenied("already_decided", item_id)
        if not approver:
            raise PolicyDenied("approver_required", item_id)
        if approver == item.requester:
            raise PolicyDenied("self_approval", item_id)
        item.status = status
        item.decided_by = approver
        item.decided_at = self.clock()
        return item

    def approve(self, item_id: str, approver: str) -> ApprovalItem:
        return self._decide(item_id, approver, "approved")

    def deny(self, item_id: str, approver: str) -> ApprovalItem:
        return self._decide(item_id, approver, "denied")

    def is_approved(self, item_id: str) -> bool:
        item = self._items.get(item_id)
        return bool(item and item.status == "approved")

    def pending(self) -> list[ApprovalItem]:
        return [i for i in self._items.values() if i.status == "pending"]


def assert_snapshot_writable(data_class: str) -> None:
    """SIMULATED outputs can never be written to the snapshot store."""
    if data_class == SIMULATED:
        raise PolicyDenied("simulated_never_snapshot")
