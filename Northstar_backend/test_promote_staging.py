"""Item 5 — the promotion gates refuse by name, and only tag when all three pass.

Every test works in its own throwaway git repository under tmp_path. Nothing here reads or
writes the real `main`: the tool is pointed at the scratch repo with `--repo`.
"""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

TOOL = Path(__file__).resolve().parents[1] / "tools" / "promote_staging.py"

COMMIT_DATE = "2026-11-09T12:00:00+00:00"
COMMIT_EPOCH = int(datetime.fromisoformat(COMMIT_DATE).timestamp())
STAMP = "20261109"


def git(repo: Path, *args: str) -> str:
    env = {
        "GIT_AUTHOR_DATE": COMMIT_DATE,
        "GIT_COMMITTER_DATE": COMMIT_DATE,
        "GIT_AUTHOR_NAME": "item5-test",
        "GIT_AUTHOR_EMAIL": "item5@test.invalid",
        "GIT_COMMITTER_NAME": "item5-test",
        "GIT_COMMITTER_EMAIL": "item5@test.invalid",
    }
    proc = subprocess.run(["git", *args], cwd=str(repo), capture_output=True, text=True,
                          env={**_base_env(), **env})
    assert proc.returncode == 0, f"git {' '.join(args)}: {proc.stderr}"
    return proc.stdout.strip()


def _base_env() -> dict:
    import os
    env = dict(os.environ)
    env.setdefault("GIT_CONFIG_NOSYSTEM", "1")
    return env


def write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def write_suite(repo: Path, *, green: bool = True, ids: list[str] | None = None,
                offset_seconds: int = 60) -> None:
    """offset_seconds is relative to the commit time: positive is newer = not stale."""
    summary = ("7067 passed, 117 skipped, 2 xfailed, 17 warnings in 1129.35s (0:18:49)"
               if green else
               "7060 passed, 7 failed, 117 skipped in 1129.35s (0:18:49)")
    report = write(repo / "reports/ty" / f"_fullsuite_final_{STAMP}.txt", "....\n" + summary + "\n")
    import os
    stamp = COMMIT_EPOCH + offset_seconds
    os.utime(report, (stamp, stamp))

    base = ["a.py::test_a", "b.py::test_b"]
    run_ids = base if ids is None else ids
    write(repo / "reports/ty/_idlist_20261107.txt",
          json.dumps({"ids": base, "status": {i: "passed" for i in base}}))
    write(repo / "reports/ty" / f"_idlist_{STAMP}.txt", json.dumps({"ids": run_ids}))
    # keep the run idlist newer than the baseline so the newest-mtime fallbacks are stable
    os.utime(repo / "reports/ty" / f"_idlist_{STAMP}.txt", (stamp, stamp))


def write_verifier(repo: Path, *, failed_units: list[str] | None = None,
                   agree: bool = True) -> None:
    failed_units = failed_units or []
    rows = ["| # | item | verdict | one-line evidence |", "|---|---|---|---|",
            "| 1 | Scorecards reproduce | **agree** | 0 diffs |"]
    for index, unit in enumerate(failed_units, start=2):
        rows.append(f"| {index} | {unit} bake-off | **FAILED** | artefacts absent |")
    if not agree:
        rows[2] = "| 1 | Scorecards reproduce | **FAILED** | cannot reproduce |"
    write(repo / "reports/ty/d15_verification.md", "\n".join(rows) + "\n")
    write(repo / "reports/ty/verifier_findings.json", json.dumps({
        "failed": [{"unit": u, "item": f"{u} work", "why": "not reproducible"} for u in failed_units],
        "blocked": [],
    }))
    write(repo / "ty/scorecards.json", json.dumps({
        "at": COMMIT_DATE, "bar": 85.0, "test_ids": 2,
        "services": [{"id": "listings", "score": 90.0, "meets_bar": True},
                     {"id": "adpilot", "score": 55.0, "meets_bar": False}],
        "at_bar": ["listings"],
    }))


def make_repo(tmp_path: Path, *, staging_paths: dict[str, str] | None = None,
              commit_subject: str = "feat: ordinary backend change") -> Path:
    repo = tmp_path / "scratch"
    repo.mkdir()
    git(repo, "init", "-b", "main")
    write(repo / "README.md", "scratch\n")
    write(repo / "northstar_backend/app.py", "print('hi')\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-m", "base")

    git(repo, "checkout", "-b", "staging")
    default = {"northstar_backend/app.py": "print('hi')\n\n# staging change\n"}
    for rel, text in (staging_paths or default).items():
        write(repo / rel, text)
    git(repo, "add", "-A")
    git(repo, "commit", "-m", commit_subject)
    return repo


def run_tool(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(TOOL), "--repo", str(repo), *args],
        cwd=str(repo), capture_output=True, text=True,
    )


# ----------------------------------------------------------------------- gate 1


def test_a_stale_suite_run_refuses_by_name(tmp_path):
    repo = make_repo(tmp_path)
    write_suite(repo, offset_seconds=-3600)          # written an hour before the commit
    write_verifier(repo)

    result = run_tool(repo, "--check")

    assert result.returncode == 2, result.stdout + result.stderr
    assert "suite_stale" in result.stdout
    assert "REFUSED -- gate 'suite'" in result.stdout
    assert git(repo, "tag", "--list") == ""


def test_a_red_suite_refuses_by_name(tmp_path):
    repo = make_repo(tmp_path)
    write_suite(repo, green=False, offset_seconds=60)
    write_verifier(repo)

    result = run_tool(repo, "--check")

    assert result.returncode == 2
    assert "suite_red" in result.stdout


def test_the_fresh_green_run_passes_and_reports_added_names(tmp_path):
    repo = make_repo(tmp_path)
    write_suite(repo, ids=["a.py::test_a", "b.py::test_b", "c.py::test_c"], offset_seconds=60)
    write_verifier(repo)

    result = run_tool(repo, "--check", "--json")

    payload = json.loads(result.stdout)
    suite = next(g for g in payload["gates"] if g["gate"] == "suite")
    assert suite["ok"] is True
    assert suite["facts"]["added"] == ["c.py::test_c"]
    assert suite["facts"]["removed"] == []
    assert result.returncode == 0


# ----------------------------------------------------------------------- gate 2


def test_a_failed_verifier_unit_in_the_bundle_refuses_by_name(tmp_path):
    repo = make_repo(tmp_path, commit_subject="D17 bake-off: six cells")
    write_suite(repo, offset_seconds=60)
    write_verifier(repo, failed_units=["D17"])

    result = run_tool(repo, "--check")

    assert result.returncode == 2
    assert "verifier_failed_unit_in_bundle" in result.stdout
    assert "REFUSED -- gate 'verifier'" in result.stdout


def test_a_failed_unit_outside_the_bundle_does_not_refuse(tmp_path):
    repo = make_repo(tmp_path, commit_subject="feat: unrelated backend change")
    write_suite(repo, offset_seconds=60)
    write_verifier(repo, failed_units=["D17"])

    result = run_tool(repo, "--check")

    assert result.returncode == 0, result.stdout
    verifier = json.loads(run_tool(repo, "--check", "--json").stdout)
    gate = next(g for g in verifier["gates"] if g["gate"] == "verifier")
    assert gate["facts"]["failed"] == ["D17"]


def test_the_verifier_note_is_recorded(tmp_path):
    repo = make_repo(tmp_path, commit_subject="D17 bake-off: six cells")
    write_suite(repo, offset_seconds=60)
    write_verifier(repo, failed_units=["D17"])

    result = run_tool(repo, "--check", "--json", "--verifier", "session-42")
    payload = json.loads(result.stdout)
    gate = next(g for g in payload["gates"] if g["gate"] == "verifier")

    assert "--verifier" not in result.stdout  # record is the note, not the flag
    assert gate["facts"]["verifier"] == "session-42"
    assert any("session-42" in line for line in gate["evidence"])
    assert result.returncode == 2  # still refused: the unit is in the bundle


# ----------------------------------------------------------------------- gate 3


def test_visual_src_change_in_the_bundle_refuses_by_name(tmp_path):
    repo = make_repo(tmp_path, staging_paths={
        "northstar_backend/app.py": "print('hi')\n",
        "northstar-os-ui/src/pages/Home.jsx": "export default function Home() {}\n",
    })
    write_suite(repo, offset_seconds=60)
    write_verifier(repo)

    result = run_tool(repo, "--check")

    assert result.returncode == 2
    assert "bundle_visual" in result.stdout
    assert "northstar-os-ui/src/pages/Home.jsx" in result.stdout
    assert "REFUSED -- gate 'bundle'" in result.stdout


def test_a_ui_test_file_is_not_creative(tmp_path):
    repo = make_repo(tmp_path, staging_paths={
        "northstar-os-ui/src/pages/Home.test.jsx": "test('x', () => {})\n",
        "northstar-os-ui/src/renders/scene.png": "not-a-real-png",
        "reports/ty/digest_composites_01.png": "not-a-real-png",
    })
    write_suite(repo, offset_seconds=60)
    write_verifier(repo)

    result = run_tool(repo, "--check")

    assert result.returncode == 0, result.stdout


def test_an_approval_note_satisfies_the_visual_gate(tmp_path):
    repo = make_repo(tmp_path, staging_paths={
        "northstar-os-ui/src/pages/Home.jsx": "export default function Home() {}\n",
    })
    write_suite(repo, offset_seconds=60)
    write_verifier(repo)

    result = run_tool(repo, "--check", "--approve-visual", "looked at the review pack")

    assert result.returncode == 0, result.stdout
    assert "operator visual approval recorded" in result.stdout


# ----------------------------------------------------------------------- promote


def test_the_eligible_bundle_produces_a_promotion_tag(tmp_path):
    repo = make_repo(tmp_path)
    write_suite(repo, offset_seconds=60)
    write_verifier(repo)
    before = git(repo, "rev-parse", "main")

    result = run_tool(repo, "--promote")

    assert result.returncode == 0, result.stdout + result.stderr
    tags = git(repo, "tag", "--list").splitlines()
    promote = [t for t in tags if t.startswith("promote/")]
    rollback = [t for t in tags if t.startswith("rollback/")]
    assert len(promote) == 1, tags
    assert len(rollback) == 1, tags
    assert promote[0].endswith(git(repo, "rev-parse", "--short=8", "staging"))
    assert promote[0] in result.stdout

    after = git(repo, "rev-parse", "main")
    assert after != before
    assert after in result.stdout
    parents = git(repo, "rev-list", "--parents", "-n1", "main").split()
    assert len(parents) == 3, "--no-ff must leave a two-parent merge commit"
    assert git(repo, "rev-parse", f"{promote[0]}^{{commit}}") == after
    assert (repo / "reports/ty/item5_promotion.md").exists()


def test_check_changes_nothing(tmp_path):
    repo = make_repo(tmp_path)
    write_suite(repo, offset_seconds=60)
    write_verifier(repo)
    before = git(repo, "rev-parse", "main")

    result = run_tool(repo, "--check")

    assert result.returncode == 0
    assert git(repo, "rev-parse", "main") == before
    assert git(repo, "tag", "--list") == ""


def test_a_refused_promote_moves_nothing_and_writes_the_review_pack(tmp_path):
    repo = make_repo(tmp_path, staging_paths={
        "northstar-os-ui/src/pages/Home.jsx": "export default function Home() {}\n",
    })
    write_suite(repo, offset_seconds=60)
    write_verifier(repo)
    before = git(repo, "rev-parse", "main")

    result = run_tool(repo, "--promote")

    assert result.returncode == 2
    assert git(repo, "rev-parse", "main") == before
    assert git(repo, "tag", "--list") == ""
    packs = list((repo / "reports/ty").glob("staging_review_*.md"))
    assert len(packs) == 1
    assert "--promote" in packs[0].read_text(encoding="utf-8")


# ----------------------------------------------------------------------- revert


def test_revert_is_a_no_op_when_the_tag_is_absent(tmp_path):
    repo = make_repo(tmp_path)
    write_suite(repo, offset_seconds=60)
    write_verifier(repo)
    before = git(repo, "rev-parse", "main")

    result = run_tool(repo, "--revert", "promote/20260101-deadbeef")

    assert result.returncode == 0, result.stdout + result.stderr
    assert "nothing to revert" in result.stdout
    assert git(repo, "rev-parse", "main") == before


@pytest.mark.parametrize("gate_key", ["suite_stale", "verifier_failed_unit_in_bundle", "bundle_visual"])
def test_each_gate_refuses_alone(tmp_path, gate_key):
    """Belt and braces: the same three refusals, asserted through the JSON payload."""
    if gate_key == "suite_stale":
        repo = make_repo(tmp_path)
        write_suite(repo, offset_seconds=-3600)
        write_verifier(repo)
    elif gate_key == "verifier_failed_unit_in_bundle":
        repo = make_repo(tmp_path, commit_subject="V9 dogfood harness")
        write_suite(repo, offset_seconds=60)
        write_verifier(repo, failed_units=["V9"])
    else:
        repo = make_repo(tmp_path, staging_paths={
            "northstar-os-ui/src/components/Nav.jsx": "export const Nav = 1\n",
        })
        write_suite(repo, offset_seconds=60)
        write_verifier(repo)

    payload = json.loads(run_tool(repo, "--check", "--json").stdout)

    assert payload["eligible"] is False
    assert len(payload["refused_by"]) == 1
    blocker_keys = [b.split(":")[0] for g in payload["gates"] for b in g["blockers"]]
    assert gate_key in blocker_keys
