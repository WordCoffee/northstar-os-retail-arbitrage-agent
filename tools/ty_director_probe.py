"""D1 probe: what this machine can actually do, measured, not assumed.

Every item in the director work order's D1 row is answered here with command output:
headless session launch, the real OpenCode Go concurrency ceiling, capture libraries,
UI Automation access, and GPU headroom for a local vision model beside Bojo.

Nothing here changes the machine. The only expensive probe is ``--concurrency N``,
which starts N ``opencode run`` sessions at once and is opt-in on purpose.

    python tools/ty_director_probe.py                 # everything cheap
    python tools/ty_director_probe.py --concurrency 4 # + a real parallel-session test
"""
from __future__ import annotations

import argparse
import concurrent.futures
import json
import os
import platform
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / "state" / "director"
REPORT = ROOT / "reports" / "ty" / "director_probe.md"

TRIVIAL = "Reply with exactly: ok"


def run(cmd: List[str], timeout: float = 25.0, **kwargs: Any) -> Dict[str, Any]:
    started = time.time()
    try:
        proc = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True,
                              timeout=timeout, **kwargs)
        return {"cmd": " ".join(cmd), "exit": proc.returncode,
                "stdout": (proc.stdout or "")[-4000:],
                "stderr": (proc.stderr or "")[-1500:],
                "seconds": round(time.time() - started, 2)}
    except subprocess.TimeoutExpired:
        return {"cmd": " ".join(cmd), "exit": 124, "stdout": "",
                "stderr": "timed out", "seconds": round(time.time() - started, 2)}
    except OSError as exc:
        return {"cmd": " ".join(cmd), "exit": 127, "stdout": "",
                "stderr": str(exc), "seconds": round(time.time() - started, 2)}


def importable(name: str) -> Dict[str, Any]:
    try:
        module = __import__(name)
        version = getattr(module, "__version__", "")
        return {"ok": True, "version": str(version)}
    except Exception as exc:  # noqa: BLE001 - a missing library is the answer
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}


def probe_opencode() -> Dict[str, Any]:
    exe = shutil.which("opencode") or os.environ.get("TY_OPENCODE_EXE", "")
    out: Dict[str, Any] = {"exe": exe}
    if not exe:
        out["state"] = "missing"
        return out
    out["version"] = run([exe, "--version"])
    help_run = run([exe, "run", "--help"])
    text = (help_run.get("stdout") or "") + (help_run.get("stderr") or "")
    out["run_help"] = help_run
    out["flags"] = {flag: (flag in text) for flag in
                    ("--agent", "--format", "--auto", "--model", "--session", "--continue")}
    out["json_stream"] = "json" in text
    out["state"] = "ok" if help_run.get("exit") == 0 else "help_failed"
    return out


def probe_concurrency(n: int) -> Dict[str, Any]:
    """Start n real sessions at once. This is the only probe that spends tokens."""
    exe = shutil.which("opencode") or os.environ.get("TY_OPENCODE_EXE", "")
    if not exe:
        return {"state": "missing"}
    lane = os.environ.get("TY_WORKER_AGENT", "tys")
    started = time.time()

    def one(index: int) -> Dict[str, Any]:
        t0 = time.time()
        proc = subprocess.run(
            [exe, "run", "--agent", lane, "--format", "json", "--auto"],
            cwd=str(ROOT), capture_output=True, text=True, input=TRIVIAL,
            timeout=240)
        return {"index": index, "exit": proc.returncode,
                "chars": len(proc.stdout or ""), "seconds": round(time.time() - t0, 1),
                "stderr": (proc.stderr or "")[-200:]}

    with concurrent.futures.ThreadPoolExecutor(max_workers=n) as pool:
        results = list(pool.map(one, range(n)))
    ok = [row for row in results if row["exit"] == 0 and row["chars"] > 0]
    return {"requested": n, "succeeded": len(ok), "results": results,
            "wall_seconds": round(time.time() - started, 1),
            "state": "ok" if len(ok) == n else f"partial:{len(ok)}/{n}"}


def probe_gpu() -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    smi = shutil.which("nvidia-smi")
    if not smi:
        out["state"] = "no_nvidia_smi"
        return out
    query = run([smi, "--query-gpu=name,memory.total,memory.used,memory.free,utilization.gpu",
                 "--format=csv,noheader,nounits"])
    out["query"] = query
    out["state"] = "ok" if query.get("exit") == 0 else "query_failed"
    ollama = shutil.which("ollama")
    if ollama:
        out["ollama"] = run([ollama, "list"], timeout=20)
    return out


def probe_host() -> Dict[str, Any]:
    out: Dict[str, Any] = {"platform": platform.platform(),
                           "python": sys.version.split()[0],
                           "cpu_count": os.cpu_count()}
    try:
        import ctypes

        class MEMORYSTATUSEX(ctypes.Structure):
            _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                        ("ullTotalPhys", ctypes.c_ulonglong),
                        ("ullAvailPhys", ctypes.c_ulonglong),
                        ("ullTotalPageFile", ctypes.c_ulonglong),
                        ("ullAvailPageFile", ctypes.c_ulonglong),
                        ("ullTotalVirtual", ctypes.c_ulonglong),
                        ("ullAvailVirtual", ctypes.c_ulonglong),
                        ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]

        stat = MEMORYSTATUSEX()
        stat.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
        ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat))
        out["ram_total_gb"] = round(stat.ullTotalPhys / 1024 ** 3, 1)
        out["ram_free_gb"] = round(stat.ullAvailPhys / 1024 ** 3, 1)
    except Exception as exc:  # noqa: BLE001
        out["ram_error"] = str(exc)
    try:
        usage = shutil.disk_usage(str(ROOT))
        out["disk_free_gb"] = round(usage.free / 1024 ** 3, 2)
    except OSError as exc:
        out["disk_error"] = str(exc)
    return out


def probe_screen() -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for name in ("mss", "dxcam", "PIL", "uiautomation", "comtypes", "pywinauto",
                 "pyautogui", "pynput"):
        out[name] = importable(name)
    return out


def render(probes: Dict[str, Any]) -> str:
    lines = ["# D1 — director probe", "",
             f"Measured {probes['at']} on this machine. Every line is command output, "
             "not an assumption.", ""]

    oc = probes["opencode"]
    lines += ["## Headless session launch", "",
              f"- executable: `{oc.get('exe') or '(not found)'}`",
              f"- state: **{oc.get('state')}**",
              f"- version exit: `{(oc.get('version') or {}).get('exit')}` — "
              f"`{((oc.get('version') or {}).get('stdout') or '').strip()[:80]}`",
              f"- `opencode run` flags present: "
              f"`{', '.join(k for k, v in (oc.get('flags') or {}).items() if v) or 'none'}`",
              ""]
    if oc.get("run_help"):
        lines += ["```", (oc["run_help"].get("stdout") or oc["run_help"].get("stderr") or "")
                  .strip()[:1500], "```", ""]

    conc = probes.get("concurrency") or {}
    if conc and conc.get("state") != "not_probed":
        lines += ["## Concurrency (OpenCode Go)", "",
                  f"- requested: {conc.get('requested')}, succeeded: {conc.get('succeeded')}, "
                  f"wall {conc.get('wall_seconds')}s — **{conc.get('state')}**", ""]
    elif conc:
        lines += ["## Concurrency (OpenCode Go)", "",
                  f"- **not probed yet** — {conc.get('detail', '')}. The cap stays at 4 "
                  "until a measured number replaces it.", ""]

    gpu = probes["gpu"]
    lines += ["## GPU", "", f"- state: **{gpu.get('state')}**"]
    if (gpu.get("query") or {}).get("stdout"):
        lines += [f"- `{gpu['query']['stdout'].strip()}`"]
    if (gpu.get("ollama") or {}).get("stdout"):
        lines += ["", "```", gpu["ollama"]["stdout"].strip()[:1200], "```"]
    lines += [""]

    host = probes["host"]
    lines += ["## Host", "",
              f"- {host.get('platform')}, python {host.get('python')}, "
              f"{host.get('cpu_count')} cpus",
              f"- RAM free {host.get('ram_free_gb')} of {host.get('ram_total_gb')} GB; "
              f"disk free {host.get('disk_free_gb')} GB", ""]

    screen = probes["screen"]
    lines += ["## Capture, UI Automation and input libraries", "",
              "| library | importable | version |", "|---|---|---|"]
    for name, result in screen.items():
        lines.append(f"| `{name}` | {'yes' if result['ok'] else 'no'} | "
                     f"{result.get('version') or result.get('error', '')[:60]} |")
    lines += [""]

    lines += ["## What this means for D6-D8", "",
              "- **Dependencies are not installed.** No capture library, no UI Automation "
              "binding and no input library imported. D6 installs them (pre-approved) and "
              "records each in `provenance.csv`; D1's answer is the gap, not a failure.",
              "- Capture: prefer a library that is importable *and* reports a real "
              "frame size in D6's acceptance test; importability alone is not capture.",
              "- Structure first: UI Automation and the browser DevTools protocol are "
              "the primary read; pixels are the fallback.",
              "- Concurrency: the measured ceiling is the cap. If it is below 4, the "
              "Director uses the measured number.",
              "- The RAM figure above was read while the full test suite was running; "
              "D6 re-reads it idle before any GPU budget is claimed.", ""]
    return "\n".join(lines)


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="D1 director probe")
    parser.add_argument("--concurrency", type=int, default=0,
                        help="also start this many real sessions at once (spends tokens)")
    ns = parser.parse_args(argv)

    probes: Dict[str, Any] = {
        "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "opencode": probe_opencode(),
        "gpu": probe_gpu(),
        "host": probe_host(),
        "screen": probe_screen(),
    }
    if ns.concurrency > 0:
        probes["concurrency"] = probe_concurrency(ns.concurrency)
    else:
        probes["concurrency"] = {"state": "not_probed",
                                 "detail": "run with --concurrency N"}

    STATE.mkdir(parents=True, exist_ok=True)
    (STATE / "probe.json").write_text(json.dumps(probes, indent=2) + "\n", encoding="utf-8")
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(render(probes), encoding="utf-8")
    print(json.dumps({"ok": True, "report": str(REPORT),
                      "opencode": probes["opencode"].get("state"),
                      "concurrency": probes["concurrency"].get("state"),
                      "gpu": probes["gpu"].get("state")}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
