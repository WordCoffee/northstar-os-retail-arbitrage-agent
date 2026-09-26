"""Phase 1C-01F authentication hardening test matrix."""
from __future__ import annotations

import datetime

import jwt as pyjwt
import pytest

from Northstar_backend.foundation.authn import (
    AuthError, environment, validate_auth_configuration, allowed_algorithms,
    decode_and_validate, assert_startup_posture, AuthPostureError,
)
from Northstar_backend.foundation.models import Membership
from Northstar_backend.foundation.tests.conftest import make_access_token, bearer, owner_headers


def _now():
    return datetime.datetime.now(datetime.timezone.utc)


def _raw(payload, *, secret=None, alg="HS256"):
    from Northstar_backend.foundation.authn import jwt_secret
    return pyjwt.encode(payload, secret or jwt_secret(), algorithm=alg)


# --- environment modes -------------------------------------------------------

def test_environment_defaults_to_development(monkeypatch):
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    assert environment() == "development"


def test_unknown_environment_is_invalid(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "banana")
    assert environment() == "invalid"
    assert "invalid_environment" in validate_auth_configuration()


def test_staging_requires_secret_issuer_audience(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "staging")
    monkeypatch.delenv("NORTHSTAR_JWT_SECRET", raising=False)
    monkeypatch.delenv("NORTHSTAR_JWT_ISSUER", raising=False)
    monkeypatch.delenv("NORTHSTAR_JWT_AUDIENCE", raising=False)
    problems = validate_auth_configuration()
    assert "missing_signing_key" in problems
    assert "missing_issuer" in problems
    assert "missing_audience" in problems


def test_production_rejects_development_secret(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("NORTHSTAR_JWT_SECRET", "test-not-real-secret")
    monkeypatch.setenv("NORTHSTAR_JWT_ISSUER", "northstar-auth")
    monkeypatch.setenv("NORTHSTAR_JWT_AUDIENCE", "northstar-api")
    assert "development_secret_in_prod" in validate_auth_configuration()


def test_production_override_rejected(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("NS_FOUNDATION_ALLOW_REMOTE_DEV", "1")
    assert "remote_dev_override_in_prod" in validate_auth_configuration()


# --- algorithm allowlist -----------------------------------------------------

def test_alg_none_rejected(seeded_state):
    tok = pyjwt.encode({"sub": "u1", "exp": _now() + datetime.timedelta(hours=1)},
                       "", algorithm="none")
    with pytest.raises(AuthError) as e:
        decode_and_validate(tok)
    assert e.value.code == "alg_none_rejected"


def test_unexpected_algorithm_rejected(seeded_state, monkeypatch):
    monkeypatch.setenv("NORTHSTAR_JWT_ALGORITHMS", "HS256")
    tok = _raw({"sub": "u1", "exp": _now() + datetime.timedelta(hours=1),
                "iat": _now()}, alg="HS384")
    with pytest.raises(AuthError) as e:
        decode_and_validate(tok)
    assert e.value.code == "unexpected_algorithm"


def test_secondary_algorithm_allowed_when_configured(seeded_state, monkeypatch):
    monkeypatch.setenv("NORTHSTAR_JWT_ALGORITHMS", "HS256,HS384")
    tok = _raw({"sub": "u1", "exp": _now() + datetime.timedelta(hours=1),
                "iat": _now()}, alg="HS384")
    payload = decode_and_validate(tok)
    assert payload["sub"] == "u1"


# --- structure / signature ---------------------------------------------------

def test_malformed_token_structure(seeded_state):
    for bad in ("abc", "a.b", "", "a.b.c.d"):
        with pytest.raises(AuthError) as e:
            decode_and_validate(bad)
        assert e.value.code == "malformed_token"


def test_empty_signature_rejected(seeded_state):
    with pytest.raises(AuthError):
        decode_and_validate("aaa.bbb.")


# --- time claims -------------------------------------------------------------

def test_expired_token(seeded_state):
    tok = make_access_token(seeded_state.ids["user"], ttl_seconds=-120)
    with pytest.raises(AuthError) as e:
        decode_and_validate(tok)
    assert e.value.code == "token_expired"


def test_nbf_in_future_rejected(seeded_state):
    tok = make_access_token(seeded_state.ids["user"],
                            extra={"nbf": int((_now() + datetime.timedelta(hours=1)).timestamp())})
    with pytest.raises(AuthError) as e:
        decode_and_validate(tok)
    assert e.value.code == "token_not_yet_valid"


def test_malformed_iat_rejected(seeded_state):
    tok = make_access_token(seeded_state.ids["user"], extra={"iat": "not-a-number"})
    with pytest.raises(AuthError) as e:
        decode_and_validate(tok)
    # PyJWT may reject a non-integer iat as invalid_token before our own check.
    assert e.value.code in ("malformed_iat", "invalid_token")


def test_token_lifetime_bound(seeded_state, monkeypatch):
    monkeypatch.setenv("NORTHSTAR_JWT_MAX_LIFETIME_SECONDS", "60")
    tok = make_access_token(seeded_state.ids["user"], ttl_seconds=3600)
    with pytest.raises(AuthError) as e:
        decode_and_validate(tok)
    assert e.value.code == "token_lifetime_exceeded"


def test_clock_skew_within_leeway_accepted(seeded_state, monkeypatch):
    monkeypatch.setenv("NORTHSTAR_JWT_LEEWAY_SECONDS", "30")
    tok = make_access_token(seeded_state.ids["user"], ttl_seconds=-10)
    assert decode_and_validate(tok)["sub"] == seeded_state.ids["user"]


def test_clock_skew_exceeded_rejected(seeded_state, monkeypatch):
    monkeypatch.setenv("NORTHSTAR_JWT_LEEWAY_SECONDS", "0")
    tok = make_access_token(seeded_state.ids["user"], ttl_seconds=-10)
    with pytest.raises(AuthError) as e:
        decode_and_validate(tok)
    assert e.value.code == "token_expired"


# --- issuer / audience -------------------------------------------------------

def test_wrong_issuer(seeded_state, monkeypatch):
    monkeypatch.setenv("NORTHSTAR_JWT_ISSUER", "northstar-auth")
    tok = make_access_token(seeded_state.ids["user"], issuer="evil")
    with pytest.raises(AuthError) as e:
        decode_and_validate(tok)
    assert e.value.code in ("invalid_issuer", "missing_required_claim", "invalid_token")


def test_missing_issuer_when_configured(seeded_state, monkeypatch):
    monkeypatch.setenv("NORTHSTAR_JWT_ISSUER", "northstar-auth")
    tok = make_access_token(seeded_state.ids["user"])
    with pytest.raises(AuthError):
        decode_and_validate(tok)


def test_wrong_audience(seeded_state, monkeypatch):
    monkeypatch.setenv("NORTHSTAR_JWT_AUDIENCE", "northstar-api")
    tok = make_access_token(seeded_state.ids["user"], audience="other")
    with pytest.raises(AuthError) as e:
        decode_and_validate(tok)
    assert e.value.code in ("invalid_audience", "missing_required_claim", "invalid_token")


def test_audience_string_ok(seeded_state, monkeypatch):
    monkeypatch.setenv("NORTHSTAR_JWT_AUDIENCE", "northstar-api")
    tok = make_access_token(seeded_state.ids["user"], audience="northstar-api")
    assert decode_and_validate(tok)["sub"]


def test_audience_array_containing_ok(seeded_state, monkeypatch):
    monkeypatch.setenv("NORTHSTAR_JWT_AUDIENCE", "northstar-api")
    tok = make_access_token(seeded_state.ids["user"],
                            audience=["other", "northstar-api"])
    assert decode_and_validate(tok)["sub"]


def test_audience_array_not_containing_rejected(seeded_state, monkeypatch):
    monkeypatch.setenv("NORTHSTAR_JWT_AUDIENCE", "northstar-api")
    tok = make_access_token(seeded_state.ids["user"], audience=["a", "b"])
    with pytest.raises(AuthError) as e:
        decode_and_validate(tok)
    assert e.value.code in ("invalid_audience", "invalid_token")


def test_production_decode_requires_issuer(seeded_state, monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("NORTHSTAR_JWT_SECRET", "production-grade-secret-value-0123456789")
    monkeypatch.delenv("NORTHSTAR_JWT_ISSUER", raising=False)
    tok = _raw({"sub": "u1", "exp": _now() + datetime.timedelta(hours=1), "iat": _now()},
               secret="production-grade-secret-value-0123456789")
    with pytest.raises(AuthError) as e:
        decode_and_validate(tok)
    assert e.value.code == "issuer_required"


# --- subject / claims --------------------------------------------------------

def test_missing_subject_rejected(seeded_state):
    tok = _raw({"exp": _now() + datetime.timedelta(hours=1), "iat": _now()})
    with pytest.raises(AuthError) as e:
        decode_and_validate(tok)
    assert e.value.code in ("missing_required_claim", "invalid_token")


# --- kid ---------------------------------------------------------------------

def test_unknown_kid_rejected(seeded_state, monkeypatch):
    monkeypatch.setenv("NORTHSTAR_JWT_KEY_ID", "trusted-kid")
    tok = make_access_token(seeded_state.ids["user"], extra={"kid_hint": "x"})
    # pyjwt headerkid is set via headers, not claims; craft manually:
    from Northstar_backend.foundation.authn import jwt_secret
    tok = pyjwt.encode({"sub": "u1", "exp": _now() + datetime.timedelta(hours=1),
                        "iat": _now()}, jwt_secret(), algorithm="HS256",
                       headers={"kid": "wrong-kid"})
    with pytest.raises(AuthError) as e:
        decode_and_validate(tok)
    assert e.value.code == "unknown_kid"


def test_malformed_empty_kid_rejected(seeded_state):
    from Northstar_backend.foundation.authn import jwt_secret
    tok = pyjwt.encode({"sub": "u1", "exp": _now() + datetime.timedelta(hours=1),
                        "iat": _now()}, jwt_secret(), algorithm="HS256",
                       headers={"kid": ""})
    with pytest.raises(AuthError) as e:
        decode_and_validate(tok)
    assert e.value.code == "malformed_kid"


def test_excessive_kid_length_rejected(seeded_state, monkeypatch):
    monkeypatch.setenv("NORTHSTAR_JWT_MAX_KID_LENGTH", "10")
    from Northstar_backend.foundation.authn import jwt_secret
    tok = pyjwt.encode({"sub": "u1", "exp": _now() + datetime.timedelta(hours=1),
                        "iat": _now()}, jwt_secret(), algorithm="HS256",
                       headers={"kid": "k" * 50})
    with pytest.raises(AuthError) as e:
        decode_and_validate(tok)
    assert e.value.code == "malformed_kid"


# --- HTTP: environment gating ------------------------------------------------

def test_dev_headers_rejected_in_staging(client, seeded_state, monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "staging")
    r = client.get("/api/v1/foundation/me", headers=owner_headers(seeded_state))
    assert r.status_code == 401


def test_dev_headers_rejected_in_production(client, seeded_state, monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    r = client.get("/api/v1/foundation/me", headers=owner_headers(seeded_state))
    assert r.status_code == 401


# --- membership status -------------------------------------------------------

def test_suspended_membership_denied(client, seeded_state):
    # suspend the only membership
    row = seeded_state.repos.memberships.for_user(seeded_state.ids["user"])[0]
    seeded_state.db.conn.execute("UPDATE memberships SET status='suspended' WHERE id=?",
                                 (row["id"],))
    seeded_state.db.conn.commit()
    tok = make_access_token(seeded_state.ids["user"], org=seeded_state.ids["org"])
    r = client.get("/api/v1/foundation/me", headers=bearer(tok))
    assert r.status_code == 403


# --- preview exit ------------------------------------------------------------

def test_preview_exit_clears_preview(client, seeded_state):
    tok = make_access_token(seeded_state.ids["user"], org=seeded_state.ids["org"])
    pid = client.post("/api/v1/foundation/preview/start", headers=bearer(tok),
                      json={"target_organization_id": seeded_state.ids["org"],
                            "reason": "x"}).json()["preview_id"]
    assert client.get("/api/v1/foundation/environment",
                      headers=bearer(tok, **{"X-Preview-Id": pid})).json()["is_preview"] is True
    client.post(f"/api/v1/foundation/preview/end?preview_id={pid}", headers=bearer(tok))
    env = client.get("/api/v1/foundation/environment",
                     headers=bearer(tok, **{"X-Preview-Id": pid})).json()
    assert env["is_preview"] is False


# --- JWKS scope note ---------------------------------------------------------

def test_jwks_not_implemented_documented():
    """1C-01F uses a static-key model; JWKS is intentionally not implemented.
    This test records that scope decision rather than asserting JWKS behavior."""
    import Northstar_backend.foundation.authn as authn
    assert not hasattr(authn, "jwks_url")
    assert allowed_algorithms()  # a non-empty allowlist is always present