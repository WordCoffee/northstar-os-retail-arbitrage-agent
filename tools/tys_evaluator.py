"""tys_evaluator - the deterministic gates that judge a candidate patch.

The author lane may be a model. The judgement of its work is not. Nothing in this
module reads a model's opinion: every gate is a command, a hash or a path
comparison, and every verdict names the gate that produced it so a rejection can be
logged, fingerprinted (M1e) and shown on disk (M1d) without interpreting prose.

Gates, in order, fail fast - the first failure is the verdict:

    out_of_scope     every changed path is inside ``contract["write_paths"]``, and
                     nothing under ``tests/``, a ``conftest``, a per-file test
                     module, or a POLICY_PATH. Scope is checked before anything is
                     executed, so a patch that reaches outside its lane never runs.
    malformed        the diff is non-empty and every path it names either exists in
                     the worktree or is a deletion. An empty diff judges nothing.
    target_red       every ``acceptance_commands`` argv exits 0. A non-zero exit, a
                     timeout or a command that cannot be started is a failure: the
                     target did not go green. (The pre-run red gate in
                     ``tys_launcher`` refuses a check that was already green, so a
                     pass here means the patch is what turned it.)
    check_tampered   when the contract pins ``check_sha256``, the file the
                     acceptance command names must still hash to it. A worker that
                     edits the check to make the check pass is caught here.
    regression       optional: ``tools/check_regression.py``'s ``compare`` over an
                     idlist, when ``contract["idlist"]`` is set. Removed or failing
                     test ids are a regression; additions are allowed.

Usage from the loop::

    verdict = evaluate(contract=card, repo=ROOT)
    if verdict["ok"]:
        ...

Usage from a shell (evidence for an artifact / a rejection record)::

    python tools/tys_evaluator.py --contract state/author/x/cand_1.json --repo .

The return value is always::

    {"ok": bool, "gate": str, "detail": str, "commands": [...]}

``gate`` is ``"pass"`` on success and the name of the first failed gate otherwise.
``commands`` is every acceptance command actually executed, with its own exit
code, so a rejection carries its evidence rather than a claim.
"""
from __future__ import annotations

import argparse
import fnmatch
import hashlib
import importlib.util
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

TOOLS = Path(__file__).resolve().parent
ROOT = Path(os.environ.get("NORTHSTAR_TY_ROOT") or TOOLS.parent).resolve()
DEFAULT_TIMEOUT_S = int(os.environ.get("TY_ACCEPTANCE_TIMEOUT_S", "1800") or 1800)

#: Files a candidate may never write, whatever its contract declares. Matched with
#: fnmatch on the repo-relative posix path, case-insensitively.
POLICY_PATHS = (
    "scripts/continuous_loop.py",
    "scripts/ty_task_runner.py",
    "tools/tys_*.py",
    "AGENTS.md",
)

#: First-token names that are a program, never the file a check lives in.
INTERPRETERS = frozenset({
    "python", "python3", "python.exe", "py", "py.exe", "pytest",
    "bash", "sh", "zsh", "powershell", "pwsh", "pwsh.exe", "cmd", "cmd.exe",
})

GATES = ("out_of_scope", "malformed", "target_red", "check_tampered", "regression")


# ------------------------------------------------------------------- path rules
def _norm(path: str) -> str:
    """Repo-relative posix spelling. Git already uses '/' but operators may not."""
    text = str(path).strip().replace("\\", "/")
    while text.startswith("./"):
        text = text[2:]
    return text


def forbidden_reason(path: str) -> str:
    """Why this changed path is off-limits even if the contract allows it, or ''."""
    rel = _norm(path)
    folded = rel.casefold()
    parts = [p for p in folded.split("/") if p]

    for pattern in POLICY_PATHS:
        if fnmatch.fnmatchcase(folded, _norm(pattern).casefold()):
            return f"{rel} is a policy path (the loop cannot edit the rules it runs under)"
    if folded == "agents.md" or folded.endswith("/agents.md"):
        return "AGENTS.md is a policy file (append-only, never a candidate's target)"

    # Any depth, so "pkg/tests/x.py" is refused as well as "tests/x.py".
    if any(part == "tests" for part in parts[:-1]):
        return f"{rel} is under tests/ - a candidate may not edit the suite that judges it"
    name = parts[-1] if parts else ""
    if name.startswith("conftest"):
        return f"{rel} is a conftest - it can change how every check runs"
    if name.startswith("test_") or name.endswith("_test.py"):
        return f"{rel} is a test module - the check must stay independent of the patch"
    return ""


def within_scope(path: str, write_paths: Sequence[str]) -> bool:
    """Is this path inside the contract's declared write scope?"""
    target = _norm(path).casefold()
    for raw in write_paths or ():
        allowed = _norm(str(raw))
        if not allowed:
            continue
        keep = allowed.casefold()
        if target == keep:
            return True
        # A declared directory ("state/probes" or "state/probes/") scopes the tree.
        if keep.endswith("/") and target.startswith(keep):
            return True
        if target.startswith(keep + "/"):
            return True
    return False


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _commands_of(contract: Dict[str, Any]) -> List[List[str]]:
    """The acceptance commands as argv lists. A bare string is one argv, not a shell line."""
    raw = contract.get("acceptance_commands") or []
    if isinstance(raw, str):
        raw = [[raw]]
    out: List[List[str]] = []
    for entry in raw:
        if isinstance(entry, str):
            out.append([entry])
        elif isinstance(entry, (list, tuple)):
            out.append([str(item) for item in entry if str(item)])
    return out


def _is_interpreter(token: str) -> bool:
    name = Path(str(token)).name.casefold()
    return name in INTERPRETERS or name.startswith("python")


def _stream_text(value: Any) -> str:
    if isinstance(value, bytes):
        return value.decode("utf-8", "replace")
    return value or ""


def _output_of(result: Any) -> str:
    """Both streams, for a command's evidence - unlike a diff, prose belongs together."""
    out = _stream_text(getattr(result, "stdout", ""))
    err = _stream_text(getattr(result, "stderr", ""))
    if out and err and not out.endswith("\n"):
        out += "\n"
    return out + err


def _result_text(result: Any) -> Tuple[int, str]:
    """Accept a CompletedProcess, a raw string or a list of lines from an injected git."""
    if isinstance(result, str):
        return 0, result
    if isinstance(result, (list, tuple)):
        return 0, "\n".join(str(line) for line in result)
    code = getattr(result, "returncode", 0)
    try:
        code = int(code)
    except (TypeError, ValueError):
        code = 0
    out = getattr(result, "stdout", "") or ""
    err = getattr(result, "stderr", "") or ""
    if isinstance(out, bytes):
        out = out.decode("utf-8", "replace")
    if isinstance(err, bytes):
        err = err.decode("utf-8", "replace")
    if code != 0 and not out:
        out = err
    return code, out


def _parse_name_status(text: str) -> List[Tuple[str, List[str]]]:
    """`git diff --name-status` lines -> [(status, [paths])]. Renames keep both paths."""
    rows: List[Tuple[str, List[str]]] = []
    for line in (text or "").splitlines():
        line = line.rstrip("\r")
        if not line.strip():
            continue
        parts = line.split("\t")
        if len(parts) < 2:
            continue
        status = (parts[0].strip()[:1] or "M").upper()
        paths = [_norm(part) for part in parts[1:] if part.strip()]
        if paths:
            rows.append((status, paths))
    return rows


def _regression_module() -> Any:
    """Load tools/check_regression.py by path - `compare` is the name-based verdict."""
    global _CHECK_REGRESSION
    if _CHECK_REGRESSION is None:
        path = TOOLS / "check_regression.py"
        spec = importlib.util.spec_from_file_location("tys__check_regression", path)
        if spec is None or spec.loader is None:
            raise ImportError(f"cannot load {path}")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        _CHECK_REGRESSION = module
    return _CHECK_REGRESSION


_CHECK_REGRESSION: Optional[Any] = None


# ---------------------------------------------------------------------- verdicts
def _fail(gate: str, detail: Any, commands: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    text = " | ".join(line.strip() for line in str(detail).splitlines() if line.strip())
    return {"ok": False, "gate": gate, "detail": text[:2000], "commands": list(commands)}


class _Judge:
    """One evaluation: the repo, the contract, the injected runners, the record."""

    def __init__(self, contract: Dict[str, Any], repo: Path,
                 run: Callable[..., Any], git: Optional[Callable[..., Any]]) -> None:
        self.contract = dict(contract or {})
        self.repo = Path(repo).resolve()
        self.run = run
        self._git = git or self._default_git
        self.commands: List[Dict[str, Any]] = []
        self.changes_error = ""
        self._changes: Optional[Dict[str, List[str]]] = None

    def _default_git(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run(["git", *[str(a) for a in args]],
                              cwd=str(self.repo), capture_output=True, text=True)

    def _git_text(self, *args: str) -> Tuple[int, str]:
        try:
            return _result_text(self._git(*args))
        except (OSError, subprocess.SubprocessError) as exc:
            return 127, str(exc)

    def changes(self) -> Dict[str, List[str]]:
        """Every path the candidate touched: tracked diff against HEAD plus untracked.

        Against HEAD rather than the index, so a staged-but-not-committed change is
        counted too. A repo with an unborn HEAD falls back to merged staged and
        unstaged diffs.
        """
        if self._changes is not None:
            return self._changes
        if self.changes_error:
            return {}
        out: Dict[str, List[str]] = {}
        code, text = self._git_text("diff", "--name-status", "HEAD")
        if code != 0:
            plain_code, plain = self._git_text("diff", "--name-status")
            staged_code, staged = self._git_text("diff", "--name-status", "--cached")
            if plain_code != 0 and staged_code != 0:
                self.changes_error = (plain or staged or "git diff failed").strip()
                return {}
            text = plain + "\n" + staged
        for status, paths in _parse_name_status(text):
            for rel in paths:
                out.setdefault(rel, []).append(status)

        code, text = self._git_text("ls-files", "--others", "--exclude-standard")
        if code != 0:
            self.changes_error = (text or "git ls-files failed").strip()
            return {}
        for line in text.splitlines():
            rel = _norm(line)
            if rel:
                out.setdefault(rel, [])
                if "A" not in out[rel]:
                    out[rel].append("A")
        self._changes = out
        return out

    def _call(self, cmd: List[str], timeout: int) -> Any:
        try:
            return self.run(cmd, cwd=str(self.repo), timeout=timeout,
                            capture_output=True, text=True)
        except TypeError:
            # An injected runner with a narrower signature (cmd only) still works.
            return self.run(cmd)

    def execute(self, argv: Sequence[str], timeout: int) -> Dict[str, Any]:
        """Run one acceptance command and record it. The record IS the evidence."""
        cmd = [str(part) for part in argv]
        record: Dict[str, Any] = {"argv": cmd, "cmd": " ".join(cmd),
                                  "exit": None, "ok": False, "seconds": 0.0, "detail": ""}
        started = time.time()
        try:
            proc = self._call(cmd, timeout)
            if isinstance(proc, int):
                code, text = int(proc), ""
            else:
                code, _ = _result_text(proc)
                text = _output_of(proc)
            record.update(exit=code, ok=code == 0, detail=(text or "")[-800:])
        except subprocess.TimeoutExpired:
            record.update(exit=124, ok=False, detail=f"timeout after {timeout}s")
        except OSError as exc:
            record.update(exit=127, ok=False, detail=f"could not start: {exc}")
        record["seconds"] = round(time.time() - started, 1)
        self.commands.append(record)
        return record

    def write_paths(self) -> List[str]:
        declared = self.contract.get("write_paths") or []
        return [declared] if isinstance(declared, str) else list(declared)

    def pre_changed(self) -> set:
        """Paths already dirty when the candidate was dispatched.

        This box runs parallel lanes, so an unrelated file is often dirty before a
        worker starts. A path that was already dirty and is outside the declared
        scope is not attributable to this candidate. Absent the key the gate is
        strict: every changed path must be inside write_paths.
        """
        raw = self.contract.get("pre_changed") or []
        if isinstance(raw, str):
            raw = [raw]
        return {_norm(str(path)).casefold() for path in raw if str(path).strip()}

    def attributable(self, path: str) -> bool:
        if within_scope(path, self.write_paths()):
            return True
        return _norm(path).casefold() not in self.pre_changed()

    def named_check(self) -> str:
        """The file the acceptance command (or contract) names, repo-relative."""
        explicit = self.contract.get("check_path")
        if explicit:
            return _norm(str(explicit))
        cwd = _norm(str(self.contract.get("cwd") or ""))
        bases = [self.repo / cwd, self.repo] if cwd else [self.repo]
        tokens: List[str] = []
        for argv in _commands_of(self.contract):
            for index, token in enumerate(argv):
                if not token or token.startswith("-"):
                    continue
                if Path(token).is_absolute():
                    continue
                if index == 0 and _is_interpreter(token):
                    continue
                tokens.append(token)
                for base in bases:
                    candidate = base / token
                    if candidate.is_file():
                        try:
                            return candidate.resolve().relative_to(self.repo).as_posix()
                        except ValueError:
                            return str(candidate)
        # `python -m pytest -q test_x.py` from the repo root names a file that
        # lives in a subpackage. Match a unique basename among tracked files; an
        # ambiguous name stays unresolved rather than guessing.
        code, tracked = self._git_text("ls-files")
        if code == 0 and tokens:
            wanted = {Path(token).name for token in tokens}
            hits = sorted({_norm(rel) for rel in tracked.splitlines()
                           if Path(_norm(rel)).name in wanted})
            if len(hits) == 1:
                return hits[0]
        return ""

    def timeout_s(self) -> int:
        try:
            return max(1, int(self.contract.get("timeout_s") or DEFAULT_TIMEOUT_S))
        except (TypeError, ValueError):
            return DEFAULT_TIMEOUT_S


# ------------------------------------------------------------------------- gates
def _gate_scope(judge: _Judge) -> Optional[Dict[str, Any]]:
    changes = judge.changes()
    if judge.changes_error:
        return _fail("out_of_scope",
                     f"cannot read the diff, so scope cannot be judged: {judge.changes_error}",
                     judge.commands)
    declared = judge.write_paths()

    outside: List[str] = []
    forbidden: List[str] = []
    for rel in sorted(changes):
        why = forbidden_reason(rel)
        if why:
            forbidden.append(why)
        elif not judge.attributable(rel):
            # Already dirty before the candidate started and outside its scope:
            # somebody else's bytes, not the patch on trial.
            continue
        elif not within_scope(rel, declared):
            outside.append(rel)

    if not outside and not forbidden:
        return None
    parts: List[str] = []
    if outside:
        shown = ", ".join(outside[:5])
        more = f" (+{len(outside) - 5} more)" if len(outside) > 5 else ""
        parts.append(f"changed outside write_paths: {shown}{more}")
    if forbidden:
        parts.extend(forbidden[:3])
        if len(forbidden) > 3:
            parts.append(f"(+{len(forbidden) - 3} more forbidden paths)")
    allowed = ", ".join(_norm(str(p)) for p in declared[:6]) or "(none declared)"
    return _fail("out_of_scope", "; ".join(parts) + f" | allowed: {allowed}", judge.commands)


def _gate_malformed(judge: _Judge) -> Optional[Dict[str, Any]]:
    changes = judge.changes()
    if judge.changes_error:
        return _fail("malformed",
                     f"cannot read the diff, so it cannot be judged: {judge.changes_error}",
                     judge.commands)
    if not changes:
        return _fail("malformed", "the diff is empty - there is nothing to judge",
                     judge.commands)

    patch = {rel: statuses for rel, statuses in changes.items() if judge.attributable(rel)}
    if not patch:
        return _fail("malformed",
                     "the candidate's own diff is empty - only pre-existing changes are present",
                     judge.commands)

    missing: List[str] = []
    ghosts: List[str] = []
    for rel, statuses in sorted(patch.items()):
        deleted = "D" in statuses
        exists = (judge.repo / rel).exists()
        if not exists and not deleted:
            missing.append(rel)
        elif exists and deleted and len(statuses) == 1:
            ghosts.append(rel)
    if missing:
        return _fail("malformed",
                     "declared path missing from the worktree and not deleted: "
                     + ", ".join(missing[:5]), judge.commands)
    if ghosts:
        return _fail("malformed",
                     "the diff deletes a path that is still on disk: "
                     + ", ".join(ghosts[:5]), judge.commands)
    return None


def _gate_target(judge: _Judge) -> Optional[Dict[str, Any]]:
    commands = _commands_of(judge.contract)
    if not commands:
        return _fail("target_red",
                     "no acceptance_commands declared - an uncheckable patch cannot be judged",
                     judge.commands)
    timeout = judge.timeout_s()
    ran = 0
    for argv in commands:
        if not argv:
            continue
        ran += 1
        record = judge.execute(argv, timeout)
        if not record["ok"]:
            detail = f"acceptance command failed (exit {record['exit']}): {record['cmd']}"
            if record["detail"]:
                detail += f" | {record['detail'][-600:]}"
            return _fail("target_red", detail, judge.commands)
    if not ran:
        return _fail("target_red", "acceptance_commands are empty", judge.commands)
    return None


def _gate_check_tampered(judge: _Judge) -> Optional[Dict[str, Any]]:
    pinned = judge.contract.get("check_sha256")
    if not pinned:
        return None
    if isinstance(pinned, str):
        rel = judge.named_check()
        if not rel:
            return _fail("check_tampered",
                         "check_sha256 is pinned but no acceptance command names a file "
                         "in the repo, so the pin cannot be verified", judge.commands)
        pins: Dict[str, str] = {rel: pinned}
    elif isinstance(pinned, dict):
        pins = {_norm(str(key)): str(value) for key, value in pinned.items()}
    else:
        return _fail("check_tampered",
                     f"check_sha256 has an unusable type: {type(pinned).__name__}",
                     judge.commands)

    broken: List[str] = []
    for rel, expected in pins.items():
        path = judge.repo / rel
        if not path.is_file():
            broken.append(f"{rel} is gone (pinned {str(expected)[:12]})")
            continue
        actual = _sha256(path)
        if actual.casefold() != str(expected).strip().casefold():
            broken.append(f"{rel} is {actual[:12]}, pinned {str(expected)[:12]}")
    if broken:
        return _fail("check_tampered",
                     "the pinned check changed: " + "; ".join(broken[:4]), judge.commands)
    return None


def _gate_regression(judge: _Judge) -> Optional[Dict[str, Any]]:
    idlist = judge.contract.get("idlist")
    if not idlist:
        return None
    source = Path(str(idlist))
    if not source.is_absolute():
        source = judge.repo / source
    if not source.is_file():
        return _fail("regression", f"idlist not found: {source}", judge.commands)
    baseline_path = judge.repo / "tests" / "BASELINE_TESTS.json"
    if not baseline_path.is_file():
        return _fail("regression",
                     f"no baseline id set at {baseline_path}, so nothing can be compared",
                     judge.commands)
    try:
        baseline = set(json.loads(baseline_path.read_text(encoding="utf-8")).get("tests") or [])
        checker = _regression_module()
        current = checker._from_idlist(source)
        result = checker.compare(current, baseline)
    except (OSError, ValueError, KeyError, AttributeError) as exc:
        return _fail("regression", f"could not compare the id set: {exc}", judge.commands)
    if result.get("ok"):
        return None

    detail = (f"{len(result['removed'])} removed, {len(result['failed'])} failing "
              f"of baseline {result['baseline']}")
    if result["removed"]:
        detail += " | removed: " + ", ".join(result["removed"][:5])
    if result["failed"]:
        detail += " | failed: " + ", ".join(result["failed"][:5])
    return _fail("regression", detail, judge.commands)


# ---------------------------------------------------------------------- entrypoint
def evaluate(*, contract: Dict[str, Any], repo: Path,
             run: Callable[..., Any] = subprocess.run,
             git: Optional[Callable[..., Any]] = None) -> Dict[str, Any]:
    """Judge one candidate patch. Deterministic; no model is consulted.

    ``contract`` is the task card: ``write_paths`` and ``acceptance_commands`` are
    required to pass, ``check_sha256`` and ``idlist`` are optional pins.
    ``repo`` is the worktree the diff lives in. ``run`` is the command runner and
    ``git(*args)`` the git runner, both injectable so a test never shells out to a
    real check.
    """
    judge = _Judge(contract or {}, Path(repo), run=run, git=git)
    for gate in (_gate_scope, _gate_malformed, _gate_target,
                 _gate_check_tampered, _gate_regression):
        verdict = gate(judge)
        if verdict:
            return verdict

    changes = judge.changes()
    shown = ", ".join(sorted(changes)[:5])
    return {
        "ok": True,
        "gate": "pass",
        "detail": f"{len(GATES)} gates green over {len(changes)} changed path(s): {shown}",
        "commands": list(judge.commands),
    }


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Deterministic candidate-patch gates.")
    parser.add_argument("--contract", required=True, help="task card JSON")
    parser.add_argument("--repo", default=str(ROOT), help="worktree the diff lives in")
    parser.add_argument("--json", action="store_true", help="print the verdict (default)")
    ns = parser.parse_args(argv)

    path = Path(ns.contract)
    try:
        contract = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        print(f"contract unreadable: {exc}", file=sys.stderr)
        return 2
    if not isinstance(contract, dict):
        print("contract must be a JSON object", file=sys.stderr)
        return 2
    verdict = evaluate(contract=contract, repo=Path(ns.repo))
    print(json.dumps(verdict, indent=2))
    return 0 if verdict["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
