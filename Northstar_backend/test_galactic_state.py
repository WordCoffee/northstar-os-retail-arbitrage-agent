"""Galactic deck telemetry endpoint: shape, real lanes, honest KV usage."""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import main


def test_galactic_state_has_topology_kv_lanes_and_hardware():
    out = asyncio.run(main.galactic_state())
    assert out["status"] == "ok"
    data = out["data"]
    nodes = {node["id"]: node for node in data["nodes"]}
    assert {"master", "ty", "bojo", "flux", "chrome", "memory", "ast"} <= set(nodes)
    assert nodes["master"]["role"] == "orchestrator"
    assert nodes["ty"]["context_tokens"] == 17408
    assert nodes["ty"]["kv_cache"].startswith("q8_0")
    assert data["links"]
    kv = {row["id"]: row for row in data["kv"]}
    assert kv["ty"]["context_total"] == 17408
    assert kv["bojo"]["context_total"] == 8192
    # Usage is either a real integer or null; never a fabricated percentage.
    assert kv["ty"]["context_used"] is None or isinstance(kv["ty"]["context_used"], int)
    assert "lanes" in data and "routes" in data["lanes"]
    assert "gpu" in data["hardware"]
    assert data["telemetry"] in ("live", "offline")
