"""Video-ad API: plan without spending GPU time, then a confirm-gated job."""
from __future__ import annotations

import base64
import json
import io

import pytest
from fastapi import HTTPException
from PIL import Image

import video_ad
import video_ad_api as api


def _body(**over):
    data = dict(platform="tiktok", seconds=3, confirm=False)
    data.update(over)
    return api.VideoAdIn(**data)


def _plate_url() -> str:
    img = Image.new("RGB", (256, 384), (213, 167, 122))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode("ascii")


@pytest.fixture(autouse=True)
def _isolated_jobs(tmp_path, monkeypatch):
    monkeypatch.setattr(api, "JOBS_DIR", tmp_path / "jobs")
    monkeypatch.setattr(api, "_JOBS", {})
    yield


def test_plan_returns_scenes_and_clip_count_without_a_job():
    out = api.plan_only(_body(), acct="test")
    assert out["dry_run"] is True
    assert len(out["plan"]["scenes"]) == 5
    assert out["sampler_clips"] >= 1
    assert not api.JOBS_DIR.exists() or not list(api.JOBS_DIR.glob("*.json"))


def test_an_invalid_platform_is_refused_before_any_work():
    with pytest.raises(HTTPException) as err:
        api.plan_only(_body(platform="myspace"), acct="test")
    assert err.value.status_code == 422
    assert "video_format_invalid" in str(err.value.detail)


def test_render_requires_an_explicit_confirm():
    with pytest.raises(HTTPException) as err:
        api.start_render(_body(), acct="test")
    assert err.value.status_code == 400
    assert err.value.detail["code"] == "confirm_render_required"
    assert err.value.detail["plan"]["dry_run"] is True


def test_a_confirmed_render_without_a_plate_is_refused():
    with pytest.raises(HTTPException) as err:
        api.start_render(_body(confirm=True), acct="test")
    assert err.value.status_code == 422
    assert err.value.detail["code"] == "plate_required"


def test_a_job_runs_the_producer_and_records_done(monkeypatch, tmp_path):
    def fake_produce(product, **kwargs):
        kwargs["on_progress"]("clip", {"scene": 0})
        return {"ok": True, "file": str(tmp_path / "video_ad.mp4"),
                "checks": {"all": True}}

    monkeypatch.setattr(video_ad, "produce", fake_produce)
    api._update("vad_0123456789ab", status="queued", stage="queued")
    api._run_job("vad_0123456789ab", {"product": "x"}, _body(), b"PNG",
                 str(tmp_path / "out"))
    job = api.get_job("vad_0123456789ab", acct="test")
    assert job["status"] == "done"
    assert job["manifest"]["ok"] is True
    assert (api.JOBS_DIR / "vad_0123456789ab.json").is_file()


def test_a_failed_job_keeps_the_reason(monkeypatch, tmp_path):
    def boom(product, **kwargs):
        raise video_ad.VideoAdError("video_ad_contract_failed: duration_within_one_frame")

    monkeypatch.setattr(video_ad, "produce", boom)
    api._update("vad_ba9876543210", status="queued")
    api._run_job("vad_ba9876543210", {"product": "x"}, _body(), b"PNG", str(tmp_path / "out"))
    job = api.get_job("vad_ba9876543210", acct="test")
    assert job["status"] == "failed"
    assert "duration_within_one_frame" in job["reason"]


def test_an_unknown_job_is_404():
    with pytest.raises(HTTPException) as err:
        api.get_job("vad_222222222222", acct="test")
    assert err.value.status_code == 404

def test_a_job_left_running_is_marked_interrupted_on_recovery(tmp_path, monkeypatch):
    monkeypatch.setattr(api, "JOBS_DIR", tmp_path)
    monkeypatch.setattr(api, "_JOBS", {})
    (tmp_path / "vad_111111111111.json").write_text(
        json.dumps({"job_id": "vad_111111111111", "status": "running", "stage": "clip"}),
        encoding="utf-8")
    rows = api.recover_interrupted()
    assert "vad_111111111111" in rows
    job = api.get_job("vad_111111111111", acct="test")
    assert job["status"] == "interrupted"
    assert "restarted" in job["reason"]
    # the replaced file is parseable, not a half-written one
    json.loads((tmp_path / "vad_111111111111.json").read_text(encoding="utf-8"))

def test_a_job_id_that_is_a_path_is_refused():
    with pytest.raises(HTTPException) as err:
        api.get_job("../config", acct="test")
    assert err.value.status_code == 404
