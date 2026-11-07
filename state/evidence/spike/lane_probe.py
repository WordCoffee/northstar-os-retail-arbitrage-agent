"""Which lane can actually run a coding task right now? (read-only probe)

The plan's wording is `run_kernel(coding_agent=True)`; its coding path builds a
model callable against CodingWorkerAdapter.BASE (llama.cpp on 127.0.0.1:8080) and
needs a TysAssistant task store. `scripts/ty_task_runner.py` is the supervised
entry point for the same CodingAgent loop and takes any local model.

This records, with real calls, what each route reports on this box so the report
states a fact rather than a preference.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "Northstar_backend"))

out = {}


def probe_llama():
    import tys_assistant as ta

    adapter = ta.CodingWorkerAdapter()
    out["run_kernel_coding_worker"] = {
        "base": adapter.BASE, "model": adapter.MODEL,
        "available": adapter.available(),
        "launcher": adapter.LAUNCHER,
        "launcher_exists": (ROOT / adapter.LAUNCHER).is_file(),
    }
    from agent_kernel import local_model

    out["llama_cpp_health"] = local_model.health()
    try:
        from agent_kernel.local_model import make_local_model

        legacy = make_local_model()
        out["legacy_make_local_model"] = {"class": type(legacy).__name__,
                                          "model": getattr(legacy, "model", None),
                                          "base_url": getattr(legacy, "base_url", None)}
    except Exception as exc:  # noqa: BLE001 - a probe never raises
        out["legacy_make_local_model"] = f"{type(exc).__name__}: {exc}"


def probe_ollama():
    import urllib.request

    try:
        with urllib.request.urlopen("http://127.0.0.1:11434/api/tags", timeout=5) as r:
            tags = json.loads(r.read().decode("utf-8"))
        names = sorted(m.get("name") for m in tags.get("models") or [])
        out["ollama"] = {"up": True, "models": names,
                         "has_northstar_coder": any("northstaros" in (n or "")
                                                    for n in names)}
    except Exception as exc:  # noqa: BLE001
        out["ollama"] = {"up": False, "error": f"{type(exc).__name__}: {exc}"}


def main() -> int:
    probe_llama()
    probe_ollama()
    env = {k: v for k, v in os.environ.items()
           if k.startswith(("TYS_CODING", "OLLAMA", "NORTHSTAR_"))}
    out["env"] = env
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
