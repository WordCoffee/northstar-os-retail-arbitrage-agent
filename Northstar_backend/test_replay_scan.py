"""Phase G — FIXES_50 #29 replay_scan CLI tests (offline)."""

from __future__ import annotations

import gzip
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import replay_scan as rs  # noqa: E402


def test_load_plain_json(tmp_path):
    p = tmp_path / "raw.json"
    p.write_text(json.dumps({"asin": "B0X", "items": [1, 2, 3]}), encoding="utf-8")
    assert rs.load_replay_file(p)["asin"] == "B0X"


def test_load_gzip_json(tmp_path):
    p = tmp_path / "raw.json.gz"
    with gzip.open(p, "wt", encoding="utf-8") as fh:
        fh.write(json.dumps({"provider": "chocodata", "status": "ok"}))
    got = rs.load_replay_file(p)
    assert got["provider"] == "chocodata"


def test_missing_file_hard_error(tmp_path):
    try:
        rs.load_replay_file(tmp_path / "missing.json")
        assert False, "expected FileNotFoundError"
    except FileNotFoundError:
        pass


def test_summarize_counts_lists():
    s = rs._summarize({"asin": "B0X", "items": [1, 2], "status": "ok"})
    assert "items=2" in s and "asin=B0X" in s


def test_main_ok_and_metrics(tmp_path, capsys):
    p = tmp_path / "raw.json.gz"
    with gzip.open(p, "wt", encoding="utf-8") as fh:
        fh.write(json.dumps({"asin": "B0X", "items": [1]}))
    metrics = tmp_path / "metrics.jsonl"
    code = rs.main(["--from-file", str(p), "--emit-metrics", str(metrics)])
    out = capsys.readouterr().out
    assert code == 0 and "REPLAY OK" in out and "items=1" in out
    assert metrics.exists()


def test_main_missing_file_fails(tmp_path, capsys):
    code = rs.main(["--from-file", str(tmp_path / "nope.json")])
    err = capsys.readouterr().err
    assert code == 1 and "not found" in err