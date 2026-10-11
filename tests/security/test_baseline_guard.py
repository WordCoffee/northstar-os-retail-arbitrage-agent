"""Baseline-growth guard — the known-active baseline can only SHRINK.

Policy: NEW findings must be remediated, never acknowledged by silently adding
them to ``.secret_scan_baseline.json``. This test pins the exact set of
(rule, fingerprint) pairs approved for the baseline as of the owner review.

Enforced here:

- every baseline entry ∈ ``FROZEN_APPROVED`` (no additions, ever);
- entry count ≤ the frozen count;
- no duplicate (rule, fingerprint) pairs;
- every entry is well formed (rule, lowercase 64-hex fingerprint, non-empty reason).

Remediated entries may be REMOVED without touching this test — shrinking is
always allowed. To genuinely approve a new escalation, BOTH the baseline and
``FROZEN_APPROVED`` must be updated in one reviewed commit, and the reason
recorded in the escalation report. That is the owner-visible path, on purpose.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
BASELINE = REPO_ROOT / ".secret_scan_baseline.json"

# Frozen approval set — owner-reviewed escalations as of 2026-10-11.
# GROWTH IS BLOCKED: changing this set is a deliberate, reviewed act.
FROZEN_APPROVED = {
    (
        "credential-assignment",
        "65a9bec280c685b1c7e3080491f438c5a9e5f26ba8099a88fa5d10ebd75bbb5a",
    ),
    (
        "openai-style-key",
        "ca2d8a22d6f0d25200c7f318141c8a37ed69412d891def707184c937e760b30c",
    ),
    (
        "credential-assignment",
        "42ce3e16410e4e5bd41af840881d4d0bf3c1e3f18c56280abeda475884ed5892",
    ),
    (
        "credential-assignment",
        "8e73174e0cef4b7173b580f96aac14692d8ec3dd1df19c819d7cc2ff8981b64e",
    ),
    (
        "github-token",
        "ef33331652fdc1f8e491f18485cdec192e2c973ab1530621188e01703f06a9d6",
    ),
}

_HEX64 = re.compile(r"[0-9a-f]{64}")


def _entries():
    data = json.loads(BASELINE.read_text(encoding="utf-8"))
    return list(data.get("entries", []))


def test_baseline_entries_are_all_frozen_approved():
    for entry in _entries():
        key = (entry.get("rule"), entry.get("fingerprint"))
        assert key in FROZEN_APPROVED, (
            f"baseline cannot grow: {key} is not in FROZEN_APPROVED. "
            "New findings must be remediated, not acknowledged. A genuinely "
            "new escalation requires a reviewed commit that updates "
            "FROZEN_APPROVED in this test AND records the reason in the "
            "escalation report."
        )


def test_baseline_cannot_exceed_the_frozen_count():
    assert len(_entries()) <= len(FROZEN_APPROVED)


def test_baseline_has_no_duplicates():
    keys = [(e.get("rule"), e.get("fingerprint")) for e in _entries()]
    assert len(keys) == len(set(keys))


def test_baseline_entries_are_well_formed():
    for entry in _entries():
        assert entry.get("rule"), entry
        assert _HEX64.fullmatch(str(entry.get("fingerprint", ""))), entry
        assert str(entry.get("reason", "")).strip(), entry
