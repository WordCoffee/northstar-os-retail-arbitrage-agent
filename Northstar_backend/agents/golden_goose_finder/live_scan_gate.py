"""Two-gate authorization for a live Golden Goose scan (B1).

A live scan is permitted ONLY when BOTH gates are set by the OPERATOR in their
own runtime environment. Neither this module nor ``run_live_scan.py`` ever sets
either one (never self-armed):

  1. ``GOLDEN_GOOSE_LIVE_OPERATOR_APPROVED=1``  — the existing §3 runtime
     envelope already checked by ``main.run_pipeline``.
  2. ``GOLDEN_GOOSE_LIVE_AUTH_PHRASE=<exact phrase>`` — an explicit operator
     authorization phrase. The value must match :data:`LIVE_AUTH_PHRASE`
     exactly (whitespace-trimmed). This mirrors the codebase's established
     two-gate pattern (``SCANNER_LIVE_ALLOWED`` + ``PROOF_BATCH_LIVE_ARMED``).

Both are absent by default, so a live scan refuses before any provider contact.
Setting one gate alone is never sufficient.
"""

from __future__ import annotations

import os
from typing import Dict, Mapping, Tuple

# Gate 1 — existing §3 runtime envelope (strict "1" opt-in).
LIVE_OPERATOR_ENV = "GOLDEN_GOOSE_LIVE_OPERATOR_APPROVED"

# Gate 2 — explicit operator authorization phrase.
LIVE_AUTH_PHRASE_ENV = "GOLDEN_GOOSE_LIVE_AUTH_PHRASE"
LIVE_AUTH_PHRASE = "AUTHORIZE GOLDEN GOOSE LIVE SCAN"


def check_live_scan_gates(env: Mapping[str, str] | None = None) -> Tuple[bool, str]:
    """Return ``(authorized, reason)``.

    ``authorized`` is True only when both gates are set correctly. ``reason`` is
    a short, secret-free explanation suitable for printing to the operator.
    """
    src: Mapping[str, str] = os.environ if env is None else env
    operator = str(src.get(LIVE_OPERATOR_ENV, "") or "").strip()
    phrase = str(src.get(LIVE_AUTH_PHRASE_ENV, "") or "").strip()

    if operator != "1":
        return False, (
            "refused: %s is not 1 (absent by default — set it in your own shell "
            "to authorize)" % LIVE_OPERATOR_ENV
        )
    if phrase != LIVE_AUTH_PHRASE:
        return False, (
            "refused: %s does not match the required operator authorization "
            "phrase (set it exactly in your own shell; never auto-set)"
            % LIVE_AUTH_PHRASE_ENV
        )
    return True, "authorized"


def gate_status(env: Mapping[str, str] | None = None) -> Dict[str, bool]:
    """Non-secret presence view of the two gates (for diagnostics/tests)."""
    src: Mapping[str, str] = os.environ if env is None else env
    return {
        "operator_approved": str(src.get(LIVE_OPERATOR_ENV, "") or "").strip() == "1",
        "auth_phrase_set": str(src.get(LIVE_AUTH_PHRASE_ENV, "") or "").strip() == LIVE_AUTH_PHRASE,
    }