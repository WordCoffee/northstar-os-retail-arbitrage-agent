"""Human-feature guardrail: intercept, warn, allow only with an explicit override."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "Northstar_backend"))

import video_guard  # noqa: E402


def test_a_product_prompt_passes_cleanly():
    report = video_guard.check_prompt("the pouch rotates on a pale studio sweep")
    assert report["blocked"] is False
    assert report["requires_override"] is False
    assert report["matched"] == []


def test_a_human_prompt_is_blocked_with_the_owner_warning():
    report = video_guard.check_prompt("a woman's hands opening the pouch")
    assert report["blocked"] is True
    assert "hands" in report["matched"] and "woman" in report["matched"]
    assert report["warning"] == video_guard.WARNING


def test_acknowledgement_allows_the_override_but_keeps_the_warning():
    report = video_guard.check_prompt("a model holding the pouch",
                                      acknowledged=True)
    assert report["blocked"] is False
    assert report["requires_override"] is True
    assert "model" in report["matched"]


def _client(monkeypatch):
    from fastapi.testclient import TestClient
    from main import app
    import design_studio_api
    import studio_generation

    monkeypatch.setattr(studio_generation, "engine_status",
                        lambda: {"armed": False, "reachable": False, "models": {}})
    app.dependency_overrides[design_studio_api.studio_account] = lambda: "org-guard"
    return TestClient(app), app


def test_shorts_refuses_a_human_prompt_before_touching_the_engine(monkeypatch):
    client, app = _client(monkeypatch)
    try:
        response = client.post("/api/design-studio/shorts", json={
            "asset_id": "asset-1", "prompt": "a dancer holding the pouch"})
        assert response.status_code == 422, response.text
        detail = response.json()["detail"]
        assert detail["code"] == "human_features_warning"
        assert "human features" in detail["warning"]
    finally:
        app.dependency_overrides = {}


def test_generate_refuses_a_human_video_brief_before_the_engine(monkeypatch):
    client, app = _client(monkeypatch)
    try:
        response = client.post("/api/design-studio/generate", json={
            "brief": "a person's face beside the pouch", "kind": "video"})
        assert response.status_code == 422, response.text
        assert response.json()["detail"]["code"] == "human_features_warning"
    finally:
        app.dependency_overrides = {}


def test_an_acknowledged_prompt_is_not_blocked_by_the_guard(monkeypatch):
    client, app = _client(monkeypatch)
    try:
        response = client.post("/api/design-studio/shorts", json={
            "asset_id": "asset-1", "prompt": "a person holding the pouch",
            "human_features_ack": True})
        # the engine is unarmed in this test; the point is it is not the guard 422
        assert response.status_code != 422 or \
            response.json()["detail"].get("code") != "human_features_warning"
    finally:
        app.dependency_overrides = {}

def test_human_override_is_audited(tmp_path):
    record = video_guard.audit_override(
        "op", "shorts", "a person holding the pouch", ["person"], True,
        audit_dir=tmp_path)
    assert record["written"] is True
    lines = (tmp_path / "human_features_overrides.jsonl").read_text(
        encoding="utf-8").splitlines()
    assert len(lines) == 1
    import json
    saved = json.loads(lines[0])
    assert saved["acknowledged"] is True
    assert saved["matched"] == ["person"]
    assert saved["prompt_sha256"]
