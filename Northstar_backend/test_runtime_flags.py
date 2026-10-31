"""Runtime flag audit: launcher flags, physical threads, Ollama env."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import runtime_flags as rf


def test_repo_launchers_carry_flash_attention_and_quantized_kv():
    audit = rf.audit_scripts()
    assert audit["all_ok"] is True
    for name, info in audit["scripts"].items():
        assert info["flash_attention"] is True, name
        assert info["quantized_kv"] is True, name


def test_a_launcher_without_the_flags_is_flagged(tmp_path):
    bad = tmp_path / "bad.ps1"
    bad.write_text("llama-server -m model.gguf", encoding="utf-8")
    audit = rf.audit_scripts([bad])
    assert audit["all_ok"] is False
    assert audit["scripts"][str(bad)]["flash_attention"] is False


def test_thread_plan_uses_physical_cores_not_logical():
    plan = rf.thread_plan()
    assert plan["num_thread"] == plan["physical_cores"]
    assert 1 <= plan["physical_cores"] <= plan["logical_cores"]
    assert isinstance(plan["measured"], bool)


def test_ollama_env_values():
    assert rf.ollama_env("q8_0") == {"OLLAMA_KV_CACHE_TYPE": "q8_0",
                                     "OLLAMA_FLASH_ATTENTION": "1"}
    assert rf.ollama_env("q4_0")["OLLAMA_KV_CACHE_TYPE"] == "q4_0"
    with pytest.raises(ValueError):
        rf.ollama_env("fp16")


def test_apply_env_is_process_scoped_and_recorded(tmp_path, monkeypatch):
    monkeypatch.setattr(rf, "CONFIG", tmp_path / "runtime_flags.json")
    rec = rf.apply_env("q4_0")
    assert rec["process_env"]["OLLAMA_KV_CACHE_TYPE"] == "q4_0"
    on_disk = json.loads((tmp_path / "runtime_flags.json").read_text(encoding="utf-8"))
    assert on_disk["kv_cache"] == "q4_0"
