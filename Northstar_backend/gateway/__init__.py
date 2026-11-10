"""Model gateway — agents ask for a ROLE, never a model (blueprint §11A).

Every model or data call goes through `service.complete()`. That is what makes
the local -> cloud switch a configuration change instead of a rewrite, and what
lets the usage ledger charge correctly.

Layout:
    roles.py     role -> provider chain, from shared/model-roles.json
    adapters.py  one adapter per provider, identical interface
    ledger.py    price table, margin rule, caps, monthly report, JSONL ledger
    service.py   retries, fallback chain, idempotency, the single entry point
"""

from __future__ import annotations

__all__ = ["roles", "adapters", "ledger", "service"]
