"""Provider-scoped tool suite tests (offline; no network, no credentials).

The point of these tests is the lane split: the LOCAL bench may run
non-commercial weights and copyleft agent runtimes; the CLOUD lane is a
commercial product and must refuse both, with an explicit reason code.
"""

from __future__ import annotations

import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import provider_suite as ps  # noqa: E402

_CLEAN = ("NORTHSTAR_PROVIDER", "MEDIA_GEN_LIVE", "CLOUD_MODEL_LIVE",
          "OPENMONTAGE_LIVE", "CHROMECONTROL_ROOT")


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    for n in _CLEAN:
        monkeypatch.delenv(n, raising=False)
    yield


# --- suite loads ------------------------------------------------------------

def test_suite_declares_both_lanes_and_tools():
    t = ps.tools()
    assert t, "shared/provider-suite.json did not load"
    for tid, cfg in t.items():
        assert cfg.get("lanes"), f"{tid} declares no lane"
        assert set(cfg["lanes"]) <= set(ps.PROVIDERS), f"{tid} has a bad lane"
        assert cfg.get("name") and cfg.get("kind")


def test_every_tool_resolves_on_its_own_lane():
    for tid, cfg in ps.tools().items():
        for lane in cfg["lanes"]:
            v = ps.verify(tid, lane)
            assert v.reason != ps.R_UNKNOWN_TOOL, tid
            # A declared lane never produces a licence block.
            assert v.reason not in (ps.R_LICENSE_NONCOMMERCIAL,
                                    ps.R_WEIGHTS_UNVERIFIED), tid


# --- the licence gate: local allows, cloud refuses --------------------------

def test_noncommercial_weights_allowed_locally():
    v = ps.verify("flux1_dev", "local")
    assert v.allowed is True
    assert v.license == "FLUX.1-dev-Non-Commercial"


def test_noncommercial_weights_blocked_on_cloud():
    v = ps.verify("flux1_dev", "cloud")
    assert v.allowed is False and v.usable is False
    assert v.reason == ps.R_LICENSE_NONCOMMERCIAL


def test_unverified_weights_blocked_on_cloud():
    # UltraTex weights turned out to ship a FLUX non-commercial licence, so the
    # confirmed-block path is what fires for it now; the unverified path is
    # covered directly below.
    v = ps.verify("ultratex", "cloud")
    assert v.allowed is False
    assert v.reason == ps.R_LICENSE_NONCOMMERCIAL


def test_unverified_weights_reason_code():
    tool = {"commercial_ok": True, "weights_license": "unverified", "license": "MIT"}
    assert ps._license_block(tool, "cloud") == ps.R_WEIGHTS_UNVERIFIED
    # Same tool is fine on the bench.
    assert ps._license_block(tool, "local") is None


def test_agpl_harness_blocked_on_cloud_not_for_noncommercial_reason():
    v = ps.verify("openmontage", "cloud")
    assert v.allowed is False
    assert v.reason == "agpl_network_copyleft_unreviewed"
    # AGPL permits commercial use; the block is the network clause, not price.
    assert v.license == "AGPL-3.0"


def test_agpl_harness_allowed_on_local_bench():
    v = ps.verify("openmontage", "local")
    assert v.allowed is True


# --- lane membership --------------------------------------------------------

def test_cloud_tool_not_offered_locally():
    v = ps.verify("fal_image_video", "local")
    assert v.allowed is False and v.reason == ps.R_NOT_IN_LANE


def test_local_tool_not_offered_on_cloud():
    v = ps.verify("birefnet", "cloud")
    assert v.allowed is False and v.reason == ps.R_NOT_IN_LANE


# --- fail closed ------------------------------------------------------------

def test_unknown_tool_fails_closed():
    v = ps.verify("definitely_not_a_tool", "local")
    assert v.allowed is False and v.usable is False
    assert v.reason == ps.R_UNKNOWN_TOOL


def test_unknown_provider_fails_closed():
    v = ps.verify("comfyui", "quantum")
    assert v.allowed is False and v.reason == ps.R_UNKNOWN_PROVIDER
    assert ps.suite("quantum")["known"] is False


# --- install + gate axes are separate ---------------------------------------

def test_ready_tool_is_allowed_but_not_installed():
    v = ps.verify("blender", "local")
    assert v.allowed is True
    assert v.installed is False and v.usable is False
    assert v.reason == ps.R_NOT_INSTALLED


def test_confirmed_probe_makes_ready_tool_installed():
    v = ps.verify("blender", "local", confirmed=["blender"])
    assert v.installed is True and v.usable is True and v.reason == ps.R_OK


def test_installed_tool_without_gate_is_not_usable():
    v = ps.verify("comfyui", "local", env={})
    assert v.installed is True and v.allowed is True
    assert v.usable is False and v.reason == ps.R_GATE_NOT_ARMED


def test_gate_armed_makes_installed_tool_usable():
    v = ps.verify("comfyui", "local", env={"MEDIA_GEN_LIVE": "1"})
    assert v.usable is True and v.reason == ps.R_OK


def test_presence_gate():
    v = ps.verify("chromeconnect", "local", env={})
    assert v.reason == ps.R_GATE_NOT_ARMED
    v2 = ps.verify("chromeconnect", "local", env={"CHROMECONTROL_ROOT": "C:/x"})
    assert v2.usable is True


# --- active lane ------------------------------------------------------------

def test_active_provider_defaults_to_operator_lane():
    assert ps.active_provider({}) == "local"


def test_active_provider_env_override():
    assert ps.active_provider({"NORTHSTAR_PROVIDER": "cloud"}) == "cloud"
    # Garbage does not silently become cloud.
    assert ps.active_provider({"NORTHSTAR_PROVIDER": "quantum"}) == "local"


# --- lane view + catalog ----------------------------------------------------

def test_suite_view_splits_usable_and_blocked():
    armed = {"CLOUD_MODEL_LIVE": "1", "MEDIA_GEN_LIVE": "1"}
    lane = ps.suite("cloud", env=armed)
    assert lane["known"] is True
    ids_usable = {c["id"] for c in lane["usable"]}
    ids_blocked = {c["id"] for c in lane["blocked"]}
    assert "openrouter_text" in ids_usable
    assert "ultratex" in ids_blocked and "openmontage" in ids_blocked
    assert lane["counts"]["total"] == len(ps.tools())


def test_cloud_lane_is_all_gated_when_unarmed():
    lane = ps.suite("cloud", env={})
    assert lane["counts"]["usable"] == 0
    reasons = {c["reason"] for c in lane["blocked"]}
    assert ps.R_GATE_NOT_ARMED in reasons
    assert "agpl_network_copyleft_unreviewed" in reasons



def test_catalog_covers_both_lanes():
    c = ps.catalog(active="local")
    assert c["active_provider"] == "local"
    assert set(c["lanes"]) == set(ps.PROVIDERS)
    assert c["policy"]["cloud_requires_commercial_ok"] is True


def test_catalog_never_leaks_credential_values(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-SECRETVALUE")
    monkeypatch.setenv("FAL_KEY", "fal-SECRETVALUE")
    blob = json.dumps(ps.catalog())
    assert "SECRETVALUE" not in blob


# --- endpoint ---------------------------------------------------------------

def test_provider_suite_endpoint_envelope(monkeypatch):
    monkeypatch.setenv("NORTHSTAR_DISABLE_RATE_LIMIT", "1")
    from fastapi.testclient import TestClient
    from main import app
    c = TestClient(app)
    r = c.get("/api/v1/provider-suite")
    assert r.status_code == 200
    b = r.json()
    assert b["contract"] == "bff/v1" and b["status"] == "ok"
    assert b["data"]["active_provider"] in ps.PROVIDERS
    assert "local" in b["data"]["lanes"] and "cloud" in b["data"]["lanes"]

    forced = c.get("/api/v1/provider-suite?provider=cloud")
    assert forced.json()["data"]["active_provider"] == "cloud"
