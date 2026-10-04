"""Local image-engine status — offline, no install, no arming.

Verifies the read-only detector used by the readiness route: presence checks,
weight detection, the media gate, and that "installed" never implies "enabled".
"""
from __future__ import annotations

from pathlib import Path

from Northstar_backend import local_image_engine as lie


def test_weights_missing_when_no_home():
    w = lie.weights_status(None)
    assert w["checked"] is False
    assert len(w["missing"]) == len(lie.EXPECTED_WEIGHTS)


def test_weights_found_in_temp_home(tmp_path: Path):
    for name, dirs in lie.EXPECTED_WEIGHTS:
        d = tmp_path / dirs[0]
        d.mkdir(parents=True, exist_ok=True)
        (d / name).write_bytes(b"stub")
    w = lie.weights_status(tmp_path)
    assert w["checked"] is True
    assert w["missing"] == []
    assert len(w["found"]) == len(lie.EXPECTED_WEIGHTS)


def test_resolve_home_from_env(tmp_path: Path, monkeypatch):
    (tmp_path / "main.py").write_text("# stub")
    monkeypatch.setenv("COMFYUI_HOME", str(tmp_path))
    assert lie.resolve_comfyui_home() == tmp_path


def test_bad_url_is_unknown():
    assert lie.comfyui_reachable("not a url") == "unknown"


def test_media_gate_off_by_default(monkeypatch):
    monkeypatch.delenv("MEDIA_GEN_LIVE", raising=False)
    assert lie.media_gate_on() is False


def test_local_setup_not_ready_without_engine(monkeypatch):
    monkeypatch.setenv("COMFYUI_HOME", "")
    monkeypatch.delenv("MEDIA_GEN_LIVE", raising=False)
    s = lie.build_local_setup(engine_state="unreachable")
    assert s["comfyui_installed"] is False
    assert s["engine_reachable"] == "unreachable"
    assert s["media_gate"] is False
    assert s["ready_for_local_generation"] is False
    assert "installed != enabled" in s["note"]


def test_local_setup_ready_requires_all_four(tmp_path: Path, monkeypatch):
    for name, dirs in lie.EXPECTED_WEIGHTS:
        d = tmp_path / dirs[0]
        d.mkdir(parents=True, exist_ok=True)
        (d / name).write_bytes(b"stub")
    (tmp_path / "main.py").write_text("# stub")
    monkeypatch.setenv("COMFYUI_HOME", str(tmp_path))
    monkeypatch.setenv("MEDIA_GEN_LIVE", "1")
    s = lie.build_local_setup(engine_state="reachable")
    assert s["ready_for_local_generation"] is True


def test_installed_is_not_enabled(tmp_path: Path, monkeypatch):
    """Engine present + weights present, but gate off -> NOT ready (installed != enabled)."""
    for name, dirs in lie.EXPECTED_WEIGHTS:
        d = tmp_path / dirs[0]
        d.mkdir(parents=True, exist_ok=True)
        (d / name).write_bytes(b"stub")
    (tmp_path / "main.py").write_text("# stub")
    monkeypatch.setenv("COMFYUI_HOME", str(tmp_path))
    monkeypatch.delenv("MEDIA_GEN_LIVE", raising=False)
    s = lie.build_local_setup(engine_state="reachable")
    assert s["comfyui_installed"] is True
    assert s["media_gate"] is False
    assert s["ready_for_local_generation"] is False
