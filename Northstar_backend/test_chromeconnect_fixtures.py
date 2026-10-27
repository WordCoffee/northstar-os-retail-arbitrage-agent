"""Fixture harness tests for Chrome Connect observation layer (Phase 1).

Verifies:
1. All 20+ fixtures fit within the token budget (4K default).
2. Element refs are stable across reloads (same HTML → same refs).
3. Fixture files exist and are loadable.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import chromeconnect_observation as obs

FIXTURE_NAMES = obs.list_fixtures()


def test_at_least_20_fixtures():
    assert len(FIXTURE_NAMES) >= 20, f"Only {len(FIXTURE_NAMES)} fixtures, need 20+"


def test_all_fixtures_load():
    for name in FIXTURE_NAMES:
        html_text = obs.load_fixture(name)
        assert html_text is not None, f"Fixture {name} could not be loaded"
        assert len(html_text) > 0, f"Fixture {name} is empty"


def test_all_fixtures_fit_budget():
    """Every fixture snapshot must fit within the 4K token budget."""
    for name in FIXTURE_NAMES:
        html_text = obs.load_fixture(name)
        snap = obs.snapshot(html_text, token_budget=4000)
        assert snap["token_count"] <= 4000, (
            f"Fixture {name}: {snap['token_count']} tokens exceeds 4K budget"
        )


def test_refs_stable_across_reload():
    """Element refs must be identical for identical HTML (reload stability)."""
    for name in FIXTURE_NAMES:
        html_text = obs.load_fixture(name)
        snap1 = obs.snapshot(html_text)
        snap2 = obs.snapshot(html_text)
        refs1 = [e["ref"] for e in snap1["elements"]]
        refs2 = [e["ref"] for e in snap2["elements"]]
        assert refs1 == refs2, f"Fixture {name}: refs not stable across reload"


def test_snapshot_hash_stable():
    """Snapshot hash must be deterministic."""
    for name in FIXTURE_NAMES:
        html_text = obs.load_fixture(name)
        h1 = obs.snapshot_hash(html_text)
        h2 = obs.snapshot_hash(html_text)
        assert h1 == h2, f"Fixture {name}: hash not stable"


def test_viewport_paging():
    """Viewport paging should work for all fixtures."""
    for name in FIXTURE_NAMES:
        html_text = obs.load_fixture(name)
        snap = obs.viewport_snapshot(html_text, offset=0, limit=5, token_budget=4000)
        assert snap["offset"] == 0
        assert snap["limit"] == 5
        assert len(snap["elements"]) <= 5


def test_empty_page_handled():
    """Empty/minimal pages should produce empty or small snapshots."""
    for name in ["empty_page", "minimal_page"]:
        if name in FIXTURE_NAMES:
            html_text = obs.load_fixture(name)
            snap = obs.snapshot(html_text)
            assert snap["total_elements"] == 0 or snap["token_count"] < 100


def test_observation_flag_default_off():
    """Observation layer must be OFF by default."""
    import os
    if not os.environ.get("CHROMECONNECT_OBSERVATION_ENABLED"):
        assert obs.OBSERVATION_ENABLED is False
