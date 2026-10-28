import pytest
from fastapi.testclient import TestClient

def test_dev_shim_cannot_authenticate_in_staging(client, seeded_state, monkeypatch):
    from Northstar_backend.foundation.tests.conftest import owner_headers
    monkeypatch.setenv("ENVIRONMENT", "staging")
    r = client.get("/api/v1/foundation/me", headers=owner_headers(seeded_state))
    assert r.status_code == 401
    assert r.json()["detail"]["code"] == "authentication_required"

def test_dev_shim_cannot_authenticate_in_production(client, seeded_state, monkeypatch):
    from Northstar_backend.foundation.tests.conftest import owner_headers
    monkeypatch.setenv("ENVIRONMENT", "production")
    r = client.get("/api/v1/foundation/me", headers=owner_headers(seeded_state))
    assert r.status_code == 401
    assert r.json()["detail"]["code"] == "authentication_required"

def test_startup_self_check_refuses_when_bind_0_0_0_0(monkeypatch):
    from Northstar_backend.foundation.authn import assert_startup_posture, AuthPostureError
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.setenv("NS_FOUNDATION_BIND_HOST", "0.0.0.0")
    monkeypatch.setenv("UVICORN_HOST", "0.0.0.0")
    monkeypatch.setenv("NORTHSTAR_JWT_SECRET", "")
    with pytest.raises(Exception):
        assert_startup_posture(bind_host="0.0.0.0")


def test_dev_shim_refused_for_non_loopback_client(seeded_state):
    from Northstar_backend.foundation.app import create_app
    from Northstar_backend.foundation.tests.conftest import owner_headers
    app = create_app()
    app.state.foundation = seeded_state
    remote = TestClient(app, client=("10.0.0.5", 5001))
    r = remote.get("/api/v1/foundation/me", headers=owner_headers(seeded_state))
    assert r.status_code == 401
    assert r.json()["detail"]["code"] == "authentication_required"


def test_dev_shim_refused_for_forwarded_untrusted_peer(seeded_state):
    from Northstar_backend.foundation.app import create_app
    from Northstar_backend.foundation.tests.conftest import owner_headers
    app = create_app()
    app.state.foundation = seeded_state
    remote = TestClient(app, client=("203.0.113.9", 5000))
    r = remote.get("/api/v1/foundation/me", headers=owner_headers(seeded_state))
    assert r.status_code == 401
    assert r.json()["detail"]["code"] == "authentication_required"


def test_dev_demo_credentials_never_mint_a_session(client):
    from Northstar_backend.foundation import credentials
    credentials.ensure_table(client.app.state.foundation.db)
    r = client.post("/api/v1/foundation/auth/login",
                    json={"email": "t2", "password": "123abc"})
    assert r.status_code == 401
    assert r.json()["detail"]["code"] == "invalid_credentials"