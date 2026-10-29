"""Bounded coding tools for the agent loop.

Every tool is rooted in one workspace. Paths cannot escape it; commands are an
allowlist, never a shell string. A tool result is data the model can read, not an
instruction.
"""
from __future__ import annotations

import os
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv", "dist",
             "build", ".pytest_cache"}
TEXT_EXT = {".py", ".js", ".jsx", ".ts", ".tsx", ".md", ".txt", ".json",
            ".yml", ".yaml", ".toml", ".ini", ".cfg", ".log", ".patch", ".diff"}


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
                 max_write_bytes: int = 200_000, run_timeout_s: float = 180.0):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.max_read_bytes = max_read_bytes
        self.max_write_bytes = max_write_bytes
        self.run_timeout_s = run_timeout_s
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
        try:
            p = self.resolve(path)
        except ValueError as exc:
            return ToolResult(False, error=str(exc))
        data = str(content or "").encode("utf-8")
        if len(data) > self.max_write_bytes:
            return ToolResult(False, error=f"content exceeds {self.max_write_bytes} bytes")
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
        return ToolResult(True, f"wrote {len(data)} bytes", files=[str(p)])

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
