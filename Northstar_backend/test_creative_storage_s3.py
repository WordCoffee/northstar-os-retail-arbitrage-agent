"""S3-compatible object-store parity test for `creative.storage`.

Uses a fake `boto3` module so the S3 backend code paths are exercised fully
offline — no network, no credentials.
"""

from __future__ import annotations

import io
import sys
import types

import pytest

from creative import storage


class _ClientError(Exception):
    pass


def _install_fake_boto3(monkeypatch):
    store: dict = {}

    class FakeClient:
        def put_object(self, Bucket, Key, Body, ContentType=None):
            store[Key] = Body

        def get_object(self, Bucket, Key):
            if Key not in store:
                raise _ClientError("NoSuchKey")
            return {"Body": io.BytesIO(store[Key])}

        def generate_presigned_url(self, op, Params, ExpiresIn):
            return f"https://s3.example/{Params['Bucket']}/{Params['Key']}?sig=x"

        def head_object(self, Bucket, Key):
            if Key not in store:
                raise _ClientError("404")
            return {}

        def list_objects_v2(self, Bucket, Prefix=""):
            return {"Contents": [{"Key": k} for k in store if k.startswith(Prefix)]}

    boto3 = types.ModuleType("boto3")
    boto3.client = lambda *a, **k: FakeClient()
    monkeypatch.setitem(sys.modules, "boto3", boto3)

    botocore = types.ModuleType("botocore")
    exc_mod = types.ModuleType("botocore.exceptions")
    exc_mod.ClientError = _ClientError
    monkeypatch.setitem(sys.modules, "botocore", botocore)
    monkeypatch.setitem(sys.modules, "botocore.exceptions", exc_mod)
    return store


def test_s3_backend_roundtrip(monkeypatch):
    store = _install_fake_boto3(monkeypatch)
    be = storage.S3Backend(bucket="mybucket", endpoint="https://s3.example", region="us-east-1")

    info = be.put("assets/one.png", b"PNGDATA", "image/png")
    assert info["backend"] == "s3" and info["bytes"] == 7
    assert be.get("assets/one.png") == b"PNGDATA"
    assert be.url("assets/one.png").startswith("https://s3.example/mybucket/")
    assert be.exists("assets/one.png") is True
    assert be.exists("assets/missing.png") is False
    assert "assets/one.png" in be.list("assets/")


def test_s3_backend_requires_boto3(monkeypatch):
    monkeypatch.setitem(sys.modules, "boto3", None)  # simulate "not installed"
    be = storage.S3Backend(bucket="b")
    with pytest.raises(storage.StorageUnavailable):
        be.put("k", b"x")


def test_get_backend_selects_s3(monkeypatch):
    _install_fake_boto3(monkeypatch)
    monkeypatch.setenv("NORTHSTAR_MEDIA_STORAGE", "s3")
    monkeypatch.setenv("NORTHSTAR_S3_BUCKET", "bucket-x")
    be = storage.get_backend()
    assert isinstance(be, storage.S3Backend) and be.bucket == "bucket-x"


def test_storage_status_s3_configured(monkeypatch):
    _install_fake_boto3(monkeypatch)
    monkeypatch.setenv("NORTHSTAR_MEDIA_STORAGE", "s3")
    monkeypatch.setenv("NORTHSTAR_S3_BUCKET", "bucket-x")
    s = storage.storage_status()
    assert s["backend"] == "s3" and s["configured"] is True and s["boto3"] is True
