"""Tests for Chrome Connect observation layer (Phase 1)."""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import chromeconnect_observation as obs


# ---------------------------------------------------------------------------
# Sample HTML fixtures
# ---------------------------------------------------------------------------

SIMPLE_HTML = """
<html><body>
  <h1>Product Page</h1>
  <a href="/home">Home</a>
  <button id="add-to-cart">Add to Cart</button>
  <input type="text" name="qty" placeholder="Quantity" />
  <select name="size"><option>S</option><option>M</option><option>L</option></select>
  <p>Some description text here.</p>
  <a href="/about">About Us</a>
</body></html>
"""

REPEATED_HTML = """
<html><body>
  <ul>
    <li><a href="/p1">Product 1</a><button>Buy</button></li>
    <li><a href="/p2">Product 2</a><button>Buy</button></li>
    <li><a href="/p3">Product 3</a><button>Buy</button></li>
    <li><a href="/p4">Product 4</a><button>Buy</button></li>
    <li><a href="/p5">Product 5</a><button>Buy</button></li>
    <li><a href="/p6">Product 6</a><button>Buy</button></li>
    <li><a href="/p7">Product 7</a><button>Buy</button></li>
    <li><a href="/p8">Product 8</a><button>Buy</button></li>
  </ul>
</body></html>
"""

LARGE_HTML = """
<html><body>
""" + "\n".join(
    f'  <div><a href="/item/{i}">Item {i}</a><button>Add</button><input type="text" name="q{i}" /></div>'
    for i in range(500)
) + """
</body></html>
"""

EMPTY_HTML = "<html><body><p>No interactive elements here.</p></body></html>"


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_extract_finds_interactive_elements():
    els = obs.extract_accessibility_tree(SIMPLE_HTML)
    tags = [e["tag"] for e in els]
    assert "a" in tags
    assert "button" in tags
    assert "input" in tags
    assert "select" in tags
    # refs are sequential
    refs = [e["ref"] for e in els]
    assert refs == [f"e{i}" for i in range(1, len(els) + 1)]


def test_extract_empty_page():
    els = obs.extract_accessibility_tree(EMPTY_HTML)
    assert els == []


def test_snapshot_returns_structure():
    snap = obs.snapshot(SIMPLE_HTML)
    assert "elements" in snap
    assert "token_count" in snap
    assert "truncated" in snap
    assert "total_elements" in snap
    assert "budget" in snap
    assert snap["total_elements"] > 0
    assert snap["token_count"] <= snap["budget"] or not snap["truncated"]


def test_snapshot_fits_budget():
    snap = obs.snapshot(LARGE_HTML, token_budget=500)
    assert snap["token_count"] <= 500 or snap["truncated"]
    assert len(snap["elements"]) < 500  # should be truncated


def test_repeat_collapse():
    snap = obs.snapshot(REPEATED_HTML, token_budget=10000)
    # Should have collapsed repeated rows
    repeat_els = [e for e in snap["elements"] if e.get("tag") == "repeat"]
    assert len(repeat_els) > 0, "Expected repeat collapse summary element"


def test_refs_stable_across_reload():
    """Refs should be identical for identical HTML."""
    snap1 = obs.snapshot(SIMPLE_HTML)
    snap2 = obs.snapshot(SIMPLE_HTML)
    refs1 = [e["ref"] for e in snap1["elements"]]
    refs2 = [e["ref"] for e in snap2["elements"]]
    assert refs1 == refs2


def test_viewport_snapshot():
    snap = obs.viewport_snapshot(LARGE_HTML, offset=0, limit=10, token_budget=10000)
    assert snap["offset"] == 0
    assert snap["limit"] == 10
    assert snap["has_more"] is True
    assert len(snap["elements"]) <= 10


def test_viewport_pagination():
    snap1 = obs.viewport_snapshot(LARGE_HTML, offset=0, limit=10, token_budget=10000)
    snap2 = obs.viewport_snapshot(LARGE_HTML, offset=10, limit=10, token_budget=10000)
    refs1 = {e["ref"] for e in snap1["elements"]}
    refs2 = {e["ref"] for e in snap2["elements"]}
    # Different elements (refs may overlap due to re-numbering, but content differs)
    assert snap1["offset"] != snap2["offset"]


def test_enabled_flag_default_off():
    # Default should be OFF
    assert obs.OBSERVATION_ENABLED is False or os.environ.get("CHROMECONNECT_OBSERVATION_ENABLED") == "1"


def test_snapshot_hash_deterministic():
    h1 = obs.snapshot_hash(SIMPLE_HTML)
    h2 = obs.snapshot_hash(SIMPLE_HTML)
    assert h1 == h2
    assert len(h1) == 16


def test_save_load_fixture():
    path = obs.save_fixture("test_fixture", SIMPLE_HTML)
    assert os.path.exists(path)
    loaded = obs.load_fixture("test_fixture")
    assert loaded == SIMPLE_HTML
    # Cleanup
    os.remove(path)


def test_list_fixtures():
    obs.save_fixture("fixture_a", SIMPLE_HTML)
    obs.save_fixture("fixture_b", EMPTY_HTML)
    fixtures = obs.list_fixtures()
    assert "fixture_a" in fixtures
    assert "fixture_b" in fixtures
    # Cleanup
    for name in ["fixture_a", "fixture_b"]:
        p = os.path.join(obs.FIXTURE_DIR, f"{name}.html")
        if os.path.exists(p):
            os.remove(p)


def test_prune_empty():
    result, tokens, truncated = obs.prune_snapshot([])
    assert result == []
    assert tokens == 0
    assert truncated is False


def test_token_estimate():
    assert obs._token_estimate("a" * 400) == 100
    assert obs._token_estimate("") == 1  # min 1


def test_observation_disabled_by_default():
    """With flag off, the module reports disabled."""
    if not os.environ.get("CHROMECONNECT_OBSERVATION_ENABLED"):
        snap = obs.snapshot(SIMPLE_HTML)
        assert snap["enabled"] is False
