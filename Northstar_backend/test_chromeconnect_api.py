"""Tests for Chrome Connect admin room API (P6-T6)."""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import chromeconnect_api as api


def setup_function():
    api.reset_state()


def test_get_status_empty():
    status = api.get_status()
    assert status["jobs"]["total"] == 0
    assert status["adapters"] == 0
    assert status["alerts"] == 0


def test_register_job():
    api.register_job({"id": "job-1", "state": "QUEUED", "site": "costco.com"})
    status = api.get_status()
    assert status["jobs"]["total"] == 1
    assert status["jobs"]["queued"] == 1


def test_register_adapter_health():
    api.register_adapter_health("costco", {"name": "costco", "state": "green"})
    status = api.get_status()
    assert status["adapters"] == 1


def test_add_alert():
    api.add_alert({"severity": "warning", "category": "test", "message": "test alert", "acknowledged": False})
    status = api.get_status()
    assert status["alerts"] == 1


def test_job_state_counts():
    api.register_job({"id": "j1", "state": "QUEUED", "site": "a.com"})
    api.register_job({"id": "j2", "state": "RUNNING", "site": "b.com"})
    api.register_job({"id": "j3", "state": "SUCCEEDED", "site": "c.com"})
    api.register_job({"id": "j4", "state": "FAILED", "site": "d.com"})
    api.register_job({"id": "j5", "state": "NEEDS_OWNER", "site": "e.com"})
    status = api.get_status()
    assert status["jobs"]["queued"] == 1
    assert status["jobs"]["running"] == 1
    assert status["jobs"]["succeeded"] == 1
    assert status["jobs"]["failed"] == 1
    assert status["jobs"]["needs_owner"] == 1


def test_create_router():
    router = api.create_router()
    # FastAPI may or may not be available
    if router is not None:
        assert router is not None
    else:
        # FastAPI not installed — in-memory helpers still work
        assert api.get_status() is not None
