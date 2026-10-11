"""Policy kernel errors (Phase 2)."""
from __future__ import annotations


class PolicyConfigError(ValueError):
    """Bad input/config — not a policy denial in itself."""


class PolicyDenied(Exception):
    """A policy check denied the request. ``reason`` is a stable code for logs."""

    def __init__(self, reason: str, detail: str = "") -> None:
        self.reason = reason
        self.detail = detail
        super().__init__(f"{reason}: {detail}" if detail else reason)
