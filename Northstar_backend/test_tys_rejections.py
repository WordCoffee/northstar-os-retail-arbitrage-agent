"""A13 - the rejection ledger: fingerprints, strikes, parks and revival.

The ledger exists so the loop stops walking into the same wall. Three properties
are what make it worth having, and each has a test:

* identity is *material*, not bytes - a reflowed or shifted patch is the same
  attempt, so the ledger cannot be beaten by moving a line;
* the count is *derived* from an append-only chain, never accumulated in the
  queue, so a hand-edited queue cannot un-park itself;
* the stop is a **status change**, because a deferral is soft by design and
  ``select_next`` would happily pick the item again.

Every test drives a real temporary git repository: the fingerprint reads real
``git diff`` bytes, and mocking that would test the mock.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

import tys_evaluator as E  # noqa: E402
import tys_runner as r  # noqa: E402


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
    git(repo, "add", "-A", "-f")
    staged = subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=str(repo))
    if staged.returncode != 0:
        git(repo, "commit", "-q", "-m", message)


@pytest.fixture(autouse=True)
def isolated_git_config(tmp_path: Path, monkeypatch) -> None:
    blank = tmp_path / "empty_gitconfig"
    blank.write_text("", encoding="utf-8")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(blank))
    monkeypatch.setenv("GIT_CONFIG_SYSTEM", str(blank))


@pytest.fixture()
def repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    (root / "pkg").mkdir(parents=True)
    (root / "pkg" / "mod.py").write_text("VALUE = 1\n", encoding="utf-8")
    # The ledger and the loop's own state are ignored, exactly as in production,
    # so freezing a candidate never makes the artifact itself look like a change.
    (root / ".gitignore").write_text("state/\nreports/\n", encoding="utf-8")
    git(root, "init", "-q")
    for key, value in (("user.email", "tester@example.test"), ("user.name", "tester"),
                       ("commit.gpgsign", "false"), ("core.autocrlf", "false")):
        git(root, "config", key, value)
    commit(root, "base")
    return root


class FakeRun:
    """An injected command runner: no process is ever started."""

    def __init__(self, codes=(0,)) -> None:
        self.codes = list(codes)
        self.calls = []

    def __call__(self, cmd, cwd=None, timeout=None, capture_output=True, text=True, **kw):
        self.calls.append([str(part) for part in cmd])
        code = self.codes.pop(0) if len(self.codes) > 1 else (self.codes[0] if self.codes else 0)
        return subprocess.CompletedProcess(cmd, code, "ran\n", "" if code == 0 else "boom\n")


def card(**extra):
    payload = {
        "id": "item",
        "write_paths": ["pkg/mod.py"],
        "acceptance_commands": [["python", "-c", "pass"]],
        "_cycle": 1,
        # The launcher always sends a dispatch snapshot; an empty one means "the
        # tree was clean when this candidate started", which is what lets the scope
        # gate judge the candidate's own additions instead of excusing them.
        "pre_changed": [],
    }
    payload.update(extra)
    return payload


def ledger(repo: Path):
    return E.rejections_path(repo)


def rows(repo: Path):
    return E.load_rejections(ledger(repo))["rows"]


def judge(repo: Path, candidate: str, contract=None, value: str = "2", code: int = 1):
    """Write a change, freeze it, and score it - the real path, injected runner."""
    contract = contract or card()
    (repo / "pkg" / "mod.py").write_text(f"VALUE = {value}\n", encoding="utf-8")
    frozen = E.freeze(repo=repo, item_id=str(contract.get("id") or "item"),
                      candidate_id=candidate, contract=contract)
    return E.evaluate_frozen(Path(frozen["json"]), repo=repo, run=FakeRun([code]))


@pytest.fixture()
def loop(repo: Path, monkeypatch):
    """A temp queue the runner reads, with every path redirected like production."""
    (repo / "reports" / "ty").mkdir(parents=True, exist_ok=True)
    (repo / "state" / "tys_runner").mkdir(parents=True, exist_ok=True)
    queue = {"phase": "C", "cycle": 1, "items": [dict(card(status="pending"))]}
    (repo / "reports" / "ty" / "autonomy_queue.json").write_text(
        json.dumps(queue), encoding="utf-8")
    monkeypatch.setattr(r, "ROOT", repo)
    monkeypatch.setattr(r, "QUEUE", repo / "reports" / "ty" / "autonomy_queue.json")
    monkeypatch.setattr(r, "STATE_DIR", repo / "state" / "tys_runner")
    monkeypatch.setattr(r, "LEDGER", repo / "state" / "tys_runner" / "ledger.json")
    monkeypatch.setattr(r, "LEASE", repo / "state" / "tys_runner" / "lease.json")
    monkeypatch.setattr(r, "CHECKPOINT", repo / "state" / "tys_runner" / "checkpoint.json")
    monkeypatch.setattr(r, "SESSIONS", repo / "state" / "tys_runner" / "sessions.jsonl")
    monkeypatch.setattr(r, "HANDOFF", repo / "reports" / "ty" / "cycle_handoff.json")
    monkeypatch.setattr(r, "STOP", repo / "STOP")
    return repo


def item_of(repo: Path) -> dict:
    return next(i for i in r.load_queue()["items"] if i["id"] == "item")


# ------------------------------------------------------------------ 1, 12: dedupe
def test_identical_diff_is_a_duplicate_and_runs_nothing(repo):
    first = judge(repo, "1", value="2")
    assert first["gate"] == "target_red"
    assert len(rows(repo)) == 1

    # The same bytes under a second candidate id: a fresh artifact, the same attempt.
    run = FakeRun([1])
    frozen = E.freeze(repo=repo, item_id="item", candidate_id="2",
                      contract=card())
    second = E.evaluate_frozen(Path(frozen["json"]), repo=repo, run=run)

    assert second["gate"] == "duplicate_rejection"
    assert run.calls == []
    assert len(rows(repo)) == 1


def test_a_duplicate_is_scored_once(repo):
    judge(repo, "1", value="2")
    frozen = E.freeze(repo=repo, item_id="item", candidate_id="2", contract=card())
    again = E.evaluate_frozen(Path(frozen["json"]), repo=repo, run=FakeRun([1]))
    assert again["gate"] == "duplicate_rejection"

    third = E.evaluate_frozen(Path(frozen["json"]), repo=repo, run=FakeRun([1]))
    assert third["gate"] == "already_scored"


# ------------------------------------------------------------ 2: normalisation
BASE_DIFF = (
    "diff --git a/pkg/mod.py b/pkg/mod.py\n"
    "index 1111111..2222222 100644\n"
    "--- a/pkg/mod.py\n"
    "+++ b/pkg/mod.py\n"
    "@@ -1,2 +1,2 @@\n"
    "-VALUE = 1\n"
    "+VALUE = 2\n"
    " keep\n"
)


def test_crlf_reflow_and_base_shift_are_the_same_fingerprint():
    original = BASE_DIFF
    crlf = BASE_DIFF.replace("\n", "\r\n")
    reflowed = BASE_DIFF.replace(" keep\n", " keep   \n").replace("+VALUE = 2\n",
                                                                 "+VALUE = 2    \n")
    shifted = BASE_DIFF.replace("@@ -1,2 +1,2 @@", "@@ -10,2 +10,2 @@")

    fingerprints = {E.attempt_fingerprint("item", card(), text.encode("utf-8"))
                    for text in (original, crlf, reflowed, shifted)}
    assert len(fingerprints) == 1


def test_a_different_line_is_a_different_attempt(repo):
    judge(repo, "1", value="2")
    calls_before = len(rows(repo))

    second = judge(repo, "2", value="3")
    assert second["gate"] == "target_red", "a different line must be judged, not deduped"
    assert len(rows(repo)) == calls_before + 1


# ----------------------------------------------------------------- 4, 7: strikes
def test_three_target_red_park_the_item(repo, loop):
    for strike, value in enumerate(("2", "3", "4"), start=1):
        verdict = judge(repo, str(strike), value=value)
        assert verdict["gate"] == "target_red"
        assert verdict["rejection"]["strike"] == strike

    report = r.reconcile_parks(repo=repo, apply=True)
    assert report["parked"] == [{"id": "item", "gate": "target_red", "streak": 3}]

    item = item_of(repo)
    assert item["status"] == "needs_author"
    assert item["needs_author"] == "rejection_cap:target_red x3"
    assert item["parked_signature"] == E.attempt_signature(item)
    assert item["defer_until_cycle"] is None


def test_a_parked_item_never_reaches_the_worker(repo, loop):
    for strike, value in enumerate(("2", "3", "4"), start=1):
        judge(repo, str(strike), value=value)
    r.reconcile_parks(repo=repo, apply=True)

    assert r.select_next() is None
    assert r.reconcile_parks(repo=repo, apply=False)["parked"] == []


def test_a_different_gate_resets_the_run(repo, loop):
    judge(repo, "1", value="2")
    judge(repo, "2", value="3")

    # A change outside the declared scope: the scope gate fires first, and it is a
    # different wall, so the run restarts at one.
    (repo / "pkg" / "other.py").write_text("X = 1\n", encoding="utf-8")
    (repo / "pkg" / "mod.py").write_text("VALUE = 4\n", encoding="utf-8")
    frozen = E.freeze(repo=repo, item_id="item", candidate_id="3", contract=card())
    verdict = E.evaluate_frozen(Path(frozen["json"]), repo=repo, run=FakeRun([1]))
    assert verdict["gate"] == "out_of_scope"
    assert verdict["rejection"]["strike"] == 1

    assert r.reconcile_parks(repo=repo, apply=True)["parked"] == []


# ------------------------------------------------------------- 6: torn tail
def test_a_torn_tail_is_dropped_and_append_still_works(repo):
    judge(repo, "1", value="2")
    path = ledger(repo)
    with path.open("a", encoding="utf-8") as handle:
        handle.write('{"schema": 1, "item_id": "it')

    loaded = E.load_rejections(path)
    assert len(loaded["rows"]) == 1
    assert loaded["torn"] is True

    judge(repo, "2", value="3")
    loaded = E.load_rejections(path)
    assert len(loaded["rows"]) == 2
    assert loaded["torn"] is False
    assert loaded["rows"][1]["prev"] == loaded["rows"][0]["row_sha256"]


# ---------------------------------------------------------------- 9: deferral
def test_a_deferral_does_not_change_the_count(repo, loop):
    for strike, value in enumerate(("2", "3", "4"), start=1):
        judge(repo, str(strike), value=value)

    queue = r.load_queue()
    item = next(i for i in queue["items"] if i["id"] == "item")
    item["defer_until_cycle"] = 99
    r._write(r.QUEUE, queue)

    signature = E.attempt_signature(item_of(repo))
    assert E.rejection_streak("item", signature,
                              path=ledger(repo)) == 3
    assert r.reconcile_parks(repo=repo, apply=True)["parked"][0]["streak"] == 3


# ------------------------------------------------------- 8: revival on change
def test_only_a_contract_change_revives_a_parked_item(repo, loop):
    for strike, value in enumerate(("2", "3", "4"), start=1):
        judge(repo, str(strike), value=value)
    r.reconcile_parks(repo=repo, apply=True)
    assert item_of(repo)["status"] == "needs_author"

    # Rewriting the identical contract, or bumping the write time, is not a change.
    queue = r.load_queue()
    item = next(i for i in queue["items"] if i["id"] == "item")
    item["contract_written_at"] = "2099-01-01T00:00:00+00:00"
    r._write(r.QUEUE, queue)
    assert r.reconcile_parks(repo=repo, apply=True)["revived"] == []
    assert item_of(repo)["status"] == "needs_author"

    # The acceptance command is material: a new check is a new question.
    queue = r.load_queue()
    item = next(i for i in queue["items"] if i["id"] == "item")
    item["acceptance_commands"] = [["python", "-c", "raise SystemExit(0)"]]
    r._write(r.QUEUE, queue)

    revived = r.reconcile_parks(repo=repo, apply=True)["revived"]
    assert revived and revived[0]["id"] == "item"
    revived_item = item_of(repo)
    assert revived_item["status"] == "pending"
    assert "needs_author" not in revived_item
    assert "parked_signature" not in revived_item


# --------------------------------------------------- 10, 13: signature identity
def test_the_queue_item_and_the_frozen_contract_share_a_signature(repo):
    contract = card()
    (repo / "pkg" / "mod.py").write_text("VALUE = 2\n", encoding="utf-8")
    frozen = E.freeze(repo=repo, item_id="item", candidate_id="1", contract=contract)

    record = json.loads(Path(frozen["json"]).read_text(encoding="utf-8"))
    queue_item = dict(card(status="pending"))
    assert E.attempt_signature(queue_item) == E.attempt_signature(record["contract"])


def test_a_different_check_pin_is_a_different_signature():
    plain = E.attempt_signature(card())
    pinned = E.attempt_signature(card(check_sha256={"pkg/mod.py": "a" * 64}))
    repinned = E.attempt_signature(card(check_sha256={"pkg/mod.py": "b" * 64}))
    assert len({plain, pinned, repinned}) == 3


# ----------------------------------------------------- 11: artifact gates never count
def test_artifact_gates_never_earn_a_strike(repo, tmp_path):
    missing = E.evaluate_frozen(tmp_path / "nope.json", repo=repo)
    assert missing["gate"] == "artifact_missing"
    assert rows(repo) == []

    (repo / "pkg" / "mod.py").write_text("VALUE = 2\n", encoding="utf-8")
    frozen = E.freeze(repo=repo, item_id="item", candidate_id="1", contract=card())
    Path(frozen["diff"]).write_bytes(b"tampered\n")

    tampered = E.evaluate_frozen(Path(frozen["json"]), repo=repo)
    assert tampered["gate"] == "artifact_tampered"
    assert rows(repo) == []


def test_a_rejection_row_carries_its_evidence(repo):
    verdict = judge(repo, "1", value="2")
    row = rows(repo)[0]

    assert row["gate"] == "target_red"
    assert row["item_id"] == "item"
    assert row["candidate_id"] == "1"
    assert row["cycle"] == 1
    frozen_diff = (repo / row["artifact"]).with_suffix(".diff").read_bytes()
    assert row["fingerprint"] == E.attempt_fingerprint("item", card(), frozen_diff)
    assert row["detail"]
    assert row["diff_sha256"] == verdict["rejection"]["diff_sha256"]
