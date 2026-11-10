"""tys_probes - the cheap local checks the T0/T1/T5 tiers are allowed to draw work from.

A generator that can invent a check can invent a pass. So the surfaces it is
allowed to notice are a fixed table of *real argv* written down here, in a policy
path (``tools/tys_*.py``, which no candidate may write). Each entry says which
band a failure belongs to, who can fix it, how often it is worth re-running, and
how long it may take. A probe that is not in this table cannot generate work.

Every argv is a plain argv list, never a shell string, and every one of them
passes ``scripts/continuous_loop.check_command`` - the same policy
``tys_runner.validate_contract`` applies - so a probe can never smuggle in a
refused token (``amazon``, ``chromeconnect``, a network client) or a second
command behind a ``;``. ``test_tys_generator.py`` asserts that property for the
whole table.

Three things are worth saying plainly:

* A **red** probe is information; a probe that could not be *started* is not.
  ``run()`` therefore exits 2 ("could not run") when nothing could be executed,
  rather than reporting a green table it never actually asked about.
* A probe answers with its **exit code only**. Parsing a probe's prose here would
  make this module a second judge of the thing it is measuring.
* The disk and RAM probes re-enter this module (``--resource disk|ram``) rather
  than using a ``python -c`` one-liner, because a ``;`` inside a ``-c`` string is
  a shell operator and the contract validator refuses it - correctly.

Usage::

    python tools/tys_probes.py --list
    python tools/tys_probes.py --probe tys-runner-tests --json
    python tools/tys_probes.py --resource disk
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence

ROOT = Path(os.environ.get("NORTHSTAR_TY_ROOT")
            or Path(__file__).resolve().parents[1]).resolve()

DEFAULT_TIMEOUT_S = 300
OUTPUT_TAIL_CHARS = 1200

#: Owner-stated operational floors (AGENTS.md): disk below 10 GB pauses GPU and
#: download work; nothing renders with fewer than 3 GB of free RAM.
DISK_FLOOR_GB = 10
RAM_FLOOR_GB = 3

_PY = "python"

#: ``severity: incident`` is what makes a failing probe preempt everything (T0).
#: A probe without it is an ordinary red check: T1 when it is a test suite, T5
#: when it is housekeeping.
_PROBE_TABLE: List[Dict[str, Any]] = [
    {
        "id": "tys-runner-tests",
        "tier": "T0",
        "severity": "incident",
        "argv": [_PY, "-m", "pytest", "-q", "Northstar_backend/test_tys_runner.py"],
        "why": ("the runner owns the lease, the cap and the queue; red here means the "
                "loop cannot reserve a cycle honestly"),
        "fixable_by": "worker",
        "cadence": "every cycle",
        "timeout_s": 600,
    },
    {
        "id": "tys-launcher-tests",
        "tier": "T1",
        "argv": [_PY, "-m", "pytest", "-q", "Northstar_backend/test_tys_launcher.py"],
        "why": "the launcher is the engine; a red cycle judgement is work nobody else will notice",
        "fixable_by": "worker",
        "cadence": "every cycle",
        "timeout_s": 900,
    },
    {
        "id": "tys-generator-tests",
        "tier": "T1",
        "argv": [_PY, "-m", "pytest", "-q", "Northstar_backend/test_tys_generator.py"],
        "why": "the generator decides what counts as work; its own tests must be green",
        "fixable_by": "worker",
        "cadence": "every cycle",
        "timeout_s": 600,
    },
    {
        "id": "backlog-tests",
        "tier": "T1",
        "argv": [_PY, "-m", "pytest", "-q", "Northstar_backend/test_autonomy_backlog.py"],
        "why": ("the improvement backlog is the only surface with authored write scopes; "
                "a red backlog test means its checks cannot be trusted"),
        "fixable_by": "worker",
        "cadence": "hourly",
        "timeout_s": 600,
    },
    {
        "id": "backlog-check",
        "tier": "T5",
        "argv": [_PY, "tools/improvement_backlog.py", "--check"],
        "why": "an untrustworthy backlog (missing scope, missing verification) is a defect",
        "fixable_by": "worker",
        "cadence": "hourly",
        "timeout_s": 120,
    },
    {
        "id": "regression-baseline",
        "tier": "T5",
        "argv": [_PY, "tools/check_regression.py", "--junit",
                 "state/probes/last_junit.xml", "--json"],
        "why": ("a test id that used to pass and no longer does is a shipped regression; "
                "exit 2 means no junit has been produced yet, which is not green"),
        "fixable_by": "worker",
        "cadence": "hourly",
        "timeout_s": 120,
    },
    {
        "id": "disk-free",
        "tier": "T5",
        "argv": [_PY, "tools/tys_probes.py", "--resource", "disk"],
        "why": f"below {DISK_FLOOR_GB} GB free disk pauses GPU and download work",
        "fixable_by": "owner",
        "cadence": "every cycle",
        "timeout_s": 60,
    },
    {
        "id": "ram-free",
        "tier": "T5",
        "argv": [_PY, "tools/tys_probes.py", "--resource", "ram"],
        "why": f"nothing renders with fewer than {RAM_FLOOR_GB} GB free RAM",
        "fixable_by": "owner",
        "cadence": "every cycle",
        "timeout_s": 60,
    },
]


# ------------------------------------------------------------------ the policy
def probe_table() -> List[Dict[str, Any]]:
    """Every probe that may generate work. Copies, so a caller cannot edit policy."""
    return [dict(spec, argv=[str(part) for part in spec["argv"]])
            for spec in _PROBE_TABLE]


def probe(probe_id: str) -> Optional[Dict[str, Any]]:
    for spec in probe_table():
        if spec["id"] == str(probe_id):
            return spec
    return None


# --------------------------------------------------------------------- running
def _tail(text: Any) -> str:
    raw = text if isinstance(text, str) else str(text or "")
    return raw[-OUTPUT_TAIL_CHARS:]


def run_probe(spec: Dict[str, Any], *, run: Callable[..., Any] = subprocess.run,
              cwd: Optional[Any] = None) -> Dict[str, Any]:
    """Run one probe. Exit code is the answer; the tail is the evidence.

    ``exit`` is 124 for a timeout and 127 for a probe that could not be started -
    both are red, and both say *which* kind of red so a caller never mistakes an
    unrunnable probe for a passing one.
    """
    probe_id = str((spec or {}).get("id") or "")
    argv = [str(part) for part in ((spec or {}).get("argv") or [])]
    started = time.time()
    if not argv:
        return {"id": probe_id, "exit": 2, "ok": False, "seconds": 0.0,
                "output_tail": "probe has no argv"}
    timeout = float((spec or {}).get("timeout_s") or DEFAULT_TIMEOUT_S)
    try:
        proc = run(argv, cwd=str(cwd or ROOT), timeout=timeout,
                   capture_output=True, text=True)
    except subprocess.TimeoutExpired:
        return {"id": probe_id, "exit": 124, "ok": False,
                "seconds": round(time.time() - started, 2),
                "output_tail": f"probe timed out after {timeout:g}s"}
    except OSError as exc:
        return {"id": probe_id, "exit": 127, "ok": False,
                "seconds": round(time.time() - started, 2),
                "output_tail": f"probe could not be started: {exc}"}
    raw = getattr(proc, "returncode", 1)
    code = int(raw) if isinstance(raw, int) else 1
    output = (getattr(proc, "stdout", "") or "") + (getattr(proc, "stderr", "") or "")
    return {"id": probe_id, "exit": code, "ok": code == 0,
            "seconds": round(time.time() - started, 2),
            "output_tail": _tail(output)}


def run(*, ids: Optional[Sequence[str]] = None,
        run: Callable[..., Any] = subprocess.run) -> Dict[str, Any]:
    """Run a selection of probes. exit 0 green, 1 red, 2 could-not-run."""
    wanted = [str(i) for i in (ids or []) if str(i).strip()]
    table = {spec["id"]: spec for spec in probe_table()}
    if not table:
        return {"ok": False, "exit": 2, "probes": [],
                "detail": "the probe table is empty; nothing could be run"}
    unknown = [i for i in wanted if i not in table]
    if unknown:
        return {"ok": False, "exit": 2, "probes": [],
                "detail": f"unknown probe(s): {', '.join(sorted(unknown))}"}
    selected = wanted or list(table)
    probes = [run_probe(table[i], run=run) for i in selected]
    red = [p for p in probes if not p["ok"]]
    unrunnable = [p for p in probes if p["exit"] in (126, 127)]
    if not probes:
        exit_code, detail = 2, "no probe ran"
    elif len(unrunnable) == len(probes):
        exit_code, detail = 2, "no probe could be started"
    elif red:
        exit_code, detail = 1, f"{len(red)} of {len(probes)} probe(s) red"
    else:
        exit_code, detail = 0, f"{len(probes)} probe(s) green"
    return {"ok": exit_code == 0, "exit": exit_code, "probes": probes, "detail": detail}


# ------------------------------------------------------------------- resources
def _free_ram_bytes() -> int:
    """Available physical memory, or -1 when this platform will not say.

    Measured, not assumed. -1 is *unknown*, and an unknown resource is reported
    red by ``resource()`` rather than green: a probe that cannot answer has not
    answered.
    """
    if sys.platform == "win32":
        try:
            import ctypes

            class _MemoryStatusEx(ctypes.Structure):
                _fields_ = [
                    ("dwLength", ctypes.c_ulong),
                    ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong),
                    ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong),
                    ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong),
                    ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
                ]

            status = _MemoryStatusEx()
            status.dwLength = ctypes.sizeof(_MemoryStatusEx)
            if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
                return -1
            return int(status.ullAvailPhys)
        except Exception:  # noqa: BLE001 - an unmeasurable resource is reported, not guessed
            return -1
    try:
        pages = int(os.sysconf("SC_AVPHYS_PAGES"))  # type: ignore[attr-defined]
        size = int(os.sysconf("SC_PAGE_SIZE"))      # type: ignore[attr-defined]
        return pages * size
    except (AttributeError, ValueError, OSError):
        return -1


def resource(name: str) -> Dict[str, Any]:
    """A local resource floor check: ``disk`` or ``ram``."""
    wanted = str(name or "").strip().lower()
    if wanted == "disk":
        try:
            free = shutil.disk_usage(str(ROOT)).free
        except OSError as exc:
            return {"ok": False, "detail": f"free disk could not be measured: {exc}"}
        floor = DISK_FLOOR_GB * 1024 ** 3
        return {"ok": free >= floor,
                "detail": f"{free / 1024 ** 3:.1f} GB free disk (floor {DISK_FLOOR_GB} GB)"}
    if wanted == "ram":
        free = _free_ram_bytes()
        if free < 0:
            return {"ok": False, "detail": "free RAM could not be measured on this platform"}
        floor = RAM_FLOOR_GB * 1024 ** 3
        return {"ok": free >= floor,
                "detail": f"{free / 1024 ** 3:.1f} GB free RAM (floor {RAM_FLOOR_GB} GB)"}
    return {"ok": False, "detail": f"unknown resource {name!r}; choose 'disk' or 'ram'"}


# ------------------------------------------------------------------------- cli
def _render(spec: Dict[str, Any]) -> str:
    return (f"{spec['id']:<22} {spec['tier']:<3} {spec['fixable_by']:<7} "
            f"{spec['cadence']:<12} {' '.join(spec['argv'])}")


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Cheap local probes for the T0/T1/T5 tiers (read-only).")
    parser.add_argument("--probe", action="append", default=[], metavar="ID",
                        help="probe id to run; repeatable, comma-separated accepted")
    parser.add_argument("--list", action="store_true", help="print the table and exit")
    parser.add_argument("--resource", default="", choices=("", "disk", "ram"),
                        help="run one resource floor check")
    parser.add_argument("--json", action="store_true")
    ns = parser.parse_args(argv)

    if ns.resource:
        got = resource(ns.resource)
        print(json.dumps(got, indent=2) if ns.json else got["detail"])
        return 0 if got["ok"] else 1
    if ns.list:
        for spec in probe_table():
            print(_render(spec))
        return 0
    ids = [part.strip() for chunk in ns.probe for part in str(chunk).split(",")
           if part.strip()]
    out = run(ids=ids or None)
    print(json.dumps(out, indent=2))
    return int(out["exit"])


if __name__ == "__main__":
    raise SystemExit(main())
