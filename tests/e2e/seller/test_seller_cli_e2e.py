"""End-to-end: the seller-tester CLI, run as a seller's operator would run it.

No browser, no model, no network: `state/vision/PAUSE` is honoured by construction here —
nothing in this file can open a page. What it does exercise is the seam a unit test
misses: the argparse surface, the module import path, the process exit code, and the
proof file the run leaves behind.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
MODULE = [sys.executable, "-m", "tools.seller_tester"]


def _run(*args: str, timeout: int = 900) -> subprocess.CompletedProcess:
    return subprocess.run(MODULE + list(args), cwd=ROOT, capture_output=True, text=True,
                          timeout=timeout, encoding="utf-8", errors="replace")


def test_the_services_command_runs_two_paths_and_writes_a_proof(tmp_path):
    out = tmp_path / "proof.json"
    result = _run("services", "--only", "golden_goose,research", "--out", str(out),
                  "--work-dir", str(tmp_path / "work"))
    assert result.returncode == 0, result.stderr[-2000:]
    proof = json.loads(out.read_text(encoding="utf-8"))
    assert proof["only"] == ["golden_goose", "research"]
    assert proof["refused"] == 0
    assert proof["scored"] == 2
    assert proof["passed"] == 2
    assert proof["paths"]["golden_goose"]["mean_score"] == 100.0
    assert proof["paths"]["research"]["mean_score"] == 100.0
    assert proof["network"].startswith("none")
    for row in proof["results"]:
        assert Path(row["artefact"]).is_file(), row["artefact"]


def test_an_unknown_path_is_refused_by_name_with_a_non_zero_exit(tmp_path):
    result = _run("services", "--only", "images", "--out", str(tmp_path / "p.json"),
                  "--work-dir", str(tmp_path / "w"))
    assert result.returncode != 0
    assert "images" in (result.stderr + result.stdout)


def test_the_packaging_and_catalog_commands_still_work(tmp_path):
    catalog = _run("catalog")
    assert catalog.returncode == 0, catalog.stderr[-2000:]
    payload = json.loads(catalog.stdout[catalog.stdout.index("{"):])
    assert payload["valid"] is True and payload["briefs"] >= 12
    packaging = _run("packaging", "--limit", "1", "--out-dir", str(tmp_path / "pack"),
                     "--summary-out", str(tmp_path / "pack.json"),
                     "--gaps", str(tmp_path / "gaps.json"))
    assert packaging.returncode == 0, packaging.stderr[-2000:]
    summary = json.loads((tmp_path / "pack.json").read_text(encoding="utf-8"))
    assert summary["selected"] == 1


@pytest.mark.parametrize("command", ["composite", "aplus", "product", "run", "escalate"])
def test_every_other_command_is_still_reachable(command):
    """--help proves the subcommand exists without running a render or a model."""
    result = _run(command, "--help", timeout=120)
    assert result.returncode == 0, result.stderr[-1000:]
    assert "usage" in result.stdout.lower()
