"""Improvement room API — status, gap queue, cycles, feedback, stop switch.

The engine itself is local and file-backed (``cie_loop``); this router is a thin,
honest surface. It never triggers a paid action and a real cycle is opt-in
(``dry_run=false``), because writing to the knowledge packs changes what Bojo
tells customers.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

import cie_loop
import cie_store
import knowledge_pack

try:  # same identity dependency the chat surface uses
    from design_studio_api import studio_account  # type: ignore
except Exception:  # pragma: no cover - isolated tests / import order
    async def studio_account():  # type: ignore
        return "local"

router = APIRouter(prefix="/api/v1/improvement", tags=["improvement"])


class FeedbackIn(BaseModel):
    verdict: str = Field(..., pattern="^(up|down|corrected)$")
    message_id: str = Field("", max_length=80)
    session_id: str = Field("", max_length=80)
    note: str = Field("", max_length=2000)
    mode: str = Field("standard", max_length=24)
    pack_version: str = Field("", max_length=40)


class CycleIn(BaseModel):
    dry_run: bool = True
    cap: int = Field(5, ge=1, le=20)


@router.get("/status")
def status(acct: str = Depends(studio_account)) -> Dict[str, Any]:
    try:
        data = cie_loop.status()
    except Exception as exc:  # noqa: BLE001 - surface honestly, never fake a status
        raise HTTPException(status_code=500, detail=f"improvement status failed: {exc}")
    data["account"] = acct
    return data


@router.get("/queue")
def queue(acct: str = Depends(studio_account)) -> Dict[str, Any]:
    return {"gaps": cie_store.list_gaps("open", 50),
            "resolved_recent": cie_store.list_gaps("resolved", 10)}


@router.get("/cycles")
def cycles(limit: int = 20, acct: str = Depends(studio_account)) -> Dict[str, Any]:
    return {"cycles": cie_store.list_cycles(max(1, min(int(limit), 200)))}


@router.get("/packs")
def packs(acct: str = Depends(studio_account)) -> Dict[str, Any]:
    out = {}
    for domain in knowledge_pack.domains():
        atoms = knowledge_pack.load_atoms(domain)
        out[domain] = {
            "version": knowledge_pack.pack_version(domain),
            "atoms": len(atoms),
            "sample": [{"id": a.get("id"), "do": a.get("do"), "dont": a.get("dont")}
                       for a in atoms[:3]],
        }
    return {"packs": out, "total": sum(v["atoms"] for v in out.values())}


@router.get("/atoms")
def atoms(domain: str = "", limit: int = 50,
          acct: str = Depends(studio_account)) -> Dict[str, Any]:
    if domain and domain not in knowledge_pack.domains():
        raise HTTPException(status_code=404, detail="unknown domain")
    pool = (knowledge_pack.load_atoms(domain) if domain
            else knowledge_pack.all_atoms())
    return {"total": len(pool), "atoms": pool[:max(1, min(int(limit), 500))]}


@router.post("/feedback")
def feedback(body: FeedbackIn, acct: str = Depends(studio_account)) -> Dict[str, Any]:
    fid = cie_store.add_feedback(
        verdict=body.verdict, message_id=body.message_id, session_id=body.session_id,
        note=body.note, mode=body.mode, pack_version=body.pack_version)
    return {"ok": True, "id": fid}


@router.post("/stop")
def stop(acct: str = Depends(studio_account)) -> Dict[str, Any]:
    return cie_store.set_stopped(True, f"stopped by {acct}")


@router.post("/resume")
def resume(acct: str = Depends(studio_account)) -> Dict[str, Any]:
    return cie_store.set_stopped(False, f"resumed by {acct}")


@router.post("/cycle")
def run_cycle(body: CycleIn, acct: str = Depends(studio_account)) -> Dict[str, Any]:
    if cie_store.is_stopped():
        raise HTTPException(status_code=409, detail="stop switch is set")
    result = cie_loop.run_cycle(dry_run=body.dry_run, cap=body.cap)
    result["account"] = acct
    return result


@router.get("/health")
def health() -> Dict[str, Any]:
    return {"ok": True, "stopped": cie_store.is_stopped(),
            "packs": knowledge_pack.pack_versions()}
