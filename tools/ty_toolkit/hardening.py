"""Scraper hardening: evaluate the tool, apply it to a copy, never to the live build silently.

`bla-agents` (MIT, npm 3.3.2) is third-party code that rewrites build artifacts. This module
therefore:
  * evaluates it (version + licence) without installing or mutating anything;
  * applies it only when `allow_install=True`, and only to a copied directory;
  * returns the exact command, exit code and output tail, so "applied" is evidence.

    python -m tools.ty_toolkit.hardening --evaluate
    python -m tools.ty_toolkit.hardening --harden northstar-os-ui/dist --out state/toolkit/hardened-ui --allow-install
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence

TOOL = "bla-agents"
ALLOWED_LICENCES = ("MIT", "Apache-2.0", "BSD-3-Clause", "ISC")

Runner = Callable[[Sequence[str]], "tuple[int, str]"]


def _run(cmd: Sequence[str], timeout: int = 900) -> "tuple[int, str]":
    try:
        # On Windows npm/npx are .cmd shims; subprocess does not resolve them from a bare name.
        resolved = list(cmd)
        if resolved:
            resolved[0] = shutil.which(resolved[0]) or resolved[0]
        proc = subprocess.run(resolved, capture_output=True, text=True, timeout=timeout)
        return int(proc.returncode), (proc.stdout or "") + (proc.stderr or "")
    except Exception as exc:  # noqa: BLE001 - reported, never raised out of a tool
        return 1, f"{type(exc).__name__}: {exc}"


def evaluate(*, runner: Optional[Runner] = None) -> Dict[str, Any]:
    """Version + licence from the registry. Does not install and does not touch artifacts."""
    run = runner or _run
    code, version = run(["npm", "view", TOOL, "version"])
    if code != 0:
        return {"ok": False, "tool": TOOL, "reason": f"npm view failed: {version.strip()[:200]}"}
    lic_code, licence = run(["npm", "view", TOOL, "license"])
    licence_text = licence.strip() if lic_code == 0 else ""
    return {"ok": bool(version.strip()), "tool": TOOL, "version": version.strip(),
            "license": licence_text,
            "licence_ok": licence_text in ALLOWED_LICENCES,
            "install_allowed": licence_text in ALLOWED_LICENCES,
            "note": ("Third-party build-artifact hardening. Applying it is opt-in; the runtime and "
                     "the test suites read source, not dist, so neither is affected by a hardened copy.")}


def harden_artifacts(src: str | Path, out: str | Path, *, allow_install: bool = False,
                     runner: Optional[Runner] = None) -> Dict[str, Any]:
    """Copy ``src`` to ``out`` and run the hardening tool on the copy."""
    source = Path(src)
    if not source.is_dir():
        return {"ok": False, "tool": TOOL, "reason": f"{source} is not a directory"}
    if not allow_install:
        return {"ok": False, "tool": TOOL, "applied": False,
                "reason": ("refused: applying a third-party artifact rewriter requires "
                           "allow_install=True")}
    target = Path(out)
    if target.exists():
        return {"ok": False, "tool": TOOL, "applied": False,
                "reason": f"refused: {target} already exists; choose a new output directory"}
    shutil.copytree(source, target)
    command = ["npx", "--yes", TOOL, "harden", str(target)]
    run = runner or _run
    code, output = run(command)
    return {"ok": code == 0, "tool": TOOL, "applied": code == 0, "command": command,
            "exit_code": code, "output_tail": output.strip()[-1200:], "out": str(target)}


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Evaluate/apply scraper hardening")
    parser.add_argument("--evaluate", action="store_true")
    parser.add_argument("--harden", default="")
    parser.add_argument("--out", default="")
    parser.add_argument("--allow-install", action="store_true")
    ns = parser.parse_args(argv)
    if ns.evaluate or not ns.harden:
        print(json.dumps(evaluate(), indent=2))
        return 0
    out = ns.out or str(Path(tempfile.mkdtemp(prefix="hardened-ui-")) / "ui")
    result = harden_artifacts(ns.harden, out, allow_install=ns.allow_install)
    print(json.dumps(result, indent=2))
    return 0 if result["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
