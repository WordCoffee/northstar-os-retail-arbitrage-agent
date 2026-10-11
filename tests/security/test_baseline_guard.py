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

# Frozen approval set — owner-reviewed escalations. CLEARED 2026-10-11: the
# archive escalations were remediated (rotation + scrub) and the final entry
# (rate_limiter.py) turned out to be a scanner false positive, resolved by the
# unquoted index/slice precision fix in secret_scan.py. The set stays empty
# until a genuinely new escalation is reviewed.
# GROWTH IS BLOCKED: changing this set is a deliberate, reviewed act.
FROZEN_APPROVED = {}  # type: set[tuple[str, str]]

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
