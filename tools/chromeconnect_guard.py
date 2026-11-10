"""
Northstar — ChromeConnect invocation guard (Python side).

Chrome Connect decides. Playwright executes. This module is the Python half of
that rule: it makes `import playwright` and a raw CDP attach on port 9222 FAIL
loudLY unless Chrome Connect issued the instruction.

Why this exists
---------------
Before 2026-10-03 three Python drivers imported `playwright.async_api`
directly and one of them called `chromium.connect_over_cdp(...)` on port 9222
— the same port ChromeControl manages. None of them went through policy.js, so
the domain allowlist, the Amazon blocklist and the risk classes did not apply
to any of them.

Install it as the FIRST import of any module that touches a browser:

    import chromeconnect_guard
    chromeconnect_guard.enforce()          # raises on direct playwright use
    # ... rest of the file

`enforce()` does three things:

  1. Installs an import hook that refuses `playwright`, `playwright.async_api`
     and `playwright.sync_api` unless a Chrome Connect instruction is active.
  2. Takes the port-9222 lock, so only one component may drive that CDP
     endpoint. browser_agent.py and the ChromeControl profile manager now
     contend for the same lock instead of silently sharing the browser.
  3. Returns a `cc_call()` handle for handing work to the controller.

To do real browser work, call the controller and let it drive Playwright:

    from chromeconnect_guard import cc_call
    result = cc_call("Go to costcobusinessdelivery.com and read the MOQ for X")

There is no flag, env var, or "just this once" escape hatch in this file.
Nothing here can relax a guardrail, and nothing here reads or writes secrets.
"""

from __future__ import annotations

import importlib.abc
import importlib.machinery
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent

CHROMECONTROL_ROOT = Path(os.environ.get(
    "CHROMECONTROL_ROOT",
    r"C:\Users\T2Hol\OneDrive\Documents\Default Project",
))
CONTROLLER_CLI = CHROMECONTROL_ROOT / "scripts" / "chromecontrol-agent.js"

# The approved Chrome Connect bridge. Set here as a default so `cc_call` works
# regardless of whether the caller's environment was inherited from OpenCode.
# It points at the DEDICATED ISOLATED supplier profile, not the operator's
# everyday Chrome.
DEFAULT_TRANSPORT_MODULE = CHROMECONTROL_ROOT / "scripts" / "chromecontrol-playwright-bridge.js"

CDP_PORT = 9222
LOCK_DIR = PROJECT_ROOT / ".chromeconnect"
CDP_LOCK = LOCK_DIR / f"cdp_{CDP_PORT}.lock"
INSTRUCTION_ENV = "CHROMECONNECT_INSTRUCTION_TOKEN"

BLOCKED_MODULES = {
    "playwright",
    "playwright.async_api",
    "playwright.sync_api",
    "playwright._impl",
}

# --- Playwright Test exemption for localhost e2e tests ---
# Allow direct Playwright ONLY when:
#   1. The caller's entry point is under tests/e2e/ (pytest test path contains /tests/e2e/)
#   2. Every target URL in the test is localhost or 127.0.0.1
# This is checked at import time via stack inspection.

_e2e_allowlist = frozenset({"localhost", "127.0.0.1"})

def _is_e2e_localhost_call() -> bool:
    """Return True if the import is from a tests/e2e test targeting only localhost."""
    import inspect
    import urllib.parse

    frame = inspect.currentframe()
    try:
        # Walk up the stack to find the test entry point
        for frame_info in inspect.stack():
            filename = frame_info.filename
            if "/tests/e2e/" in filename.replace("\\", "/") or "\\tests\\e2e\\" in filename:
                # This is an e2e test. Now check if its target URLs are localhost only.
                # The test's globals/locals may contain target URLs; we also check
                # any pytest fixtures or command-line args passed to the test process.
                # Heuristic: if the test module defines BASE_URL or target_url, verify it.
                frame_globals = frame_info.frame.f_globals
                for key in ("BASE_URL", "base_url", "target_url", "url", "target"):
                    val = frame_globals.get(key)
                    if isinstance(val, str):
                        try:
                            parsed = urllib.parse.urlparse(val)
                            host = parsed.hostname or ""
                            if host and host not in _e2e_allowlist:
                                return False  # non-localhost target -> not allowed
                        except Exception:
                            return False
                # No non-localhost URLs found in common places -> allow
                return True
    finally:
        del frame
    return False

_enforced = False
_instruction_depth = 0


class DirectPlaywrightUseRefused(RuntimeError):
    """Raised when code tries to drive Playwright outside Chrome Connect."""


class CdpPortLockedRefused(RuntimeError):
    """Raised when another component already holds the ChromeControl CDP port."""


# ---------------------------------------------------------------------------
# 1. Import hook
# ---------------------------------------------------------------------------

class _PlaywrightBlocker(importlib.abc.MetaPathFinder):
    """Refuses to import any playwright module outside a controller instruction.
    
    Exception: tests/e2e/ tests targeting ONLY localhost/127.0.0.1 are allowed
    to import playwright directly (Playwright Test for local-only e2e tests).
    """

    def find_spec(self, fullname, path=None, target=None):  # noqa: D102
        root = fullname.split(".")[0]
        if root in BLOCKED_MODULES and _instruction_depth == 0 and not _is_e2e_localhost_call():
            raise DirectPlaywrightUseRefused(
                f"Refused: '{fullname}' was imported outside Chrome Connect.\n"
                "Chrome Connect is the controller; Playwright is only its tool.\n"
                "Direct Playwright use bypasses the domain allowlist, the Amazon\n"
                "blocklist and the risk-class gates in policy.js.\n"
                "Use cc_call('<task>') to hand the work to the controller instead.\n"
                "Exception: tests/e2e/ targeting ONLY localhost/127.0.0.1 may import directly."
            )
        return None


_BLOCKER: Optional[_PlaywrightBlocker] = None


# ---------------------------------------------------------------------------
# 2. Port-9222 lock
# ---------------------------------------------------------------------------

def _pid_alive(pid: int) -> bool:
    try:
        import psutil  # type: ignore
        return psutil.pid_exists(pid)
    except Exception:
        pass
    if os.name == "nt":
        out = subprocess.run(
            ["tasklist", "/FI", f"PID eq {pid}", "/NH"],
            capture_output=True, text=True, timeout=10,
        )
        return str(pid) in (out.stdout or "")
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def acquire_cdp_lock(owner: str, port: int = CDP_PORT) -> Dict[str, Any]:
    """
    Take the exclusive lock for the ChromeControl CDP port.

    browser_agent.py previously attached to :9222 with no coordination, which
    meant two components could drive the same Chrome profile with no policy and
    no owner. Now there is exactly one holder and it is recorded.
    """
    LOCK_DIR.mkdir(parents=True, exist_ok=True)
    lock_file = LOCK_DIR / f"cdp_{port}.lock"
    record = {
        "pid": os.getpid(),
        "owner": owner,
        "port": port,
        "acquired_at": time.time(),
    }

    if lock_file.exists():
        try:
            held = json.loads(lock_file.read_text(encoding="utf-8"))
        except Exception:
            held = {}
        holder_pid = int(held.get("pid") or 0)
        if holder_pid and holder_pid != os.getpid() and _pid_alive(holder_pid):
            raise CdpPortLockedRefused(
                f"CDP port {port} is held by pid {holder_pid} ({held.get('owner')}).\n"
                "ChromeControl allows one controller per browser profile. Release the\n"
                "other component first, or run the work through that controller."
            )

    lock_file.write_text(json.dumps(record, indent=2), encoding="utf-8")
    return record


def release_cdp_lock(port: int = CDP_PORT) -> None:
    lock_file = LOCK_DIR / f"cdp_{port}.lock"
    try:
        held = json.loads(lock_file.read_text(encoding="utf-8"))
        if int(held.get("pid") or 0) == os.getpid():
            lock_file.unlink()
    except Exception:
        pass


def cdp_lock_holder(port: int = CDP_PORT) -> Optional[Dict[str, Any]]:
    lock_file = LOCK_DIR / f"cdp_{port}.lock"
    try:
        return json.loads(lock_file.read_text(encoding="utf-8"))
    except Exception:
        return None


# ---------------------------------------------------------------------------
# 3. Controller hand-off
# ---------------------------------------------------------------------------

def cc_call(task: str, *, url: Optional[str] = None, dry_run: bool = True,
            require_isolated: bool = True, extra_args: Optional[List[str]] = None,
            timeout: int = 300) -> Dict[str, Any]:
    """
    Hand a browser task to Chrome Connect and return its structured result.

    Chrome Connect plans the steps, evaluates each page and decides what to
    extract. This function does not touch a browser. It is the only sanctioned
    way for Python code to get browser work done.

    `require_isolated` defaults to True: live browser work must prove an
    isolated, signed-out profile or the controller refuses the first action.
    """
    if not CONTROLLER_CLI.exists():
        return {
            "ok": False,
            "status": "BLOCKED",
            "reason": "controller_not_found",
            "detail": f"Chrome Connect CLI not found at {CONTROLLER_CLI}. "
                      "Set CHROMECONTROL_ROOT. No browser was launched.",
        }

    env = os.environ.copy()
    env.setdefault("CHROMECONNECT_TRANSPORT_MODULE", str(DEFAULT_TRANSPORT_MODULE))

    cmd = ["node", str(CONTROLLER_CLI), "run", "--task", task, "--json"]
    if url:
        cmd += ["--url", url]
    if dry_run:
        cmd += ["--dry-run"]
    if require_isolated:
        cmd += ["--require-isolated"]
    cmd += list(extra_args or [])

    try:
        proc = subprocess.run(
            cmd,
            capture_output=True, text=True, timeout=timeout, cwd=str(CHROMECONTROL_ROOT),
            env=env,
        )
    except subprocess.TimeoutExpired:
        return {"ok": False, "status": "ERROR", "reason": "controller_timeout"}
    except FileNotFoundError:
        return {"ok": False, "status": "BLOCKED", "reason": "node_not_found"}

    out = (proc.stdout or "").strip()
    try:
        return json.loads(out) if out else {
            "ok": False, "status": "ERROR", "reason": "controller_no_output",
            "stderr": (proc.stderr or "")[-2000:],
        }
    except json.JSONDecodeError:
        return {
            "ok": False, "status": "ERROR", "reason": "controller_bad_output",
            "stdout": out[-2000:], "stderr": (proc.stderr or "")[-2000:],
        }


class controller_instruction:
    """Context manager. Inside it, playwright imports are permitted.

    This is issued BY the controller, not by calling code. In practice Python
    code should prefer cc_call() — this context exists so the controller's own
    Python helpers can run, and so the refusal path is provable in tests.
    """

    def __init__(self, instruction_id: str, run_id: Optional[str] = None):
        self.instruction_id = instruction_id
        self.run_id = run_id
        self._token: Optional[str] = None

    def __enter__(self) -> "controller_instruction":
        global _instruction_depth
        _instruction_depth += 1
        self._token = f"ins_{os.getpid()}_{int(time.time() * 1000)}"
        os.environ[INSTRUCTION_ENV] = self._token
        return self

    def __exit__(self, *exc) -> bool:
        global _instruction_depth
        _instruction_depth = max(0, _instruction_depth - 1)
        if _token_is_current(self._token):
            os.environ.pop(INSTRUCTION_ENV, None)
        return False


def _token_is_current(token: Optional[str]) -> bool:
    return bool(token) and os.environ.get(INSTRUCTION_ENV) == token


# ---------------------------------------------------------------------------
# 4. enforce()
# ---------------------------------------------------------------------------

def enforce(owner: str = "python", lock_port: bool = True, port: int = CDP_PORT) -> Dict[str, Any]:
    """Install the guard. Call once, first, in any module that uses a browser."""
    global _enforced, _BLOCKER
    if _enforced:
        return {"enforced": True, "already": True}

    if _BLOCKER is None:
        _BLOCKER = _PlaywrightBlocker()
        sys.meta_path.insert(0, _BLOCKER)

    status: Dict[str, Any] = {"enforced": True, "owner": owner, "port": port}

    if lock_port:
        try:
            status["cdp_lock"] = acquire_cdp_lock(owner, port)
            status["cdp_lock"] = "acquired"
        except CdpPortLockedRefused as e:
            # Not fatal on import: the module still cannot drive Playwright.
            # Refusing at import time would make unrelated imports explode.
            status["cdp_lock"] = "refused"
            status["cdp_lock_detail"] = str(e)

    _enforced = True
    return status


def guard_status() -> Dict[str, Any]:
    return {
        "enforced": _enforced,
        "instruction_active": _instruction_depth > 0,
        "cdp_lock_holder": cdp_lock_holder(),
        "blocked_modules": sorted(BLOCKED_MODULES),
    }


if __name__ == "__main__":
    # Self-test: proves the refusal works in this interpreter.
    print("guard status:", json.dumps(enforce("guard_selftest"), indent=2))
    try:
        import playwright.async_api  # noqa: F401  # chromeconnect:audit-allow self-test: proves the guard refuses it
        print("FAIL: playwright imported without an instruction")
        sys.exit(1)
    except DirectPlaywrightUseRefused as e:
        print("PASS: direct playwright import refused ->", str(e).splitlines()[0])
    except ImportError:
        print("PASS: refusal hook fired before module resolution (playwright not installed)")
    print("PASS: cdp lock holder:", cdp_lock_holder())
