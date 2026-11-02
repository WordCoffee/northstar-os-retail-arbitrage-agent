"""Studio dashboard: packages, safe file serving, proposals and decisions."""
from __future__ import annotations

import io
import json
import sys
from pathlib import Path

import pytest
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))

import studio_dashboard as sd  # noqa: E402


def _png(size=(32, 32)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", size, (200, 180, 150)).save(buf, format="PNG")
    return buf.getvalue()


def _package(root: Path, run_id: str, *, manifest=True, video=False) -> Path:
    folder = root / run_id
    folder.mkdir(parents=True)
    (folder / "final.png").write_bytes(_png())
    if video:
        (folder / "short.webm").write_bytes(b"WEBM" * 8)
    if manifest:
        (folder / "manifest.json").write_text(json.dumps({
            "run_id": run_id, "kind": "shorts_clip" if video else "relight",
            "created_at": "2026-11-02T10:00:00",
            "quality": {"verdict": {"ok": True, "score": "2/2"}},
        }), encoding="utf-8")
    return folder


@pytest.fixture()
def client(monkeypatch, tmp_path):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    import design_studio_api

    deliverables = tmp_path / "deliverables"
    proposals = tmp_path / "proposals"
    deliverables.mkdir()
    proposals.mkdir()
    monkeypatch.setattr(sd, "DELIVERABLES", deliverables)
    monkeypatch.setattr(sd, "PROPOSALS", proposals)

    app = FastAPI()
    app.include_router(sd.router)
    app.dependency_overrides[design_studio_api.studio_account] = lambda: "org-dash"
    return SimpleClient(TestClient(app), deliverables, proposals)


class SimpleClient:
    def __init__(self, client, deliverables, proposals):
        self.client = client
        self.deliverables = deliverables
        self.proposals = proposals


def test_packages_are_listed_with_a_video_preview_first(client):
    _package(client.deliverables, "short_1", video=True)
    _package(client.deliverables, "img_1")
    data = client.client.get("/api/design-studio/dashboard/packages").json()
    assert data["count"] == 2
    by_id = {row["run_id"]: row for row in data["packages"]}
    assert by_id["short_1"]["preview"]["kind"] == "video"
    assert by_id["img_1"]["preview"]["kind"] == "image"
    assert by_id["img_1"]["score"] == "2/2"


def test_a_package_without_a_manifest_is_still_listed_but_flagged(client):
    _package(client.deliverables, "broken_1", manifest=False)
    row = client.client.get("/api/design-studio/dashboard/packages").json()["packages"][0]
    assert row["manifest"] is False
    assert row["manifest_url"] is None
    assert client.client.get("/api/design-studio/dashboard/packages/broken_1").status_code == 422


def test_a_manifest_is_served_as_json(client):
    _package(client.deliverables, "img_2")
    r = client.client.get("/api/design-studio/dashboard/packages/img_2/manifest")
    assert r.status_code == 200
    assert r.json()["kind"] == "relight"


def test_files_are_served_with_their_media_type(client):
    _package(client.deliverables, "img_3")
    r = client.client.get("/api/design-studio/dashboard/packages/img_3/file/final.png")
    assert r.status_code == 200
    assert r.headers["content-type"] == "image/png"
    assert r.content[:4] == b"\x89PNG"


def test_a_traversal_attempt_is_a_404(client):
    _package(client.deliverables, "img_4")
    from fastapi import HTTPException
    for bad in ("..", "../..", "img_4/../img_4", "a/b", "a\\b", ".hidden"):
        with pytest.raises(HTTPException) as caught:
            sd._safe_name(bad, "package")
        assert caught.value.status_code == 404
    # An encoded separator survives routing and still must not resolve.
    assert client.client.get(
        "/api/design-studio/dashboard/packages/img_4/file/..%2Fmanifest.json").status_code == 404
    assert client.client.get(
        "/api/design-studio/dashboard/packages/img_4/file/sub%2Ffinal.png").status_code == 404


def test_an_unknown_package_is_a_404(client):
    assert client.client.get(
        "/api/design-studio/dashboard/packages/nope/manifest").status_code == 404


def _proposal(root: Path, stem="repo_thing_v1") -> Path:
    path = root / f"{stem}.json"
    path.write_text(json.dumps({
        "key": "repo/thing@v1", "repo": "repo/thing", "tag": "v1",
        "licence": "MIT", "eligible": True, "status": "proposed",
    }), encoding="utf-8")
    return path


def test_proposals_are_listed(client):
    _proposal(client.proposals)
    data = client.client.get("/api/design-studio/dashboard/proposals").json()
    assert data["count"] == 1
    assert data["proposals"][0]["licence"] == "MIT"
    assert "never downloads" in data["note"]


def test_a_decision_moves_the_file_and_records_it(client):
    _proposal(client.proposals)
    r = client.client.post("/api/design-studio/dashboard/proposals/repo_thing_v1/decide",
                           json={"decision": "approved", "note": "worth a trial"})
    assert r.status_code == 200, r.text
    approved = client.proposals / "approved" / "repo_thing_v1.json"
    assert approved.is_file()
    assert not (client.proposals / "repo_thing_v1.json").exists()
    data = json.loads(approved.read_text(encoding="utf-8"))
    assert data["decision"] == "approved"
    assert data["status"] == "approved"
    assert data["decision_note"] == "worth a trial"


def test_deciding_twice_is_a_409(client):
    _proposal(client.proposals, "dup_v1")
    assert client.client.post(
        "/api/design-studio/dashboard/proposals/dup_v1/decide",
        json={"decision": "rejected"}).status_code == 200
    second = client.client.post(
        "/api/design-studio/dashboard/proposals/dup_v1/decide",
        json={"decision": "approved"})
    assert second.status_code == 409
    assert second.json()["detail"]["decision"] == "rejected"


def test_an_unknown_proposal_is_a_404(client):
    assert client.client.post(
        "/api/design-studio/dashboard/proposals/ghost/decide",
        json={"decision": "approved"}).status_code == 404
