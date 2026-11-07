"""tys_author - the only automated source of a write scope.

A write scope is a claim about *where* a fix has to go. A model asserting that
claim is an opinion; a traceback is evidence. This module therefore derives
``write_paths`` the only way that can be checked later: it runs the item's
acceptance command once, reads the frames that actually failed, and keeps the
repository source files among them.

What it keeps, and what it refuses:

    keep    repository source frames (the files a fix may legitimately touch)
    drop    tests/ and any test_*.py / *_test.py / conftest.py  (test code)
    drop    scripts/continuous_loop.py, scripts/ty_task_runner.py (loop plumbing)
    drop    tools/tys_*.py                                        (the harness)
    drop    AGENTS.md, site-packages, dist-packages, stdlib outside the repo

If nothing survives, the answer is ``ok: False`` with ``reason:
"scope_unproven"`` and nothing is written. That is deliberate: a candidate that
can only edit tests has proven nothing, and "no derivation artifact" is the
signal the launcher and the evaluator use to refuse the item instead of
inventing a scope.

The artifact (``state/author/<item_id>/derivation.json``) records the failing
command, the trimmed traceback, every dropped frame with its reason, the chosen
paths and the sha256 of the check file. The sha is the evaluator's tamper gate:
the check the acceptance command names must still hash the same when the
candidate is graded.

Contract::

    derive(*, item_id, acceptance_commands, run=subprocess.run, repo=Path)
      -> {"ok": bool, "write_paths": list[str], "check_sha256": str | None,
          "artifact": str, "reason": str}

Usage::

    python tools/tys_author.py --item M1f-scope-deriver \
        --command "python -m pytest -q test_tys_evaluator.py"
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shlex
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence

REPO = Path(os.environ.get("NORTHSTAR_TY_ROOT")
            or Path(__file__).resolve().parents[1]).resolve()

TIMEOUT_S = int(os.environ.get("TY_ACCEPTANCE_TIMEOUT_S", "900"))
OUTPUT_TAIL_CHARS = 8000

# Harness and policy files: never a legitimate place for an authored fix.
EXCLUDED_FILES = frozenset({
    "agents.md",
    "conftest.py",
    "scripts/continuous_loop.py",
    "scripts/ty_task_runner.py",
})
EXCLUDED_PREFIXES = ("tools/tys_",)

# Directories that mean the frame is not the product's own source.
_EXCLUDED_PARTS = frozenset({
    "tests",
    "site-packages",
    "dist-packages",
    "_pytest",
    "node_modules",
})

# Directories that are never worth walking when locating a path.
_SKIP_WALK = frozenset({
    ".git", ".hg", ".venv", "venv", "env", "node_modules", "__pycache__",
    ".pytest_cache", ".mypy_cache", ".ruff_cache", "dist", "build", ".next",
    "htmlcov", "state", "logs", "data",
})

_FRAME_STD = re.compile(
    r'^\s*File "(?P<file>[^"]+)",\s*line (?P<line>\d+)(?:,\s*in (?P<func>.+?))?\s*$')
_FRAME_PYTEST = re.compile(
    r"^(?P<file>.+?\.pyw?):(?P<line>\d+): in (?P<func>.+?)\s*$")
_FRAME_PYTEST_LINE = re.compile(
    r"^(?P<file>.+?\.pyw?):(?P<line>\d+):\s*(?P<func>.*)$")

# reason vocabulary: scope_derived | scope_unproven | acceptance_passed |
# no_acceptance_command | command_timeout | command_failed


# --------------------------------------------------------------------- helpers


# --------------------------------------------------------------------- helpers
def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _write(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n",
                   encoding="utf-8")
    tmp.replace(path)


def _safe_id(item_id: str) -> str:
    """An item id is a path segment; it must not be able to leave the root."""
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", str(item_id or "")).strip("._")
    return cleaned or "_"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _first_command(acceptance_commands: Any) -> List[str]:
    """Normalise the queue's many shapes into one argv.

    The queue stores ``[[argv], [argv]]``. A single ``[argv]`` and a plain
    string are also accepted so the CLI and a hand-written contract behave the
    same. Only the first command is run: one failure is enough evidence, and
    running a whole suite to guess a scope is how the loop burns a budget.
    """
    if acceptance_commands is None:
        return []
    if isinstance(acceptance_commands, str):
        return acceptance_commands.split()
    if isinstance(acceptance_commands, (list, tuple)):
        if not acceptance_commands:
            return []
        first = acceptance_commands[0]
        if isinstance(first, str):
            return [str(a) for a in acceptance_commands]
        if isinstance(first, (list, tuple)):
            return [str(a) for a in first]
    return []


def _looks_like_test(token: str) -> bool:
    name = str(token).replace("\\", "/").rsplit("/", 1)[-1].lower()
    return (name == "conftest.py"
            or (name.startswith("test_") and name.endswith(".py"))
            or name.endswith("_test.py"))


def _named_test_file(cmd: Sequence[str]) -> Optional[str]:
    """The test file the acceptance command names, if it names one.

    Handles ``test_x.py``, ``test_x.py::test_case`` and nested paths, and
    ignores flags. A command with no test file (a smoke script, say) yields
    ``None`` - the scope can still be derived, there is simply no tamper gate.
    """
    candidates: List[str] = []
    for arg in list(cmd)[1:]:
        token = str(arg).split("::", 1)[0]
        if token.startswith("-"):
            continue
        if token.lower().endswith((".py", ".pyw")) and _looks_like_test(token):
            candidates.append(token)
    return candidates[0] if candidates else None


def _walk_for(repo: Path, name: str, limit_dirs: int = 4000) -> List[Path]:
    hits: List[Path] = []
    seen = 0
    for root, dirs, files in os.walk(repo):
        dirs[:] = sorted(d for d in dirs if d.lower() not in _SKIP_WALK)
        seen += 1
        if seen > limit_dirs:
            break
        if name in files:
            try:
                hits.append((Path(root) / name).resolve())
            except OSError:
                continue
    return hits


def _locate(repo: Path, raw: str, cache: Optional[Dict[str, str]] = None) -> Optional[Path]:
    """Turn a path from a traceback into a real file inside ``repo``.

    Pytest prints paths relative to its rootdir, which is not always the repo
    root, so a relative token is tried against the repo root and the common
    package roots before a bounded walk by basename. Anything that cannot be
    found inside the repo is not evidence and is dropped by the caller.
    """
    token = str(raw or "").strip().strip('"').strip("'")
    if not token:
        return None
    key = os.path.normcase(token)
    if cache is not None and key in cache:
        cached = cache[key]
        return Path(cached) if cached else None

    found = _locate_uncached(repo, token)
    if cache is not None:
        cache[key] = str(found) if found else ""
    return found


def _locate_uncached(repo: Path, token: str) -> Optional[Path]:
    rel = Path(token.replace("\\", os.sep).replace("/", os.sep))
    candidates: List[Path] = []
    if rel.is_absolute():
        candidates.append(rel)
    else:
        for base in ("", "Northstar_backend", "tools", "scripts",
                     "northstar-os-ui", "tests"):
            candidates.append(repo / base / rel if base else repo / rel)
    for candidate in candidates:
        try:
            if candidate.is_file():
                return candidate.resolve()
        except OSError:
            continue
    if rel.is_absolute():
        return None
    hits = _walk_for(repo, rel.name)
    if not hits:
        return None
    suffix = rel.as_posix().lstrip("./")
    for hit in hits:
        try:
            if hit.relative_to(repo).as_posix().endswith(suffix):
                return hit
        except ValueError:
            continue
    return hits[0]


def _output(proc: Any) -> str:
    parts: List[str] = []
    for attr in ("stdout", "stderr"):
        value = getattr(proc, attr, None)
        if isinstance(value, bytes):
            value = value.decode("utf-8", "replace")
        if value:
            parts.append(str(value))
    return "\n".join(parts)


def _run_once(run: Callable[..., Any], cmd: Sequence[str], repo: Path) -> Any:
    """Run the acceptance command exactly once, tolerating a narrow runner."""
    full = {"cwd": str(repo), "capture_output": True, "text": True,
            "timeout": TIMEOUT_S}
    try:
        return run(list(cmd), **full)
    except TypeError:
        pass
    try:
        return run(list(cmd), cwd=str(repo), capture_output=True, text=True)
    except TypeError:
        return run(list(cmd), cwd=str(repo))


def _parse_frames(text: str) -> List[Dict[str, Any]]:
    """Extract frames from a python traceback or a pytest report.

    Both shapes matter in practice: a raw ``subprocess`` failure prints
    ``File "...", line N, in fn`` while pytest prints ``path.py:N: in fn``.
    The last positional form (``path.py:N: NameError: ...``, pytest's
    ``--tb=line``) is accepted as a frame too, because it still names the file.
    """
    frames: List[Dict[str, Any]] = []
    for line in str(text or "").splitlines():
        match = _FRAME_STD.match(line)
        if match:
            frames.append(_frame(match, line))
            continue
        if not line or line[0] in " \t":
            continue                        # indented source / captured values
        match = _FRAME_PYTEST.match(line)
        if match:
            frames.append(_frame(match, line))
            continue
        if line.startswith("E ") or line.startswith("E   "):
            continue
        match = _FRAME_PYTEST_LINE.match(line)
        if match and not match.group("func").startswith("E "):
            frames.append(_frame(match, line))
    return frames


def _frame(match: "re.Match[str]", raw: str) -> Dict[str, Any]:
    return {
        "file": match.group("file"),
        "line": int(match.group("line")),
        "function": (match.group("func") or "").strip() or None,
        "frame": raw.strip(),
    }


def _reason_excluded(rel: str) -> Optional[str]:
    """Why a repository-relative path is not writable source, or ``None``.

    Order matters: site-packages and tests are classified first so the artifact
    says *why* a frame was dropped rather than a vague "other".
    """
    posix = rel.replace("\\", "/")
    while posix.startswith("./"):
        posix = posix[2:]
    low = posix.lower()
    parts = [part.lower() for part in posix.split("/")]
    name = parts[-1]

    if any(part in _EXCLUDED_PARTS for part in parts[:-1]):
        return "tests" if "tests" in parts[:-1] else "stdlib"
    if low.startswith("tests/"):
        return "tests"
    if low in EXCLUDED_FILES or name == "agents.md":
        return "policy"
    if any(low.startswith(prefix) for prefix in EXCLUDED_PREFIXES):
        return "policy"
    if (name.startswith("test_") and name.endswith(".py")) or name.endswith("_test.py"):
        return "tests"
    return None


# ---------------------------------------------------------------------- public
def derive(
    *,
    item_id: str,
    acceptance_commands: Any,
    run: Callable[..., Any] = subprocess.run,
    repo: Optional[Path] = None,
) -> Dict[str, Any]:
    """Derive a write scope from a real failing run. Writes only on success."""
    repo_path = Path(repo or REPO).resolve()
    out: Dict[str, Any] = {
        "ok": False,
        "write_paths": [],
        "check_sha256": None,
        "artifact": "",
        "reason": "scope_unproven",
    }

    cmd = _first_command(acceptance_commands)
    if not cmd:
        out["reason"] = "no_acceptance_command"
        return out

    cache: Dict[str, str] = {}
    named = _named_test_file(cmd)
    check_file = _locate(repo_path, named, cache) if named else None
    if check_file is not None and not _inside(check_file, repo_path):
        # A tamper gate that hashes a file outside the repo is not a gate.
        check_file = None
    if check_file is not None:
        out["check_sha256"] = _sha256(check_file)

    try:
        proc = _run_once(run, cmd, repo_path)
    except subprocess.TimeoutExpired:
        out["reason"] = "command_timeout"
        return out
    except OSError as exc:
        out["reason"] = f"command_failed:{exc.__class__.__name__}"
        return out

    raw_rc = getattr(proc, "returncode", -1)
    returncode = raw_rc if isinstance(raw_rc, int) else -1
    if returncode == 0:
        # A green check is A8's problem, not a scope: there is no traceback to
        # read, and inventing one here is how a scope becomes an opinion.
        out["reason"] = "acceptance_passed"
        return out

    text = _output(proc)
    kept: List[Dict[str, Any]] = []
    trimmed: List[str] = []
    dropped: List[Dict[str, Any]] = []
    for frame in _parse_frames(text):
        located = _locate(repo_path, frame["file"], cache)
        rel: Optional[str] = None
        if located is not None:
            try:
                rel = located.relative_to(repo_path).as_posix()
            except ValueError:
                rel = None
        if rel is None:
            dropped.append({**_audit(frame), "reason": "outside_repo"})
            continue
        excluded = _reason_excluded(rel)
        if excluded:
            dropped.append({**_audit(frame, rel), "reason": excluded})
            continue
        kept.append({"path": rel, "line": frame["line"],
                     "function": frame["function"], "frame": frame["frame"]})
        trimmed.append(frame["frame"])

    write_paths = sorted({entry["path"] for entry in kept})
    if not write_paths:
        out["reason"] = "scope_unproven"
        return out

    payload = {
        "item_id": str(item_id),
        "derived_at": _now(),
        "failing_command": cmd,
        "returncode": returncode,
        "write_paths": write_paths,
        "check_file": _relative(check_file, repo_path),
        "check_sha256": out["check_sha256"],
        "frames": kept,
        "traceback": trimmed,
        "dropped_frames": dropped,
        "output_tail": text[-OUTPUT_TAIL_CHARS:],
    }
    artifact = repo_path / "state" / "author" / _safe_id(item_id) / "derivation.json"
    _write(artifact, payload)

    out["ok"] = True
    out["write_paths"] = write_paths
    out["artifact"] = str(artifact)
    out["reason"] = "scope_derived"
    return out


def _relative(path: Optional[Path], repo: Path) -> Optional[str]:
    if path is None:
        return None
    try:
        return path.resolve().relative_to(repo).as_posix()
    except (OSError, ValueError):
        return str(path)


def _inside(path: Path, repo: Path) -> bool:
    try:
        path.resolve().relative_to(repo)
        return True
    except (OSError, ValueError):
        return False


def _audit(frame: Dict[str, Any], rel: Optional[str] = None) -> Dict[str, Any]:
    return {"file": rel or frame["file"], "line": frame["line"],
            "function": frame["function"], "frame": frame["frame"]}


def _split_command(text: str) -> List[str]:
    argv: List[str] = []
    for token in shlex.split(str(text or ""), posix=False):
        if len(token) >= 2 and token[0] == token[-1] and token[0] in "\"'":
            token = token[1:-1]
        if token:
            argv.append(token)
    return argv


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Northstar scope author")
    parser.add_argument("--item", required=True, help="queue item id")
    parser.add_argument("--command", action="append", required=True,
                        help="acceptance command (repeatable; the first is run)")
    parser.add_argument("--repo", default=None, help="repository root")
    ns = parser.parse_args(argv)
    commands = [_split_command(c) for c in ns.command]
    result = derive(item_id=ns.item,
                    acceptance_commands=[c for c in commands if c],
                    repo=Path(ns.repo) if ns.repo else None)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
