"""Repository / provider / observability tests."""
from __future__ import annotations

import json

from Northstar_backend.foundation.models import Organization, User, Membership, UiPreference
from Northstar_backend.foundation.enums import Role, ProviderHealth
from Northstar_backend.foundation.observability import redact, FoundationLogger


def test_repository_crud(seeded_state):
    org = Organization(name="CRUD Org", slug="crud")
    row = seeded_state.repos.organizations.add(org)
    assert seeded_state.repos.organizations.get(org.id)["name"] == "CRUD Org"
    assert seeded_state.repos.organizations.count() >= 1


def test_ui_preference_roundtrip(seeded_state):
    seeded_state.repos.ui_prefs.set_pref("u1", "org1", "sidebar_collapsed", True)
    val = seeded_state.repos.ui_prefs.get_pref("u1", "org1", "sidebar_collapsed")
    assert val in (True, "true", 1, "True")


def test_fixture_adapter_read(seeded_state):
    # fixture_price is registered but disabled -> guarded read refuses
    res = seeded_state.providers.execute_read(
        "fixture_price", {"fixture_key": "sample_price", "environment": "sandbox"})
    assert res.ok is False
    assert res.error_class == "provider_disabled"


def test_fixture_adapter_direct_read(seeded_state):
    adapter = seeded_state.providers.adapter("fixture_price")
    res = adapter.read({"fixture_key": "sample_price", "environment": "sandbox"})
    assert res.ok
    assert res.observations[0].observed_value == {"amount": 12.34, "currency": "USD"}
    assert res.observations[0].provenance_class == "mocked"


def test_fixture_adapter_missing_key_is_null(seeded_state):
    adapter = seeded_state.providers.adapter("fixture_price")
    res = adapter.read({"fixture_key": "does_not_exist"})
    assert res.observations[0].observed_value is None
    assert res.observations[0].provenance_class == "unavailable"


def test_provider_write_never_executes(seeded_state):
    res = seeded_state.providers.execute_write("fixture_price", {})
    assert res.ok is False
    assert res.error_class == "write_not_permitted"


def test_redact_scrubs_nested_keys():
    data = {"a": 1, "authorization": "Bearer x", "nested": {"api_key": "y", "b": 2}}
    out = redact(data)
    assert out["authorization"] == "[REDACTED]"
    assert out["nested"]["api_key"] == "[REDACTED]"
    assert out["a"] == 1 and out["nested"]["b"] == 2


def test_logger_redacts(capsys):
    log = FoundationLogger("northstar.test")
    log.event(event="test", token="should-not-appear", organization_id="o1")
    captured = capsys.readouterr().out
    assert "should-not-appear" not in captured
    assert "REDACTED" in captured