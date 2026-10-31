"""HITL API: repo-root scoped pending/approve/deny over the local queue."""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import pytest
from fastapi import HTTPException

sys.path.insert(0, str(Path(__file__).resolve().parent))

import main
from agent_kernel import hitl


def test_hitl_pending_approve_deny(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "_hitl_root", lambda: tmp_path)
    first = hitl.request("apply_self_patch", root=tmp_path, requested_by="worker")
    second = hitl.request("publish_listing", root=tmp_path, requested_by="worker")

    pending = asyncio.run(main.hitl_pending())
    assert pending["status"] == "ok"
    ids = {row["id"] for row in pending["data"]["requests"]}
    assert {first["id"], second["id"]} <= ids

    approved = asyncio.run(main.hitl_approve(
        first["id"], main.HitlDecision(operator="operator", note="looks right")))
    assert approved["data"]["request"]["status"] == "approved"
    assert approved["data"]["request"]["operator"] == "operator"

    denied = asyncio.run(main.hitl_deny(
        second["id"], main.HitlDecision(operator="operator", note="not now")))
    assert denied["data"]["request"]["status"] == "denied"


def test_hitl_unknown_id_is_409(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "_hitl_root", lambda: tmp_path)
    with pytest.raises(HTTPException) as exc:
        asyncio.run(main.hitl_approve(
            "hitl_20260101T000000_deadbeef", main.HitlDecision()))
    assert exc.value.status_code == 409
