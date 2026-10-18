"""Brand SEO Engine router (V3 S7) — the canonical, versioned brand profile.

The SEO engine's principle (plan §5): SEO is not a listings feature; it is a
property of the brand that every service serves. This router owns the ONE
canonical profile each brand has, and its immutable version history.

Honesty boundaries:
  • Versions are append-only. Editing a profile appends a version; the old ones
    stay readable and rollback-safe. Nothing is silently rewritten.
  • A profile body is validated for shape (`seo_profile.normalize_body`) but the
    engine never invents content for the operator — absence stays absence.
  • Tenant-scoped: a profile owned by another account reports 404, never a leak.
  • These routes read/write local SQLite only; they arm no live/paid action.
"""

from __future__ import annotations

import os
import sys
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from data_layer import get_northstar_db  # noqa: E402
from design_studio_api import studio_account  # noqa: E402

router = APIRouter(prefix="/api/seo", tags=["seo"])


class ProfileIn(BaseModel):
    brand_key: str = Field(..., min_length=1, max_length=80)
    name: Optional[str] = Field(None, max_length=160)
    body: Dict[str, Any] = Field(default_factory=dict)
    note: Optional[str] = Field(None, max_length=500)


class VersionIn(BaseModel):
    body: Dict[str, Any] = Field(default_factory=dict)
    note: Optional[str] = Field(None, max_length=500)
    created_by: Optional[str] = Field(None, max_length=80)


@router.get("/profiles")
def list_profiles(limit: int = 100, acct: str = Depends(studio_account)):
    db = get_northstar_db()
    return {"profiles": db.seo.profiles.list_profiles(
        acct, limit=min(max(int(limit), 1), 500))}


@router.post("/profiles")
def create_profile(body: ProfileIn, acct: str = Depends(studio_account)):
    db = get_northstar_db()
    try:
        profile = db.seo.profiles.create_profile({
            "account_id": acct,
            "brand_key": body.brand_key,
            "name": body.name,
            "body": body.body,
            "note": body.note,
            "created_by": acct,
        })
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return profile


@router.get("/profiles/{pid}")
def get_profile(pid: str, acct: str = Depends(studio_account)):
    db = get_northstar_db()
    profile = db.seo.profiles.get_profile(pid, account_id=acct)
    if not profile:
        raise HTTPException(status_code=404, detail="SEO profile not found")
    return profile


@router.get("/profiles/{pid}/versions")
def list_versions(pid: str, acct: str = Depends(studio_account)):
    db = get_northstar_db()
    if not db.seo.profiles.get_profile(pid, account_id=acct):
        raise HTTPException(status_code=404, detail="SEO profile not found")
    return {"versions": db.seo.profiles.list_versions(pid, account_id=acct)}


@router.get("/profiles/{pid}/versions/{version}")
def get_version(pid: str, version: int, acct: str = Depends(studio_account)):
    db = get_northstar_db()
    v = db.seo.profiles.get_version(pid, version, account_id=acct)
    if not v:
        raise HTTPException(status_code=404, detail="SEO profile version not found")
    return v


@router.post("/profiles/{pid}/versions")
def add_version(pid: str, body: VersionIn, acct: str = Depends(studio_account)):
    """Append a new immutable version. The previous versions are never touched."""
    db = get_northstar_db()
    try:
        profile = db.seo.profiles.add_version(
            pid, acct, body.body, note=body.note, created_by=body.created_by or acct)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if not profile:
        raise HTTPException(status_code=404, detail="SEO profile not found")
    return profile
