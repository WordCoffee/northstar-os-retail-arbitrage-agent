"""B3 tests — credit ledger (credit-ledger/v1)."""

from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from credit_ledger import (  # noqa: E402
    COMPUTE,
    CreditLedger,
    InsufficientCredits,
    UnknownPlanError,
    allotment_for_plan,
)


def test_grant_and_balance():
    led = CreditLedger()
    led.grant("acct1", 100)
    assert led.balance("acct1") == 100
    led.grant("acct1", 50)
    assert led.balance("acct1") == 150
    assert led.balance("other") == 0


def test_grant_rejects_non_positive():
    led = CreditLedger()
    with pytest.raises(ValueError):
        led.grant("acct1", 0)


def test_consume_reduces_balance():
    led = CreditLedger()
    led.grant("acct1", 100)
    led.consume("acct1", 10, action="goose.scan.live")
    assert led.balance("acct1") == 90


def test_insufficient_credits_fails_closed_no_negative():
    led = CreditLedger()
    led.grant("acct1", 5)
    with pytest.raises(InsufficientCredits):
        led.consume("acct1", 10, action="autothink.run")
    assert led.balance("acct1") == 5          # unchanged, never negative


def test_idempotency_prevents_double_charge():
    led = CreditLedger()
    led.grant("acct1", 100, idempotency_key="g1")
    led.grant("acct1", 100, idempotency_key="g1")   # replay -> no second grant
    assert led.balance("acct1") == 100
    led.consume("acct1", 10, action="x", idempotency_key="c1")
    led.consume("acct1", 10, action="x", idempotency_key="c1")   # replay
    assert led.balance("acct1") == 90
    assert len([e for e in led.entries() if e["idempotency_key"] == "c1"]) == 1


def test_reserve_commit_release_flow():
    led = CreditLedger()
    led.grant("acct1", 100)
    res = led.reserve("acct1", 10, action="goose.scan.live")
    assert led.balance("acct1") == 90          # hold moved the balance
    assert res.reservation_id and res.expires_at
    led.commit(res.reservation_id)
    assert led.balance("acct1") == 90          # commit finalizes (no extra debit)

    res2 = led.reserve("acct1", 10, action="goose.scan.live")
    assert led.balance("acct1") == 80
    led.release(res2.reservation_id)
    assert led.balance("acct1") == 90          # released hold returned


def test_reserve_insufficient_fails_closed():
    led = CreditLedger()
    led.grant("acct1", 3)
    with pytest.raises(InsufficientCredits):
        led.reserve("acct1", 10, action="goose.scan.live")
    assert led.balance("acct1") == 3


def test_release_unknown_reservation_fails_closed():
    led = CreditLedger()
    with pytest.raises(KeyError):
        led.release("resv_missing")


def test_ledger_is_append_only_and_balance_equals_sum():
    led = CreditLedger()
    led.grant("acct1", 100)
    led.consume("acct1", 30, action="a")
    entries = led.entries()
    assert sum(e["amount"] for e in entries if e["account_id"] == "acct1" and e["class"] == COMPUTE) == led.balance("acct1")
    # entries() returns copies — mutating them does not affect the ledger
    entries[0]["amount"] = 99999
    assert led.balance("acct1") == 70


def test_allotment_for_plan_validated_against_catalog():
    assert allotment_for_plan("foundation") == 0
    assert allotment_for_plan("autothink") == 2000
    with pytest.raises(UnknownPlanError):
        allotment_for_plan("enterprise_plus")