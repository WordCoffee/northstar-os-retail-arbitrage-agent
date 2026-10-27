"""Tests for Chrome Connect profile lease (policy change)."""

from __future__ import annotations

import os
import sys
import tempfile
import json

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import chromeconnect_profile_lease as lease


def test_lease_initial_state():
    mgr = lease.LeaseManager(lease_path=os.path.join(tempfile.mkdtemp(), "lease.json"))
    assert mgr.lease.state == lease.LeaseState.UNLEASED.value
    assert mgr.is_active is False


def test_acquire_lease():
    tmpdir = tempfile.mkdtemp()
    mgr = lease.LeaseManager(lease_path=os.path.join(tmpdir, "lease.json"))
    l = mgr.acquire("Profile 7", "Northstar Research", "northstarosllc@gmail.com")
    assert l.state == lease.LeaseState.ACTIVE.value
    assert l.profile_dir == "Profile 7"
    assert l.profile_name == "Northstar Research"
    assert mgr.is_active is True
    assert l.lease_id is not None


def test_touch_keeps_alive():
    tmpdir = tempfile.mkdtemp()
    mgr = lease.LeaseManager(lease_path=os.path.join(tmpdir, "lease.json"))
    mgr.acquire("Profile 7")
    assert mgr.touch() is True
    assert mgr.is_active is True


def test_revoke():
    tmpdir = tempfile.mkdtemp()
    mgr = lease.LeaseManager(lease_path=os.path.join(tmpdir, "lease.json"))
    mgr.acquire("Profile 7")
    assert mgr.is_active is True
    mgr.revoke()
    assert mgr.is_active is False
    assert mgr.lease.state == lease.LeaseState.REVOKED.value


def test_lease_persistence():
    tmpdir = tempfile.mkdtemp()
    path = os.path.join(tmpdir, "lease.json")
    mgr1 = lease.LeaseManager(lease_path=path)
    mgr1.acquire("Profile 7", "Northstar Research")
    lease_id = mgr1.lease.lease_id
    # Load from same file
    mgr2 = lease.LeaseManager(lease_path=path)
    assert mgr2.lease.profile_dir == "Profile 7"
    assert mgr2.lease.lease_id == lease_id
    assert mgr2.is_active is True


def test_lease_status():
    tmpdir = tempfile.mkdtemp()
    mgr = lease.LeaseManager(lease_path=os.path.join(tmpdir, "lease.json"))
    mgr.acquire("Profile 7", "Northstar Research")
    status = mgr.status()
    assert status["state"] == "active"
    assert status["is_active"] is True
    assert status["profile_dir"] == "Profile 7"
    assert status["idle_minutes"] == 30
    assert status["idle_seconds"] is not None


def test_lease_idle_expiry():
    tmpdir = tempfile.mkdtemp()
    mgr = lease.LeaseManager(lease_path=os.path.join(tmpdir, "lease.json"))
    mgr.acquire("Profile 7")
    mgr.lease.idle_minutes = 0  # expire immediately
    mgr._save()
    # Reload
    mgr2 = lease.LeaseManager(lease_path=os.path.join(tmpdir, "lease.json"))
    assert mgr2.is_active is False
    assert mgr2.lease.state == lease.LeaseState.EXPIRED.value


def test_record_policy_change():
    path = lease.record_policy_change()
    assert os.path.exists(path)
    content = open(path, encoding="utf-8").read()
    assert "profile lease" in content.lower() or "Profile Lease" in content
    assert "signed-out" in content.lower() or "signed out" in content.lower()


def test_default_idle_minutes():
    assert lease.DEFAULT_IDLE_MINUTES == 30


def test_lease_env_override():
    os.environ["CC_LEASE_IDLE_MINUTES"] = "15"
    # Re-import to pick up env
    import importlib
    importlib.reload(lease)
    assert lease.DEFAULT_IDLE_MINUTES == 15
    del os.environ["CC_LEASE_IDLE_MINUTES"]
    importlib.reload(lease)
    assert lease.DEFAULT_IDLE_MINUTES == 30
