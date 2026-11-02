"""Studio dashboard: read the deliverables and proposals that already exist on disk.

Four lanes now write packages (`state/deliverables/<run_id>/`) and the discovery
queue writes proposals (`state/proposals/*.json`). Until this router existed the
only way to see any of it was to open the folder or call the studio API with the
right asset id.

Everything here is read-mostly and local: it lists packages, serves their files
by safe basename, lists proposals and records an approve/reject decision by moving
the file. It does not install anything, and it never invents a record: a package
without a manifest is reported as invalid, not skipped silently or filled in.

Path safety: run ids and file names are matched against a strict pattern and the
resolved path must stay inside its package folder. A traversal attempt is a 404,
not a redirect.
"""
from __future__ import annotations

import json
import re
import shutil
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from design_studio_api import studio_account

router = APIRouter(prefix="/api/design-studio/dashboard", tags=["studio-dashboard"])

ROOT = Path(__file__).resolve().parents[1]
DELIVERABLES = ROOT / "state" / "deliverables"
PROPOSALS = ROOT / "state" / "proposals"

SAFE = re.compile(r"^[A-Za-z0-9_@-][A-Za-z0-9._@-]*$")
IMAGE_EXT = {".png", ".jpg", ".jpeg", ".webp"}
VIDEO_EXT = {".webm", ".mp4"}


def _safe_name(value: str, what: str) -> str:
    name = str(value or "").strip()
    if not name or not SAFE.match(name) or name in (".", ".."):
        raise HTTPException(status_code=404, detail=f"{what} not found")
    return name


def _package_dir(run_id: str) -> Path:
    name = _safe_name(run_id, "package")
    folder = (DELIVERABLES / name).resolve()
    root = DELIVERABLES.resolve()
    if root not in folder.parents or not folder.is_dir():
        raise HTTPException(status_code=404, detail="Package not found")
    return folder


def _file_kind(name: str) -> str:
    ext = Path(name).suffix.lower()
    if ext in IMAGE_EXT:
        return "image"
    if ext in VIDEO_EXT:
        return "video"
    if ext == ".json":
        return "json"
    return "other"


def _media_type(name: str) -> str:
    ext = Path(name).suffix.lower()
    return {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
            ".webp": "image/webp", ".webm": "video/webm", ".mp4": "video/mp4",
            ".json": "application/json"}.get(ext, "application/octet-stream")


def _read_manifest(folder: Path) -> Optional[Dict[str, Any]]:
    path = folder / "manifest.json"
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def _package_row(folder: Path) -> Dict[str, Any]:
    manifest = _read_manifest(folder)
    files = []
    for path in sorted(p for p in folder.iterdir() if p.is_file()):
        files.append({"name": path.name, "bytes": path.stat().st_size,
                      "kind": _file_kind(path.name),
                      "url": f"/api/design-studio/dashboard/packages/{folder.name}/file/{path.name}"})
    preview = next((f for f in files if f["kind"] == "video"), None) or \
              next((f for f in files if f["kind"] == "image"), None)
    verdict = ((manifest or {}).get("quality") or {}).get("verdict") or {}
    return {
        "run_id": folder.name,
        "kind": (manifest or {}).get("kind") or "unknown",
        "created_at": (manifest or {}).get("created_at"),
        "manifest": manifest is not None,
        "ok": verdict.get("ok"),
        "score": verdict.get("score"),
        "files": files,
        "preview": preview,
        "manifest_url": (f"/api/design-studio/dashboard/packages/{folder.name}/manifest"
                         if manifest is not None else None),
    }


@router.get("/packages")
def list_packages(limit: int = 200, acct: str = Depends(studio_account)):
    """Every package on disk, newest first. Invalid packages are reported, not hidden."""
    if not DELIVERABLES.is_dir():
        return {"count": 0, "packages": [], "root": str(DELIVERABLES)}
    rows = []
    folders = sorted((p for p in DELIVERABLES.iterdir() if p.is_dir()),
                     key=lambda p: p.stat().st_mtime, reverse=True)[:max(1, min(limit, 1000))]
    for folder in folders:
        rows.append(_package_row(folder))
    return {"count": len(rows), "packages": rows, "root": str(DELIVERABLES)}


@router.get("/packages/{run_id}")
def get_package(run_id: str, acct: str = Depends(studio_account)):
    folder = _package_dir(run_id)
    row = _package_row(folder)
    if not row["manifest"]:
        raise HTTPException(status_code=422, detail={
            "code": "package_without_manifest",
            "message": "this folder has no readable manifest.json; files are listed but the run is invalid"})
    return row


@router.get("/packages/{run_id}/manifest")
def get_manifest(run_id: str, acct: str = Depends(studio_account)):
    folder = _package_dir(run_id)
    manifest = _read_manifest(folder)
    if manifest is None:
        raise HTTPException(status_code=404, detail="manifest.json not found or unreadable")
    return manifest


@router.get("/packages/{run_id}/file/{name}")
def get_package_file(run_id: str, name: str, acct: str = Depends(studio_account)):
    folder = _package_dir(run_id)
    safe = _safe_name(name, "file")
    path = (folder / safe).resolve()
    if folder not in path.parents or not path.is_file():
        raise HTTPException(status_code=404, detail="file not found")
    return FileResponse(str(path), media_type=_media_type(safe), filename=safe)


# --- proposals ---------------------------------------------------------------

DECISIONS = ("approved", "rejected")


def _proposal_rows() -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    if not PROPOSALS.is_dir():
        return rows
    for path in sorted(PROPOSALS.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if not isinstance(data, dict):
            continue
        rows.append({
            "id": path.stem,
            "key": data.get("key"),
            "repo": data.get("repo"),
            "tag": data.get("tag"),
            "why": data.get("why"),
            "licence": data.get("licence"),
            "eligible": data.get("eligible"),
            "status": data.get("status"),
            "proposed_at": data.get("proposed_at"),
            "next_step": data.get("next_step"),
        })
    return rows


@router.get("/proposals")
def list_proposals(acct: str = Depends(studio_account)):
    """Undecided proposals. A decision moves the file; nothing is installed."""
    return {"count": len(_proposal_rows()), "proposals": _proposal_rows(),
            "decided": {d: len(list((PROPOSALS / d).glob("*.json"))) if (PROPOSALS / d).is_dir() else 0
                        for d in DECISIONS},
            "note": ("Approving records a decision. Installing a tool is still a separate, "
                     "logged step - this queue never downloads or executes anything.")}


class DecisionIn(BaseModel):
    decision: str = Field(..., pattern="^(approved|rejected)$")
    note: str = Field("", max_length=400)


@router.post("/proposals/{proposal_id}/decide")
def decide_proposal(proposal_id: str, body: DecisionIn, acct: str = Depends(studio_account)):
    safe = _safe_name(proposal_id, "proposal")
    source = PROPOSALS / f"{safe}.json"
    if not source.is_file():
        for decision in DECISIONS:
            if (PROPOSALS / decision / f"{safe}.json").is_file():
                raise HTTPException(status_code=409, detail={
                    "code": "already_decided", "decision": decision})
        raise HTTPException(status_code=404, detail="Proposal not found")
    try:
        data = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=f"proposal is not readable JSON: {exc}")
    if not isinstance(data, dict):
        raise HTTPException(status_code=422, detail="proposal is not a JSON object")

    data["decision"] = body.decision
    data["decided_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    data["status"] = body.decision
    if body.note:
        data["decision_note"] = body.note
    target_dir = PROPOSALS / body.decision
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / source.name
    source.write_text(json.dumps(data, indent=2), encoding="utf-8")
    shutil.move(str(source), str(target))
    try:
        shown = str(target.relative_to(ROOT)).replace("\\", "/")
    except ValueError:  # a test or an operator may point the queue elsewhere
        shown = str(target)
    return {"ok": True, "id": safe, "decision": body.decision,
            "path": shown,
            "note": "recorded; installing remains a separate approved step"}


__all__ = ["router"]
