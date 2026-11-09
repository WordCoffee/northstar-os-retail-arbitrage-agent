"""Isolation between tests: a path env var set by one test must not reach the next.

This is the smallest reproduction of a real order dependence found on 2026-11-09. In a full run,
``test_costco_api_client.py`` left ``SCANNER_SEARCH_CACHE_PATH`` pointing at a temp file that no
longer existed, and ``test_contract_check.py`` then saw a scanner with no candidates and failed an
assertion — while the same test passed when run alone. ``conftest.py`` now restores these names to
their session baseline after every test, and these two tests fail if that stops happening.
"""
from __future__ import annotations

import os


def test_a_test_may_leak_a_path_env_var(tmp_path):
    # a deliberate, unpatched assignment: this is what the CLI mains do
    os.environ["SCANNER_SEARCH_CACHE_PATH"] = str(tmp_path / "leaked.json")
    assert os.environ["SCANNER_SEARCH_CACHE_PATH"].endswith("leaked.json")


def test_the_next_test_does_not_inherit_it():
    leaked = os.environ.get("SCANNER_SEARCH_CACHE_PATH", "")
    assert not leaked.endswith("leaked.json"), (
        "the previous test's SCANNER_SEARCH_CACHE_PATH survived into this one; "
        "conftest's baseline restore is not running")
