"""Phase F/S6 — rate-limiter production posture checks."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_BACKEND = Path(__file__).resolve().parent
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from rate_limiter import assert_prod_posture, prod_posture_ok  # noqa: E402


def test_ok_when_flag_unset(monkeypatch):
    monkeypatch.delenv("NORTHSTAR_DISABLE_RATE_LIMIT", raising=False)
    monkeypatch.setenv("ENVIRONMENT", "production")
    assert prod_posture_ok() is True


def test_ok_when_flag_set_but_not_production(monkeypatch):
    monkeypatch.setenv("NORTHSTAR_DISABLE_RATE_LIMIT", "1")
    monkeypatch.setenv("ENVIRONMENT", "staging")
    assert prod_posture_ok() is True


def test_violation_raises_in_production(monkeypatch):
    monkeypatch.setenv("NORTHSTAR_DISABLE_RATE_LIMIT", "1")
    monkeypatch.setenv("ENVIRONMENT", "production")
    assert prod_posture_ok() is False
    with pytest.raises(RuntimeError, match="PROD POSTURE"):
        assert_prod_posture()


def test_assert_ok_outside_production(monkeypatch):
    monkeypatch.setenv("NORTHSTAR_DISABLE_RATE_LIMIT", "1")
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    assert_prod_posture()   # must not raise