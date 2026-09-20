"""Northstar OS credit ledger (B3) — Compute/Creative Credit metering.

Implements docs/contracts/CREDIT_LEDGER_v1.md. Offline and deterministic: no
network, no billing, no Stripe. In-memory by default; optional append-only
JSONL persistence for alpha.

Integrity guarantees:
  - append-only entries (never mutated/deleted; balance derived by sum)
  - idempotency by key (a replayed mutation appends no second entry)
  - fail-closed consumption (InsufficientCredits; balance never goes negative)
  - reservation -> commit/release with an expiry
"""

from __future__ import annotations

import json
import os
import secrets
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

# --- plan allotments (keyed by catalog plan id; validated against the catalog)
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CATALOG_PATH = os.path.join(_REPO_ROOT, "shared", "subscription-plans.json")

# Proposed alpha allotments — operator sign-off required (see contract §2).
PLAN_CREDIT_ALLOTMENT: Dict[str, int] = {
    "foundation": 0,
    "scout": 100,
    "mover": 500,
    "autothink": 2000,
}

DEFAULT_RESERVATION_TTL_SECONDS = 900  # 15 minutes

COMPUTE = "compute"
CREATIVE = "creative"

GRANT = "grant"
RESERVE = "reserve"
COMMIT = "commit"
RELEASE = "release"
ADJUST = "adjust"


class InsufficientCredits(Exception):
    """Raised when a consume/reserve would drive the balance below zero."""


class UnknownPlanError(ValueError):
    """Raised when an allotment is requested for a plan not in the catalog."""


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.isoformat()


def _new_entry_id() -> str:
    return "cle_" + secrets.token_hex(16)


def _catalog_plan_ids() -> List[str]:
    try:
        with open(CATALOG_PATH, "r", encoding="utf-8-sig") as fh:
            catalog = json.load(fh)
    except (OSError, ValueError) as exc:
        raise UnknownPlanError("cannot read plan catalog: %s" % exc) from exc
    return [p.get("id") for p in catalog.get("plans", []) if p.get("id")]


def allotment_for_plan(plan_id: str) -> int:
    """Monthly Compute Credit allotment for a plan id. Unknown ids fail closed."""
    if plan_id not in _catalog_plan_ids():
        raise UnknownPlanError("unknown plan id: %r" % (plan_id,))
    return int(PLAN_CREDIT_ALLOTMENT.get(plan_id, 0))


@dataclass
class LedgerEntry:
    entry_id: str
    account_id: str
    kind: str
    amount: int
    class_: str = COMPUTE
    action: Optional[str] = None
    idempotency_key: Optional[str] = None
    reservation_id: Optional[str] = None
    expires_at: Optional[str] = None
    created_at: str = field(default_factory=lambda: _iso(_now()))
    balance_after: int = 0

    def to_dict(self) -> dict:
        return {
            "entry_id": self.entry_id,
            "account_id": self.account_id,
            "kind": self.kind,
            "class": self.class_,
            "amount": self.amount,
            "action": self.action,
            "idempotency_key": self.idempotency_key,
            "reservation_id": self.reservation_id,
            "expires_at": self.expires_at,
            "created_at": self.created_at,
            "balance_after": self.balance_after,
        }


class CreditLedger:
    """Append-only Compute/Creative credit ledger (alpha: in-memory)."""

    def __init__(self, path: Optional[str] = None) -> None:
        self._entries: List[LedgerEntry] = []
        self._by_idem: Dict[str, LedgerEntry] = {}
        self._reservations: Dict[str, LedgerEntry] = {}
        self._path = path
        if path and os.path.isfile(path):
            self._load(path)

    # -- internals -----------------------------------------------------------
    def _balance(self, account_id: str, class_: str = COMPUTE) -> int:
        return sum(
            e.amount for e in self._entries
            if e.account_id == account_id and e.class_ == class_
        )

    def _append(self, entry: LedgerEntry) -> LedgerEntry:
        entry.balance_after = self._balance(entry.account_id, entry.class_)
        self._entries.append(entry)
        if entry.idempotency_key:
            self._by_idem[entry.idempotency_key] = entry
        if entry.kind == RESERVE and entry.reservation_id:
            self._reservations[entry.reservation_id] = entry
        if self._path:
            with open(self._path, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(entry.to_dict()) + "\n")
        return entry

    def _load(self, path: str) -> None:
        with open(path, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                d = json.loads(line)
                e = LedgerEntry(
                    entry_id=d["entry_id"], account_id=d["account_id"],
                    kind=d["kind"], amount=d["amount"], class_=d.get("class", COMPUTE),
                    action=d.get("action"), idempotency_key=d.get("idempotency_key"),
                    reservation_id=d.get("reservation_id"), expires_at=d.get("expires_at"),
                    created_at=d.get("created_at"), balance_after=d.get("balance_after", 0),
                )
                self._entries.append(e)
                if e.idempotency_key:
                    self._by_idem[e.idempotency_key] = e
                if e.kind == RESERVE and e.reservation_id:
                    self._reservations[e.reservation_id] = e

    # -- public API ----------------------------------------------------------
    def balance(self, account_id: str, class_: str = COMPUTE) -> int:
        return self._balance(account_id, class_)

    def entries(self) -> List[dict]:
        """Append-only view (copies) for audit/reporting."""
        return [e.to_dict() for e in self._entries]

    def grant(self, account_id: str, amount: int, *, reason: str = "grant",
              class_: str = COMPUTE, idempotency_key: Optional[str] = None) -> LedgerEntry:
        if amount <= 0:
            raise ValueError("grant amount must be positive")
        if idempotency_key and idempotency_key in self._by_idem:
            return self._by_idem[idempotency_key]
        return self._append(LedgerEntry(
            entry_id=_new_entry_id(), account_id=account_id, kind=GRANT,
            amount=int(amount), class_=class_, action=reason,
            idempotency_key=idempotency_key,
        ))

    def reserve(self, account_id: str, amount: int, *, action: str,
                idempotency_key: Optional[str] = None,
                ttl_seconds: int = DEFAULT_RESERVATION_TTL_SECONDS,
                class_: str = COMPUTE) -> LedgerEntry:
        """Hold credits for a job. Fail closed when balance < amount."""
        if amount <= 0:
            raise ValueError("reserve amount must be positive")
        if idempotency_key and idempotency_key in self._by_idem:
            return self._by_idem[idempotency_key]
        if self._balance(account_id, class_) < amount:
            raise InsufficientCredits(
                "insufficient credits: need %d, have %d" % (amount, self._balance(account_id, class_))
            )
        return self._append(LedgerEntry(
            entry_id=_new_entry_id(), account_id=account_id, kind=RESERVE,
            amount=-int(amount), class_=class_, action=action,
            idempotency_key=idempotency_key,
            reservation_id="resv_" + secrets.token_hex(16),
            expires_at=_iso(_now() + timedelta(seconds=ttl_seconds)),
        ))

    def release(self, reservation_id: str, *, idempotency_key: Optional[str] = None) -> LedgerEntry:
        """Return a held reservation (e.g. job cancelled or expired)."""
        if idempotency_key and idempotency_key in self._by_idem:
            return self._by_idem[idempotency_key]
        res = self._reservations.get(reservation_id)
        if res is None:
            raise KeyError("unknown reservation: %r" % (reservation_id,))
        return self._append(LedgerEntry(
            entry_id=_new_entry_id(), account_id=res.account_id, kind=RELEASE,
            amount=-res.amount, class_=res.class_, action=res.action,
            idempotency_key=idempotency_key, reservation_id=reservation_id,
        ))

    def commit(self, reservation_id: str, *, idempotency_key: Optional[str] = None) -> LedgerEntry:
        """Finalize a reservation as a charge (records an audit row; the hold
        already moved the balance)."""
        if idempotency_key and idempotency_key in self._by_idem:
            return self._by_idem[idempotency_key]
        res = self._reservations.get(reservation_id)
        if res is None:
            raise KeyError("unknown reservation: %r" % (reservation_id,))
        return self._append(LedgerEntry(
            entry_id=_new_entry_id(), account_id=res.account_id, kind=COMMIT,
            amount=0, class_=res.class_, action=res.action,
            idempotency_key=idempotency_key, reservation_id=reservation_id,
        ))

    def consume(self, account_id: str, amount: int, *, action: str,
                idempotency_key: Optional[str] = None, class_: str = COMPUTE) -> LedgerEntry:
        """Charge credits directly (no reservation). Fail closed when short."""
        if amount < 0:
            raise ValueError("consume amount must be non-negative")
        if idempotency_key and idempotency_key in self._by_idem:
            return self._by_idem[idempotency_key]
        if self._balance(account_id, class_) < amount:
            raise InsufficientCredits(
                "insufficient credits: need %d, have %d" % (amount, self._balance(account_id, class_))
            )
        return self._append(LedgerEntry(
            entry_id=_new_entry_id(), account_id=account_id, kind=COMMIT,
            amount=-int(amount), class_=class_, action=action,
            idempotency_key=idempotency_key,
        ))