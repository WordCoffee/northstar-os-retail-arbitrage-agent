"""Tests for tools/tys_evaluator.py - deterministic gates, no model verdicts.

Every scope and well-formedness case drives a **real** temporary git repository, so
the git plumbing is exercised rather than mocked. Only the acceptance-command
runner is injected, because a test must never shell out to a real pytest or probe:
the fake records the argv it was handed and returns a chosen exit code.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

import tys_evaluator as E  # noqa: E402


# ------------------------------------------------------------------- fixtures
def git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    env = {**os.environ,
           "GIT_AUTHOR_NAME": "tester", "GIT_AUTHOR_EMAIL": "tester@example.test",
           "GIT_COMMITTER_NAME": "tester", "GIT_COMMITTER_EMAIL": "tester@example.test"}
    proc = subprocess.run(["git", *args], cwd=str(repo), capture_output=True,
                          text=True, env=env)
    assert proc.returncode == 0, f"git {' '.join(args)} failed: {proc.stderr}"
    return proc


def commit(repo: Path, message: str = "change") -> None:
    # -f makes the fixture immune to a machine-wide ignore rule that happened to
    # match "state/" or "tools/": what the test says is committed, is committed.
    git(repo, "add", "-A", "-f")
    staged = subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=str(repo))
    if staged.returncode != 0:
        git(repo, "commit", "-q", "-m", message)


@pytest.fixture(autouse=True)
def isolated_git_config(tmp_path: Path, monkeypatch) -> None:
    """No global/system gitconfig: a user's exclude file must not change these tests."""
    blank = tmp_path / "empty_gitconfig"
    blank.write_text("", encoding="utf-8")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(blank))
    monkeypatch.setenv("GIT_CONFIG_SYSTEM", str(blank))


@pytest.fixture()
def repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    (root / "pkg").mkdir(parents=True)
    (root / "pkg" / "mod.py").write_text("VALUE = 1\n", encoding="utf-8")
    git(root, "init", "-q")
    for key, value in (("user.email", "tester@example.test"), ("user.name", "tester"),
                       ("commit.gpgsign", "false"), ("core.autocrlf", "false")):
        git(root, "config", key, value)
    commit(root, "base")
    return root


class FakeRun:
    """An injected command runner: no process is ever started."""

    def __init__(self, codes=(0,), timeout: bool = False) -> None:
        self.codes = list(codes)
        self.timeout = timeout
        self.calls = []

    def __call__(self, cmd, cwd=None, timeout=None, capture_output=True, text=True, **kw):
        self.calls.append([str(part) for part in cmd])
        if self.timeout:
            raise subprocess.TimeoutExpired(cmd, timeout or 1)
        code = self.codes.pop(0) if len(self.codes) > 1 else (self.codes[0] if self.codes else 0)
        return subprocess.CompletedProcess(cmd, code, "ran\n", "" if code == 0 else "boom\n")


def card(write_paths, commands=(("python", "-c", "pass"),), **extra):
    payload = {
        "id": "cand",
        "write_paths": list(write_paths),
        "acceptance_commands": [list(entry) for entry in commands],
    }
    payload.update(extra)
    return payload


# ----------------------------------------------------------------- scope + shape
def test_clean_diff_passes(repo):
    (repo / "pkg" / "mod.py").write_text("VALUE = 2\n", encoding="utf-8")
    runner = FakeRun([0])

    verdict = E.evaluate(contract=card(["pkg/mod.py"]), repo=repo, run=runner)

    assert verdict["ok"] is True, verdict
    assert verdict["gate"] == "pass"
    assert runner.calls == [["python", "-c", "pass"]]
    assert verdict["commands"][0]["exit"] == 0


def test_change_outside_write_paths_is_out_of_scope(repo):
    (repo / "pkg" / "mod.py").write_text("VALUE = 2\n", encoding="utf-8")
    (repo / "elsewhere.py").write_text("X = 1\n", encoding="utf-8")
    runner = FakeRun([0])

    verdict = E.evaluate(contract=card(["pkg/mod.py"]), repo=repo, run=runner)

    assert verdict["ok"] is False
    assert verdict["gate"] == "out_of_scope"
    assert "elsewhere.py" in verdict["detail"]
    assert runner.calls == [], "scope is judged before anything is executed"


def test_change_to_a_test_file_is_out_of_scope(repo):
    (repo / "tests").mkdir()
    (repo / "tests" / "test_thing.py").write_text("def test_x():\n    assert True\n",
                                                 encoding="utf-8")
    # Declared as writable on purpose: the policy override must beat the scope.
    runner = FakeRun([0])

    verdict = E.evaluate(contract=card(["tests/test_thing.py", "pkg/mod.py"]),
                         repo=repo, run=runner)

    assert verdict["ok"] is False
    assert verdict["gate"] == "out_of_scope"
    assert "tests/" in verdict["detail"]
    assert runner.calls == []


def test_policy_path_is_refused_even_when_declared(repo):
    (repo / "tools").mkdir()
    (repo / "tools" / "tys_runner.py").write_text("# proposal\n", encoding="utf-8")
    runner = FakeRun([0])

    verdict = E.evaluate(contract=card(["tools/tys_runner.py"]), repo=repo, run=runner)

    assert verdict["gate"] == "out_of_scope"
    assert "policy path" in verdict["detail"]


def test_empty_diff_is_malformed(repo):
    runner = FakeRun([0])

    verdict = E.evaluate(contract=card(["pkg/mod.py"]), repo=repo, run=runner)

    assert verdict["ok"] is False
    assert verdict["gate"] == "malformed"
    assert "empty" in verdict["detail"]
    assert runner.calls == []


def test_pre_changed_paths_are_not_blamed_on_the_candidate(repo):
    """Parallel lanes leave other people's files dirty; those are not this patch."""
    (repo / "pkg" / "mod.py").write_text("VALUE = 2\n", encoding="utf-8")
    (repo / "other_lane.py").write_text("X = 1\n", encoding="utf-8")

    strict = E.evaluate(contract=card(["pkg/mod.py"]), repo=repo, run=FakeRun([0]))
    assert strict["gate"] == "out_of_scope"

    tolerant = E.evaluate(contract=card(["pkg/mod.py"], pre_changed=["other_lane.py"]),
                          repo=repo, run=FakeRun([0]))
    assert tolerant["ok"] is True, tolerant


def test_pre_changed_never_excuses_a_policy_path(repo):
    (repo / "AGENTS.md").write_text("payload\n", encoding="utf-8")

    verdict = E.evaluate(contract=card(["pkg/mod.py"], pre_changed=["AGENTS.md"]),
                         repo=repo, run=FakeRun([0]))

    assert verdict["gate"] == "out_of_scope"
    assert "AGENTS.md" in verdict["detail"]


def test_deletion_inside_scope_is_well_formed(repo):
    (repo / "pkg" / "mod.py").unlink()

    verdict = E.evaluate(contract=card(["pkg/mod.py"]), repo=repo, run=FakeRun([0]))

    assert verdict["ok"] is True, verdict
    assert verdict["gate"] == "pass"


def test_staged_change_counts(repo):
    (repo / "pkg" / "mod.py").write_text("VALUE = 3\n", encoding="utf-8")
    git(repo, "add", "pkg/mod.py")

    verdict = E.evaluate(contract=card(["pkg/mod.py"]), repo=repo, run=FakeRun([0]))

    assert verdict["ok"] is True, verdict


# ------------------------------------------------------------------ target green
def test_failing_command_is_target_red(repo):
    (repo / "pkg" / "mod.py").write_text("VALUE = 2\n", encoding="utf-8")
    runner = FakeRun([1])

    verdict = E.evaluate(contract=card(["pkg/mod.py"]), repo=repo, run=runner)

    assert verdict["ok"] is False
    assert verdict["gate"] == "target_red"
    assert "exit 1" in verdict["detail"]
    assert "boom" in verdict["detail"]
    assert verdict["commands"][0]["ok"] is False


def test_second_command_failing_is_target_red(repo):
    (repo / "pkg" / "mod.py").write_text("VALUE = 2\n", encoding="utf-8")
    runner = FakeRun([0, 2])

    verdict = E.evaluate(
        contract=card(["pkg/mod.py"],
                      commands=[["python", "-c", "pass"], ["python", "-c", "raise"]]),
        repo=repo, run=runner)

    assert verdict["gate"] == "target_red"
    assert len(runner.calls) == 2
    assert verdict["commands"][1]["exit"] == 2


def test_timeout_is_target_red(repo):
    (repo / "pkg" / "mod.py").write_text("VALUE = 2\n", encoding="utf-8")
    runner = FakeRun(timeout=True)

    verdict = E.evaluate(contract=card(["pkg/mod.py"]), repo=repo, run=runner)

    assert verdict["gate"] == "target_red"
    assert verdict["commands"][0]["exit"] == 124
    assert "timeout" in verdict["detail"]


def test_no_acceptance_commands_is_target_red(repo):
    (repo / "pkg" / "mod.py").write_text("VALUE = 2\n", encoding="utf-8")
    runner = FakeRun([0])
    contract = card(["pkg/mod.py"])
    contract["acceptance_commands"] = []

    verdict = E.evaluate(contract=contract, repo=repo, run=runner)

    assert verdict["gate"] == "target_red"
    assert "no acceptance_commands" in verdict["detail"]
    assert runner.calls == []


# ------------------------------------------------------------ check not tampered
def _pinned_probe(repo: Path) -> str:
    """A committed check script, hashed the way a contract would pin it."""
    probe = repo / "state" / "probes" / "check.py"
    probe.parent.mkdir(parents=True)
    probe.write_text("print('green')\n", encoding="utf-8")
    commit(repo, "add probe")
    return hashlib.sha256(probe.read_bytes()).hexdigest()


def test_touching_the_pinned_check_is_check_tampered(repo):
    digest = _pinned_probe(repo)
    (repo / "state" / "probes" / "check.py").write_text("print('green')  # edited\n",
                                                       encoding="utf-8")

    verdict = E.evaluate(
        contract=card(["state/probes/check.py"],
                      commands=[["python", "state/probes/check.py"]],
                      check_sha256=digest),
        repo=repo, run=FakeRun([0]))

    assert verdict["ok"] is False
    assert verdict["gate"] == "check_tampered"
    assert "check.py" in verdict["detail"]


def test_untouched_pinned_check_passes(repo):
    digest = _pinned_probe(repo)
    (repo / "pkg" / "mod.py").write_text("VALUE = 2\n", encoding="utf-8")

    verdict = E.evaluate(
        contract=card(["pkg/mod.py", "state/probes/check.py"],
                      commands=[["python", "state/probes/check.py"]],
                      check_sha256=digest),
        repo=repo, run=FakeRun([0]))

    assert verdict["ok"] is True, verdict


def test_pin_with_no_named_file_fails_closed(repo):
    (repo / "pkg" / "mod.py").write_text("VALUE = 2\n", encoding="utf-8")
    digest = hashlib.sha256(b"whatever").hexdigest()

    verdict = E.evaluate(
        contract=card(["pkg/mod.py"], commands=[["python", "-c", "pass"]],
                      check_sha256=digest),
        repo=repo, run=FakeRun([0]))

    assert verdict["gate"] == "check_tampered"
    assert "cannot be verified" in verdict["detail"]


def test_pin_resolves_the_named_file_by_basename(repo):
    digest = _pinned_probe(repo)
    (repo / "state" / "probes" / "check.py").write_text("print('edited')\n",
                                                       encoding="utf-8")

    verdict = E.evaluate(
        contract=card(["state/probes/check.py"], commands=[["python", "check.py"]],
                      check_sha256=digest),
        repo=repo, run=FakeRun([0]))

    assert verdict["gate"] == "check_tampered", verdict
    assert "check.py" in verdict["detail"]


# --------------------------------------------------------------------- regression
def _idlist_repo(repo: Path, ids, status=None) -> None:
    """Commit the baseline and the idlist so neither shows up as a change."""
    (repo / "tests").mkdir()
    (repo / "tests" / "BASELINE_TESTS.json").write_text(
        json.dumps({"schema": 1, "count": 3,
                    "tests": ["a::b", "c::d", "e::f"]}), encoding="utf-8")
    (repo / "state").mkdir()
    (repo / "state" / "run.json").write_text(
        json.dumps({"ids": ids, "status": status or {name: "passed" for name in ids}}),
        encoding="utf-8")
    commit(repo, "baseline + idlist")


def test_regression_gate_is_green_when_ids_are_kept(repo):
    ids = ["a::b", "c::d", "e::f"]
    _idlist_repo(repo, ids)
    (repo / "pkg" / "mod.py").write_text("VALUE = 2\n", encoding="utf-8")

    verdict = E.evaluate(contract=card(["pkg/mod.py"], idlist="state/run.json"),
                         repo=repo, run=FakeRun([0]))

    assert verdict["ok"] is True, verdict


def test_regression_gate_flags_a_removed_test(repo):
    _idlist_repo(repo, ["a::b", "c::d"])
    (repo / "pkg" / "mod.py").write_text("VALUE = 2\n", encoding="utf-8")

    verdict = E.evaluate(contract=card(["pkg/mod.py"], idlist="state/run.json"),
                         repo=repo, run=FakeRun([0]))

    assert verdict["ok"] is False
    assert verdict["gate"] == "regression"
    assert "e::f" in verdict["detail"]


def test_missing_idlist_fails_closed(repo):
    (repo / "pkg" / "mod.py").write_text("VALUE = 2\n", encoding="utf-8")

    verdict = E.evaluate(contract=card(["pkg/mod.py"], idlist="state/absent.json"),
                         repo=repo, run=FakeRun([0]))

    assert verdict["gate"] == "regression"
    assert "not found" in verdict["detail"]
