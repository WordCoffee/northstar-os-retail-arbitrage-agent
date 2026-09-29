"""P2-T5a owner credential storage + bootstrap tests (SQLite local; PG if set)."""
from __future__ import annotations

import os

import pytest

from Northstar_backend.foundation import credentials
from Northstar_backend.foundation.api.state import FoundationState

import Northstar_backend.foundation_seed_owner as seed_owner

PG_URL = os.environ.get("FOUNDATION_DB_URL") or os.environ.get("DB_URL")
PW = "Sup3rSecretPassw0rd!"
PW2 = "An0therSecretPassw0rd!"


@pytest.fixture()
def sqlite_state(tmp_path):
    st = FoundationState.build(str(tmp_path / "foundation.db"))
    yield st
    st.close()


def test_hash_and_verify_roundtrip():
    h = credentials.hash_password(PW)
    assert h.startswith("$2")
    assert h != PW
    assert credentials.verify_password(PW, h) is True
    assert credentials.verify_password("wrong", h) is False
    assert credentials.verify_password(PW, "not-a-hash") is False


def test_ensure_table_and_crud_sqlite(sqlite_state):
    db = sqlite_state.db
    credentials.ensure_table(db)
    credentials.create(db, user_id="u1", email="Owner@Test.Test", password=PW)
    row = credentials.get_by_email(db, "owner@test.test")
    assert row is not None and row["user_id"] == "u1"
    assert credentials.verify_password(PW, row["password_hash"])
    assert credentials.count(db) == 1


def _seed(tmp_path, email, pw, *extra):
    prompts = [pw, pw]
    return seed_owner.main(
        ["--db-path", str(tmp_path / "foundation.db"), "--email", email, *extra],
        password_prompt=lambda _msg: prompts.pop(0))


def test_bootstrap_success_and_idempotent_refusal(tmp_path, capsys):
    rc = _seed(tmp_path, "owner@test.test", PW)
    assert rc == seed_owner.EXIT_OK
    out = capsys.readouterr().out
    assert PW not in out and "$2b$" not in out

    st = FoundationState.build(str(tmp_path / "foundation.db"))
    row = credentials.get_by_email(st.db, "owner@test.test")
    first_hash = row["password_hash"]
    st.close()

    rc2 = seed_owner.main(["--db-path", str(tmp_path / "foundation.db"),
                           "--email", "owner@test.test"],
                          password_prompt=lambda _m: PW)
    assert rc2 == seed_owner.EXIT_EXISTS

    st = FoundationState.build(str(tmp_path / "foundation.db"))
    assert credentials.get_by_email(st.db, "owner@test.test")["password_hash"] == first_hash
    assert credentials.count(st.db) == 1
    st.close()


def test_rotate_replaces_hash(tmp_path):
    assert _seed(tmp_path, "owner@test.test", PW) == seed_owner.EXIT_OK
    rc = _seed(tmp_path, "owner@test.test", PW2, "--rotate")
    assert rc == seed_owner.EXIT_OK
    st = FoundationState.build(str(tmp_path / "foundation.db"))
    row = credentials.get_by_email(st.db, "owner@test.test")
    assert credentials.verify_password(PW2, row["password_hash"])
    assert not credentials.verify_password(PW, row["password_hash"])
    assert credentials.count(st.db) == 1
    st.close()


def test_ambiguous_second_admin_refused(tmp_path):
    assert _seed(tmp_path, "owner@test.test", PW) == seed_owner.EXIT_OK
    rc = seed_owner.main(["--db-path", str(tmp_path / "foundation.db"),
                          "--email", "other@test.test"],
                         password_prompt=lambda _m: PW)
    assert rc == seed_owner.EXIT_AMBIGUOUS


def test_weak_password_refused(tmp_path):
    rc = _seed(tmp_path, "owner@test.test", "short")
    assert rc == seed_owner.EXIT_WEAK


def test_refuse_non_loopback_without_flag(monkeypatch, tmp_path):
    monkeypatch.setenv("DB_URL", "postgresql://u:p@db.example.com:5432/northstar")
    monkeypatch.delenv("FOUNDATION_DB_URL", raising=False)
    with pytest.raises(SystemExit) as e:
        seed_owner.main(["--email", "owner@test.test"],
                        password_prompt=lambda _m: PW)
    assert e.value.code == seed_owner.EXIT_UNSAFE


def test_refuse_production_denylist(monkeypatch):
    monkeypatch.setenv("DB_URL", "postgresql://u:p@prod-db.internal:5432/northstar")
    monkeypatch.delenv("FOUNDATION_DB_URL", raising=False)
    with pytest.raises(SystemExit) as e:
        seed_owner.main(["--email", "owner@test.test"],
                        password_prompt=lambda _m: PW)
    assert e.value.code == seed_owner.EXIT_UNSAFE


@pytest.mark.skipif(not PG_URL, reason="FOUNDATION_DB_URL/DB_URL not set (PostgreSQL)")
def test_credentials_on_postgres():
    st = FoundationState.build()  # uses DB_URL
    try:
        db = st.db
        credentials.ensure_table(db)
        email = "pg-cred-test@test.test"
        if credentials.get_by_email(db, email):
            db._raw.execute("DELETE FROM owner_credentials WHERE lower(email)=%s", [email])
            db._raw.commit()
        credentials.create(db, user_id="pg-u1", email=email, password=PW)
        row = credentials.get_by_email(db, email)
        assert row and credentials.verify_password(PW, row["password_hash"])
        db._raw.execute("DELETE FROM owner_credentials WHERE lower(email)=%s", [email])
        db._raw.commit()
    finally:
        st.close()