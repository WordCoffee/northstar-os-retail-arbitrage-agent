"""Operator asset uploads (Bojo attachments).

The design-studio asset *store* already exists: an asset record carries a
``storage_key`` which the GET ``/assets/{id}/file`` route serves from
``data/studio_generated/``. This module adds the missing write half — store the
bytes the operator attached, then register the asset.

Honesty / safety
----------------
* The stored filename is a **basename** with a generated prefix: traversal cannot
  escape the output directory.
* An allow-list of mime types, and a hard size cap. Anything else is refused with
  a reason the operator can act on.
* The pure helper (``store_upload``) is tested without FastAPI or a live server.
* An upload is stored and registered — never silently converted, resized or sent
  to a provider.
"""
from __future__ import annotations

import os
import re
import uuid
from typing import Any, Dict, Optional, Tuple

MAX_UPLOAD_BYTES = 25 * 1024 * 1024          # 25 MB

ALLOWED_MIME = {
    "image/png", "image/jpeg", "image/webp", "image/gif", "image/svg+xml",
    "video/mp4", "video/webm", "video/quicktime",
    "application/pdf", "text/plain", "text/csv",
}

_EXT_BY_MIME = {
    "image/png": ".png", "image/jpeg": ".jpg", "image/webp": ".webp",
    "image/gif": ".gif", "image/svg+xml": ".svg", "video/mp4": ".mp4",
    "video/webm": ".webm", "video/quicktime": ".mov", "application/pdf": ".pdf",
    "text/plain": ".txt", "text/csv": ".csv",
}

_SAFE = re.compile(r"[^A-Za-z0-9._-]+")


def output_dir() -> str:
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "data",
                        "studio_generated")


def _safe_name(filename: str, mime: str) -> str:
    base = os.path.basename(str(filename or "")).strip() or "upload"
    base = _SAFE.sub("-", base).strip(".-") or "upload"
    root, ext = os.path.splitext(base)
    ext = ext.lower() or _EXT_BY_MIME.get(mime, "")
    root = (root or "upload")[: max(1, 80 - len(ext))]
    return root + ext


def asset_type_for(mime: str) -> str:
    if mime.startswith("image/"):
        return "image"
    if mime.startswith("video/"):
        return "video"
    if mime == "application/pdf":
        return "document"
    return "file"


def validate(mime: str, size: int) -> Optional[str]:
    if not mime:
        return "the file has no content type"
    if mime not in ALLOWED_MIME:
        return f"'{mime}' is not an accepted type (images, video, pdf, csv, text)"
    if size <= 0:
        return "the file is empty"
    if size > MAX_UPLOAD_BYTES:
        return f"the file is {size / 1024 / 1024:.1f} MB; the limit is {MAX_UPLOAD_BYTES // 1024 // 1024} MB"
    return None


def store_upload(filename: str, mime: str, data: bytes,
                 directory: Optional[str] = None) -> Dict[str, Any]:
    """Write the bytes to the studio output dir. Returns the asset fields or a reason."""
    reason = validate(mime, len(data or b""))
    if reason:
        return {"ok": False, "error": reason}
    target_dir = directory or output_dir()
    os.makedirs(target_dir, exist_ok=True)
    safe = _safe_name(filename, mime)
    key = f"upload-{uuid.uuid4().hex[:10]}-{safe}"
    path = os.path.join(target_dir, key)
    # Belt and braces: the key is derived from a basename, so it cannot traverse.
    if os.path.dirname(os.path.abspath(path)) != os.path.abspath(target_dir):
        return {"ok": False, "error": "unsafe filename"}
    with open(path, "wb") as fh:
        fh.write(data)
    return {
        "ok": True,
        "storage_key": key,
        "name": safe,
        "mime_type": mime,
        "asset_type": asset_type_for(mime),
        "size_bytes": len(data),
        "path": path,
    }
