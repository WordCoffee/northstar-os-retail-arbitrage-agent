"""pytest plugin: write the exact node ids and outcomes of a run.

Junit XML is not an identity format. It reports ``classname`` as a dotted module
path (``agents.golden_goose_finder.tests.test_amazon_adapters.TestGate``) while
collection ids are paths (``agents/golden_goose_finder/tests/test_amazon_adapters.py::TestGate``),
so any comparison between the two finds zero overlap and reports every test as
removed. That is exactly what happened on 2026-11-06.

This plugin writes what pytest itself knows:

    {"ids": ["path/to/test.py::Class::test_name", ...],
     "status": {"path/to/test.py::Class::test_name": "passed|failed|skipped"}}

    pytest -q -p pytest_idlist --idlist=run_ids.json

It is test infrastructure, not a test. The file name deliberately does not start
with ``test_`` so pytest does not collect it.
"""
from __future__ import annotations

import json
from typing import Dict, List

_IDS: List[str] = []
_STATUS: Dict[str, str] = {}


def pytest_addoption(parser) -> None:
    parser.addoption("--idlist", action="store", default=None,
                     help="write node ids + outcomes to this JSON file")


def pytest_collection_modifyitems(config, items) -> None:
    global _IDS
    _IDS = [item.nodeid for item in items]


def _worse(a: str, b: str) -> str:
    rank = {"passed": 0, "skipped": 1, "failed": 2}
    return a if rank.get(a, 0) >= rank.get(b, 0) else b


def pytest_runtest_logreport(report) -> None:
    current = _STATUS.get(report.nodeid, "passed")
    if report.outcome == "failed":
        _STATUS[report.nodeid] = _worse(current, "failed")
    elif report.outcome == "skipped":
        _STATUS[report.nodeid] = _worse(current, "skipped")
    else:
        _STATUS.setdefault(report.nodeid, "passed")


def pytest_sessionfinish(session, exitstatus) -> None:
    target = session.config.getoption("--idlist")
    if not target:
        return
    payload = {"ids": sorted(set(_IDS) | set(_STATUS)),
               "status": {k: v for k, v in _STATUS.items()}}
    with open(target, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=1)
