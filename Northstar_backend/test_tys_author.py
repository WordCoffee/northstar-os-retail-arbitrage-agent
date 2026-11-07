"""A14 / M1f: a write scope comes from a real traceback, never an opinion.

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
