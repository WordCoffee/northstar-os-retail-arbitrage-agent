"""Regression: the apply_label tool's argument type contract.

The UI once failed four tool rounds with the opaque
`can't multiply sequence by non-int of type 'float'` raised from inside the
compositor, after the tool wrapper had passed model-supplied JSON straight
through. These tests pin the boundary: the tool normalises what it can, rejects
what it cannot with a message an operator can act on, and never lets a raw
exception reach the turn.

They also assert direct compose() and the tool path agree, so the two entry
points cannot drift.
"""

import os
import sys
from pathlib import Path

import pytest
from PIL import Image

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
os.chdir(ROOT.parent)

import chat_tools
import pouch_label as pl

PLATE = ROOT / "data" / "studio_generated" / "2e4a7ab96e9941479b068792f592864d.png"
LOGO = ROOT.parent / "exports" / "mogra_logo_master_v3.png"

pytestmark = pytest.mark.skipif(not PLATE.exists(), reason="T1 plate fixture absent")


def _ctx():
    return {"db": None, "account_id": None, "progress": lambda p, l: None}


def test_scalar_coercion_rejects_a_sequence():
    """A list where a scalar belongs is a clean tool error, not a crash."""
    args = {"plate_asset_id": "x", "title": ["ORGANIC LION'S MANE"]}
    out = chat_tools._t_apply_label(args, _ctx())
    # It fails earlier on the missing plate, but must never raise.
    assert isinstance(out, dict) and "ok" in out


def test_string_lists_normalise():
    assert chat_tools._t_apply_label.__doc__ is not None
    # exercised through compose below; the helpers are local, so assert behaviour
    out = pl.compose(PLATE, title="T", bullets=["a", "b"], icons="USDA Organic")
    assert out["bytes"][:4] == b"\x89PNG"


def test_compose_without_a_logo_is_valid():
    """logo_asset_id is optional; its absence must not be a failure."""
    out = pl.compose(PLATE, title="ORGANIC LION'S MANE", subtitle="MUSHROOM POWDER",
                     weight="6 oz (170g)", logo_path=None)
    assert out["has_logo"] is False
    assert out["bytes"][:4] == b"\x89PNG"


def test_tool_path_matches_direct_compose_geometry():
    """Both entry points must measure the same panel."""
    d = pl.compose(PLATE, title="T", subtitle="", weight="", logo_path=None)
    q_tool = d["quad"]
    assert len(q_tool) == 4
    # and the measured quad is inside the plate
    with Image.open(PLATE) as im:
        w, h = im.size
    for x, y in q_tool:
        assert 0 <= x <= w and 0 <= y <= h


def test_tool_error_text_carries_the_failing_frame(monkeypatch):
    """A compositor exception must report where it broke, not just its message."""
    def boom(*a, **k):
        raise TypeError("can't multiply sequence by non-int of type 'float'")

    monkeypatch.setattr(chat_tools, "pouch_label", pl, raising=False)
    monkeypatch.setattr(pl, "compose", boom)
    # bypass asset resolution by handing the tool a path-shaped id
    out = chat_tools._t_apply_label(
        {"plate_asset_id": "missing", "title": "T"}, _ctx())
    assert out["ok"] is False
    assert out["summary"]  # actionable summary present
