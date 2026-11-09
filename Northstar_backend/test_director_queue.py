"""D3 - the queue store: scope manifests, overlap serialisation, worktrees, merges.

The pass evidence for D3 is behavioural, not structural: two parallel builders on
disjoint scopes merge cleanly, and an overlap is serialised. Both are proven here
against a real temporary git repository, with gates that really run.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

import director_queue as DQ  # noqa: E402


def git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    env = {**os.environ, "GIT_AUTHOR_NAME": "tester",
           "GIT_AUTHOR_EMAIL": "tester@example.test",
           "GIT_COMMITTER_NAME": "tester",
           "GIT_COMMITTER_EMAIL": "tester@example.test"}
    return subprocess.run(["git", *args], cwd=str(repo), capture_output=True,
                          text=True, env=env)


@pytest.fixture(autouse=True)
def isolated_git_config(tmp_path, monkeypatch):
    blank = tmp_path / "empty_gitconfig"
    blank.write_text("", encoding="utf-8")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(blank))
    monkeypatch.setenv("GIT_CONFIG_SYSTEM", str(blank))


@pytest.fixture()
def repo(tmp_path, monkeypatch):
    root = tmp_path / "repo"
    (root / "pkg").mkdir(parents=True)
    (root / "pkg" / "base.py").write_text("VALUE = 1\n", encoding="utf-8")
    # State and reports are ignored: the queue store lives inside the repo, and a
    # `git add -A` in a builder branch would otherwise commit (and later delete) the
    # very database the test is asserting on.
    (root / ".gitignore").write_text("state/\nreports/\n", encoding="utf-8")
    git(root, "init", "-q")
    for key, value in (("user.email", "tester@example.test"), ("user.name", "tester"),
                       ("commit.gpgsign", "false"), ("core.autocrlf", "false")):
        git(root, "config", key, value)
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", "base")

    mirror = root / "reports" / "ty" / "director_queue.json"
    mirror.parent.mkdir(parents=True)
    mirror.write_text(json.dumps({"units": {"D3": {"status": "pending"}}, "jobs": []}),
                      encoding="utf-8")
    for name, value in {
        "ROOT": root,
        "DB": root / "state" / "director" / "queue.sqlite",
        "MIRROR": mirror,
        "WORKTREES": root / "state" / "worktrees",
    }.items():
        monkeypatch.setattr(DQ, name, value)
    # A queue test must never depend on this machine's free RAM. Tests that care
    # about the gate pass their own `governor=` callable.
    monkeypatch.setattr(DQ, "DEFAULT_GOVERNOR",
                        lambda: {"paused": False, "free_gb": 8.0,
                                 "max_builders": 4, "reason": "test stub"})
    return root


def _job(repo: Path, job_id: str, paths, acceptance=()):
    return DQ.add_job(unit="D3", title=f"job {job_id}", write_paths=paths,
                      acceptance=acceptance, job_id=job_id)


# ------------------------------------------------------------------- manifests
def test_a_directory_manifest_covers_its_tree():
    assert DQ.paths_conflict(["northstar-os-ui/src"], ["northstar-os-ui/src/App.tsx"])
    assert DQ.paths_conflict(["pkg/"], ["pkg/mod.py"])
    assert not DQ.paths_conflict(["pkg/mod.py"], ["pkg/other.py"])
    assert not DQ.paths_conflict(["a/b"], ["a/bc"])


def test_two_claims_on_the_same_path_are_serialised(repo):
    _job(repo, "wide", ["pkg/"])
    _job(repo, "narrow", ["pkg/mod.py"])

    assert DQ.claim("wide", "builder-1")["ok"] is True
    refused = DQ.claim("narrow", "builder-2")

    assert refused["ok"] is False
    assert refused["reason"] == "scope_overlap"
    assert refused["conflicts"][0]["id"] == "wide"


def test_disjoint_scopes_both_claim(repo):
    _job(repo, "left", ["northstar-os-ui/src/a"])
    _job(repo, "right", ["Northstar_backend/b"])

    assert DQ.claim("left", "builder-1")["ok"] is True
    assert DQ.claim("right", "builder-2")["ok"] is True


def test_a_job_cannot_be_claimed_twice(repo):
    _job(repo, "once", ["pkg/x.py"])
    assert DQ.claim("once", "builder-1")["ok"] is True

    again = DQ.claim("once", "builder-2")
    assert again["ok"] is False
    assert again["reason"].startswith("not_claimable")


def test_the_mirror_carries_the_jobs_for_resume(repo):
    _job(repo, "mirrored", ["pkg/x.py"])
    data = json.loads(DQ.MIRROR.read_text(encoding="utf-8"))
    assert [row["id"] for row in data["jobs"]] == ["mirrored"]
    assert data["units"]["D3"]["status"] == "pending"   # units are not clobbered


# -------------------------------------------------------------------- RAM gate
def _governor(paused: bool, free_gb: float = 8.0):
    return lambda: {"paused": paused, "free_gb": free_gb,
                    "max_builders": 0 if paused else 4,
                    "reason": f"free RAM {free_gb:.2f} GB (test)"}


def test_a_paused_governor_refuses_a_builder_claim(repo):
    """A job nobody can run is not handed back as a claim."""
    _job(repo, "starved", ["pkg/x.py"])

    out = DQ.claim("starved", "builder-1", governor=_governor(True, 0.7))

    assert out["ok"] is False
    assert out["reason"] == "ram_paused"
    assert out["free_gb"] == 0.7
    assert DQ.job("starved")["status"] == "queued"


def test_an_unpaused_governor_lets_the_claim_through(repo):
    _job(repo, "roomy", ["pkg/y.py"])

    out = DQ.claim("roomy", "builder-1", governor=_governor(False, 6.0))

    assert out["ok"] is True
    assert DQ.job("roomy")["status"] == "claimed"


def test_a_unit_that_needs_no_builder_claims_while_paused(repo):
    """Bookkeeping and verification work do not occupy a builder lane."""
    data = json.loads(DQ.MIRROR.read_text(encoding="utf-8"))
    data["units"]["D3"]["needs_builder"] = False
    DQ.MIRROR.write_text(json.dumps(data), encoding="utf-8")
    _job(repo, "bookkeeping", ["pkg/z.py"])

    out = DQ.claim("bookkeeping", "operator-1", governor=_governor(True, 0.5))

    assert out["ok"] is True
    assert DQ.job("bookkeeping")["status"] == "claimed"


def test_a_paused_refusal_leaves_the_job_for_later(repo):
    """Refusal is not a status change: an unpaused governor can still claim it."""
    _job(repo, "later", ["pkg/later.py"])

    assert DQ.claim("later", "builder-1", governor=_governor(True))["reason"] == "ram_paused"
    assert DQ.claim("later", "builder-1", governor=_governor(False))["ok"] is True


# ---------------------------------------------------------------------- merges
def _default_branch(repo: Path) -> str:
    for name in ("main", "master"):
        if git(repo, "rev-parse", "--verify", name).returncode == 0:
            return name
    return "HEAD"


def _branch_with_change(repo: Path, job_id: str, rel: str, text: str) -> None:
    git(repo, "checkout", "-q", "-b", f"ty/{job_id}", "HEAD")
    target = repo / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")
    git(repo, "add", "--", rel)
    git(repo, "commit", "-q", "-m", f"{job_id} work")


def test_two_parallel_builders_on_disjoint_scopes_merge_cleanly(repo):
    _job(repo, "one", ["pkg/one.py"])
    _job(repo, "two", ["pkg/two.py"])
    assert DQ.claim("one", "builder-1")["ok"] and DQ.claim("two", "builder-2")["ok"]

    _branch_with_change(repo, "one", "pkg/one.py", "ONE = 1\n")
    _branch_with_change(repo, "two", "pkg/two.py", "TWO = 2\n")
    git(repo, "checkout", "-q", _default_branch(repo))

    assert DQ.ensure_staging()["ok"] is True
    DQ.set_status("one", "ready")
    DQ.set_status("two", "ready")

    first = DQ.merge("one", gates=[["python", "-c", "import sys; sys.exit(0)"]])
    second = DQ.merge("two", gates=[["python", "-c", "import sys; sys.exit(0)"]])

    assert first["ok"] is True, first
    assert second["ok"] is True, second
    assert (repo / "pkg" / "one.py").exists() and (repo / "pkg" / "two.py").exists()
    assert {row["id"]: row["status"] for row in DQ.jobs()} == {"one": "merged",
                                                               "two": "merged"}


def test_a_failing_gate_reverts_the_merge(repo):
    _job(repo, "bad", ["pkg/bad.py"])
    DQ.claim("bad", "builder-1")
    _branch_with_change(repo, "bad", "pkg/bad.py", "BAD = 1\n")
    DQ.ensure_staging()
    before = git(repo, "rev-parse", "staging").stdout.strip()
    DQ.set_status("bad", "ready")

    out = DQ.merge("bad", gates=[["python", "-c", "import sys; sys.exit(1)"]])

    assert out["ok"] is False and out["reason"] == "gates_failed"
    assert git(repo, "rev-parse", "staging").stdout.strip() == before
    assert DQ.job("bad")["status"] == "rejected"


def test_main_is_never_moved_without_the_verifier(repo):
    _job(repo, "prod", ["pkg/prod.py"])
    DQ.claim("prod", "builder-1")

    out = DQ.merge("prod", into="main")

    assert out["ok"] is False and out["reason"] == "protected_branch"
    assert "verifier" in out["detail"]


# ------------------------------------------------------------------- worktrees
def test_a_builder_gets_its_own_worktree(repo):
    added = DQ.worktree_add("builder-1")

    assert added["ok"] is True, added
    names = [Path(row["worktree"]).name for row in DQ.worktrees()]
    assert "builder-1" in names
    assert DQ.worktree_remove("builder-1", force=True)["ok"] is True
