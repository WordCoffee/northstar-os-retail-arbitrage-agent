#!/usr/bin/env python3
"""Runtime flag audit: quantized KV cache, FlashAttention, physical threads.

The memory rule this exists for: an FP16 KV cache grows linearly with context
and competes with the weights for VRAM. q8_0 roughly halves it, q4_0 cuts it to
a third/quarter, and FlashAttention removes the quadratic attention buffer. The
llama.cpp launchers already pass `-fa on -ctk q8_0 -ctv q8_0`; this tool proves
that from the scripts instead of trusting a comment, and reports the Ollama
environment the CPU tier needs.

`--apply` only sets the current process environment and writes
`config/runtime_flags.json`; it does not silently edit a launcher. The operator
owns persistent environment changes.

    python tools/runtime_flags.py --check
    python tools/runtime_flags.py --apply --kv q8_0
"""
from __future__ import annotations

import argparse
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = [ROOT / "scripts" / "start-northstar-llm.ps1",
           ROOT / "scripts" / "start-northstar-moe.ps1",
           ROOT / "tools" / "northstar_lane_router.py"]
CONFIG = ROOT / "config" / "runtime_flags.json"
VALID_KV = {"f16", "q8_0", "q4_0", "q4_1", "q5_0", "q5_1"}


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def audit_scripts(paths: Optional[List[Path]] = None) -> Dict[str, Any]:
    """Check the launchers for the flags the memory model depends on."""
    out: Dict[str, Any] = {"scripts": {}, "all_ok": True}
    for path in (paths or SCRIPTS):
        text = _read(Path(path))
        flash = bool(re.search(r"(-fa\W+on|\"fa\"\s*,\s*\"on\"|OLLAMA_FLASH_ATTENTION\s*=\s*\"?1)",
                               text, re.IGNORECASE))
        kv_values = re.findall(r"(?:-ctk|-ctv|\$Kv\s*=|OLLAMA_KV_CACHE_TYPE\s*=\s*\"?)(\w+)", text)
        kv_values += re.findall(r"\"(q[458]_[01])\"", text)
        kv_ok = any(v.lower() in ("q8_0", "q4_0") for v in kv_values)
        ollama_kv = bool(re.search(r"OLLAMA_KV_CACHE_TYPE", text))
        ollama_flash = bool(re.search(r"OLLAMA_FLASH_ATTENTION", text))
        ok = flash and kv_ok
        try:
            label = str(Path(path).relative_to(ROOT))
        except ValueError:
            label = str(path)
        out["scripts"][label] = {
            "flash_attention": flash,
            "quantized_kv": kv_ok,
            "kv_values": sorted(set(kv_values)),
            "ollama_kv_export": ollama_kv,
            "ollama_flash_export": ollama_flash,
            "ok": ok,
        }
        out["all_ok"] = out["all_ok"] and ok
    return out


def thread_plan() -> Dict[str, Any]:
    """Physical cores, never logical SMT threads, for a llama.cpp CPU lane."""
    physical = None
    try:
        import psutil  # type: ignore
        physical = int(psutil.cpu_count(logical=False) or 0) or None
    except Exception:  # noqa: BLE001 - psutil is optional
        physical = None
    logical = os.cpu_count() or 1
    if physical is None:
        # Conservative: half the logical count is the usual SMT layout. The
        # report marks this as an estimate, not a measurement.
        physical = max(1, logical // 2)
        measured = False
    else:
        measured = True
    return {"physical_cores": int(physical), "logical_cores": int(logical),
            "num_thread": int(physical), "measured": measured,
            "note": "num_thread must equal physical cores; SMT threads thrash L2/L3"}


def ollama_env(kv: str = "q8_0") -> Dict[str, str]:
    value = str(kv or "q8_0").lower()
    if value not in VALID_KV:
        raise ValueError(f"unknown KV cache type {kv!r}; known: {sorted(VALID_KV)}")
    return {"OLLAMA_KV_CACHE_TYPE": value, "OLLAMA_FLASH_ATTENTION": "1"}


def apply_env(kv: str = "q8_0") -> Dict[str, Any]:
    env = ollama_env(kv)
    for key, value in env.items():
        os.environ[key] = value
    CONFIG.parent.mkdir(parents=True, exist_ok=True)
    record = {"applied_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
              "process_env": env, "kv_cache": kv,
              "note": "process-scoped; persistent changes belong to the operator"}
    CONFIG.write_text(json.dumps(record, indent=2), encoding="utf-8")
    return record


def report() -> Dict[str, Any]:
    audit = audit_scripts()
    return {
        "scripts": audit["scripts"],
        "scripts_all_ok": audit["all_ok"],
        "threads": thread_plan(),
        "ollama_env_now": {k: os.environ.get(k) for k in
                           ("OLLAMA_KV_CACHE_TYPE", "OLLAMA_FLASH_ATTENTION")},
        "expected_ollama_env": ollama_env("q8_0"),
    }


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true", help="audit only (default)")
    ap.add_argument("--apply", action="store_true",
                    help="set the current process env and write config/runtime_flags.json")
    ap.add_argument("--kv", default="q8_0", choices=sorted(VALID_KV))
    args = ap.parse_args(argv)
    if args.apply:
        print(json.dumps(apply_env(args.kv), indent=2))
        return 0
    out = report()
    print(json.dumps(out, indent=2))
    return 0 if out["scripts_all_ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["audit_scripts", "thread_plan", "ollama_env", "apply_env", "report"]
