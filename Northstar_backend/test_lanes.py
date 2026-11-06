"""A busy lane is a deferral, not a failure - and the floors are never lowered."""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

import lanes  # noqa: E402


@pytest.fixture()
def lane_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(lanes, "LANES", tmp_path)
    monkeypatch.setattr(lanes, "vram_free_mb", lambda: 16000)
    monkeypatch.setattr(lanes, "ram_free_mb", lambda: 8000)
    return tmp_path


def test_a_lane_is_exclusive(lane_dir):
    assert lanes.acquire("gpu", cycle=1)["ok"] is True
    second = lanes.acquire("gpu", cycle=2)
    assert second["ok"] is False
    assert second["reason"] == "lane_held"
    assert second["holder"]["holder_cycle"] == 1


def test_release_frees_the_lane(lane_dir):
    lanes.acquire("gpu", cycle=3)
    assert lanes.release("gpu")["released"] == 3
    assert lanes.acquire("gpu", cycle=4)["ok"] is True


def test_an_expired_lease_is_reclaimable(lane_dir):
    lanes.acquire("gpu", cycle=5, ttl_s=1)
    body = json.loads((lane_dir / "gpu.json").read_text(encoding="utf-8"))
    body["taken_ts"] = time.time() - 10
    body["ttl_s"] = 1
    (lane_dir / "gpu.json").write_text(json.dumps(body), encoding="utf-8")
    assert lanes.status("gpu")["held"] is False
    assert lanes.acquire("gpu", cycle=6)["ok"] is True


def test_vram_below_the_floor_defers_without_taking_the_lane(lane_dir, monkeypatch):
    monkeypatch.setattr(lanes, "vram_free_mb", lambda: 2000)
    out = lanes.acquire("gpu", cycle=7)
    assert out["ok"] is False
    assert out["reason"] == "vram_below_floor"
    assert lanes.status("gpu")["held"] is False


def test_ram_below_the_floor_defers(lane_dir, monkeypatch):
    monkeypatch.setattr(lanes, "ram_free_mb", lambda: 1200)
    out = lanes.acquire("gpu", cycle=8)
    assert out["ok"] is False and out["reason"] == "ram_below_floor"


def test_unknown_vram_is_a_refusal_not_a_guess(lane_dir, monkeypatch):
    monkeypatch.setattr(lanes, "vram_free_mb", lambda: None)
    out = lanes.acquire("gpu", cycle=9)
    assert out["ok"] is False and out["reason"] == "vram_unknown"


def test_cpu_and_browser_lanes_have_no_resource_floor(lane_dir):
    assert lanes.acquire("cpu", cycle=10)["ok"] is True
    assert lanes.acquire("browser", cycle=10)["ok"] is True


def test_an_unreadable_lease_file_is_treated_as_free(lane_dir):
    (lane_dir / "gpu.json").write_text("{not json", encoding="utf-8")
    st = lanes.status("gpu")
    assert st["held"] is False
    assert lanes.acquire("gpu", cycle=11)["ok"] is True


def test_unknown_lane_is_refused(lane_dir):
    with pytest.raises(ValueError):
        lanes.acquire("quantum", cycle=1)
