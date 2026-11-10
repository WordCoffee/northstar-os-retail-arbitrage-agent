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

Deriving a scope is only half the contract. ``write_contract`` is the other
half: it turns a *proven* derivation into the queue item the launcher can
dispatch - ``write_paths``, ``acceptance_commands`` (argv lists, never a shell
string), ``objective``, ``check_sha256``, ``scope_derivation`` and
``forbidden_paths`` - clears ``needs_author``/``blocked_reason``, writes the
queue atomically, and re-reads it to prove the bytes on disk are what it
claims. A derivation that failed, or one with no paths, is refused: there is no
code path here that writes a scope it was not given.

Contract::

    derive(*, item_id, acceptance_commands, run=subprocess.run, repo=Path)
      -> {"ok": bool, "write_paths": list[str], "check_sha256": str | None,
          "artifact": str, "reason": str}

    write_contract(*, queue_path, item_id, derived, objective, read_paths=None)
      -> {"ok": bool, "reason": str, "write_paths": list[str],
          "acceptance_commands": list[list[str]], "check_sha256": str | None,
          "scope_derivation": str, "forbidden_paths": list[str],
          "problems": list[str]}

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


def _write_queue(path: Path, data: Any) -> None:
    """Atomic queue write: tmp file, fsync, then ``os.replace``.

    Same shape as ``tys_runner._write``, with the rename made explicit: the
    launcher may read the queue from another process at any moment, so a
    half-written file must never be observable under the real name.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, path)


def _read(path: Path, default: Any = None) -> Any:
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


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


# ------------------------------------------------------------ contract writing
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def _argv_only(raw: Any) -> "tuple[List[List[str]], str]":
    """Normalise to ``[[argv], ...]`` and refuse anything else.

    The queue's contract is argv, not a command line: a shell string re-parses
    after every allowlist has looked at it, so a string is a refusal here rather
    than something to split and hope about.
    """
    if isinstance(raw, str):
        return [], "shell_string_command: acceptance_commands must be argv lists"
    if not isinstance(raw, (list, tuple)) or not raw:
        return [], "no_acceptance_command"
    commands: List[List[str]] = []
    for index, cmd in enumerate([raw] if isinstance(raw[0], str) else list(raw)):
        if isinstance(cmd, str):
            return [], f"shell_string_command: command[{index}] must be an argv list"
        if not isinstance(cmd, (list, tuple)) or not cmd:
            return [], f"empty_command: command[{index}] is not a non-empty argv list"
        if not all(isinstance(token, str) and token.strip() for token in cmd):
            return [], (f"argv_not_strings: command[{index}] has an empty or "
                        f"non-string token")
        commands.append([token for token in cmd])
    if not commands:
        return [], "no_acceptance_command"
    return commands, ""


def _contract_commands(derived: Dict[str, Any]) -> "tuple[List[List[str]], str]":
    """The argv the item will be graded by, preferring the derivation artifact.

    ``derive`` returns the paths and the sha but not the command, so the command
    is read back from the artifact it wrote - the same bytes that justify the
    scope. A caller may pass ``acceptance_commands`` explicitly instead; both
    paths still have to be argv.
    """
    if derived.get("acceptance_commands") is not None:
        return _argv_only(derived.get("acceptance_commands"))
    artifact = str(derived.get("artifact") or "").strip()
    payload = _read(Path(artifact), {}) if artifact else {}
    if isinstance(payload, dict) and payload.get("failing_command"):
        return _argv_only(payload["failing_command"])
    return [], "no_acceptance_command"


def _forbidden_paths(payload: Any, derived: Dict[str, Any],
                     commands: List[List[str]]) -> List[str]:
    """The test file the contract grades, so a candidate cannot edit its own gate.

    Read from the artifact first (that is the check that actually failed), then
    from the command itself when the artifact names no test file.
    """
    out: List[str] = []
    values: List[Any] = []
    if isinstance(payload, dict):
        values.append(payload.get("check_file"))
    values.append(derived.get("check_file"))
    for value in values:
        text = str(value or "").replace("\\", "/").strip()
        if text and text not in out:
            out.append(text)
    if not out and commands:
        named = _named_test_file(commands[0])
        if named:
            out.append(str(named).replace("\\", "/").strip())
    return out


def _contract_problems(item: Dict[str, Any]) -> List[str]:
    """Structural check of a written contract - what ``validate_contract`` needs."""
    problems: List[str] = []
    paths = item.get("write_paths")
    if not isinstance(paths, list) or not paths:
        problems.append("write_paths is empty")
    elif not all(isinstance(p, str) and p.strip() for p in paths):
        problems.append("write_paths must be non-empty strings")

    commands = item.get("acceptance_commands")
    if isinstance(commands, str):
        problems.append("acceptance_commands is a shell string, not argv lists")
    elif not isinstance(commands, list) or not commands:
        problems.append("acceptance_commands is empty")
    else:
        for index, cmd in enumerate(commands):
            if isinstance(cmd, str):
                problems.append(f"command[{index}] is a shell string")
            elif (not isinstance(cmd, list) or not cmd
                  or not all(isinstance(a, str) and a.strip() for a in cmd)):
                problems.append(f"command[{index}] is not a non-empty argv list")

    if not str(item.get("objective") or "").strip():
        problems.append("objective is empty")
    sha = item.get("check_sha256")
    if sha is not None and not _SHA256_RE.match(str(sha)):
        problems.append("check_sha256 is not a sha256 hex digest")
    if not str(item.get("scope_derivation") or "").strip():
        problems.append("scope_derivation is missing")
    if not isinstance(item.get("forbidden_paths"), list):
        problems.append("forbidden_paths must be a list")
    if item.get("needs_author"):
        problems.append(f"needs_author is still set: {item.get('needs_author')}")
    if item.get("blocked_reason"):
        problems.append(f"blocked_reason is still set: {item.get('blocked_reason')}")
    return problems


def write_contract(
    *,
    queue_path: Any,
    item_id: str,
    derived: Dict[str, Any],
    objective: str,
    read_paths: Optional[Sequence[str]] = None,
) -> Dict[str, Any]:
    """Write a *proven* derivation into the queue as a dispatchable contract.

    Refuses when the derivation did not succeed or carries no write paths: an
    authored contract is evidence about where a fix goes, and this function
    never supplies a path the traceback did not.
    """
    out: Dict[str, Any] = {
        "ok": False,
        "item_id": str(item_id),
        "queue": str(queue_path),
        "write_paths": [],
        "acceptance_commands": [],
        "check_sha256": None,
        "scope_derivation": "",
        "forbidden_paths": [],
        "reason": "contract_refused",
        "problems": [],
    }

    if not isinstance(derived, dict) or not derived.get("ok"):
        reason = derived.get("reason") if isinstance(derived, dict) else "not_an_object"
        out["reason"] = "scope_not_derived"
        out["problems"] = [f"derivation refused: {reason or 'unknown'}"]
        return out

    write_paths = [str(p).replace("\\", "/").strip()
                   for p in (derived.get("write_paths") or [])
                   if str(p).strip()]
    if not write_paths:
        out["reason"] = "scope_unproven"
        out["problems"] = ["derivation carries no write_paths"]
        return out

    commands, why = _contract_commands(derived)
    if why:
        out["reason"] = why.split(":", 1)[0]
        out["problems"] = [why]
        return out

    queue_file = Path(queue_path)
    queue = _read(queue_file, None)
    if not isinstance(queue, dict) or not isinstance(queue.get("items"), list):
        out["reason"] = "queue_unreadable"
        return out
    index = next((n for n, item in enumerate(queue["items"])
                  if isinstance(item, dict) and str(item.get("id")) == str(item_id)), None)
    if index is None:
        out["reason"] = "item_not_found"
        return out

    item = queue["items"][index]
    before = dict(item)
    artifact = str(derived.get("artifact") or "").strip()
    payload = _read(Path(artifact), {}) if artifact else {}
    forbidden = _forbidden_paths(payload, derived, commands)
    check_sha = derived.get("check_sha256")
    goal = str(objective or "").strip() or str(item.get("next")
                                              or item.get("title") or "").strip()
    if not goal:
        out["reason"] = "objective_missing"
        return out

    item.update({
        "write_paths": write_paths,
        "acceptance_commands": commands,
        "objective": goal,
        "check_sha256": check_sha,
        "scope_derivation": artifact,
        "forbidden_paths": forbidden,
        "needs_author": None,
        "blocked_reason": None,
        "contract_written_at": _now(),
    })
    if read_paths is not None:
        item["read_paths"] = [str(p).replace("\\", "/").strip()
                              for p in read_paths if str(p).strip()]
    queue["updated_at"] = _now()
    _write_queue(queue_file, queue)

    # Re-read from disk: the launcher judges the file, not this function's intent.
    written = _read(queue_file, None)
    reread = None
    if isinstance(written, dict):
        reread = next((row for row in written.get("items", [])
                       if isinstance(row, dict) and str(row.get("id")) == str(item_id)), None)
    problems = (["the queue on disk is not the queue that was written"] if reread is None
                else _contract_problems(reread))
    if problems:
        # Never leave a contract in the queue that does not survive its own read.
        queue["items"][index] = before
        _write_queue(queue_file, queue)
        out["reason"] = "readback_invalid"
        out["problems"] = problems
        return out

    out.update({
        "ok": True,
        "reason": "contract_written",
        "write_paths": write_paths,
        "acceptance_commands": commands,
        "check_sha256": check_sha,
        "scope_derivation": artifact,
        "forbidden_paths": forbidden,
        "objective": goal,
        "problems": [],
    })
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
