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
    # The production rule (A12), so a frozen artifact written into the repo is not
    # itself an untracked change that trips the next candidate's scope gate.
    (root / ".gitignore").write_text("state/author/\n", encoding="utf-8")
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


def test_a_pre_changed_test_file_is_not_blamed_on_the_candidate(repo):
    """The box carries dozens of other lanes' dirty test files.

    Measured on the real repo: one cycle was refused with 40 forbidden paths, all of
    them test modules that were already dirty at dispatch. A candidate's *own* edit
    to a test is still refused (see test_change_to_a_test_file_is_out_of_scope).
    """
    (repo / "pkg" / "test_mod.py").write_text("def test_x():\n    assert True\n",
                                              encoding="utf-8")
    (repo / "pkg" / "mod.py").write_text("VALUE = 2\n", encoding="utf-8")

    strict = E.evaluate(contract=card(["pkg/mod.py"]), repo=repo, run=FakeRun([0]))
    assert strict["gate"] == "out_of_scope", strict

    tolerant = E.evaluate(
        contract=card(["pkg/mod.py"], pre_changed=["pkg/test_mod.py"]),
        repo=repo, run=FakeRun([0]))
    assert tolerant["ok"] is True, tolerant


def test_pre_changed_never_excuses_a_policy_path(repo):
    (repo / "AGENTS.md").write_text("payload\n", encoding="utf-8")

    verdict = E.evaluate(contract=card(["pkg/mod.py"], pre_changed=["AGENTS.md"]),
                         repo=repo, run=FakeRun([0]))

    assert verdict["gate"] == "out_of_scope"
    assert "AGENTS.md" in verdict["detail"]


def test_a_pre_changed_directory_covers_its_tree(repo):
    """`git status --porcelain` collapses an untracked tree to its directory.

    A dispatch snapshot that names `vendor/` means everything under it was dirty
    before the worker started, so none of it is this candidate's change.
    """
    (repo / "vendor").mkdir()
    (repo / "vendor" / "dep.py").write_text("X = 1\n", encoding="utf-8")
    (repo / "pkg" / "mod.py").write_text("VALUE = 2\n", encoding="utf-8")

    verdict = E.evaluate(contract=card(["pkg/mod.py"], pre_changed=["vendor"]),
                         repo=repo, run=FakeRun([0]))

    assert verdict["gate"] == "pass", verdict


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


# ------------------------------------------------- frozen artifacts (A12 / M1d)
def _frozen_record(frozen) -> dict:
    return json.loads(Path(frozen["json"]).read_text(encoding="utf-8"))


def _without_wall_clock(verdict: dict) -> dict:
    """The verdict minus its stopwatch: seconds are evidence, not identity.

    Two runs of the same command on the same bytes must agree on every judgement;
    the elapsed time is the one field that legitimately differs between them.
    """
    copy = json.loads(json.dumps(verdict))
    for command in copy.get("commands") or []:
        command["seconds"] = 0.0
    return copy


def test_freeze_then_evaluate_frozen_gives_the_same_verdict(repo):
    (repo / "pkg" / "mod.py").write_text("VALUE = 2\n", encoding="utf-8")
    (repo / "pkg" / "added.py").write_text("NEW = 1\n", encoding="utf-8")
    contract = card(["pkg/mod.py", "pkg/added.py"], pre_changed=[])

    live = E.evaluate(contract=contract, repo=repo, run=FakeRun([0]))
    frozen = E.freeze(repo=repo, item_id="A12", candidate_id="1", contract=contract)
    replay = E.evaluate_frozen(frozen["json"], repo=repo, run=FakeRun([0]))

    assert live["gate"] == "pass", live
    assert replay["gate"] == "pass", replay
    assert _without_wall_clock(replay) == _without_wall_clock(live)
    assert Path(frozen["diff"]).is_file() and Path(frozen["json"]).is_file()
    assert _frozen_record(frozen)["diff_sha256"] == frozen["diff_sha256"]
    # The artifact holds the patch itself, not a summary of it.
    assert "VALUE = 2" in Path(frozen["diff"]).read_text(encoding="utf-8")


def test_freeze_names_its_artifacts_cand_k(repo):
    (repo / "pkg" / "mod.py").write_text("VALUE = 2\n", encoding="utf-8")

    frozen = E.freeze(repo=repo, item_id="M1d-artifacts", candidate_id="cand_2",
                      contract=card(["pkg/mod.py"]))

    assert Path(frozen["diff"]).name == "cand_2.diff"
    assert Path(frozen["json"]).name == "cand_2.json"
    assert Path(frozen["json"]).parent.name == "M1d-artifacts"
    record = _frozen_record(frozen)
    assert record["schema"] == E.FROZEN_SCHEMA
    assert record["candidate_id"] == "cand_2"
    assert record["frozen_at"].endswith("Z")
    assert record["changes"] == {"pkg/mod.py": ["M"]}
    assert record["diff_bytes"] == Path(frozen["diff"]).stat().st_size


def test_scoring_one_frozen_candidate_twice_is_already_scored(repo):
    (repo / "pkg" / "mod.py").write_text("VALUE = 2\n", encoding="utf-8")
    frozen = E.freeze(repo=repo, item_id="A12", candidate_id="2",
                      contract=card(["pkg/mod.py"], pre_changed=[]))

    first = E.evaluate_frozen(frozen["json"], repo=repo, run=FakeRun([0]))
    second_runner = FakeRun([0])
    second = E.evaluate_frozen(frozen["json"], repo=repo, run=second_runner)

    assert first["gate"] == "pass", first
    assert second["gate"] == "already_scored"
    assert second["ok"] is True
    assert second["commands"] == []
    assert second_runner.calls == [], "a candidate that was already judged runs nothing"
    assert _frozen_record(frozen)["scored"]["gate"] == "pass"


def test_a_second_score_does_not_launder_a_failure(repo):
    (repo / "pkg" / "mod.py").write_text("VALUE = 2\n", encoding="utf-8")
    frozen = E.freeze(repo=repo, item_id="A12", candidate_id="3",
                      contract=card(["pkg/mod.py"], pre_changed=[]))

    first = E.evaluate_frozen(frozen["json"], repo=repo, run=FakeRun([1]))
    second = E.evaluate_frozen(frozen["json"], repo=repo, run=FakeRun([0]))

    assert first["gate"] == "target_red"
    assert second["gate"] == "already_scored"
    assert second["ok"] is False, "re-running must not turn a red verdict green"


def test_a_tampered_frozen_diff_is_refused(repo):
    (repo / "pkg" / "mod.py").write_text("VALUE = 2\n", encoding="utf-8")
    frozen = E.freeze(repo=repo, item_id="A12", candidate_id="4",
                      contract=card(["pkg/mod.py"], pre_changed=[]))
    diff = Path(frozen["diff"])
    diff.write_text(diff.read_text(encoding="utf-8").replace("VALUE = 2", "VALUE = 999"),
                    encoding="utf-8")
    runner = FakeRun([0])

    verdict = E.evaluate_frozen(frozen["json"], repo=repo, run=runner)

    assert verdict["ok"] is False
    assert verdict["gate"] == "artifact_tampered"
    assert "cand_4.diff" in verdict["detail"]
    assert runner.calls == [], "a tampered artifact is refused before anything runs"
    assert "scored" not in _frozen_record(frozen)


def test_an_edited_frozen_record_is_refused(repo):
    (repo / "pkg" / "mod.py").write_text("VALUE = 2\n", encoding="utf-8")
    frozen = E.freeze(repo=repo, item_id="A12", candidate_id="5",
                      contract=card(["pkg/mod.py"], pre_changed=[]))
    path = Path(frozen["json"])
    record = json.loads(path.read_text(encoding="utf-8"))
    record["contract"]["write_paths"] = ["pkg/mod.py", "pkg/everything.py"]
    path.write_text(json.dumps(record), encoding="utf-8")

    verdict = E.evaluate_frozen(path, repo=repo, run=FakeRun([0]))

    assert verdict["gate"] == "artifact_tampered"
    assert "edited after it was frozen" in verdict["detail"]


def test_a_missing_frozen_diff_is_refused(repo):
    (repo / "pkg" / "mod.py").write_text("VALUE = 2\n", encoding="utf-8")
    frozen = E.freeze(repo=repo, item_id="A12", candidate_id="6",
                      contract=card(["pkg/mod.py"]))
    Path(frozen["diff"]).unlink()

    verdict = E.evaluate_frozen(frozen["json"], repo=repo, run=FakeRun([0]))

    assert verdict["gate"] == "artifact_missing"
    assert "diff is gone" in verdict["detail"]


def test_pre_changed_is_not_attributed_but_policy_paths_still_are(repo):
    (repo / "AGENTS.md").write_text("the rules\n", encoding="utf-8")
    commit(repo, "policy file")
    (repo / "pkg" / "mod.py").write_text("VALUE = 2\n", encoding="utf-8")
    (repo / "other_lane.py").write_text("X = 1\n", encoding="utf-8")
    (repo / "AGENTS.md").write_text("the rules, rewritten by the worker\n", encoding="utf-8")
    contract = card(["pkg/mod.py"], pre_changed=["other_lane.py", "AGENTS.md"])

    frozen = E.freeze(repo=repo, item_id="A12", candidate_id="7", contract=contract)
    record = _frozen_record(frozen)
    assert record["pre_changed"] == ["AGENTS.md", "other_lane.py"]
    assert record["pre_changed_source"] == "dispatch"
    assert "other_lane.py" not in record["untracked"]

    verdict = E.evaluate_frozen(frozen["json"], repo=repo, run=FakeRun([0]))

    assert verdict["gate"] == "out_of_scope"
    assert "AGENTS.md" in verdict["detail"], "a policy path is never excused"
    assert "policy" in verdict["detail"]
    assert "other_lane.py" not in verdict["detail"], "another lane's file is not this patch"


def test_freeze_without_a_snapshot_records_the_foreign_dirty_set(repo):
    """Freeze cannot know the earlier tree, so it names what is not this candidate's."""
    (repo / "pkg" / "mod.py").write_text("VALUE = 2\n", encoding="utf-8")
    (repo / "other_lane.py").write_text("X = 1\n", encoding="utf-8")

    frozen = E.freeze(repo=repo, item_id="A12", candidate_id="8",
                      contract=card(["pkg/mod.py"]))
    record = _frozen_record(frozen)

    assert record["pre_changed_source"] == "freeze-observed"
    assert record["pre_changed"] == ["other_lane.py"]
    assert E.evaluate_frozen(frozen["json"], repo=repo,
                             run=FakeRun([0]))["gate"] == "pass"


def test_a_candidate_id_is_never_refrozen_over_new_bytes(repo):
    (repo / "pkg" / "mod.py").write_text("VALUE = 2\n", encoding="utf-8")
    E.freeze(repo=repo, item_id="A12", candidate_id="9", contract=card(["pkg/mod.py"]))
    (repo / "pkg" / "mod.py").write_text("VALUE = 3\n", encoding="utf-8")

    with pytest.raises(RuntimeError, match="already frozen"):
        E.freeze(repo=repo, item_id="A12", candidate_id="9",
                 contract=card(["pkg/mod.py"]))


def test_frozen_artifacts_never_trip_the_next_candidates_scope(repo):
    """The whole point of the .gitignore rule: artifacts are evidence, not changes."""
    (repo / "pkg" / "mod.py").write_text("VALUE = 2\n", encoding="utf-8")
    frozen = E.freeze(repo=repo, item_id="A12", candidate_id="10",
                      contract=card(["pkg/mod.py"]))
    assert frozen["ignored"] is True

    (repo / "pkg" / "next.py").write_text("NEXT = 1\n", encoding="utf-8")
    verdict = E.evaluate(contract=card(["pkg/next.py"], pre_changed=["pkg/mod.py"]),
                         repo=repo, run=FakeRun([0]))

    assert verdict["gate"] == "pass", verdict
    listed = git(repo, "ls-files", "--others", "--exclude-standard").stdout
    assert "state/author" not in listed
    assert "pkg/next.py" in listed


def test_the_repository_ignores_frozen_artifacts():
    root = Path(__file__).resolve().parents[1]
    rules = [line.strip() for line in
             (root / ".gitignore").read_text(encoding="utf-8").splitlines()]
    assert "state/author/" in rules

