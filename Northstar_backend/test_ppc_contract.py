"""PPC's contract: the primary action must persist, not merely respond.

AdPilot's registry entry listed three reads and one external action, so `select_primary` chose a read,
`persisted` stayed `None`, and the scorecard's `contract` dimension was 0. A campaign plan that is
only a response is a report; the product claim is that AdPilot keeps a plan the seller returns to.

The fix is one declared write against the foundation's durable jobs store — the same route and
read-back the `jobs` service is proved with — so the contract can prove persistence rather than assert
it.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import contract_check as cc  # noqa: E402


def _adpilot():
    return next(service for service in cc.registry_services() if service["id"] == "adpilot")


def test_the_primary_action_is_a_write_not_a_read():
    primary, skipped, _ = cc.select_primary(_adpilot())
    assert primary is not None, "a service with a write action must have a primary action"
    assert primary["effect"] == "write", (primary["name"], primary["effect"])
    assert primary["endpoint"] == "/api/v1/foundation/jobs-durable"


def test_the_write_has_a_request_and_a_read_back_defined():
    primary, _, _ = cc.select_primary(_adpilot())
    endpoint = str(primary["endpoint"])
    assert endpoint in cc.REQUESTS, "no request body: the probe cannot run"
    assert cc.REQUESTS[endpoint]["method"] == "POST"
    assert endpoint in cc.READBACK, "a write with no read-back can never prove persistence"


def test_persistence_is_what_the_contract_checks():
    """`persisted` is the field the scorecard's contract dimension reads."""
    assert "persisted" in cc.READBACK["/api/v1/foundation/jobs-durable"]["check"] or \
        cc.READBACK["/api/v1/foundation/jobs-durable"].get("id_key")
