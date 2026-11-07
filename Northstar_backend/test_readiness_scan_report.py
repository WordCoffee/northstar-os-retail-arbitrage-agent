"""The readiness scan must say how many files it looked at.

A report that says "0 findings" without saying "over 0 files" cannot be told apart
from a report that says "0 findings" after reading the whole tree. The work
generator treats that difference as a finding in its own right (`discovery-vacuous`):
a scanner that saw nothing has not proved anything is well, so the bootstrap of
every T2 discovery depends on this number being present and honest.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

import production_readiness_scan as scan  # noqa: E402


def test_the_report_says_how_many_files_it_scanned():
    report = scan.scan()

    assert isinstance(report.get("files_scanned"), int), (
        f"the report has no integer files_scanned (keys: {sorted(report)})")
    assert report["files_scanned"] == len(scan._ui_files())
    assert report["files_scanned"] > 0, "a scan over zero files proves nothing"
