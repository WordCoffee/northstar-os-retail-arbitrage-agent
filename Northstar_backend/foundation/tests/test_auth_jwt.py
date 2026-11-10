"""JWT authentication tests (Phase 1C-01): validation, expiry, issuer/audience,
revocation, and HTTP enforcement. Amendment criteria G5, G7."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from Northstar_backend.foundation.authn import decode_and_validate, AuthError
from Northstar_backend.foundation.tests.conftest import make_access_token, bearer


# --- direct validation -------------------------------------------------------

def test_valid_token_decodes(seeded_state):
    tok = make_access_token(seeded_state.ids["user"], org=seeded_state.ids["org"])
    payload = decode_and_validate(tok)
    assert payload["sub"] == seeded_state.ids["user"]


def test_expired_token_rejected(seeded_state):
    tok = make_access_token(seeded_state.ids["user"], ttl_seconds=-120)
    with pytest.raises(AuthError) as e:
        decode_and_validate(tok)
    assert e.value.code == "token_expired"


def test_wrong_signature_rejected(seeded_state):
    tok = make_access_token(seeded_state.ids["user"], secret="a-different-signing-key")
    with pytest.raises(AuthError) as e:
        decode_and_validate(tok)
    assert e.value.code == "invalid_token"


def test_missing_signing_key_fails_closed(seeded_state, monkeypatch):
    monkeypatch.delenv("NORTHSTAR_JWT_SECRET", raising=False)
    tok = make_access_token(seeded_state.ids["user"], secret="whatever")
    with pytest.raises(AuthError) as e:
        decode_and_validate(tok)
    assert e.value.code == "no_signing_key_configured"


def test_invalid_issuer_rejected(seeded_state, monkeypatch):
    monkeypatch.setenv("NORTHSTAR_JWT_ISSUER", "northstar-auth")
    tok = make_access_token(seeded_state.ids["user"], issuer="some-other-issuer")
    with pytest.raises(AuthError) as e:
        decode_and_validate(tok)
    assert e.value.code in ("invalid_issuer", "invalid_token")


def test_missing_issuer_rejected_when_configured(seeded_state, monkeypatch):
    monkeypatch.setenv("NORTHSTAR_JWT_ISSUER", "northstar-auth")
    tok = make_access_token(seeded_state.ids["user"])  # no iss claim
    with pytest.raises(AuthError):
        decode_and_validate(tok)


def test_invalid_audience_rejected(seeded_state, monkeypatch):
    monkeypatch.setenv("NORTHSTAR_JWT_AUDIENCE", "northstar-api")
    tok = make_access_token(seeded_state.ids["user"], audience="some-other-aud")
    with pytest.raises(AuthError) as e:
        decode_and_validate(tok)
    assert e.value.code in ("invalid_audience", "invalid_token")


def test_refresh_token_type_rejected(seeded_state):
    tok = make_access_token(seeded_state.ids["user"], token_type="refresh")
    with pytest.raises(AuthError) as e:
        decode_and_validate(tok)
    assert e.value.code == "unapproved_token_type"


# --- HTTP enforcement --------------------------------------------------------

def test_valid_bearer_succeeds(client, seeded_state):
    tok = make_access_token(seeded_state.ids["user"], org=seeded_state.ids["org"])
    r = client.get("/api/v1/foundation/me", headers=bearer(tok))
    assert r.status_code == 200
    body = r.json()
    assert body["role"] == "organization_owner"
    assert "manage_org" in body["permissions"]


def test_bad_bearer_rejected(client, seeded_state):
    r = client.get("/api/v1/foundation/me", headers=bearer("not-a-jwt"))
    assert r.status_code == 401
    assert r.json()["detail"]["code"] in ("malformed_token", "invalid_token")


def test_expired_bearer_rejected(client, seeded_state):
    tok = make_access_token(seeded_state.ids["user"], ttl_seconds=-120)
    r = client.get("/api/v1/foundation/me", headers=bearer(tok))
    assert r.status_code == 401
    assert r.json()["detail"]["code"] == "token_expired"


def test_remote_client_with_valid_jwt_succeeds(seeded_state):
    from Northstar_backend.foundation.app import create_app
    app = create_app()
    app.state.foundation = seeded_state
    remote = TestClient(app, client=("203.0.113.9", 5000))
    tok = make_access_token(seeded_state.ids["user"], org=seeded_state.ids["org"])
    r = remote.get("/api/v1/foundation/me", headers=bearer(tok))
    assert r.status_code == 200  # remote access succeeds ONLY with valid auth


def test_revoked_session_rejected(client, seeded_state):
    tok = make_access_token(seeded_state.ids["user"], org=seeded_state.ids["org"],
                            jti="sess_revoke_me")
    h = bearer(tok)
    assert client.get("/api/v1/foundation/me", headers=h).status_code == 200
    rv = client.post("/api/v1/foundation/session/revoke?jti=sess_revoke_me", headers=h)
    assert rv.status_code == 200
    r2 = client.get("/api/v1/foundation/me", headers=h)
    assert r2.status_code == 401
    assert r2.json()["detail"]["code"] == "session_revoked"


def test_invalid_authorization_scheme_rejected(client):
    r = client.get("/api/v1/foundation/me", headers={"Authorization": "Basic abc"})
    assert r.status_code == 401
    assert r.json()["detail"]["code"] == "invalid_authorization_header"