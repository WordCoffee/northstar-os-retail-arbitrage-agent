"""Media storage abstraction for the creative lanes.

Two backends behind one interface:

* **local** (default) — files on disk under a configurable root, served by the
  app's own file route. No credentials, no network.
* **s3** — any S3-compatible object store (AWS S3 / Cloudflare R2 / MinIO).
  Activates only when configured; uses ``boto3`` if importable, otherwise reports
  ``configured: false`` honestly (it never pretends to store something).

Selection: ``NORTHSTAR_MEDIA_STORAGE = local | s3`` (default ``local``).
Secret values are never read or returned — only presence/booleans.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Protocol


class StorageUnavailable(RuntimeError):
    pass


class Backend(Protocol):
    name: str

    def put(self, key: str, data: bytes, content_type: str = "application/octet-stream") -> Dict[str, Any]: ...
    def get(self, key: str) -> bytes: ...
    def url(self, key: str, *, expires: int = 3600) -> str: ...
    def exists(self, key: str) -> bool: ...
    def list(self, prefix: str = "") -> List[str]: ...


@dataclass
class LocalBackend:
    root: Path
    url_prefix: str = "/api/creative/file"
    name: str = "local"

    def _path(self, key: str) -> Path:
        safe = key.replace("\\", "/").lstrip("/")
        if ".." in safe.split("/"):
            raise StorageUnavailable("invalid key")
        p = (self.root / safe).resolve()
        if self.root.resolve() not in p.parents and p != self.root.resolve():
            raise StorageUnavailable("key escapes storage root")
        return p

    def put(self, key: str, data: bytes, content_type: str = "application/octet-stream") -> Dict[str, Any]:
        p = self._path(key)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
        return {"backend": self.name, "key": key, "bytes": len(data),
                "url": self.url(key), "content_type": content_type}

    def get(self, key: str) -> bytes:
        return self._path(key).read_bytes()

    def url(self, key: str, *, expires: int = 3600) -> str:
        return f"{self.url_prefix}/{Path(key).name}"

    def exists(self, key: str) -> bool:
        return self._path(key).exists()

    def list(self, prefix: str = "") -> List[str]:
        base = self.root / prefix if prefix else self.root
        if not base.exists():
            return []
        return sorted(str(p.relative_to(self.root)).replace("\\", "/")
                      for p in base.rglob("*") if p.is_file())


@dataclass
class S3Backend:
    bucket: str
    endpoint: str = ""
    region: str = ""
    url_prefix: str = ""
    name: str = "s3"

    def _client(self):
        try:
            import boto3  # type: ignore
        except Exception as exc:  # pragma: no cover - optional dep
            raise StorageUnavailable(
                "boto3 is not installed; pip install boto3 to use the s3 backend"
            ) from exc
        return boto3.client("s3", endpoint_url=self.endpoint or None,
                            region_name=self.region or None)

    def put(self, key: str, data: bytes, content_type: str = "application/octet-stream") -> Dict[str, Any]:
        self._client().put_object(Bucket=self.bucket, Key=key, Body=data,
                                  ContentType=content_type)
        return {"backend": self.name, "key": key, "bytes": len(data),
                "url": self.url(key), "content_type": content_type}

    def get(self, key: str) -> bytes:
        obj = self._client().get_object(Bucket=self.bucket, Key=key)
        return obj["Body"].read()

    def url(self, key: str, *, expires: int = 3600) -> str:
        try:
            return self._client().generate_presigned_url(
                "get_object", Params={"Bucket": self.bucket, "Key": key},
                ExpiresIn=expires)
        except Exception:
            if self.url_prefix:
                return f"{self.url_prefix.rstrip('/')}/{key}"
            raise StorageUnavailable("cannot sign url (boto3 missing)")

    def exists(self, key: str) -> bool:
        from botocore.exceptions import ClientError  # type: ignore
        try:
            self._client().head_object(Bucket=self.bucket, Key=key)
            return True
        except ClientError:
            return False

    def list(self, prefix: str = "") -> List[str]:
        resp = self._client().list_objects_v2(Bucket=self.bucket, Prefix=prefix)
        return [o["Key"] for o in resp.get("Contents", [])]


def _local_root() -> Path:
    env = os.environ.get("NORTHSTAR_MEDIA_DIR")
    if env:
        return Path(env)
    # Reuse the creative output dir so existing assets are already addressable.
    return Path(__file__).resolve().parents[2] / "generated_images" / "mogra_mockups"


def get_backend() -> Backend:
    kind = (os.environ.get("NORTHSTAR_MEDIA_STORAGE") or "local").strip().lower()
    if kind == "s3":
        bucket = os.environ.get("NORTHSTAR_S3_BUCKET", "")
        if not bucket:
            raise StorageUnavailable("NORTHSTAR_MEDIA_STORAGE=s3 but NORTHSTAR_S3_BUCKET is unset")
        return S3Backend(bucket=bucket,
                         endpoint=os.environ.get("NORTHSTAR_S3_ENDPOINT", ""),
                         region=os.environ.get("NORTHSTAR_S3_REGION", ""),
                         url_prefix=os.environ.get("NORTHSTAR_S3_PUBLIC_URL", ""))
    return LocalBackend(root=_local_root())


def storage_status() -> Dict[str, Any]:
    """Report the configured backend WITHOUT reading any secret value."""
    kind = (os.environ.get("NORTHSTAR_MEDIA_STORAGE") or "local").strip().lower()
    if kind == "s3":
        has_boto = True
        try:
            import boto3  # noqa: F401
        except Exception:
            has_boto = False
        return {
            "backend": "s3",
            "configured": bool(os.environ.get("NORTHSTAR_S3_BUCKET")) and has_boto,
            "bucket_set": bool(os.environ.get("NORTHSTAR_S3_BUCKET")),
            "endpoint_set": bool(os.environ.get("NORTHSTAR_S3_ENDPOINT")),
            "boto3": has_boto,
        }
    return {"backend": "local", "configured": True, "root": str(_local_root())}
