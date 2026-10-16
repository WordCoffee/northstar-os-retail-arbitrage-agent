"""Box library — external Boxes.py generator bridge (2026-10-16).

Boxes.py (https://github.com/florianfesti/boxes, GPL-3.0) is a local,
external tool: it generates parametric box/dieline SVGs on this machine. We
invoke it as a SEPARATE PROCESS and consume its OUTPUT — its code is never
embedded in Northstar and no network call is made. If the tool is not
installed the feature says so (503) rather than faking a dieline.

Safety: the generator name is checked against a curated allowlist; every
numeric parameter is bounded; the process runs with a timeout and its output
is size-capped. Nothing here touches Amazon or any provider.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from typing import Any, Dict, List, Optional

BOXES_LICENSE_NOTE = (
    "Box structures are generated locally by Boxes.py (GPL-3.0), an external "
    "tool run as a separate process; Northstar consumes the SVG output only."
)

# Curated generators (name → label + description). The full Boxes.py library
# has hundreds; these cover packaging-relevant structures first.
BOX_LIBRARY: List[Dict[str, Any]] = [
    {"id": "ClosedBox", "label": "Closed box", "note": "Fully closed box — the classic shipper"},
    {"id": "OpenBox", "label": "Open box", "note": "Top and front open — display/tray"},
    {"id": "UniversalBox", "label": "Universal box", "note": "Many lid and style options"},
    {"id": "TwoPiece", "label": "Two-piece box", "note": "Top slips over the bottom half"},
    {"id": "SlidingLidBox", "label": "Sliding-lid box", "note": "Rails for a sliding lid"},
    {"id": "SlidingDrawer", "label": "Sliding drawer", "note": "Drawer-in-sleeve construction"},
    {"id": "RoundedBox", "label": "Rounded box", "note": "Rounded vertical edges (living hinge)"},
    {"id": "RegularBox", "label": "Regular polygon box", "note": "Hexagon/octagon bases"},
    {"id": "Crate", "label": "Crate", "note": "Handles; stackable option"},
    {"id": "DisplayCase", "label": "Display case", "note": "Closed display case (acrylic-friendly)"},
    {"id": "NotesHolder", "label": "Notes holder", "note": "Holds a stack of paper/coasters"},
    {"id": "HeartBox", "label": "Heart box", "note": "Heart-shaped — gift packaging"},
]

_ALLOWED = {g["id"] for g in BOX_LIBRARY}

PARAM_SPEC = {
    "x": {"min": 20.0, "max": 600.0, "default": 100.0, "label": "Width (mm)"},
    "y": {"min": 20.0, "max": 600.0, "default": 80.0, "label": "Depth (mm)"},
    "h": {"min": 10.0, "max": 600.0, "default": 60.0, "label": "Height (mm)"},
    "thickness": {"min": 0.5, "max": 20.0, "default": 3.0, "label": "Material thickness (mm)"},
}


class BoxesUnavailable(RuntimeError):
    """The external Boxes.py tool is not installed — reported, never faked."""


def boxes_binary() -> Optional[str]:
    """Locate the boxes CLI: the console script first, then `python -m` form."""
    found = shutil.which("boxes")
    if found:
        return found
    # Fallback: the package is importable but the script is not on PATH.
    try:
        import boxes  # noqa: F401
        return f"{sys.executable} -m boxes"
    except Exception:  # noqa: BLE001
        return None


def _num(params: Dict[str, Any], key: str) -> float:
    spec = PARAM_SPEC[key]
    try:
        v = float(params.get(key, spec["default"]))
    except (TypeError, ValueError):
        raise ValueError(f"{key} must be a number")
    if not (spec["min"] <= v <= spec["max"]):
        raise ValueError(f"{key} must be between {spec['min']} and {spec['max']} mm")
    return v


def generate_box(generator: str, params: Dict[str, Any], *, timeout_s: int = 45,
                 max_bytes: int = 4 * 1024 * 1024) -> Dict[str, Any]:
    """Run Boxes.py for one generator and return its SVG.

    Raises ValueError for bad input and BoxesUnavailable when the tool is
    missing. The subprocess gets NO shell, an explicit argument list, a
    timeout, and its output is size-capped before it is returned.
    """
    if generator not in _ALLOWED:
        raise ValueError(f"generator '{generator}' is not in the box library")
    args = {
        "x": _num(params, "x"),
        "y": _num(params, "y"),
        "h": _num(params, "h"),
        "thickness": _num(params, "thickness"),
    }
    binary = boxes_binary()
    if not binary:
        raise BoxesUnavailable(
            "Boxes.py is not installed on this machine. Install it with "
            "`pip install https://codeload.github.com/florianfesti/boxes/tar.gz/master` "
            "and restart the API."
        )
    with tempfile.TemporaryDirectory(prefix="ns-boxes-") as tmp:
        out = os.path.join(tmp, "box.svg")
        cmd: List[str] = []
        if " " in binary:  # the "python -m boxes" fallback form
            cmd.extend(binary.split())
        else:
            cmd.append(binary)
        cmd.extend([generator, "--output", out])
        cmd.extend([f"--{k}={v}" for k, v in args.items()])
        try:
            proc = subprocess.run(  # noqa: S603 - fixed argv, no shell
                cmd, capture_output=True, timeout=timeout_s, check=False,
                cwd=tmp, env={**os.environ, "PYTHONIOENCODING": "utf-8"},
            )
        except subprocess.TimeoutExpired:
            raise ValueError(f"the generator timed out after {timeout_s}s")
        if proc.returncode != 0 or not os.path.exists(out):
            tail = (proc.stderr or proc.stdout or b"")[-400:].decode("utf-8", "replace")
            raise ValueError(f"the generator failed: {tail or 'no output'}")
        size = os.path.getsize(out)
        if size > max_bytes:
            raise ValueError(f"the generated SVG is too large ({size} bytes)")
        with open(out, "r", encoding="utf-8") as fh:
            svg = fh.read()
    if "<svg" not in svg[:2000]:
        raise ValueError("the generator returned no SVG")
    return {
        "generator": generator,
        "params": args,
        "svg": svg,
        "size_bytes": len(svg.encode("utf-8")),
        "license_note": BOXES_LICENSE_NOTE,
        "note": "Generated locally by Boxes.py as an external process; nothing was sent anywhere.",
    }
