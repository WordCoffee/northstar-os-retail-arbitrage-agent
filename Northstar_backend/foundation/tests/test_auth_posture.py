"""Startup auth/bind posture tests (Phase 1C-01, amendment G1/G2)."""
from __future__ import annotations

import pytest

from Northstar_backend.foundation.authn import (
    assert_startup_posture, AuthPostureError,
)


def test_development_loopback_no_secret_ok():
    p = assert_startup_posture(env="development", bind_host="127.0.0.1",
                               jwt_secret_present=False, remote_dev_allowed=False)
    assert p["dev_shim_active"] is True
    assert p["auth_posture"] == "dev_shim_local_only"


def test_development_remote_bind_without_override_fails():
    with pytest.raises(AuthPostureError):
        assert_startup_posture(env="development", bind_host="0.0.0.0",
                               jwt_secret_present=False, remote_dev_allowed=False)


def test_development_remote_bind_with_override_ok():
    p = assert_startup_posture(env="development", bind_host="0.0.0.0",
                               jwt_secret_present=False, remote_dev_allowed=True)
    assert p["binds_beyond_loopback"] is True
    assert p["remote_dev_override"] is True


def test_production_override_rejected():
    with pytest.raises(AuthPostureError):
        assert_startup_posture(env="production", bind_host="127.0.0.1",
                               jwt_secret_present=True, remote_dev_allowed=True)


def test_staging_override_rejected():
    with pytest.raises(AuthPostureError):
        assert_startup_posture(env="staging", bind_host="127.0.0.1",
                               jwt_secret_present=True, remote_dev_allowed=True)


def test_production_without_secret_fails_closed():
    with pytest.raises(AuthPostureError):
        assert_startup_posture(env="production", bind_host="127.0.0.1",
                               jwt_secret_present=False, remote_dev_allowed=False)


def test_production_with_secret_remote_bind_ok():
    p = assert_startup_posture(env="production", bind_host="0.0.0.0",
                               jwt_secret_present=True, remote_dev_allowed=False)
    assert p["auth_posture"] == "jwt"
    assert p["dev_shim_active"] is False


def test_remote_bind_with_real_auth_ok_even_in_development():
    p = assert_startup_posture(env="development", bind_host="0.0.0.0",
                               jwt_secret_present=True, remote_dev_allowed=False)
    assert p["auth_posture"] == "jwt"


def test_env_derived_posture_fails_closed_in_production(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.delenv("NORTHSTAR_JWT_SECRET", raising=False)
    monkeypatch.delenv("NS_FOUNDATION_ALLOW_REMOTE_DEV", raising=False)
    with pytest.raises(AuthPostureError):
        assert_startup_posture(bind_host="127.0.0.1")