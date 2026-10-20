"""Operator uploads — safety and behaviour of the write half."""
from __future__ import annotations

import os

import pytest

import studio_uploads as su


# ── validation ─────────────────────────────────────────────────────────────

def test_accepts_the_documented_types():
    for mime in ("image/png", "image/jpeg", "video/mp4", "application/pdf", "text/csv"):
        assert su.validate(mime, 1000) is None


def test_refuses_an_unlisted_type_with_an_actionable_reason():
    reason = su.validate("application/x-msdownload", 10)
    assert reason and "not an accepted type" in reason


def test_refuses_empty_and_oversized_files():
    assert "empty" in su.validate("image/png", 0)
    big = su.MAX_UPLOAD_BYTES + 1
    assert "limit is 25 MB" in su.validate("image/png", big)


# ── storage ────────────────────────────────────────────────────────────────

def test_stores_bytes_and_returns_asset_fields(tmp_path):
    out = su.store_upload("My Photo.PNG", "image/png", b"\x89PNG-data", str(tmp_path))
    assert out["ok"] is True
    assert out["asset_type"] == "image"
    assert out["mime_type"] == "image/png"
    assert out["size_bytes"] == 9
    assert out["storage_key"].startswith("upload-") and out["storage_key"].endswith(".png")
    assert os.path.isfile(os.path.join(str(tmp_path), out["storage_key"]))


def test_traversal_in_the_filename_cannot_escape(tmp_path):
    out = su.store_upload("../../../../etc/passwd", "text/plain", b"x", str(tmp_path))
    assert out["ok"] is True
    assert ".." not in out["storage_key"]
    assert os.path.dirname(os.path.abspath(out["path"])) == os.path.abspath(str(tmp_path))


def test_a_missing_extension_is_taken_from_the_mime(tmp_path):
    out = su.store_upload("dieline", "application/pdf", b"%PDF", str(tmp_path))
    assert out["storage_key"].endswith(".pdf")


def test_weird_characters_are_neutralised(tmp_path):
    out = su.store_upload("a b\tc:d*e?.png", "image/png", b"x", str(tmp_path))
    key = out["storage_key"]
    assert all(ch.isalnum() or ch in "._-" for ch in key), key


def test_refused_upload_writes_nothing(tmp_path):
    out = su.store_upload("x.exe", "application/x-msdownload", b"x", str(tmp_path))
    assert out["ok"] is False
    assert os.listdir(str(tmp_path)) == []


def test_asset_type_mapping():
    assert su.asset_type_for("image/webp") == "image"
    assert su.asset_type_for("video/webm") == "video"
    assert su.asset_type_for("application/pdf") == "document"
    assert su.asset_type_for("text/csv") == "file"
