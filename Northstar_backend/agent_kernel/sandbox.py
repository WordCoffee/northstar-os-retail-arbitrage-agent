"""Sandboxed command execution with credential scrubbing.

The gateway owns the real secrets. A worker or a self-patching loop gets a
scrubbed environment and, when a container runtime is present, an isolated
filesystem/network. The process fallback is useful for local tests but is NOT a
security boundary, and the audit says so.

Runtimes, in preference order:
    docker      docker run --rm --network=none -v <cwd>:/work -w /work <image>
    bubblewrap  bwrap --unshare-all --die-with-parent --ro-bind / / --bind <cwd> /work
    process     subprocess with a scrubbed env (no isolation; production_safe=False)

No runtime is installed by this module. `require_isolated()` is the gate a
self-patching caller must pass before writing a live tree.
"""
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence

#: Names that look like credentials are removed even if the caller forgot one.
_SECRET_HINTS = ("KEY", "TOKEN", "SECRET", "PASSWORD", "PASSWD", "PASS",
                 "CREDENTIAL", "AUTH", "COOKIE", "SESSION", "PRIVATE")
#: The minimum a subprocess needs to start on Windows/POSIX.
_SAFE_ENV = {"PATH", "PYTHONPATH", "PYTHONHOME", "SYSTEMROOT", "SYSTEMDRIVE",
             "WINDIR", "COMSPEC", "PATHEXT", "TEMP", "TMP", "TMPDIR", "HOME",
             "USERPROFILE", "HOMEDRIVE", "HOMEPATH", "LANG", "LC_ALL",
             "LC_CTYPE", "NUMBER_OF_PROCESSORS", "PROCESSOR_ARCHITECTURE"}

DEFAULT_IMAGE = os.environ.get("NORTHSTAR_SANDBOX_IMAGE", "python:3.12-slim")


class SandboxUnavailable(RuntimeError):
    """No isolation runtime is installed and the caller requires one."""


def _looks_secret(name: str) -> bool:
    upper = str(name or "").upper()
    return any(h in upper for h in _SECRET_HINTS)


def scrub_env(env: Optional[Dict[str, str]] = None,
              *, allow: Optional[Iterable[str]] = None) -> Dict[str, str]:
    """Return a child environment with credential-shaped names removed.

    An explicit `env` is merged over the allowlisted parent values, but every
    key is still checked: a caller cannot smuggle `OPENAI_API_KEY` through.
    """
    parent = dict(os.environ if env is None else env)
    extra = set(allow or ())
    out: Dict[str, str] = {}
    for key, value in parent.items():
        if _looks_secret(key) and key not in extra:
            continue
        if key in _SAFE_ENV or key in extra:
            out[key] = str(value)
    return out


def detect_runtimes() -> Dict[str, bool]:
    return {
        "docker": bool(shutil.which("docker")),
        "bubblewrap": bool(shutil.which("bwrap")),
        "process": True,
    }


def choose_runtime(prefer: str = "auto") -> str:
    found = detect_runtimes()
    if prefer not in ("auto", "docker", "bubblewrap", "process"):
        raise ValueError(f"unknown sandbox runtime {prefer!r}")
    if prefer != "auto":
        if not found.get(prefer):
            raise SandboxUnavailable(f"{prefer} is not installed")
        return prefer
    if found["docker"]:
        return "docker"
    if found["bubblewrap"]:
        return "bubblewrap"
    return "process"


def require_isolated(prefer: str = "auto") -> str:
    runtime = choose_runtime(prefer)
    if runtime == "process":
        raise SandboxUnavailable(
            "no container runtime (docker/bubblewrap) is installed; refusing an "
            "isolated self-patch. Install one or run the diagnosis-only path.")
    return runtime


def _command(runtime: str, cmd: Sequence[str], cwd: Path) -> List[str]:
    if runtime == "docker":
        return ["docker", "run", "--rm", "--network=none",
                "-v", f"{cwd}:/work", "-w", "/work", DEFAULT_IMAGE, *cmd]
    if runtime == "bubblewrap":
        return ["bwrap", "--unshare-all", "--die-with-parent", "--ro-bind", "/", "/",
                "--bind", str(cwd), "/work", "--chdir", "/work", *cmd]
    return list(cmd)


def run(cmd: Sequence[str], *, cwd: Path | str, timeout: float = 60.0,
        runtime: str = "auto", env: Optional[Dict[str, str]] = None,
        allow_env: Optional[Iterable[str]] = None) -> Dict[str, Any]:
    """Run one command in the chosen runtime; never uses a shell."""
    args = [str(c) for c in (cmd or [])]
    if not args:
        raise ValueError("empty sandbox command")
    workdir = Path(cwd).resolve()
    if not workdir.is_dir():
        raise ValueError(f"sandbox cwd is not a directory: {workdir}")
    chosen = choose_runtime(runtime)
    child_env = scrub_env(env, allow=allow_env)
    argv = _command(chosen, args, workdir)
    try:
        proc = subprocess.run(argv, cwd=str(workdir), capture_output=True,
                              text=True, timeout=float(timeout), env=child_env,
                              shell=False)
    except subprocess.TimeoutExpired:
        return {"ok": False, "runtime": chosen, "isolation": chosen,
                "timeout": True, "output": "", "error": f"timeout after {timeout}s"}
    except OSError as exc:
        return {"ok": False, "runtime": chosen, "isolation": chosen,
                "timeout": False, "output": "", "error": str(exc)[:400]}
    output = (proc.stdout or "") + (("\n" + proc.stderr) if proc.stderr else "")
    return {"ok": proc.returncode == 0, "runtime": chosen, "isolation": chosen,
            "timeout": False, "exit": proc.returncode,
            "output": output[-6000:], "error": "" if proc.returncode == 0
            else f"exit {proc.returncode}"}


def audit() -> Dict[str, Any]:
    found = detect_runtimes()
    try:
        chosen = choose_runtime()
    except SandboxUnavailable:
        chosen = "none"
    visible = sorted(k for k in os.environ if _looks_secret(k))
    return {
        "runtimes": found,
        "chosen": chosen,
        "production_safe": chosen in ("docker", "bubblewrap"),
        "secret_shaped_env_names": visible,
        "secret_count": len(visible),
        "note": ("The process fallback scrubs the environment but does not "
                 "isolate the filesystem or network; it is not a security boundary."),
    }


def main(argv: Optional[List[str]] = None) -> int:
    import argparse
    import json
    ap = argparse.ArgumentParser(description="Sandbox/credential audit.")
    ap.add_argument("--audit", action="store_true")
    args = ap.parse_args(argv)
    print(json.dumps(audit(), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["SandboxUnavailable", "scrub_env", "detect_runtimes",
           "choose_runtime", "require_isolated", "run", "audit"]
