"""Item 5 — promotion in slices: one unit at a time, visual slices refused by name.

Every test works in its own throwaway git repository under `tmp_path`. Nothing here reads
or writes the real `main`: the tool is pointed at the scratch repo with `--repo`.

A slice is a directory-level unit (one service's UI paths, one backend area, one tool).
The four properties under test:

1. paths group into slices deterministically, and the table says code vs visual;
2. a code-only slice promotes on its own when the candidate suite is green, and carries
   only its own paths onto the target;
3. a visual slice refuses, and its review pack carries 5 to 10 image links;
4. a slice whose commits are named by a FAILED verifier unit refuses by that name.
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

TOOL = Path(__file__).resolve().parents[1] / "tools" / "promote_staging.py"

_spec = importlib.util.spec_from_file_location("promote_staging_under_test", TOOL)
promote_staging = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = promote_staging
_spec.loader.exec_module(promote_staging)

COMMIT_DATE = "2026-11-09T12:00:00+00:00"
COMMIT_EPOCH = int(datetime.fromisoformat(COMMIT_DATE).timestamp())
STAMP = "20261109"

STAGING_TEXT = "print('hi')\n\n# staging change\n"
TOOL_TEXT = "print('tool change')\n"


def git(repo: Path, *args: str) -> str:
    env = {
        "GIT_AUTHOR_DATE": COMMIT_DATE,
        "GIT_COMMITTER_DATE": COMMIT_DATE,
        "GIT_AUTHOR_NAME": "item5-test",
        "GIT_AUTHOR_EMAIL": "item5@test.invalid",
        "GIT_COMMITTER_NAME": "item5-test",
        "GIT_COMMITTER_EMAIL": "item5@test.invalid",
    }
    import os
    proc = subprocess.run(["git", *args], cwd=str(repo), capture_output=True, text=True,
                          env={**os.environ, **env})
    assert proc.returncode == 0, f"git {' '.join(args)}: {proc.stderr}"
    return proc.stdout.strip()


def write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def write_suite(repo: Path, *, green: bool = True, offset_seconds: int = 60) -> None:
    import os
    summary = ("7067 passed, 117 skipped, 2 xfailed, 17 warnings, 125 subtests passed "
               "in 1129.35s (0:18:49)"
               if green else
               "7060 passed, 7 failed, 117 skipped in 1129.35s (0:18:49)")
    report = write(repo / "reports/ty" / f"_fullsuite_{STAMP}.txt", "....\n" + summary + "\n")
    stamp = COMMIT_EPOCH + offset_seconds
    os.utime(report, (stamp, stamp))

    base = ["a.py::test_a", "b.py::test_b"]
    write(repo / "reports/ty/_idlist_20261107.txt", json.dumps({"ids": base}))
    run_ids = write(repo / "reports/ty" / f"_idlist_{STAMP}.txt", json.dumps({"ids": base}))
    os.utime(run_ids, (stamp, stamp))


def write_verifier(repo: Path, *, failed_units: list[str] | None = None) -> None:
    failed_units = failed_units or []
    rows = ["| # | item | verdict | one-line evidence |", "|---|---|---|---|",
            "| 1 | Scorecards reproduce | **agree** | 0 diffs |"]
    for index, unit in enumerate(failed_units, start=2):
        rows.append(f"| {index} | {unit} colour work | **FAILED** | artefacts absent |")
    write(repo / "reports/ty/d15_verification.md", "\n".join(rows) + "\n")
    write(repo / "reports/ty/verifier_findings.json", json.dumps({
        "failed": [{"unit": u, "item": f"{u} work", "why": "not reproducible"}
                   for u in failed_units],
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
    git(repo, "config", "user.name", "item5-test")
    git(repo, "config", "user.email", "item5@test.invalid")
    write(repo / "README.md", "scratch\n")
    write(repo / "Northstar_backend/app.py", "print('hi')\n")
    write(repo / "tools/thing.py", "print('thing')\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-m", "base")

    git(repo, "checkout", "-b", "staging")
    default = {"Northstar_backend/app.py": STAGING_TEXT}
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


# ----------------------------------------------------------------------- grouping


def test_paths_group_into_slices_by_unit():
    paths = [
        "northstar-os-ui/src/pages/Home.jsx",
        "northstar-os-ui/src/pages/Plan.jsx",
        "northstar-os-ui/src/pages/Home.test.jsx",
        "Northstar_backend/app.py",
        "Northstar_backend/agents/worker.py",
        "tools/promote_staging.py",
        "reports/ty/digest_20261109.md",
        "README.md",
    ]
    groups = promote_staging.build_slices(paths)

    assert sorted(groups) == [
        "Northstar_backend-agents", "Northstar_backend-root", "reports-ty",
        "root", "tools-root", "ui-pages",
    ]
    assert groups["ui-pages"] == [
        "northstar-os-ui/src/pages/Home.jsx",
        "northstar-os-ui/src/pages/Home.test.jsx",
        "northstar-os-ui/src/pages/Plan.jsx",
    ]


def test_rendering_paths_make_a_slice_visual_and_a_test_file_does_not():
    visual = promote_staging.build_slices([
        "northstar-os-ui/src/pages/Home.jsx",
        "northstar-os-ui/src/pages/Home.test.jsx",
    ])["ui-pages"]
    code = promote_staging.build_slices([
        "northstar-os-ui/src/pages/Home.test.jsx",
        "northstar-os-ui/src/renders/scene.png",
    ])["ui-pages"]

    assert promote_staging.slice_is_visual(visual) is True
    assert promote_staging.slice_is_visual(code) is False


def test_the_slice_table_writes_code_and_visual_rows(tmp_path):
    repo = make_repo(tmp_path, staging_paths={
        "Northstar_backend/app.py": STAGING_TEXT,
        "northstar-os-ui/src/assets/hero.png": "not-a-png",
    })

    result = run_tool(repo, "--list-slices", "--json")

    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    kinds = {row["slice"]: row["kind"] for row in payload["slices"]}
    assert kinds["Northstar_backend-root"] == "code"
    assert kinds["ui-assets"] == "visual"
    table = repo / "reports/ty/item5_slices.md"
    assert table.exists()
    text = table.read_text(encoding="utf-8")
    assert "`Northstar_backend-root` | code" in text
    assert "`ui-assets` | visual" in text


# ----------------------------------------------------------------------- code slice


def test_a_code_only_slice_promotes_on_its_own_and_carries_only_its_paths(tmp_path):
    repo = make_repo(tmp_path, staging_paths={
        "Northstar_backend/app.py": STAGING_TEXT,
        "tools/thing.py": TOOL_TEXT,
    })
    write_suite(repo)
    write_verifier(repo)
    before = git(repo, "rev-parse", "main")

    check = run_tool(repo, "--slice", "Northstar_backend-root", "--check")
    assert check.returncode == 0, check.stdout + check.stderr
    assert "slice: Northstar_backend-root" in check.stdout

    result = run_tool(repo, "--slice", "Northstar_backend-root", "--promote")

    assert result.returncode == 0, result.stdout + result.stderr
    assert git(repo, "rev-parse", "main") != before
    assert STAGING_TEXT.strip() in git(repo, "show", "main:Northstar_backend/app.py")
    # the other unit stayed behind
    assert "tool change" not in git(repo, "show", "main:tools/thing.py")

    tags = git(repo, "tag", "--list").splitlines()
    promote = [t for t in tags if t.startswith("promote/")]
    assert len(promote) == 1, tags
    assert "northstar-backend-root" in promote[0]
    assert promote[0].endswith(git(repo, "rev-parse", "--short=8", "staging"))
    assert [t for t in tags if t.startswith("rollback/")]

    parents = git(repo, "rev-list", "--parents", "-n1", "main").split()
    assert len(parents) == 2, "a slice is one commit on the target, not a merge"
    assert (repo / "reports/ty/item5_slices.md").exists()


# ----------------------------------------------------------------------- visual slice


def test_a_visual_slice_refuses_and_writes_a_pack_with_five_to_ten_images(tmp_path):
    images = {f"northstar-os-ui/src/assets/shot{i}.png": "not-a-png" for i in range(6)}
    repo = make_repo(tmp_path, staging_paths={
        "Northstar_backend/app.py": STAGING_TEXT,
        **images,
    })
    write_suite(repo)
    write_verifier(repo)
    before = git(repo, "rev-parse", "main")

    result = run_tool(repo, "--slice", "ui-assets", "--check")

    assert result.returncode == 2, result.stdout + result.stderr
    assert "slice_visual" in result.stdout
    assert "REFUSED -- gate 'slice'" in result.stdout
    assert git(repo, "rev-parse", "main") == before
    assert git(repo, "tag", "--list") == ""

    packs = list((repo / "reports/ty/review").glob("ui-assets_*.md"))
    assert len(packs) == 1, packs
    text = packs[0].read_text(encoding="utf-8")
    links = text.count("![after]")
    assert 5 <= links <= 10, f"{links} image links"
    assert "--promote" in text and "--revert" in text
    assert "northstar-os-ui/src/assets/shot0.png" in text


def test_a_visual_slice_promotes_only_with_a_recorded_approval(tmp_path):
    repo = make_repo(tmp_path, staging_paths={
        "northstar-os-ui/src/assets/hero.png": "not-a-png",
    })
    write_suite(repo)
    write_verifier(repo)
    before = git(repo, "rev-parse", "main")

    refused = run_tool(repo, "--slice", "ui-assets", "--promote")
    assert refused.returncode == 2
    assert git(repo, "rev-parse", "main") == before

    approved = run_tool(repo, "--slice", "ui-assets", "--promote",
                        "--approve-visual", "looked at the pack")
    assert approved.returncode == 0, approved.stdout + approved.stderr
    assert "hero.png" in git(repo, "show", "--stat", "main")


# ----------------------------------------------------------------------- verifier


def test_a_slice_named_by_a_failed_verifier_unit_refuses(tmp_path):
    repo = make_repo(tmp_path, staging_paths={"Northstar_backend/app.py": STAGING_TEXT},
                     commit_subject="SEL01d colour work on the app")
    write_suite(repo)
    write_verifier(repo, failed_units=["SEL01d"])
    before = git(repo, "rev-parse", "main")

    result = run_tool(repo, "--slice", "Northstar_backend-root", "--check")

    assert result.returncode == 2, result.stdout + result.stderr
    assert "verifier_failed_unit_in_bundle" in result.stdout
    assert "REFUSED -- gate 'verifier'" in result.stdout
    assert git(repo, "rev-parse", "main") == before
