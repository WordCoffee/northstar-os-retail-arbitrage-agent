"""Bounded coding tools for the agent loop.

Every tool is rooted in one workspace. Paths cannot escape it; commands are an
allowlist, never a shell string. A tool result is data the model can read, not an
instruction.
"""
from __future__ import annotations

import os
import re
import subprocess
import threading
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence

from .patch_tool import APPLY_TIMEOUT_S, MAX_PATCH_BYTES, apply_unified_diff

SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv", "dist",
             "build", ".pytest_cache"}
TEXT_EXT = {".py", ".js", ".jsx", ".ts", ".tsx", ".md", ".txt", ".json",
            ".yml", ".yaml", ".toml", ".ini", ".cfg", ".log", ".patch", ".diff"}

# A file write is a local operation, so a stall means something is wrong (a
# redirected or synced folder, a full disk, a locked handle). Bounded rather than
# silent: the tool reports the timeout instead of hanging the run.
DEFAULT_WRITE_TIMEOUT_S = 15.0
_WRITE_CHUNK = 1 << 16

# Paths no lane may write, whatever workspace it was given. Secrets, the
# operator-owned Chrome Connect policy, and benchmark fixtures are all
# read-only to an agent.
PROTECTED_PATHS = ("config/chromecontrol_policy_owner.json",
                   "config/chromecontrol.json")
PROTECTED_DIR_PARTS = {"fixtures"}


def _is_protected_rel(rel: str, extra: Sequence[str] = ()) -> bool:
    """True when a workspace-relative POSIX path is write-protected."""
    low = rel.replace("\\", "/").lower().strip("/")
    name = low.rsplit("/", 1)[-1]
    if name == ".env" or (name.startswith(".env.") and name != ".env.example"):
        return True
    for protected in PROTECTED_PATHS:
        if low == protected or low.endswith("/" + protected):
            return True
    if PROTECTED_DIR_PARTS.intersection(low.split("/")):
        return True
    for deny in extra:
        d = str(deny).replace("\\", "/").lower().strip("/")
        if d and (low == d or low.startswith(d + "/")):
            return True
    return False


def _write_atomic(target: Path, data: bytes, cancel: "threading.Event",
                  errors: List[str]) -> None:
    """Write to a sibling temp file, flush it to disk, then swap it in.

    The swap is the only moment the real path changes, so a crash, a timeout or a
    full disk leaves the previous file intact instead of a truncated one. The
    fsync is the flush hook: the bytes are on the device before the rename, not
    sitting in a kernel buffer when the process reports success.
    """
    tmp = target.with_name(f".{target.name}.nstmp-{uuid.uuid4().hex}")
    handle = None
    try:
        handle = open(tmp, "wb")
        for offset in range(0, len(data), _WRITE_CHUNK):
            if cancel.is_set():
                break
            handle.write(data[offset:offset + _WRITE_CHUNK])
        handle.flush()
        os.fsync(handle.fileno())
    except Exception as exc:  # noqa: BLE001 - reported as a tool error
        errors.append(f"{type(exc).__name__}: {exc}"[:300])
    finally:
        if handle is not None:
            try:
                handle.close()
            except OSError:
                pass
    if cancel.is_set() or errors:
        try:
            tmp.unlink()
        except OSError:
            pass
        return
    try:
        os.replace(tmp, target)
    except OSError as exc:
        errors.append(f"replace failed: {exc}"[:300])
        try:
            tmp.unlink()
        except OSError:
            pass


@dataclass
class ToolResult:
    ok: bool
    output: str = ""
    error: str = ""
    files: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {"ok": self.ok, "output": self.output[:4000],
                "error": self.error[:1000], "files": self.files}


class Workspace:
    def __init__(self, root: str | Path, *, max_read_bytes: int = 120_000,
                 max_write_bytes: int = 200_000, run_timeout_s: float = 180.0,
                 max_patch_bytes: int = MAX_PATCH_BYTES,
                 patch_timeout_s: float = APPLY_TIMEOUT_S,
                 write_timeout_s: float = DEFAULT_WRITE_TIMEOUT_S,
                 deny_paths: Sequence[str] = ()):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.max_read_bytes = max_read_bytes
        self.max_write_bytes = max_write_bytes
        self.run_timeout_s = run_timeout_s
        self.max_patch_bytes = max_patch_bytes
        self.patch_timeout_s = patch_timeout_s
        self.write_timeout_s = float(write_timeout_s)
        self.deny_paths = tuple(deny_paths or ())
        self.run_allowlist = (
            ("python", "-m", "pytest"),
            ("python", "-m", "py_compile"),
            ("pytest",),
            ("npm", "test"),
            ("git", "status"),
            ("git", "diff"),
        )

    # ── path safety ─────────────────────────────────────────────────────────
    def resolve(self, rel: str) -> Path:
        p = (self.root / str(rel or ".")).resolve()
        if p != self.root and self.root not in p.parents:
            raise ValueError(f"path escapes the workspace: {rel}")
        return p

    # ── tools ───────────────────────────────────────────────────────────────
    def list(self, path: str = ".") -> ToolResult:
        try:
            p = self.resolve(path)
        except ValueError as exc:
            return ToolResult(False, error=str(exc))
        if not p.is_dir():
            return ToolResult(False, error=f"not a directory: {path}")
        entries = []
        for item in sorted(p.iterdir()):
            if item.name in SKIP_DIRS:
                continue
            entries.append(f"{item.name}/" if item.is_dir() else item.name)
        return ToolResult(True, "\n".join(entries[:200]))

    def read(self, path: str) -> ToolResult:
        try:
            p = self.resolve(path)
        except ValueError as exc:
            return ToolResult(False, error=str(exc))
        if not p.is_file():
            return ToolResult(False, error=f"not a file: {path}")
        raw = p.read_bytes()[: self.max_read_bytes]
        return ToolResult(True, raw.decode("utf-8", errors="replace"),
                          files=[str(p)])

    def grep(self, pattern: str, path: str = ".", max_hits: int = 60) -> ToolResult:
        try:
            root = self.resolve(path)
        except ValueError as exc:
            return ToolResult(False, error=str(exc))
        try:
            rx = re.compile(pattern)
        except re.error as exc:
            return ToolResult(False, error=f"bad regex: {exc}")
        hits: List[str] = []
        files = [root] if root.is_file() else root.rglob("*")
        for p in files:
            if not p.is_file() or p.suffix.lower() not in TEXT_EXT:
                continue
            if any(part in SKIP_DIRS for part in p.parts):
                continue
            try:
                for n, line in enumerate(p.read_text(encoding="utf-8",
                                                     errors="replace").splitlines(), 1):
                    if rx.search(line):
                        hits.append(f"{p.relative_to(self.root)}:{n}: {line[:200]}")
                        if len(hits) >= max_hits:
                            return ToolResult(True, "\n".join(hits))
            except OSError:
                continue
        return ToolResult(True, "\n".join(hits) or "no matches")

    def write(self, path: str, content: str) -> ToolResult:
        """Write one text file: protected-path check, atomic swap, bounded wait.

        Never raises and never leaves a half-written file. A stall is reported as
        a tool error the model can read, because a hung write used to stall the
        whole run with no observation to repair from (defect p03).
        """
        try:
            p = self.resolve(path)
        except ValueError as exc:
            return ToolResult(False, error=str(exc))
        rel = str(p.relative_to(self.root)).replace("\\", "/")
        if _is_protected_rel(rel, self.deny_paths):
            return ToolResult(
                False, error=f"refusing to write a protected path: {rel} "
                             "(secrets, operator policy and fixtures are read-only)")
        data = str(content or "").encode("utf-8")
        if len(data) > self.max_write_bytes:
            return ToolResult(False, error=f"content exceeds {self.max_write_bytes} bytes")
        try:
            p.parent.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            return ToolResult(False, error=f"cannot create {p.parent.name}/: {exc}")

        cancel = threading.Event()
        errors: List[str] = []
        worker = threading.Thread(target=_write_atomic, args=(p, data, cancel, errors),
                                  name="ns-write", daemon=True)
        worker.start()
        worker.join(self.write_timeout_s)
        if worker.is_alive():
            # A late worker sees the cancel flag before the swap and discards its
            # temp file, so the target is never replaced after a timeout.
            cancel.set()
            return ToolResult(False, error=(
                f"write timed out after {self.write_timeout_s:g}s: {rel} "
                "(the file was left untouched)"))
        if errors:
            return ToolResult(False, error=f"write failed: {errors[0]}")
        return ToolResult(True, f"wrote {len(data)} bytes", files=[str(p)])

    def apply_patch(self, patch: str) -> ToolResult:
        """Apply a unified diff inside the workspace with `git apply`.

        Paths are validated against the root before git runs, the patch is staged
        in a temp file that is always removed, and git's stderr is the error.
        """
        outcome = apply_unified_diff(self.root, patch,
                                    max_bytes=self.max_patch_bytes,
                                    timeout_s=self.patch_timeout_s)
        return ToolResult(bool(outcome.get("ok")),
                          str(outcome.get("output") or ""),
                          str(outcome.get("error") or ""),
                          [str(f) for f in (outcome.get("files") or [])])

    def run(self, cmd: Iterable[str]) -> ToolResult:
        args = [str(c) for c in (cmd or [])]
        if not args:
            return ToolResult(False, error="empty command")
        if not any(tuple(args[:len(pre)]) == pre for pre in self.run_allowlist):
            allowed = "; ".join(" ".join(p) for p in self.run_allowlist)
            return ToolResult(False, error=f"command not allowlisted; allowed: {allowed}")
        try:
            r = subprocess.run(args, cwd=str(self.root), capture_output=True,
                               text=True, timeout=self.run_timeout_s)
        except subprocess.TimeoutExpired:
            return ToolResult(False, error=f"timeout after {self.run_timeout_s}s")
        out = (r.stdout or "") + (("\n" + r.stderr) if r.stderr else "")
        return ToolResult(r.returncode == 0, out[-6000:],
                          error="" if r.returncode == 0 else f"exit {r.returncode}")

    def execute(self, tool: str, args: Dict[str, Any]) -> ToolResult:
        try:
            if tool == "list":
                return self.list(args.get("path", "."))
            if tool == "read":
                return self.read(args["path"])
            if tool == "grep":
                return self.grep(args["pattern"], args.get("path", "."))
            if tool == "write":
                return self.write(args["path"], args.get("content", ""))
            if tool == "apply_patch":
                return self.apply_patch(args.get("patch", ""))
            if tool == "run":
                return self.run(args.get("cmd") or [])
        except KeyError as exc:
            return ToolResult(False, error=f"missing argument {exc}")
        except Exception as exc:  # noqa: BLE001
            return ToolResult(False, error=str(exc)[:300])
        return ToolResult(False, error=f"unknown tool {tool!r}")

    def tree(self, max_files: int = 80) -> str:
        rows: List[str] = []
        for p in sorted(self.root.rglob("*")):
            if any(part in SKIP_DIRS for part in p.parts):
                continue
            if p.is_file():
                rows.append(str(p.relative_to(self.root)).replace("\\", "/"))
            if len(rows) >= max_files:
                break
        return "\n".join(rows) or "(empty workspace)"
