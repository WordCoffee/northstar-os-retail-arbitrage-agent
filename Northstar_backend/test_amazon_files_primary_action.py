"""PPC lane, end to end through the API: upload -> propose -> approve -> write -> download.

The existing coverage tests the parsers and writers as libraries. The operator's actual path is
the API, where a proposal can be blocked, a spend limit can demand a second confirmation, a change
file's version has to increment, and the download has to be the bytes that were written. Nothing
here reaches a network: the bulksheet is built in memory and the store is a real sqlite file in the
test's own directory.
"""
from __future__ import annotations

import base64
import io
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
for extra in (str(ROOT / "Northstar_backend"),):
    if extra not in sys.path:
        sys.path.insert(0, extra)

# The bulksheet shape the parser detects: one campaign, one ad group, two keywords.
SHEET_ROWS = [
    ["Product", "Entity", "Operation", "Campaign ID", "Ad Group ID", "Keyword ID",
     "Campaign Name", "Ad Group Name", "Keyword Text", "Match Type", "Bid", "State"],
    ["Sponsored Products", "Campaign", "Update", "C100", "", "", "Launch", "", "", "", "", "enabled"],
    ["Sponsored Products", "Ad Group", "Update", "C100", "A200", "", "Launch", "Broad", "", "", "", "enabled"],
    ["Sponsored Products", "Keyword", "Update", "C100", "A200", "K300", "Launch", "Broad",
     "tumbler steel", "broad", "0.75", "enabled"],
    ["Sponsored Products", "Keyword", "Update", "C100", "A200", "K301", "Launch", "Broad",
     "cold brew filter", "exact", "1.10", "enabled"],
]


def _xlsx(rows) -> bytes:
    openpyxl = pytest.importorskip("openpyxl")
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Sponsored Products Campaigns"
    for row in rows:
        ws.append(row)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


@pytest.fixture()
def api(tmp_path, monkeypatch):
    """The real store on a temp file, the real app, one overridden identity."""
    import data_layer

    monkeypatch.setattr(data_layer, "_SQLITE_PATH", tmp_path / "northstar.db")
    db = data_layer.NorthstarDB()

    import design_studio_api
    from fastapi.testclient import TestClient
    from main import app

    monkeypatch.setattr(design_studio_api, "get_northstar_db", lambda: db)
    app.dependency_overrides[design_studio_api.studio_account] = lambda: "org-ppc"
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides = {}


def _upload(api, content: bytes):
    return api.post("/api/design-studio/amazon-files/upload",
                    json={"filename": "bulk-20261111.xlsx",
                          "content_b64": base64.b64encode(content).decode("ascii")})


def _sheet_name(api, uid: str) -> str:
    upload = api.get(f"/api/design-studio/amazon-files/{uid}").json()["upload"]
    sheets = upload.get("sheets") or []
    assert sheets, "the upload reported no sheets"
    return sheets[0]["name"]


def test_the_full_path_ends_with_a_downloadable_file_and_an_incremented_version(api):
    up = _upload(api, _xlsx(SHEET_ROWS))
    assert up.status_code == 200, up.text
    upload = up.json()["upload"]
    uid = upload["id"]
    assert upload["kind"] == "ads_bulksheet"
    assert upload["row_count"] >= 4

    sheet = _sheet_name(api, uid)
    # row_index 3 is the "cold brew filter" keyword (the parser's rows start at the first data row).
    prop = api.post(f"/api/design-studio/amazon-files/{uid}/proposals",
                    json={"changes": [{"sheet": sheet, "row_index": 3, "op": "Update",
                                       "fields": {"bid": "0.90"},
                                       "reason": "raise the bid on the converting term"}]})
    assert prop.status_code == 200, prop.text
    body = prop.json()
    assert body["count"] == 1
    proposal = body["proposals"][0]
    assert proposal["blocks"] == [], proposal
    assert proposal["before"]["bid"] == "1.10"
    assert proposal["after"]["bid"] == "0.90"

    approved = api.post(f"/api/design-studio/amazon-files/proposals/{proposal['id']}/approve",
                        json={})
    assert approved.status_code == 200, approved.text
    assert approved.json()["proposal"]["status"] == "approved"

    first = api.post(f"/api/design-studio/amazon-files/{uid}/write", json={})
    assert first.status_code == 200, first.text
    f1 = first.json()["change_file"]
    assert f1["version"] == 1
    assert f1["row_count"] >= 1
    assert first.json()["roundtrip"]["ok"] is True

    # The same approved row written again is a NEW file, never an overwrite.
    second = api.post(f"/api/design-studio/amazon-files/{uid}/write", json={})
    assert second.status_code == 200, second.text
    f2 = second.json()["change_file"]
    assert f2["version"] == 2
    assert f2["id"] != f1["id"]
    assert f2["filename"].endswith("-v2." + f2["format"])

    dl = api.get(f"/api/design-studio/amazon-files/change/{f1['id']}/download")
    assert dl.status_code == 200
    if f1["format"] == "xlsx":
        assert dl.content[:2] == b"PK", "an xlsx download must start with the zip signature"
    assert len(dl.content) > 1000
    import hashlib

    assert hashlib.sha256(dl.content).hexdigest() == f1["checksum"], (
        "the downloaded bytes must be the bytes that were written and hashed")

    detail = api.get(f"/api/design-studio/amazon-files/change/{f1['id']}").json()
    assert detail["change_file"]["version"] == 1
    assert detail["roundtrip"]["ok"] is True


def test_a_write_with_nothing_approved_is_refused(api):
    up = _upload(api, _xlsx(SHEET_ROWS))
    uid = up.json()["upload"]["id"]
    r = api.post(f"/api/design-studio/amazon-files/{uid}/write", json={})
    assert r.status_code == 422
    assert r.json()["detail"]["code"] == "nothing_approved"


def test_an_unknown_row_is_blocked_and_cannot_be_approved(api):
    up = _upload(api, _xlsx(SHEET_ROWS))
    uid = up.json()["upload"]["id"]
    sheet = _sheet_name(api, uid)
    prop = api.post(f"/api/design-studio/amazon-files/{uid}/proposals",
                    json={"changes": [{"sheet": sheet, "row_index": 999, "op": "Update",
                                       "fields": {"bid": "0.90"}}]})
    assert prop.status_code == 200, prop.text
    proposal = prop.json()["proposals"][0]
    assert proposal["blocks"], "an out-of-range row must be blocked, not silently proposed"
    blocked = api.post(f"/api/design-studio/amazon-files/proposals/{proposal['id']}/approve",
                       json={})
    assert blocked.status_code == 409
    assert blocked.json()["detail"]["code"] == "proposal_blocked"


def test_a_second_account_cannot_see_the_first_accounts_upload(api):
    up = _upload(api, _xlsx(SHEET_ROWS))
    uid = up.json()["upload"]["id"]
    import design_studio_api
    from main import app

    app.dependency_overrides[design_studio_api.studio_account] = lambda: "org-other"
    leaked = api.get(f"/api/design-studio/amazon-files/{uid}")
    assert leaked.status_code == 404
