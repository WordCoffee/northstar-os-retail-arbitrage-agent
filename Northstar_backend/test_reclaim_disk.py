"""Reclaiming disk must never touch the operator's data."""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

import reclaim_disk as rd  # noqa: E402


def _make(root: Path, rel: str, size: int = 1024, age_days: float = 0) -> Path:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"x" * size)
    if age_days:
        old = time.time() - age_days * 86400
        import os
        os.utime(path, (old, old))
    return path


def test_old_run_scratch_is_reclaimed(tmp_path, monkeypatch):
    monkeypatch.setattr(rd, "ROOT", tmp_path)
    _make(tmp_path, "state/runs/r1/file.txt", age_days=30)
    _make(tmp_path, "state/runs/r2/file.txt", age_days=1)
    items = rd.plan(run_days=7)
    paths = {i["path"] for i in items}
    assert "state/runs/r1" in paths
    assert "state/runs/r2" not in paths


def test_over_retention_checkpoints_are_dropped(tmp_path, monkeypatch):
    monkeypatch.setattr(rd, "ROOT", tmp_path)
    for n, age in enumerate([40, 30, 20, 10, 5, 1]):
        _make(tmp_path, f"state/checkpoints/c{n}/x.json", age_days=age)
    items = rd.plan(keep_checkpoints=3)
    names = {i["path"] for i in items}
    assert "state/checkpoints/c5" not in names and "state/checkpoints/c4" not in names
    assert "state/checkpoints/c0" in names


def test_retry_artifacts_go_but_the_first_attempt_stays(tmp_path, monkeypatch):
    monkeypatch.setattr(rd, "ROOT", tmp_path)
    _make(tmp_path, "renders/autonomy_probe/bench/case_a1.png")
    _make(tmp_path, "renders/autonomy_probe/bench/case_a2.png")
    _make(tmp_path, "renders/autonomy_probe/bench/case_a3.png")
    paths = {i["path"] for i in rd.plan()}
    assert "renders/autonomy_probe/bench/case_a1.png" not in paths
    assert "renders/autonomy_probe/bench/case_a2.png" in paths
    assert "renders/autonomy_probe/bench/case_a3.png" in paths


def test_operator_artifacts_are_never_listed(tmp_path, monkeypatch):
    monkeypatch.setattr(rd, "ROOT", tmp_path)
    _make(tmp_path, "data/scanner.json", age_days=400)
    _make(tmp_path, "backups/old/x.bin", age_days=400)
    _make(tmp_path, "renders/mogra_lions_mane/product_front.png", age_days=400)
    _make(tmp_path, "renders/references/mogra/lions_mane/x.png", age_days=400)
    _make(tmp_path, "state/runs/old/x.txt", age_days=400)
    paths = {i["path"] for i in rd.plan()}
    for protected in ("data/scanner.json", "backups/old",
                      "renders/mogra_lions_mane/product_front.png",
                      "renders/references/mogra/lions_mane/x.png"):
        assert protected not in paths
    assert "state/runs/old" in paths


def test_apply_reports_what_it_freed(tmp_path, monkeypatch):
    monkeypatch.setattr(rd, "ROOT", tmp_path)
    _make(tmp_path, "state/runs/old/a.bin", size=2048, age_days=30)
    items = rd.plan(run_days=7)
    result = rd.apply(items)
    assert result["removed"] == 1
    assert result["freed_bytes"] >= 2048
    assert not (tmp_path / "state" / "runs" / "old").exists()


def test_dry_run_is_the_default(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(rd, "ROOT", tmp_path)
    _make(tmp_path, "state/runs/old/a.bin", age_days=30)
    assert rd.main([]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["dry_run"] is True
    assert (tmp_path / "state" / "runs" / "old").exists()


def test_caches_are_included_but_never_inside_protected_trees(tmp_path, monkeypatch):
    monkeypatch.setattr(rd, "ROOT", tmp_path)
    (tmp_path / "src" / "__pycache__").mkdir(parents=True)
    (tmp_path / "src" / "__pycache__" / "a.pyc").write_bytes(b"x")
    (tmp_path / "data" / "__pycache__").mkdir(parents=True)
    (tmp_path / "data" / "__pycache__" / "b.pyc").write_bytes(b"x")
    paths = {i["path"] for i in rd.plan()}
    assert "src/__pycache__" in paths
    assert "data/__pycache__" not in paths
