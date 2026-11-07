"""A14 / M1f: a write scope comes from a real traceback, never an opinion.

A15 / M1g adds the other half: a *proven* derivation is written into the queue
as a dispatchable contract, atomically, and is refused when the derivation
proved nothing.

Every test uses a throwaway repo and an injected runner, so nothing here runs a
real acceptance command, touches the real queue or writes under the real
``state/``.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

import tys_author as a  # noqa: E402
import tys_launcher  # noqa: E402
import tys_runner as r  # noqa: E402


SOURCE = "Northstar_backend/lib/thing.py"
TESTFILE = "Northstar_backend/test_thing.py"
ITEM = "M1f-scope-deriver"

PYTEST_FAILURE = """\
============================= test session starts =============================
collected 1 item

Northstar_backend/test_thing.py:7: in test_add
    assert add(1, 2) == 4
Northstar_backend/lib/thing.py:4: in add
    return a + b
E   assert 3 == 4
=========================== short test summary info ============================
FAILED Northstar_backend/test_thing.py::test_add - assert 3 == 4
"""

TEST_ONLY_FAILURE = """\
Northstar_backend/test_thing.py:7: in test_add
    assert add(1, 2) == 4
E   assert 3 == 4
"""

POLICY_FAILURE = """\
tools/tys_runner.py:11: in helper
scripts/continuous_loop.py:3: in step
scripts/ty_task_runner.py:5: in tick
Northstar_backend/tests/test_helper.py:2: in helper
.venv/Lib/site-packages/pkg/mod.py:3: in vendored
Northstar_backend/lib/thing.py:4: in add
E   TypeError: boom
"""


class _Proc:
    def __init__(self, returncode=1, stdout="", stderr=""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def _runner(output, returncode=1, channel="stdout"):
    calls = []

    def run(cmd, **kwargs):
        calls.append((cmd, kwargs))
        return _Proc(returncode, **{channel: output})

    run.calls = calls
    return run


def _traceback(repo, frames):
    lines = ["Traceback (most recent call last):"]
    for rel, line, func in frames:
        lines.append(f'  File "{repo / rel}", line {line}, in {func}')
        lines.append("    return add(1, 'x')")
    lines.append("TypeError: unsupported operand type(s) for +: 'int' and 'str'")
    return "\n".join(lines) + "\n"


@pytest.fixture()
def repo(tmp_path):
    files = {
        SOURCE: "def add(a, b):\n    return a + b\n",
        TESTFILE: "from lib.thing import add\n\ndef test_add():\n    assert add(1, 2) == 4\n",
        "tools/tys_runner.py": "print('harness')\n",
        "scripts/continuous_loop.py": "print('loop')\n",
        "scripts/ty_task_runner.py": "print('task')\n",
        "AGENTS.md": "# capsule\n",
        "Northstar_backend/tests/test_helper.py": "def helper():\n    pass\n",
        ".venv/Lib/site-packages/pkg/mod.py": "def vendored():\n    pass\n",
    }
    for rel, body in files.items():
        path = tmp_path / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding="utf-8")
    return tmp_path


def test_a_source_frame_becomes_a_write_path_and_the_command_runs_once(repo):
    run = _runner(PYTEST_FAILURE)
    out = a.derive(
        item_id=ITEM,
        acceptance_commands=[["python", "-m", "pytest", "-q", TESTFILE]],
        run=run,
        repo=repo,
    )

    assert out["ok"] is True
    assert out["reason"] == "scope_derived"
    assert out["write_paths"] == [SOURCE]
    assert len(run.calls) == 1, "the acceptance command runs exactly once"

    artifact = Path(out["artifact"])
    assert artifact.is_file()
    payload = json.loads(artifact.read_text(encoding="utf-8"))
    assert payload["failing_command"][-1] == TESTFILE
    assert payload["write_paths"] == [SOURCE]
    assert payload["returncode"] == 1
    # The trimmed traceback keeps the source frame, not the test frame.
    assert payload["traceback"] == ["Northstar_backend/lib/thing.py:4: in add"]
    assert payload["frames"][0]["path"] == SOURCE


def test_a_test_only_traceback_proves_nothing_and_writes_nothing(repo):
    out = a.derive(
        item_id="test-only",
        acceptance_commands=[["python", "-m", "pytest", "-q", TESTFILE]],
        run=_runner(TEST_ONLY_FAILURE),
        repo=repo,
    )

    assert out["ok"] is False
    assert out["reason"] == "scope_unproven"
    assert out["write_paths"] == []
    assert out["artifact"] == ""
    assert not (repo / "state").exists(), "a refused scope writes no artifact"


def test_policy_test_and_vendored_paths_are_never_writable(repo):
    out = a.derive(
        item_id=ITEM,
        acceptance_commands=[["python", "-m", "pytest", "-q", TESTFILE]],
        run=_runner(POLICY_FAILURE),
        repo=repo,
    )

    assert out["ok"] is True
    assert out["write_paths"] == [SOURCE]
    payload = json.loads(Path(out["artifact"]).read_text(encoding="utf-8"))
    reasons = {row["file"]: row["reason"] for row in payload["dropped_frames"]}
    assert reasons["tools/tys_runner.py"] == "policy"
    assert reasons["scripts/continuous_loop.py"] == "policy"
    assert reasons["scripts/ty_task_runner.py"] == "policy"
    assert reasons["Northstar_backend/tests/test_helper.py"] == "tests"
    assert reasons[".venv/Lib/site-packages/pkg/mod.py"] == "stdlib"


@pytest.mark.parametrize("rel,reason", [
    ("AGENTS.md", "policy"),
    ("conftest.py", "policy"),
    ("tools/tys_author.py", "policy"),
    ("tools/tys_evaluator.py", "policy"),
    ("scripts/continuous_loop.py", "policy"),
    ("scripts/ty_task_runner.py", "policy"),
    ("Northstar_backend/tests/test_x.py", "tests"),
    ("Northstar_backend/test_x.py", "tests"),
    ("Northstar_backend/lib/thing_test.py", "tests"),
    ("./.venv/Lib/site-packages/pkg/mod.py", "stdlib"),
    (".gitignore", None),
    ("Northstar_backend/lib/thing.py", None),
])
def test_the_policy_classifier_is_exact(rel, reason):
    assert a._reason_excluded(rel) == reason


def test_the_sha_is_computed_for_the_test_file_the_command_names(repo):
    expected = hashlib.sha256((repo / TESTFILE).read_bytes()).hexdigest()
    cmd = ["python", "-m", "pytest", "-q", f"{TESTFILE}::test_add"]

    out = a.derive(item_id=ITEM, acceptance_commands=[cmd],
                   run=_runner(PYTEST_FAILURE), repo=repo)
    assert out["check_sha256"] == expected

    payload = json.loads(Path(out["artifact"]).read_text(encoding="utf-8"))
    assert payload["check_sha256"] == expected
    assert payload["check_file"] == TESTFILE

    # The evaluator's tamper gate only works if the value moves when the check does.
    (repo / TESTFILE).write_text("# rewritten\n", encoding="utf-8")
    again = a.derive(item_id="tampered", acceptance_commands=[cmd],
                     run=_runner(PYTEST_FAILURE), repo=repo)
    assert again["check_sha256"] != expected


def test_a_check_file_outside_the_repo_is_not_a_tamper_gate(repo):
    outside = repo.parent / "outside_test.py"
    outside.write_text("# not part of the repo\n", encoding="utf-8")
    cmd = ["python", "-m", "pytest", "-q", f"..{os.sep}outside_test.py"]

    out = a.derive(item_id="escape-check", acceptance_commands=[cmd],
                   run=_runner(PYTEST_FAILURE), repo=repo)

    assert out["check_sha256"] is None


def test_a_non_pytest_command_still_derives_a_scope(repo):
    output = _traceback(repo, [
        ("<frozen importlib._bootstrap>", 241, "_call_with_frames_removed"),
        (SOURCE, 4, "add"),
    ])
    out = a.derive(
        item_id="non-pytest",
        acceptance_commands=[["python", "Northstar_backend/scripts/probe.py"]],
        run=_runner(output),
        repo=repo,
    )

    assert out["ok"] is True
    assert out["write_paths"] == [SOURCE]
    assert out["check_sha256"] is None, "no test file named, so no tamper gate"
    payload = json.loads(Path(out["artifact"]).read_text(encoding="utf-8"))
    assert payload["check_file"] is None
    assert payload["dropped_frames"], "the unresolvable entry frame is recorded"


def test_a_non_pytest_command_refuses_when_only_non_source_frames_fail(repo):
    output = _traceback(repo, [
        (".venv/Lib/site-packages/pkg/mod.py", 3, "vendored"),
    ])
    out = a.derive(
        item_id="non-pytest-refused",
        acceptance_commands=[["python", "Northstar_backend/scripts/probe.py"]],
        run=_runner(output),
        repo=repo,
    )

    assert out["ok"] is False
    assert out["reason"] == "scope_unproven"
    assert not (repo / "state").exists()


def test_a_green_acceptance_command_is_not_a_scope(repo):
    out = a.derive(
        item_id="already-green",
        acceptance_commands=[["python", "-m", "pytest", "-q", TESTFILE]],
        run=_runner("1 passed in 0.02s\n", returncode=0),
        repo=repo,
    )

    assert out["ok"] is False
    assert out["reason"] == "acceptance_passed"
    assert not (repo / "state").exists()


def test_an_item_id_cannot_escape_the_artifact_root(repo):
    out = a.derive(
        item_id="../../escape",
        acceptance_commands=[["python", "-m", "pytest", "-q", TESTFILE]],
        run=_runner(PYTEST_FAILURE),
        repo=repo,
    )

    artifact = Path(out["artifact"]).resolve()
    assert artifact.is_file()
    assert artifact.parent.parent == (repo / "state" / "author").resolve()


# ------------------------------------------------------------ A15: contract writer
def _queue(repo, **item):
    path = repo / "reports" / "ty" / "autonomy_queue.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    row = {"id": ITEM, "status": "pending", "priority": 1140,
           "title": "Write the authored contract", "workstream": "automation"}
    row.update(item)
    path.write_text(json.dumps({"schema_version": 2, "cycle": 37,
                                "items": [row]}, indent=2), encoding="utf-8")
    return path


def _derived(repo, item_id=ITEM):
    return a.derive(
        item_id=item_id,
        acceptance_commands=[["python", "-m", "pytest", "-q", TESTFILE]],
        run=_runner(PYTEST_FAILURE),
        repo=repo,
    )


def test_a_derived_scope_turns_the_item_runnable(repo):
    derived = _derived(repo)
    assert derived["ok"] is True, derived["reason"]
    # A planned scope with no check is exactly what the deriver exists to fix:
    # the launcher cannot dispatch it, and says so.
    path = _queue(repo, write_paths=[SOURCE],
                  needs_author="no acceptance_commands declared",
                  blocked_reason="targets_dirty: lib/thing.py")

    before_item = json.loads(path.read_text(encoding="utf-8"))["items"][0]
    assert tys_launcher.runnable(before_item) == (False, "no acceptance_commands declared")
    assert r.validate_contract(before_item) == ["no acceptance_commands declared"]

    out = a.write_contract(queue_path=path, item_id=ITEM, derived=derived,
                           objective="make add(1, 2) return 3")
    assert out["ok"] is True, out
    assert out["reason"] == "contract_written"
    assert out["problems"] == []

    written = json.loads(path.read_text(encoding="utf-8"))["items"][0]
    assert tys_launcher.runnable(written) == (True, "")
    assert r.validate_contract(written) == []
    assert written["write_paths"] == [SOURCE]
    assert written["acceptance_commands"] == [
        ["python", "-m", "pytest", "-q", TESTFILE]]
    assert written["objective"] == "make add(1, 2) return 3"
    assert written["check_sha256"] == derived["check_sha256"]
    assert written["scope_derivation"] == derived["artifact"]
    assert written["forbidden_paths"] == [TESTFILE], "the graded test file is off limits"
    assert not written.get("needs_author")
    assert not written.get("blocked_reason")
    assert out["write_paths"] == written["write_paths"]


def test_an_unproven_derivation_writes_nothing(repo):
    # A real derivation that failed on the traceback, not on the contract layer.
    refused = a.derive(
        item_id=ITEM,
        acceptance_commands=[["python", "-m", "pytest", "-q", TESTFILE]],
        run=_runner(TEST_ONLY_FAILURE),
        repo=repo,
    )
    assert refused["ok"] is False and refused["reason"] == "scope_unproven"

    path = _queue(repo)
    before = path.read_text(encoding="utf-8")
    out = a.write_contract(queue_path=path, item_id=ITEM, derived=refused,
                           objective="fix the thing")
    assert out["ok"] is False
    assert out["reason"] == "scope_not_derived"
    assert out["write_paths"] == []
    assert path.read_text(encoding="utf-8") == before, "a refused contract writes nothing"
    assert not path.with_suffix(".json.tmp").exists()

    # Even a derivation claiming success cannot invent paths it does not carry.
    empty = {"ok": True, "write_paths": [], "check_sha256": None,
             "artifact": "", "reason": "scope_derived"}
    out = a.write_contract(queue_path=path, item_id=ITEM, derived=empty,
                           objective="fix the thing")
    assert out["ok"] is False
    assert out["reason"] == "scope_unproven"
    assert path.read_text(encoding="utf-8") == before

    # And a derivation for a different item still has to name one in the queue.
    out = a.write_contract(queue_path=path, item_id="not-in-the-queue",
                           derived=_derived(repo), objective="fix the thing")
    assert out["ok"] is False and out["reason"] == "item_not_found"
    assert path.read_text(encoding="utf-8") == before


def test_a_shell_string_command_is_rejected(repo):
    derived = _derived(repo)
    assert derived["ok"] is True
    path = _queue(repo)
    before = path.read_text(encoding="utf-8")

    forged = dict(derived, acceptance_commands=f"python -m pytest -q {TESTFILE}")
    out = a.write_contract(queue_path=path, item_id=ITEM, derived=forged,
                           objective="fix the thing")
    assert out["ok"] is False
    assert out["reason"] == "shell_string_command"
    assert path.read_text(encoding="utf-8") == before

    problems = r.validate_contract({
        "id": ITEM,
        "write_paths": [SOURCE],
        "acceptance_commands": [f"python -m pytest -q {TESTFILE}"],
    })
    assert any("shell string" in p for p in problems), problems

    problems = r.validate_contract({
        "id": ITEM,
        "write_paths": [SOURCE],
        "acceptance_commands": [["python", "-c", "print(1); import os"]],
    })
    assert any("shell operators" in p for p in problems), problems


def test_the_atomic_write_leaves_a_valid_json_queue(repo):
    derived = _derived(repo)
    path = _queue(repo)
    queue = json.loads(path.read_text(encoding="utf-8"))
    queue["items"].append({"id": "other", "status": "done", "priority": 1})
    path.write_text(json.dumps(queue, indent=2), encoding="utf-8")

    out = a.write_contract(queue_path=path, item_id=ITEM, derived=derived,
                           objective="fix the thing",
                           read_paths=[SOURCE, "Northstar_backend/test_thing.py"])
    assert out["ok"] is True

    reloaded = json.loads(path.read_text(encoding="utf-8"))
    assert reloaded["cycle"] == 37, "a contract write never rewrites the loop's bookkeeping"
    assert reloaded["items"][1] == {"id": "other", "status": "done", "priority": 1}
    assert reloaded["items"][0]["read_paths"] == [SOURCE, TESTFILE]
    assert not path.with_suffix(".json.tmp").exists(), "the tmp file is renamed, not left"
    assert sorted(p.name for p in path.parent.iterdir()) == ["autonomy_queue.json"]
