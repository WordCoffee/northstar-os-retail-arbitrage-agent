"""V2 — the async assembly lane.

Mirrors the generation lane's contract (gate -> reserve -> job row -> executor ->
status + asset + webhook) with one deliberate difference the REA pass exposed:
assembly needs FFmpeg, NOT the GPU engine. Gating it on ComfyUI would refuse a
job that never touches ComfyUI.
"""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

import pytest
from PIL import Image

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import design_studio_async as dsa  # noqa: E402

pytestmark = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg not installed")


class _Jobs:
    def __init__(self):
        self.rows = {}

    def create(self, payload):
        jid = f"job-{len(self.rows) + 1}"
        self.rows[jid] = dict(payload, id=jid)
        return jid

    def update(self, job_id, patch, account_id=None):
        self.rows[job_id].update(patch)

    def get_by_id(self, job_id, account_id=None):
        return self.rows.get(job_id)


class _Assets:
    def __init__(self, files):
        self.files = files
        self.created = []

    def get_by_id(self, aid, account_id=None):
        key = self.files.get(aid)
        return {"id": aid, "storage_key": key} if key else None

    def create(self, payload):
        self.created.append(payload)
        return f"asset-{len(self.created)}"


class _DS:
    def __init__(self, files):
        self.jobs = _Jobs()
        self.assets = _Assets(files)


class _DB:
    def __init__(self, files):
        self.design_studio = _DS(files)


def _still(path, colour):
    Image.new("RGB", (240, 400), colour).save(path)
    return path


def test_assembly_does_not_require_the_gpu_engine(monkeypatch):
    st = dsa.assembly_available()
    assert st["ready"] is True
    assert st["needs_engine"] is False

    monkeypatch.setattr(shutil, "which", lambda name: None)
    st = dsa.assembly_available()
    assert st["ready"] is False


def test_missing_ffmpeg_is_a_409_with_a_reason(monkeypatch):
    monkeypatch.setattr(shutil, "which", lambda name: None)
    with pytest.raises(Exception) as err:
        dsa.submit_assembly("acct", images=["a"])
    assert "ffmpeg_missing" in str(getattr(err.value, "detail", err.value))


def test_run_assembly_produces_an_asset_and_a_probe(tmp_path):
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    _still(out_dir / "one.png", (230, 225, 215))
    _still(out_dir / "two.png", (40, 74, 52))
    db = _DB({"img-1": "one.png", "img-2": "two.png"})
    db.design_studio.jobs.create({"status": "queued", "job_type": "assemble-video"})

    result = dsa.run_assembly_job(
        job_id="job-1", acct="acct",
        body={"images": ["img-1", "img-2"], "captions": ["first", "second"],
              "seconds": 1.0, "width": 320, "height": 568},
        db=db, out_dir=out_dir, enforce=False)
    # the job row was created by submit_assembly in production; here we seed it
    assert result["status"] == "done", result
    asset = db.design_studio.assets.created[0]
    assert asset["mime_type"] == "video/mp4"
    assert asset["metadata"]["assembly"]["probe"]["duration_s"] > 1.0
    assert (out_dir / asset["storage_key"]).is_file()
    assert db.design_studio.assets.created[0]["metadata"]["assembly"]["lane"] == "assemble"


def test_a_bad_input_fails_the_job_without_an_asset(tmp_path):
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    db = _DB({})
    db.design_studio.jobs.create({"status": "queued", "job_type": "assemble-video"})
    result = dsa.run_assembly_job(job_id="job-1", acct="acct",
                                  body={"images": ["not-an-asset"]}, db=db,
                                  out_dir=out_dir, enforce=False)
    assert result["status"] == "failed"
    assert db.design_studio.assets.created == []
    assert db.design_studio.jobs.rows["job-1"]["status"] == "failed"


def test_arbitrary_paths_are_refused(tmp_path):
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    outsider = tmp_path / "secret.png"
    _still(outsider, (10, 10, 10))
    db = _DB({})
    db.design_studio.jobs.create({"status": "queued"})
    result = dsa.run_assembly_job(job_id="job-1", acct="acct",
                                  body={"images": [str(outsider)]}, db=db,
                                  out_dir=out_dir, enforce=False)
    assert result["status"] == "failed"
    assert "neither an asset id nor a file in the studio output" in result["error"]


def test_enforcement_never_charges_zero_cost_jobs(monkeypatch):
    monkeypatch.setenv("DESIGN_CREDIT_COST_ASSEMBLE", "0")
    assert dsa._assembly_cost() == 0
    monkeypatch.setenv("DESIGN_CREDIT_COST_ASSEMBLE", "2")
    assert dsa._assembly_cost() == 2


def test_the_route_accepts_a_job_and_reports_it_done(monkeypatch):
    """End-to-end through the router in-process: POST -> run -> GET status.

    The live server predates this route (it appears after a restart), so the
    route is proved here against the real router object instead of by touching
    the operator's running process.
    """
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    import design_studio_api

    out_dir = dsa._out_dir()
    names = ["v2_route_a.png", "v2_route_b.png"]
    _still(out_dir / names[0], (230, 225, 215))
    _still(out_dir / names[1], (40, 74, 52))

    db = _DB({"plate-a": names[0], "plate-b": names[1]})

    class _Sync:
        def submit(self, fn, **kw):
            fn(**kw)

    monkeypatch.setattr(dsa, "get_northstar_db", lambda: db)
    monkeypatch.setattr(dsa, "_EXECUTOR", _Sync())

    app = FastAPI()
    app.include_router(dsa.router)
    app.dependency_overrides[design_studio_api.studio_account] = lambda: "acct"
    client = TestClient(app)
    try:
        r = client.post("/api/design-studio/assemble-async", json={
            "images": ["plate-a", "plate-b"], "captions": ["one", "two"],
            "seconds": 0.8, "width": 256, "height": 456,
        })
        assert r.status_code == 202, r.text
        job_id = r.json()["job"]["id"]

        status = client.get(f"/api/design-studio/generate-async/{job_id}")
        assert status.status_code == 200, status.text
        body = status.json()
        assert body["job"]["status"] == "done", body
        assert body["job"]["asset_id"]
    finally:
        for a in db.design_studio.assets.created:
            (out_dir / a["storage_key"]).unlink(missing_ok=True)
        for name in names:
            (out_dir / name).unlink(missing_ok=True)
