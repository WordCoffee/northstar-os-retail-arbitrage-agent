"""Backlog supply: read the report the runner actually writes.

PowerShell's Tee-Object writes UTF-16LE on this box. A UTF-8-only read turned
every FAILED line into interleaved NULs, so the backlog produced 0 proposals
from a real 10-failure report. The parser now honours the BOM and normalises
CRLF before matching.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import continuous_loop as cl  # noqa: E402


def test_a_utf16_windows_report_yields_one_proposal_per_failure(tmp_path):
    report = tmp_path / "report.txt"
    text = ("FAILED Northstar_backend\\test_x.py::test_a\r\n"
            "FAILED Northstar_backend\\test_x.py::test_b - AssertionError\r\n"
            "10 failed, 5918 passed in 1s\r\n")
    report.write_bytes(text.encode("utf-16"))
    proposals = cl.proposals_from_pytest_report(report)
    assert len(proposals) == 2, proposals
    assert all(p["authorized"] is False for p in proposals)
    assert all("needs_author" in p["blocked"] for p in proposals)
    ids = [p["id"] for p in proposals]
    assert len(set(ids)) == 2


def test_a_utf8_report_still_parses(tmp_path):
    report = tmp_path / "report.txt"
    report.write_text("FAILED Northstar_backend/test_x.py::test_a\n", encoding="utf-8")
    proposals = cl.proposals_from_pytest_report(report)
    assert len(proposals) == 1
    assert "test_a" in proposals[0]["objective"]
