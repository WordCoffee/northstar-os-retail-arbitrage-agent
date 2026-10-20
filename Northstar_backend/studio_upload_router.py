"""HTTP surface for operator uploads. Thin: logic lives in studio_uploads."""

from __future__ import annotations

import os
import sys
from typing import Optional

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile  # noqa: E402

import studio_uploads  # noqa: E402
from data_layer import get_northstar_db  # noqa: E402
from design_studio_api import studio_account  # noqa: E402

router = APIRouter(prefix="/api/design-studio", tags=["design-studio"])


@router.post("/assets/upload")
async def upload_asset(file: UploadFile = File(...),
                       acct: str = Depends(studio_account)):
    """Store an operator attachment and register it as a design-studio asset."""
    data = await file.read()
    stored = studio_uploads.store_upload(file.filename or "upload",
                                         file.content_type or "", data)
    if not stored.get("ok"):
        raise HTTPException(status_code=400, detail=stored.get("error") or "upload refused")
    db = get_northstar_db()
    aid = db.design_studio.assets.create({
        "account_id": acct,
        "name": stored["name"],
        "asset_type": stored["asset_type"],
        "mime_type": stored["mime_type"],
        "storage_key": stored["storage_key"],
        "size_bytes": stored["size_bytes"],
        "metadata": {"origin": "operator_upload"},
    })
    return {"id": aid,
            "asset": db.design_studio.assets.get_by_id(aid, account_id=acct),
            "file_url": f"/api/design-studio/assets/{aid}/file"}
