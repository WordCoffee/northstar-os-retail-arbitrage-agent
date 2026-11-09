"""The free-RAM governor: thresholds, the two-reading cross-check, and the gate.

Every test injects both readings, so the policy is proven without depending on how
much RAM this machine happens to have while the suite runs.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

import ram_governor as G  # noqa: E402


@pytest.fixture(autouse=True)
def isolated_state(tmp_path, monkeypatch):
    monkeypatch.setattr(G, "CAPS", tmp_path / "caps.json")
    monkeypatch.setattr(G, "JOURNAL", tmp_path / "ram_gate.jsonl")
    return tmp_path


def _readings(psutil_gb, win32_gb=None):
    return {"psutil_gb": psutil_gb,
            "win32_gb": psutil_gb if win32_gb is None else win32_gb}


def _status(psutil_gb, win32_gb=None, who="pytest"):
    return G.status(who=who, reading=_readings(psutil_gb, win32_gb))


# ------------------------------------------------------------------ thresholds
@pytest.mark.parametrize("free_gb,expected,paused", [
    (3.0, 4, False),
    (2.0, 4, False),     # the >= 2 GB boundary is the full lane
    (1.9, 2, False),
    (1.0, 2, False),     # the 1 GB boundary still allows two builders
    (0.9, 0, True),
    (0.4, 0, True),
])
def test_the_thresholds(free_gb, expected, paused):
    decision = _status(free_gb)

    assert decision["max_builders"] == expected
    assert decision["paused"] is paused
    assert decision["free_gb"] == free_gb
    assert f"{free_gb:.2f}" in decision["reason"]


# ---------------------------------------------------- two readings, lower wins
def test_a_disagreement_picks_the_lower_reading_and_reports_both():
    decision = _status(3.0, 1.5)          # 50 % apart: optimistic psutil loses

    assert decision["free_gb"] == 1.5
    assert decision["max_builders"] == 2
    assert decision["paused"] is False
    assert decision["disagreement"] is True
    assert decision["readings"] == {"psutil_gb": 3.0, "win32_gb": 1.5}
    assert "3.00" in decision["reason"] and "1.50" in decision["reason"]


def test_a_small_difference_uses_the_primary_reading():
    decision = _status(3.0, 2.8)          # 6.7 % apart: not a disagreement

    assert decision["free_gb"] == 3.0
    assert decision["max_builders"] == 4
    assert decision["disagreement"] is False


def test_one_missing_probe_still_decides():
    assert G.status(reading={"psutil_gb": 1.9, "win32_gb": None})["max_builders"] == 2
    assert G.status(reading={"psutil_gb": None, "win32_gb": 2.5})["max_builders"] == 4


def test_both_probes_unreadable_pauses_rather_than_guesses():
    decision = G.status(reading={"psutil_gb": None, "win32_gb": None})

    assert decision["free_gb"] is None
    assert decision["max_builders"] == 0
    assert decision["paused"] is True


# ---------------------------------------------------------------- measured cap
def test_the_measured_concurrency_cap_is_a_minimum(isolated_state):
    G.CAPS.write_text(json.dumps({"cloud_workers": 2}), encoding="utf-8")

    decision = _status(3.0)

    assert decision["max_builders"] == 2
    assert "cloud_workers" in decision["reason"]


def test_no_caps_file_means_no_cap():
    assert _status(3.0)["max_builders"] == 4


# ------------------------------------------------------------------ --gate N
def test_gate_three_passes_with_four_allowed(monkeypatch):
    monkeypatch.setattr(G, "measure", lambda: _readings(3.0))

    result = G.gate(3, who="pytest")

    assert result["allowed"] is True
    assert G.main(["--gate", "3", "--who", "pytest"]) == 0


def test_gate_three_fails_when_paused(monkeypatch):
    monkeypatch.setattr(G, "measure", lambda: _readings(0.9))

    result = G.gate(3, who="pytest")

    assert result["allowed"] is False
    assert G.main(["--gate", "3", "--who", "pytest"]) == 1


def test_gate_at_the_cap_fails(monkeypatch):
    monkeypatch.setattr(G, "measure", lambda: _readings(3.0))

    assert G.gate(3)["allowed"] is True
    assert G.gate(4)["allowed"] is False


# -------------------------------------------------------------- the journal
def test_every_decision_is_one_json_line(isolated_state):
    _status(1.9, who="builder-dispatch")
    G.gate(2, who="builder-dispatch", reading=_readings(1.9))

    lines = [json.loads(line) for line in
             G.JOURNAL.read_text(encoding="utf-8").splitlines() if line.strip()]

    assert len(lines) == 2
    first, second = lines
    assert first["who"] == "builder-dispatch"
    assert first["free_gb"] == 1.9
    assert first["max_builders"] == 2
    assert first["paused"] is False
    assert first["event"] == "status"
    assert second["event"] == "gate"
    assert second["running"] == 2 and second["allowed"] is False


def test_status_output_has_the_documented_shape(monkeypatch, capsys):
    monkeypatch.setattr(G, "measure", lambda: _readings(3.0))

    assert G.main(["--status", "--who", "pytest"]) == 0

    payload = json.loads(capsys.readouterr().out)
    assert set(payload) >= {"free_gb", "max_builders", "paused", "reason"}
