"""P3-T3: Owner Test Mode must NOT bypass non-bypassable controls.

All tests run with NORTHSTAR_OWNER_TEST_MODE=1 and ENVIRONMENT=development so
that Owner Test Mode is ACTIVE; the controls must still hold.
"""
from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

from Northstar_backend.foundation.api.state import FoundationState
from Northstar_backend.foundation.app import create_app
from Northstar_backend.foundation.bootstrap import bootstrap_owner
from Northstar_backend.foundation.enums import Role
from Northstar_backend.foundation import golden_goose_decision as gg
from Northstar_backend.foundation.jobs_handlers import HandlerRegistry, UnknownJobType
from Northstar_backend.foundation.providers import ProviderRegistry, ProviderDisabledError

ADMIN = Role.INTERNAL_PLATFORM_ADMIN.value
VIEWER = Role.VIEWER.value


@pytest.fixture(autouse=True)
def _otm_on(monkeypatch):
    monkeypatch.setenv("NORTHSTAR_OWNER_TEST_MODE", "1")
    monkeypatch.setenv("ENVIRONMENT", "development")


def test_missing_gates_are_unknown_not_pass():
    gates = gg.evaluate_gates({})
    assert gates and all(v == gg.UNKNOWN for v in gates.values())


def test_score_alone_cannot_reach_purchase_ready():
    result = gg.decide(
        gate_inputs={}, economics_readiness="COMPLETE",
        component_scores={k: 1.0 for k in ("net_profit", "demand", "bsr_stability")},
        component_weights={k: 1.0 for k in ("net_profit", "demand", "bsr_stability")},
    )
    assert result["decision_state"] != gg.PURCHASE_READY
    assert result["purchase_ready"] is False


def test_gates_and_econ_alone_require_separate_approval():
    gates_pass = {name: gg.PASS for name in gg.MANDATORY_GATES}
    no_approval = gg.decide(gate_inputs=gates_pass, economics_readiness="COMPLETE")
    assert no_approval["decision_state"] == gg.APPROVAL_REQUIRED
    assert no_approval["purchase_ready"] is False

    with_approval = gg.decide(gate_inputs=gates_pass, economics_readiness="COMPLETE",
                              approval={"present": True})
    assert with_approval["decision_state"] == gg.PURCHASE_READY
    assert with_approval["purchase_ready"] is True


def test_unregistered_job_type_fails_closed():
    reg = HandlerRegistry()
    with pytest.raises(UnknownJobType):
        reg.spec("definitely.not.registered")
    with pytest.raises(UnknownJobType):
        reg.handler("definitely.not.registered")


def test_disabled_provider_fails_closed(tmp_path):
    st = FoundationState.build(str(tmp_path / "f.db"))
    try:
        reg = ProviderRegistry(st.repos)
        assert reg.is_enabled("brightdata") is False
        res = reg.execute_read("brightdata", {})
        assert res.ok is False and res.error_class == "provider_disabled"
        with pytest.raises(ProviderDisabledError):
            reg.adapter("brightdata")
    finally:
        st.close()


def test_provider_enabled_state_not_changed_by_test_mode(tmp_path):
    # NOTE: provider ARMING + hard daily/monthly spend caps are P7-T1 and are not
    # implemented yet; this asserts only that test mode does not alter provider
    # enabled state. Arming/caps remain an untested-until-P7-T1 control.
    st = FoundationState.build(str(tmp_path / "f.db"))
    try:
        reg = ProviderRegistry(st.repos)
        before = reg.is_enabled("dataforseo")
        reg2 = ProviderRegistry(st.repos)  # separate call under active test mode
        assert reg2.is_enabled("dataforseo") == before
    finally:
        st.close()


def test_signed_out_request_is_401_even_in_test_mode(monkeypatch):
    monkeypatch.setenv("DB_URL", "")
    monkeypatch.delenv("FOUNDATION_DB_URL", raising=False)
    app = create_app()
    client = TestClient(app)
    assert client.get("/api/v1/foundation/me").status_code == 401


def test_tenant_isolation_holds_for_non_owner(monkeypatch, tmp_path):
    monkeypatch.setenv("DB_URL", "")
    monkeypatch.delenv("FOUNDATION_DB_URL", raising=False)
    app = create_app()
    st = app.state.foundation
    a = bootstrap_owner(st, org_name="Org A", user_email="a@t.test", role=VIEWER, recover=True)
    b = bootstrap_owner(st, org_name="Org B", user_email="b@t.test", role=VIEWER, recover=True)
    client = TestClient(app)
    # member of A may not act as a member of B
    r = client.get("/api/v1/foundation/me",
                   headers={"X-User-Id": a["user_id"], "X-Org-Id": b["organization_id"]})
    assert r.status_code == 403
    assert r.json()["detail"]["code"] == "cross_organization_access_denied"


def _repo_root() -> str:
    """Repo root found by walking up to the 00_STATE.json marker.

    The frozen paths below are repo-root relative, and this test used to assume
    pytest was launched from the root - so running the suite from
    Northstar_backend/ looked for Northstar_backend/Northstar_backend/... and
    failed on a file that exists (2026-10-19). Resolve from __file__ instead.
    """
    p = os.path.dirname(os.path.abspath(__file__))
    for _ in range(6):
        if os.path.isfile(os.path.join(p, "00_STATE.json")):
            return p
        p = os.path.dirname(p)
    return p


def test_frozen_file_boundary_is_a_static_rule():
    # Process/repo rule, NOT a runtime-tested control: the frozen files must exist
    # and must not be imported by Owner Test Mode code paths.
    root = _repo_root()
    frozen = [
        "Northstar_backend/costco_non_kirkland/brightdata_costco_live.py",
        "Northstar_backend/costco_non_kirkland/brightdata_costco_enrichment.py",
        "Northstar_backend/costco_non_kirkland/enrichment.py",
    ]
    for f in frozen:
        assert os.path.exists(os.path.join(root, f)), f
    otm_modules = ["Northstar_backend/foundation/owner_test_mode.py",
                   "Northstar_backend/foundation/permissions.py",
                   "Northstar_backend/foundation/approvals.py"]
    for m in otm_modules:
        with open(os.path.join(root, m), encoding="utf-8") as fh:
            body = fh.read()
        assert "brightdata_costco_live" not in body
        assert "brightdata_costco_enrichment" not in body