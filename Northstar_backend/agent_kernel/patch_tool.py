"""Apply a unified diff inside one workspace, using `git apply`.

The workspace root is the trust boundary. A diff is *data* from a model, never a
command: every path it names is resolved and checked against the root before git
is invoked, so `a/../../etc/passwd` and `b/C:/Windows/x` never reach the writer.
The only thing that touches the tree is `git apply`, run with `--whitespace=nowarn`
and no `--unsafe-paths`; if git refuses, its stderr is returned verbatim and no
Python fallback silently writes the file instead.

The workspace must be its own git repo (a `.git` entry at its root). `git apply`
resolves patch paths from the repo root, so a workspace nested inside a larger
repo is refused rather than applied to the wrong tree.

There is no pure-python applier. If git is missing the tool fails and says so.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Dict, List, Optional, Tuple

MAX_PATCH_BYTES = 200_000
APPLY_TIMEOUT_S = 60.0

_DIFF_GIT_RE = re.compile(r"^diff --git (\S+) (\S+)\s*$")
_RENAME_RE = re.compile(r"^(?:rename|copy) (?:from|to) (.+?)\s*$")
_WIN_ABS_RE = re.compile(r"^[A-Za-z]:")
DEV_NULL = "/dev/null"


class PatchError(ValueError):
    """The patch was rejected before git was invoked."""


# ── paths ───────────────────────────────────────────────────────────────────
def _clean_path(raw: str) -> Optional[str]:
    """Normalise one path token from a diff header to a workspace-relative path."""
    p = (raw or "").strip()
    if not p:
        return None
    if len(p) >= 2 and p.startswith('"') and p.endswith('"'):
        p = p[1:-1]  # git C-quotes unusual names
    if p == DEV_NULL:
        return None
    # `git diff` prefixes the two sides with a/ and b/; strip exactly one level,
    # the way git's default -p1 does, so "a/a/x" stays "a/x".
    if p[:2] in ("a/", "b/"):
        p = p[2:]
    return p


def patch_paths(patch: str) -> List[str]:
    """Every path a patch claims to touch, in order, without duplicates."""
    lines = str(patch or "").splitlines()
    out: List[str] = []
    in_hunk = False

    def add(raw: str) -> None:
        p = _clean_path(raw)
        if p and p not in out:
            out.append(p)

    for i, line in enumerate(lines):
        if line.startswith("diff --git "):
            in_hunk = False
            m = _DIFF_GIT_RE.match(line)
            if m:
                add(m.group(1))
                add(m.group(2))
            continue
        if line.startswith("@@"):
            in_hunk = True
            continue
        nxt = lines[i + 1] if i + 1 < len(lines) else ""
        # A file header pair, also valid after a hunk (bare multi-file diff).
        # A hunk body line can never be followed by a `+++ ` line at the same
        # depth in a well-formed diff, so this cannot swallow file content.
        if line.startswith("--- ") and nxt.startswith("+++ "):
            in_hunk = False
            add(line[4:])
            add(nxt[4:])
            continue
        if in_hunk:
            continue  # body text is content, never a path
        if line.startswith("+++ "):
            add(line[4:])
            continue
        m = _RENAME_RE.match(line)
        if m:
            add(m.group(1))
    return out


def validate_path(rel: str, root: Path) -> Path:
    """Resolve `rel` under `root`, refusing anything that leaves it."""
    raw = str(rel or "").replace("\\", "/").strip()
    if not raw:
        raise PatchError("empty path in patch")
    if "\x00" in raw:
        raise PatchError(f"NUL byte in patch path: {rel!r}")
    if raw.startswith("/") or _WIN_ABS_RE.match(raw):
        raise PatchError(f"absolute path in patch: {rel}")
    parts = [p for p in raw.split("/") if p not in ("", ".")]
    if not parts:
        raise PatchError(f"unusable path in patch: {rel}")
    if any(p == ".." for p in parts):
        raise PatchError(f"path escapes the workspace: {rel}")
    resolved = (root / raw).resolve()
    if resolved != root and root not in resolved.parents:
        raise PatchError(f"path escapes the workspace: {rel}")
    return resolved


def validate_patch(patch: str, root: Path) -> List[Tuple[str, Path]]:
    """Return (shown path, absolute path) for every path, or raise PatchError."""
    root = Path(root).resolve()
    paths = patch_paths(patch)
    if not paths:
        raise PatchError("patch names no files; expected a unified diff "
                         "(--- / +++ / @@ or diff --git)")
    return [(p, validate_path(p, root)) for p in paths]


# ── git ─────────────────────────────────────────────────────────────────────
def find_git() -> Optional[str]:
    return shutil.which("git")


def worktree_root(root: Path) -> Optional[Path]:
    """The nearest directory at or above `root` that holds a `.git` entry."""
    root = Path(root).resolve()
    for d in (root, *root.parents):
        if (d / ".git").exists():
            return d
    return None


def _env() -> Dict[str, str]:
    env = os.environ.copy()
    env["GIT_TERMINAL_PROMPT"] = "0"
    env["GIT_OPTIONAL_LOCKS"] = "0"
    env["GIT_PAGER"] = "cat"
    return env


def _fail(reason: str) -> Dict[str, object]:
    return {"ok": False, "output": "", "error": reason, "files": []}


def apply_unified_diff(root: str | Path, patch: str, *,
                       max_bytes: int = MAX_PATCH_BYTES,
                       timeout_s: float = APPLY_TIMEOUT_S) -> Dict[str, object]:
    """Apply `patch` under `root` with `git apply`. Never writes outside `root`."""
    root = Path(root).resolve()
    text = str(patch or "")
    if not text.strip():
        return _fail("empty patch; nothing to apply")

    data = text.encode("utf-8")
    if len(data) > max_bytes:
        return _fail(f"patch is {len(data)} bytes, over the {max_bytes}-byte cap")

    try:
        targets = validate_patch(text, root)
    except PatchError as exc:
        return _fail(str(exc))

    git = find_git()
    if not git:
        return _fail("git is not installed on PATH; apply_patch is git-only "
                     "(there is no pure-python fallback)")
    parent = worktree_root(root)
    if parent is None:
        return _fail(f"not a git workspace: no .git in {root}; run `git init` in "
                     "the workspace first (apply_patch is git-only, there is no "
                     "pure-python fallback)")
    if parent != root:
        return _fail(f"not a git workspace root: {root} sits inside the repo at "
                     f"{parent}, whose root paths `git apply` resolves against; "
                     "apply_patch needs a workspace that is its own repo (git "
                     "init in the workspace)")
    if not root.is_dir():
        return _fail(f"workspace is not a directory: {root}")

    if not text.endswith("\n"):
        text += "\n"  # a diff without its final newline is a corrupt patch

    cmd_tail = ["apply", "--whitespace=nowarn"]

    def _attempt(payload: str):
        """Stage `payload` in the temp file and run git apply once."""
        tmp.write_bytes(payload.encode("utf-8"))
        # core.autocrlf is pinned so the applied bytes match the patch bytes
        # instead of whatever the machine's global git config prefers.
        return subprocess.run([git, "-c", "core.autocrlf=false",
                               "-c", "core.safecrlf=false", *cmd_tail, str(tmp)],
                              cwd=str(root), capture_output=True, text=True,
                              timeout=timeout_s, env=_env())

    tmp: Optional[Path] = None
    try:
        try:
            fd, name = tempfile.mkstemp(prefix=".northstar_patch_",
                                        suffix=".patch", dir=str(root))
            os.close(fd)
            tmp = Path(name)
        except OSError as exc:
            return _fail(f"could not stage the patch file: {exc}")

        try:
            r = _attempt(text)
        except subprocess.TimeoutExpired:
            return _fail(f"git apply timed out after {timeout_s}s")
        except OSError as exc:
            return _fail(f"could not run git apply: {exc}")

        # Model output on Windows often carries CRLF line endings, which git
        # will not match against an LF tree. Retry once with normalised endings;
        # if that also fails, the error below is git's own.
        if r.returncode != 0 and "\r" in text:
            normalised = text.replace("\r\n", "\n").replace("\r", "\n")
            if normalised != text:
                try:
                    r = _attempt(normalised)
                except subprocess.TimeoutExpired:
                    return _fail(f"git apply timed out after {timeout_s}s")
                except OSError as exc:
                    return _fail(f"could not run git apply: {exc}")
    finally:
        if tmp is not None:
            try:
                tmp.unlink()
            except OSError:
                pass

    stdout = (r.stdout or "").strip()
    stderr = (r.stderr or "").strip()
    if r.returncode != 0:
        return {"ok": False, "output": stdout[-2000:],
                "error": (stderr or stdout or f"git apply exited {r.returncode}")[-2000:],
                "files": []}

    shown = ", ".join(p for p, _ in targets)
    files = [str(abs_path) for _, abs_path in targets]
    detail = f"applied {len(targets)} file(s): {shown}"
    return {"ok": True, "output": (detail + ("\n" + stdout if stdout else "")).strip(),
            "error": "", "files": files}
