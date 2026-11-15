"""Offline tests for Ty's capability toolkit (capture, media, hardening, UI specs, proposals, mesh)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "Northstar_backend"))

from tools.ty_toolkit import capture, hardening, mesh_route, openverse, proposals, ui_benchmark  # noqa: E402


def test_capture_generates_compilable_python_and_typescript():
    doc = {"requests": [
        {"method": "GET", "url": "https://x.test/api/items?page=2"},
        {"method": "POST", "url": "https://x.test/api/items", "json": {"title": "a", "price": 1}},
    ]}
    out = capture.generate(doc)
    assert out["ok"] is True
    assert [e["name"] for e in out["endpoints"]] == ["get_api_items", "post_api_items"]
    assert out["endpoints"][0]["query"] == ["page"]
    assert out["endpoints"][1]["body"] == ["price", "title"]
    compile(out["code"], "<client>", "exec")  # the generated client is real Python

    ts = capture.generate(doc, language="typescript")
    assert ts["ok"] is True
    assert "export class" in ts["code"] and "get_api_items" in ts["code"]

    assert capture.generate({"requests": []})["ok"] is False
    assert capture.generate(doc, language="ruby")["ok"] is False


def test_capture_reads_a_har_and_dedupes():
    har = {"log": {"entries": [
        {"request": {"method": "GET", "url": "https://x.test/a", "queryString": [{"name": "q"}]}},
        {"request": {"method": "GET", "url": "https://x.test/a"}},
    ]}}
    out = capture.generate(har)
    assert out["ok"] is True and len(out["endpoints"]) == 1
    assert out["endpoints"][0]["query"] == ["q"]


def test_openverse_keeps_only_licensed_large_rows():
    def transport(url, params):
        assert "q" in params
        return 200, {"results": [
            {"id": "a", "license": "cc0", "width": 1200, "height": 900, "url": "https://x/a.jpg"},
            {"id": "b", "license": "by-nc", "width": 1200, "height": 900},
            {"id": "c", "license": "by", "width": 600, "height": 900},
        ]}

    out = openverse.search("mug", transport=transport)
    assert out["ok"] is True
    assert [row["id"] for row in out["rows"]] == ["a"]
    assert {row["id"] for row in out["refused"]} == {"b", "c"}

    def gateway(url, params):
        return 504, {"error": "HTTP 504"}

    refused = openverse.search("mug", transport=gateway)
    assert refused["ok"] is False and "504" in refused["reason"]


def test_hardening_refuses_without_allow_install(tmp_path):
    src = tmp_path / "dist"
    src.mkdir()
    (src / "index.html").write_text("<html></html>", encoding="utf-8")

    refused = hardening.harden_artifacts(src, tmp_path / "out")
    assert refused["ok"] is False and "allow_install" in refused["reason"]

    calls = {}

    def runner(command):
        calls["command"] = list(command)
        return 0, "hardened ok"

    applied = hardening.harden_artifacts(src, tmp_path / "out2", allow_install=True, runner=runner)
    assert applied["ok"] is True and applied["applied"] is True
    assert calls["command"][:3] == ["npx", "--yes", hardening.TOOL]
    assert (tmp_path / "out2" / "index.html").is_file()


def test_ui_spec_compare_flags_missing_landmarks():
    reference = ui_benchmark.spec_from_html(
        "<html><head><title>Shop</title></head><body><header>h</header><nav>n</nav>"
        "<main><h1>Hi</h1><button>Buy</button></main><footer>f</footer></body></html>"
    )
    target = ui_benchmark.spec_from_html("<html><body><main><h1>Hi</h1></main></body></html>")
    diff = ui_benchmark.compare(target, reference)
    assert diff["ok"] is True and diff["score"] < 100
    assert any(f["area"] == "landmarks" and "header" in f["detail"] for f in diff["findings"])
    assert any(f["area"] == "controls" and "button" in f["detail"] for f in diff["findings"])


def test_proposals_rank_gaps_and_flag_owner_gates():
    scores = {"services": [
        {"id": "a", "score": 70, "bar": 85, "gap": 9, "weakest": "seller", "meets_bar": False},
        {"id": "b", "score": 90, "bar": 85, "gap": 0, "weakest": "x", "meets_bar": True},
    ]}
    queue = {"jobs": [{"id": "j", "status": "blocked", "title": "blocked job", "blocked_on": "owner"}]}
    needs = "# Needs\n\n## OPEN-1. do a thing\n\n## RESOLVED. done\n"
    out = proposals.build(scores, queue, needs, limit=8)
    ids = [row["id"] for row in out["proposals"]]
    assert any(item.startswith("raise-a") for item in ids)
    assert any(item.startswith("unblock-j") for item in ids)
    assert not any("resolved" in item for item in ids)
    assert all("owner_gate" in row for row in out["proposals"])


def test_mesh_route_uses_local_only_when_a_probe_is_healthy():
    config = {
        "enabled": True,
        "endpoints": [{"id": "l", "model": "m", "tasks": ["classify"],
                       "base_url": "http://l"}],
        "cloud_fallback": {"model": "beam-free", "provider": "opencode-go"},
    }
    assert mesh_route.choose("classify", config)["route"] == "cloud"  # health unknown
    assert mesh_route.choose("classify", config, health=lambda e: False)["route"] == "cloud"
    local = mesh_route.choose("classify", config, health=lambda e: True)
    assert local["route"] == "local" and local["model"] == "m"
    assert mesh_route.choose("nope", config)["ok"] is False


def test_mesh_route_is_disabled_by_default():
    config = mesh_route.load()
    assert config["loaded"] is True
    assert config["enabled"] is False
    route = mesh_route.choose("classify", config)
    assert route["route"] == "cloud" and "disabled" in route["reason"]
