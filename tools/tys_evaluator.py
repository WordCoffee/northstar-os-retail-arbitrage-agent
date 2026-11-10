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

Before any of those, ``evaluate_frozen`` answers about the artifact itself:
``artifact_missing`` / ``artifact_invalid`` when it is absent or unreadable,
``artifact_tampered`` when its seal no longer matches, and ``already_scored``
when the candidate has already been judged. None of these runs a command.

A verdict that cannot be reproduced from disk is not a verdict, so a candidate is
**frozen** before it is judged. ``freeze`` captures the patch as bytes - the whole
``git diff --binary HEAD`` plus the untracked files that belong to the candidate -
and writes ``state/author/<item_id>/cand_<k>.{diff,json}``. ``evaluate_frozen``
replays those bytes through the same gates and never asks the working tree what
changed, so two verdicts over one candidate can be compared, diffed and audited.
The record is hash-sealed: an edited diff or an edited contract is refused as
``artifact_tampered`` rather than re-scored, and a candidate is scored once -
a second attempt is ``already_scored`` and starts no command.

Usage from the loop::

    verdict = evaluate(contract=card, repo=ROOT)
    if verdict["ok"]:
        ...

    frozen = freeze(repo=ROOT, item_id="M1d", candidate_id="1", contract=card,
                    pre_changed=dirty_at_dispatch)
    verdict = evaluate_frozen(frozen["json"], repo=ROOT)

Usage from a shell (evidence for an artifact / a rejection record)::

    python tools/tys_evaluator.py --contract card.json --item M1d --candidate 1 --freeze
    python tools/tys_evaluator.py --frozen state/author/M1d/cand_1.json --repo .

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
import re
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

#: Gates that judge the frozen artifact rather than the patch. A verdict that
#: cannot be reproduced from disk is refused, never guessed at.
ARTIFACT_GATES = ("artifact_missing", "artifact_invalid", "artifact_tampered",
                  "already_scored")

#: Fields sealed by ``payload_sha256``. The ``scored`` block is deliberately not
#: among them: scoring appends a verdict, it never rewrites the evidence.
FROZEN_FIELDS = (
    "schema", "item_id", "candidate_id", "frozen_at", "contract",
    "pre_changed_source", "pre_changed", "changes", "untracked",
    "diff_sha256", "diff_bytes", "diff_path", "ignored",
)

FROZEN_SCHEMA = 1


# ------------------------------------------------------------------- path rules
def _norm(path: str) -> str:
    """Repo-relative posix spelling. Git already uses '/' but operators may not."""
    text = str(path).strip().replace("\\", "/")
    while text.startswith("./"):
        text = text[2:]
    return text


def policy_reason(path: str) -> str:
    """Why this path is off-limits *absolutely* - never excused by pre_changed.

    The rules the loop runs under cannot be edited by a candidate, and a dispatch
    snapshot cannot excuse them either: "somebody else changed the policy first" is
    exactly the argument a compromised patch would make.
    """
    rel = _norm(path)
    folded = rel.casefold()
    for pattern in POLICY_PATHS:
        if fnmatch.fnmatchcase(folded, _norm(pattern).casefold()):
            return f"{rel} is a policy path (the loop cannot edit the rules it runs under)"
    if folded == "agents.md" or folded.endswith("/agents.md"):
        return "AGENTS.md is a policy file (append-only, never a candidate's target)"
    return ""


def test_reason(path: str) -> str:
    """Why a *candidate's own edit* to this path is refused: it judges itself.

    This one is excusable by pre_changed, and it has to be. This box carries dozens
    of test files that were already dirty when a cycle started - other lanes' work.
    Treating those as the candidate's edit refused every cycle with 40 forbidden
    paths and made the loop unable to ship anything at all.
    """
    rel = _norm(path)
    folded = rel.casefold()
    parts = [p for p in folded.split("/") if p]
    # Any depth, so "pkg/tests/x.py" is refused as well as "tests/x.py".
    if any(part == "tests" for part in parts[:-1]):
        return f"{rel} is under tests/ - a candidate may not edit the suite that judges it"
    name = parts[-1] if parts else ""
    if name.startswith("conftest"):
        return f"{rel} is a conftest - it can change how every check runs"
    if name.startswith("test_") or name.endswith("_test.py"):
        return f"{rel} is a test module - the check must stay independent of the patch"
    return ""


def forbidden_reason(path: str) -> str:
    """Why this changed path is off-limits even if the contract allows it, or ''."""
    return policy_reason(path) or test_reason(path)


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
        self._excused: Optional[Tuple[set, Tuple[str, ...]]] = None

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

    def _pre_excuse(self) -> Tuple[set, Tuple[str, ...]]:
        """The dirty set as exact paths plus directory roots.

        ``git status --porcelain`` collapses an untracked tree to its directory, so
        a dispatch snapshot legitimately names ``vendor/`` rather than each of the
        ten thousand files under it. A directory entry covers its whole tree - it
        says the tree was dirty before the worker started, which is true whether it
        was listed file by file or not.
        """
        if self._excused is not None:
            return self._excused
        entries = self.pre_changed()
        roots = tuple(sorted(entry for entry in entries
                             if entry.endswith("/") or (self.repo / entry).is_dir()))
        self._excused = (entries, roots)
        return self._excused

    def attributable(self, path: str) -> bool:
        if within_scope(path, self.write_paths()):
            return True
        target = _norm(path).casefold()
        exact, roots = self._pre_excuse()
        if target in exact:
            return False
        for root in roots:
            if target.startswith(root.rstrip("/") + "/"):
                return False
        return True

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
        policy = policy_reason(rel)
        if policy:
            # Never excused, not even by a dispatch snapshot.
            forbidden.append(policy)
            continue
        if not judge.attributable(rel):
            # Already dirty before the candidate started: somebody else's bytes,
            # not the patch on trial. That excuse covers test files too - otherwise
            # another lane's dirty test refused every cycle on this box.
            continue
        check = test_reason(rel)
        if check:
            forbidden.append(check)
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
    patch = {rel: statuses for rel, statuses in changes.items() if judge.attributable(rel)}
    shown = ", ".join(sorted(patch)[:5])
    return {
        "ok": True,
        "gate": "pass",
        "detail": f"{len(GATES)} gates green over {len(patch)} changed path(s): {shown}",
        "commands": list(judge.commands),
    }


def _slug(value: Any) -> str:
    """A filesystem-safe id: ``cand_1`` and ``1`` both name ``cand_1.diff``."""
    text = re.sub(r"[^A-Za-z0-9._-]+", "_", str(value).strip()).strip("._-")
    text = text or "unnamed"
    if text.startswith("cand_") and len(text) > 5:
        text = text[5:]
    return text


def _repo_git(repo: Path) -> Callable[..., Any]:
    """The fallback git runner: read-only questions the artifact does not answer."""
    def call(*args: str) -> subprocess.CompletedProcess:
        return subprocess.run(["git", *[str(a) for a in args]],
                              cwd=str(repo), capture_output=True, text=True)
    return call


def _seal(record: Dict[str, Any]) -> str:
    """sha256 over the frozen fields only, so appending ``scored`` stays legal."""
    canonical = json.dumps({key: record.get(key) for key in FROZEN_FIELDS},
                           sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    """Atomic: a half-written artifact would read as a tampered one."""
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def _diff_bytes(judge: "_Judge", paths: Optional[Sequence[str]] = None) -> bytes:
    """``git diff --binary HEAD`` over the declared paths, with the unborn-HEAD fallback.

    ``--binary`` keeps a binary change base64 in the patch, which is what makes
    the captured bytes ASCII and hashable; the bytes written are the bytes hashed.

    ``paths`` is the candidate's attributable set, and it matters: this box carries
    a 40 MB tracked database that another lane keeps modified, so a diff over the
    whole tree froze 52 MB per candidate. The artifact is meant to answer "what
    exactly is on trial", and a database nobody's patch touched is not on trial.
    ``None`` keeps the old whole-tree behaviour for callers that want it.
    """
    if paths is not None and not paths:
        return b""
    scope = ["--", *[str(path) for path in paths]] if paths is not None else []
    code, text = judge._git_text("diff", "--binary", "HEAD", *scope)
    if code != 0:
        plain_code, plain = judge._git_text("diff", "--binary", *scope)
        staged_code, staged = judge._git_text("diff", "--binary", "--cached", *scope)
        if plain_code != 0 and staged_code != 0:
            raise RuntimeError(f"cannot capture the diff: {(plain or staged).strip()}")
        text = plain + "\n" + staged
    return text.encode("utf-8")


def freeze(*, repo: Path, item_id: str, candidate_id: str, contract: Dict[str, Any],
           pre_changed: Optional[Sequence[str]] = None,
           run: Callable[..., Any] = subprocess.run,
           git: Optional[Callable[..., Any]] = None) -> Dict[str, Any]:
    """Freeze one candidate to disk before it is judged, and return its paths.

    Writes ``state/author/<item_id>/cand_<k>.diff`` (the bytes) and
    ``cand_<k>.json`` (the contract, the diff's sha256, a timestamp, the
    dispatch-time dirty set as ``pre_changed``, and the path set the gates read
    back). The diff is captured against ``HEAD`` and the untracked list comes from
    ``git ls-files --others``; a file that was already dirty at dispatch is
    somebody else's bytes and is not stored as this candidate's change.

    ``pre_changed`` is the dirty set snapshotted *before* the worker was
    dispatched - read from ``contract["pre_changed"]``, or from this same keyword
    when the caller keeps it beside the card. It matters: this box carries
    thousands of untracked files, and only a dispatch-time snapshot can tell them
    apart from the candidate's own additions. Without it, everything outside
    ``write_paths`` is recorded as pre-existing - the honest default when freeze
    cannot know what the tree looked like earlier. A policy path is never excused
    either way.

    Freezing is once per ``(item_id, candidate_id)``: re-freezing identical bytes
    returns the existing artifact, and different bytes are refused rather than
    overwriting evidence.
    """
    repo_path = Path(repo).resolve()
    frozen_contract = dict(contract or {})
    judge = _Judge(frozen_contract, repo_path, run=run, git=git)

    changes = judge.changes()
    if judge.changes_error:
        raise RuntimeError(f"cannot freeze: {judge.changes_error}")

    scope = judge.write_paths()
    code, others = judge._git_text("ls-files", "--others", "--exclude-standard")
    if code != 0:
        raise RuntimeError(f"cannot list untracked files: {(others or '').strip()}")
    untracked = sorted({_norm(line) for line in others.splitlines() if line.strip()})

    if pre_changed is None and isinstance(contract, dict):
        # The card is where the dispatcher puts its snapshot; a kwarg is for callers
        # that keep the dispatch state beside the card.
        pre_changed = contract.get("pre_changed")
    if pre_changed is None:
        source = "freeze-observed"
        raw = [rel for rel in changes
               if not within_scope(rel, scope) and not forbidden_reason(rel)]
    else:
        source = "dispatch"
        raw = [pre_changed] if isinstance(pre_changed, str) else list(pre_changed)
    before = sorted({_norm(str(path)) for path in raw if str(path).strip()})
    frozen_contract["pre_changed"] = before

    # Untracked files are the reason this list is filtered: store the candidate's
    # additions, anything under write_paths, and anything a gate must still see
    # (a policy path). A file that was dirty at dispatch - or under a directory that
    # was - stays out of the artifact, or a ten-thousand-file worktree would be
    # frozen into every candidate.
    untracked_set = set(untracked)
    kept_untracked = [rel for rel in untracked
                      if within_scope(rel, scope) or forbidden_reason(rel)
                      or judge.attributable(rel)]
    tracked = {rel: list(statuses) for rel, statuses in changes.items()
               if rel not in untracked_set}
    # The bytes on trial: this candidate's own changes, never another lane's dirty
    # file. Freezing the whole tree made every artifact 52 MB on this box because a
    # 40 MB tracked database is permanently modified by a parallel lane.
    attributable = sorted({rel for rel in changes if judge.attributable(rel)})

    diff_bytes = _diff_bytes(judge, attributable)
    candidate = _slug(candidate_id)
    directory = repo_path / "state" / "author" / _slug(item_id)
    directory.mkdir(parents=True, exist_ok=True)
    diff_path = directory / f"cand_{candidate}.diff"
    json_path = directory / f"cand_{candidate}.json"

    if diff_path.is_file() and json_path.is_file():
        try:
            previous = json.loads(json_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            previous = None
        if isinstance(previous, dict) and diff_path.read_bytes() == diff_bytes:
            return {"diff": str(diff_path), "json": str(json_path),
                    "diff_sha256": str(previous.get("diff_sha256") or ""),
                    "diff_bytes": int(previous.get("diff_bytes") or 0),
                    "changed": len(previous.get("changes") or {})
                    + len(previous.get("untracked") or []),
                    "pre_changed": len(previous.get("pre_changed") or []),
                    "ignored": bool(previous.get("ignored")), "reused": True}
        raise RuntimeError(
            f"{json_path.name} is already frozen with different content - "
            "a candidate id is never reused (freeze a new one)")

    diff_path.write_bytes(diff_bytes)
    try:
        rel_diff = _norm(diff_path.relative_to(repo_path).as_posix())
    except ValueError:
        rel_diff = _norm(diff_path.as_posix())
    record: Dict[str, Any] = {
        "schema": FROZEN_SCHEMA,
        "item_id": str(item_id),
        "candidate_id": str(candidate_id),
        "frozen_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "contract": frozen_contract,
        "pre_changed_source": source,
        "pre_changed": before,
        "changes": tracked,
        "untracked": kept_untracked,
        "diff_sha256": hashlib.sha256(diff_bytes).hexdigest(),
        "diff_bytes": len(diff_bytes),
        "diff_path": rel_diff,
        "ignored": judge._git_text("check-ignore", "-q", "--", rel_diff)[0] == 0,
    }
    record["payload_sha256"] = _seal(record)
    _write_json(json_path, record)

    return {"diff": str(diff_path), "json": str(json_path),
            "diff_sha256": record["diff_sha256"],
            "diff_bytes": record["diff_bytes"],
            "changed": len(tracked) + len(kept_untracked),
            "pre_changed": len(before), "ignored": record["ignored"],
            "reused": False}


def _frozen_git(record: Dict[str, Any], fallback: Callable[..., Any]) -> Callable[..., Any]:
    """A git runner that answers from the frozen record, not from the worktree.

    ``changes()`` asks two questions - the tracked name-status list and the
    untracked list - so those two are served from disk. Anything else
    (``ls-files`` for basename resolution) is a read-only question the artifact
    never captured and cannot change a verdict into a false pass.
    """
    changes = record.get("changes") or {}
    untracked = [str(path) for path in (record.get("untracked") or [])]

    def shim(*args: str) -> subprocess.CompletedProcess:
        tokens = [str(part) for part in args]
        if tokens[:2] == ["diff", "--name-status"]:
            rows = "".join(f"{(changes[rel] or ['M'])[0]}\t{rel}\n"
                           for rel in sorted(changes))
            return subprocess.CompletedProcess(["git", *tokens], 0, rows, "")
        if tokens[:2] == ["ls-files", "--others"]:
            return subprocess.CompletedProcess(["git", *tokens], 0,
                                               "".join(f"{path}\n" for path in untracked), "")
        return fallback(*args)

    return shim


def _diff_file_for(json_path: Path, record: Dict[str, Any], repo: Path) -> Path:
    """The recorded diff, resolved against the repo, else the sibling ``.diff``."""
    candidates: List[Path] = []
    rel = str(record.get("diff_path") or "").strip()
    if rel:
        candidate = Path(rel)
        candidates.append(candidate if candidate.is_absolute() else Path(repo) / candidate)
    candidates.append(json_path.with_suffix(".diff"))
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return candidates[0]


def _artifact_fail(gate: str, detail: Any) -> Dict[str, Any]:
    return {"ok": False, "gate": gate,
            "detail": " | ".join(line.strip() for line in str(detail).splitlines()
                                 if line.strip())[:2000],
            "commands": []}


# --------------------------------------------------------------- rejection ledger
#: How many rejections on the same material contract, on the same gate, before the
#: item leaves ACTIVE. Three, because one rejection can be noise, two can be a
#: coincidence, and three is a wall the loop keeps walking into.
STRIKE_LIMIT = 3

REJECTION_SCHEMA = 1


def rejections_path(repo: Optional[Path] = None) -> Path:
    """The append-only ledger. ``state/`` is gitignored, so it can never trip a gate."""
    return Path(repo or ROOT) / "state" / "author" / "rejections.jsonl"


def _diff_line(line: str) -> str:
    """Drop CR and trailing spaces; keep indentation and blank lines."""
    return line.replace("\r", "").rstrip(" ")


def patch_identity(diff_bytes: bytes) -> List[Dict[str, Any]]:
    """The diff reduced to what makes two attempts the same question.

    Line numbers, ``@@`` offsets and ``index`` hashes are dropped on purpose: a
    reflowed, rebased or one-line-shifted patch is the same attempt, and a ledger
    that keyed on bytes would let the loop retry a wall by moving it one line down.
    """
    text = diff_bytes.decode("utf-8", "replace")
    files: List[Dict[str, Any]] = []
    current: Optional[Dict[str, Any]] = None
    for raw in text.split("\n"):
        line = _diff_line(raw)
        if line.startswith("diff --git "):
            remainder = line[len("diff --git "):]
            path = remainder.rsplit(" b/", 1)[1] if " b/" in remainder else ""
            current = {"path": _norm(path), "status": "M",
                       "added": [], "removed": [], "context": []}
            files.append(current)
            continue
        if current is None:
            continue
        if line.startswith("new file mode"):
            current["status"] = "A"
            continue
        if line.startswith("deleted file mode"):
            current["status"] = "D"
            continue
        if line.startswith("rename from ") or line.startswith("rename to "):
            current["status"] = "R"
            continue
        if line.startswith("--- "):
            continue
        if line.startswith("+++ "):
            path = line[4:].strip()
            if path and path != "/dev/null":
                if path.startswith("b/"):
                    path = path[2:]
                current["path"] = _norm(path)
            continue
        if (line.startswith("@@") or line.startswith("index ")
                or line.startswith("\\ No newline")
                or line.startswith("old mode") or line.startswith("new mode")
                or line.startswith("similarity index")):
            continue
        if line.startswith("Binary files "):
            continue
        if line.startswith("+"):
            current["added"].append(line[1:])
        elif line.startswith("-"):
            current["removed"].append(line[1:])
        elif line.startswith(" "):
            current["context"].append(line[1:])
        elif line == "":
            current["context"].append("")
        # Anything else is diff metadata this fingerprint deliberately ignores.
    files.sort(key=lambda item: item["path"])
    return files


def attempt_signature(contract: Optional[Dict[str, Any]]) -> str:
    """sha256 over the *material* contract - what must change to be a new question.

    ``diff_sha256``, ``candidate_id``, ``frozen_at``, ``pre_changed``, ``objective``,
    ``timeout_s``, ``model`` and the verdict are all excluded. Two attempts with the
    same write paths, the same acceptance commands and the same pinned check are the
    same attempt, however their bytes differ.
    """
    contract = contract if isinstance(contract, dict) else {}
    paths = sorted({_norm(str(path)).casefold()
                    for path in (contract.get("write_paths") or [])
                    if str(path).strip()})
    commands: List[Any] = []
    for command in contract.get("acceptance_commands") or []:
        if isinstance(command, str):
            commands.append(command)
        elif isinstance(command, (list, tuple)):
            commands.append([str(token) for token in command])
        else:
            commands.append(str(command))
    pin = contract.get("check_sha256")
    if isinstance(pin, dict):
        pin_material: Any = {str(key): str(value) for key, value in pin.items()}
    elif pin:
        pin_material = str(pin)
    else:
        pin_material = None
    material = {"v": 1, "write_paths": paths,
                "acceptance_commands": commands, "check_sha256": pin_material}
    canonical = json.dumps(material, sort_keys=True, separators=(",", ":"),
                           ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def attempt_fingerprint(item_id: Any, contract: Optional[Dict[str, Any]],
                        diff_bytes: bytes) -> str:
    """The identity of one attempt: this item, this contract, these material changes."""
    material = {"v": 1, "item": str(item_id),
                "sig": attempt_signature(contract),
                "files": patch_identity(diff_bytes)}
    canonical = json.dumps(material, sort_keys=True, separators=(",", ":"),
                           ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def row_sha256(row: Dict[str, Any]) -> str:
    """The row's own hash, with ``row_sha256`` itself excluded."""
    body = {key: value for key, value in row.items() if key != "row_sha256"}
    canonical = json.dumps(body, sort_keys=True, separators=(",", ":"),
                           ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def load_rejections(path: Optional[Path] = None) -> Dict[str, Any]:
    """Read the ledger, dropping a torn tail and any row whose chain does not hold.

    A half-written line is what a crash looks like, not what a rejection looks like.
    ``torn`` names it, ``corrupt`` counts rows that failed their own hash and
    ``chain_broken_at`` names the first index whose ``prev`` no longer matches.
    """
    target = Path(path or rejections_path())
    out: Dict[str, Any] = {"rows": [], "torn": False, "corrupt": 0,
                           "chain_broken_at": None, "path": str(target)}
    try:
        raw = target.read_bytes()
    except OSError:
        return out
    if not raw:
        return out
    text = raw.decode("utf-8", "replace")
    lines = text.split("\n")
    if text and not text.endswith("\n"):
        out["torn"] = True
        lines = lines[:-1]
    previous = ""
    for index, line in enumerate(lines):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except ValueError:
            out["corrupt"] += 1
            if index == len(lines) - 1:
                out["torn"] = True
            continue
        if not isinstance(row, dict):
            out["corrupt"] += 1
            continue
        recorded = str(row.get("row_sha256") or "")
        if not recorded or recorded.casefold() != row_sha256(row).casefold():
            out["corrupt"] += 1
            continue
        if str(row.get("prev") or "") != previous:
            out["corrupt"] += 1
            if out["chain_broken_at"] is None:
                out["chain_broken_at"] = len(out["rows"])
            continue
        out["rows"].append(row)
        previous = recorded
    return out


def _sig_rows(item_id: Any, signature: str, path: Optional[Path]) -> List[Dict[str, Any]]:
    ledger = load_rejections(path)
    return [row for row in ledger["rows"]
            if str(row.get("item_id")) == str(item_id)
            and str(row.get("signature") or "").casefold() == str(signature).casefold()]


def rejection_streak(item_id: Any, signature: str, *, gate: Optional[str] = None,
                     path: Optional[Path] = None) -> int:
    """Rejections in the current unbroken run - derived on demand, never accumulated.

    Without ``gate``: the length of the trailing run of rows that share the newest
    row's gate. With ``gate``: what the count *would* be if this gate were recorded
    now - so a different gate resets the run to 1. ``target_red, target_red,
    out_of_scope`` is 1, because a different gate is a different wall.
    """
    rows = _sig_rows(item_id, signature, path)
    if not rows:
        return 0 if gate is None else 1
    newest = str(rows[-1].get("gate") or "")
    trailing = 0
    for row in reversed(rows):
        if str(row.get("gate") or "") != newest:
            break
        trailing += 1
    if gate is None:
        return trailing
    return trailing + 1 if str(gate) == newest else 1


def latest_rejection(item_id: Any, signature: str, *,
                     path: Optional[Path] = None) -> Dict[str, Any]:
    """The newest row for this item and signature, or an empty dict."""
    rows = _sig_rows(item_id, signature, path)
    return rows[-1] if rows else {}


def _truncate_torn_tail(path: Path) -> None:
    """Repair a half-written last line. Valid rows are never rewritten."""
    try:
        raw = path.read_bytes()
    except OSError:
        return
    if not raw or raw.endswith(b"\n"):
        return
    keep = raw.rfind(b"\n")
    path.write_bytes(raw[:keep + 1] if keep >= 0 else b"")


def record_rejection(*, item_id: Any, candidate_id: Any,
                     contract: Optional[Dict[str, Any]], diff_bytes: bytes,
                     gate: str, detail: Any = "", cycle: int = 0,
                     artifact: str = "", payload_sha256: str = "",
                     repo: Optional[Path] = None) -> Dict[str, Any]:
    """Append one rejection row, or return the row already on disk.

    Written only for a real gate (the five that judge the patch) and only once per
    ``(item_id, candidate_id)``. Artifact gates and pre-run skips are not attempts
    and never count - a candidate that could not be read was not judged.
    """
    if str(gate) not in GATES:
        return {}
    path = rejections_path(repo)
    for row in load_rejections(path)["rows"]:
        if (str(row.get("item_id")) == str(item_id)
                and str(row.get("candidate_id")) == str(candidate_id)):
            return row

    signature = attempt_signature(contract)
    fingerprint = attempt_fingerprint(item_id, contract, diff_bytes)
    strike = rejection_streak(item_id, signature, gate=str(gate), path=path)
    ledger = load_rejections(path)
    previous = str(ledger["rows"][-1].get("row_sha256") or "") if ledger["rows"] else ""
    row: Dict[str, Any] = {
        "schema": REJECTION_SCHEMA,
        "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "item_id": str(item_id),
        "candidate_id": str(candidate_id),
        "cycle": int(cycle or 0),
        "gate": str(gate),
        "fingerprint": fingerprint,
        "signature": signature,
        "diff_sha256": hashlib.sha256(diff_bytes).hexdigest(),
        "artifact": str(artifact or ""),
        "payload_sha256": str(payload_sha256 or ""),
        "strike": strike,
        "detail": " ".join(str(detail or "").split())[:2000],
        "prev": previous,
    }
    row["row_sha256"] = row_sha256(row)
    path.parent.mkdir(parents=True, exist_ok=True)
    _truncate_torn_tail(path)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False) + "\n")
        handle.flush()
        os.fsync(handle.fileno())
    return row


def duplicate_rejection(item_id: Any, contract: Optional[Dict[str, Any]],
                        diff_bytes: bytes, *, path: Optional[Path] = None
                        ) -> Dict[str, Any]:
    """A row for this exact attempt, if this attempt was already rejected."""
    fingerprint = attempt_fingerprint(item_id, contract, diff_bytes)
    for row in load_rejections(path)["rows"]:
        if (str(row.get("item_id")) == str(item_id)
                and str(row.get("fingerprint") or "").casefold()
                == fingerprint.casefold()):
            return row
    return {}


def evaluate_frozen(path_to_json: Path, *, repo: Path,
                    run: Callable[..., Any] = subprocess.run,
                    git: Optional[Callable[..., Any]] = None) -> Dict[str, Any]:
    """Re-score a frozen candidate from disk. The same gates, the same contract.

    Nothing here asks the worktree what changed: the name-status list and the
    untracked list are read from the artifact, so the verdict is a function of the
    bytes that were frozen. The acceptance commands still run - that is the gate -
    but a candidate is judged once: the verdict is appended to the artifact and a
    second call answers ``already_scored`` without starting anything.

    Refusals are about the artifact, not the patch: a diff whose sha256 no longer
    matches its record, or a record edited after it was sealed, is
    ``artifact_tampered``. Re-scoring an edited candidate would launder it.
    """
    path = Path(path_to_json)
    if not path.is_file():
        return _artifact_fail("artifact_missing", f"no frozen artifact at {path}")
    try:
        record = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return _artifact_fail("artifact_invalid", f"{path.name} is unreadable: {exc}")
    if not isinstance(record, dict):
        return _artifact_fail("artifact_invalid", f"{path.name} is not a JSON object")
    absent = [field for field in FROZEN_FIELDS if field not in record]
    if absent:
        return _artifact_fail("artifact_invalid",
                              f"{path.name} is missing {', '.join(absent)}")
    sealed = str(record.get("payload_sha256") or "")
    actual = _seal(record)
    if sealed and actual.casefold() != sealed.casefold():
        return _artifact_fail(
            "artifact_tampered",
            f"{path.name} was edited after it was frozen "
            f"(seal is {actual[:12]}, recorded {sealed[:12]})")
    contract = record.get("contract")
    if not isinstance(contract, dict):
        return _artifact_fail("artifact_invalid", f"{path.name} has no usable contract")

    repo_path = Path(repo).resolve()
    diff_path = _diff_file_for(path, record, repo_path)
    if not diff_path.is_file():
        return _artifact_fail("artifact_missing", f"the frozen diff is gone: {diff_path}")
    diff_bytes = diff_path.read_bytes()
    digest = hashlib.sha256(diff_bytes).hexdigest()
    pinned = str(record.get("diff_sha256") or "").strip()
    if not pinned or digest.casefold() != pinned.casefold():
        return _artifact_fail(
            "artifact_tampered",
            f"{diff_path.name} is {digest[:12]}, frozen as {(pinned or '(unpinned)')[:12]}")

    scored = record.get("scored")
    if isinstance(scored, dict) and scored.get("at"):
        return {"ok": bool(scored.get("ok")), "gate": "already_scored",
                "detail": f"already scored at {scored['at']} (gate {scored.get('gate')}); "
                          "a frozen candidate is judged once - freeze the next candidate "
                          "instead of re-running this one",
                "commands": []}

    # A13: the same material attempt, already rejected, is not re-run. The check is
    # after the artifact gates on purpose - an unreadable candidate was never judged,
    # so it can neither be a duplicate nor earn a strike.
    try:
        duplicate = duplicate_rejection(record.get("item_id"), contract, diff_bytes,
                                        path=rejections_path(repo_path))
    except (OSError, ValueError):
        duplicate = {}
    if duplicate:
        detail = (f"this attempt was already rejected at {duplicate.get('at')} "
                  f"(gate {duplicate.get('gate')}, strike {duplicate.get('strike')}): "
                  "the same material change on the same contract, so its checks are "
                  "not run again")
        record["scored"] = {
            "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "ok": False, "gate": "duplicate_rejection",
            "detail": detail, "commands": [],
        }
        _write_json(path, record)
        return {"ok": False, "gate": "duplicate_rejection", "detail": detail,
                "commands": [], "rejection": duplicate}

    verdict = evaluate(contract=contract, repo=repo_path, run=run,
                       git=_frozen_git(record, git or _repo_git(repo_path)))
    record["scored"] = {
        "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "ok": bool(verdict["ok"]),
        "gate": verdict["gate"],
        "detail": verdict["detail"],
        "commands": [{key: command.get(key)
                      for key in ("cmd", "exit", "ok", "seconds")}
                     for command in verdict.get("commands") or []],
    }
    # A13: a real rejection is written once, here, so the strike count survives the
    # process that judged it. Artifact gates are excluded: they judge the record, not
    # the attempt, and a torn file must not be able to park an item.
    if not verdict["ok"] and str(verdict.get("gate")) in GATES:
        try:
            artifact = _norm(path.resolve().relative_to(repo_path).as_posix())
        except (ValueError, OSError):
            artifact = _norm(path.as_posix())
        try:
            cycle = int(contract.get("_cycle") or contract.get("cycle") or 0)
        except (TypeError, ValueError):
            cycle = 0
        try:
            rejection = record_rejection(
                item_id=record.get("item_id"),
                candidate_id=record.get("candidate_id"),
                contract=contract, diff_bytes=diff_bytes,
                gate=str(verdict["gate"]), detail=str(verdict.get("detail") or ""),
                cycle=cycle, artifact=artifact,
                payload_sha256=str(record.get("payload_sha256") or ""),
                repo=repo_path)
        except (OSError, ValueError) as exc:
            rejection = {}
            verdict["rejection_error"] = str(exc)
        if rejection:
            verdict["rejection"] = rejection
    _write_json(path, record)
    return verdict


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Deterministic candidate-patch gates.")
    parser.add_argument("--contract", help="task card JSON (live evaluation, or --freeze)")
    parser.add_argument("--frozen", help="a frozen cand_<k>.json - replay its verdict")
    parser.add_argument("--item", help="queue item id, for --freeze")
    parser.add_argument("--candidate", help="candidate id, for --freeze")
    parser.add_argument("--freeze", action="store_true",
                        help="capture the contract's candidate to state/author/ first")
    parser.add_argument("--repo", default=str(ROOT), help="worktree the diff lives in")
    ns = parser.parse_args(argv)

    if ns.frozen:
        verdict = evaluate_frozen(Path(ns.frozen), repo=Path(ns.repo))
        print(json.dumps(verdict, indent=2))
        return 0 if verdict["ok"] else 1

    if not ns.contract:
        parser.error("--contract is required unless --frozen is given")
    path = Path(ns.contract)
    try:
        contract = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        print(f"contract unreadable: {exc}", file=sys.stderr)
        return 2
    if not isinstance(contract, dict):
        print("contract must be a JSON object", file=sys.stderr)
        return 2

    if ns.freeze:
        if not (ns.item and ns.candidate):
            parser.error("--freeze needs --item and --candidate")
        try:
            frozen = freeze(repo=Path(ns.repo), item_id=ns.item,
                            candidate_id=ns.candidate, contract=contract)
        except RuntimeError as exc:
            print(f"not frozen: {exc}", file=sys.stderr)
            return 2
        print(json.dumps(frozen, indent=2))
        return 0

    verdict = evaluate(contract=contract, repo=Path(ns.repo))
    print(json.dumps(verdict, indent=2))
    return 0 if verdict["ok"] else 1



if __name__ == "__main__":
    raise SystemExit(main())
