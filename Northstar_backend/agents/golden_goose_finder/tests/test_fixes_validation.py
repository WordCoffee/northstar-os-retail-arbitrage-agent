"""Phase F/S11b — FIXES_50 validation subset (#13 price sanity, #20 ROI floor)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_BACKEND = Path(__file__).resolve().parents[3]
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from agents.golden_goose_finder.amazon_matcher import (  # noqa: E402
    MATCH_ROI_FLOOR_PCT,
    AmazonMatch,
    _validate_match_quality,
    rank_candidates,
)
from agents.golden_goose_finder.wholesale_scanner import WholesaleProduct  # noqa: E402

from agents.golden_goose_finder.tests.test_amazon_matcher import _make_wholesale, _make_amazon  # noqa: E402


def test_roi_floor_rejects_match_that_cannot_clear_floor():
    # cogs high, price low -> gross ROI below floor: must be dropped at match
    wp = _make_wholesale(wholesale_price=100.0, pack_count=1)   # cogs 100
    low = _make_amazon(asin="B0LOWROI01", amazon_price=95.0)    # ROI ~ -5%
    ok, reason = _validate_match_quality(low, wp)
    assert ok is False and "roi_below_floor_at_match" in reason


def test_roi_floor_accepts_match_clearing_floor():
    wp = _make_wholesale(wholesale_price=100.0, pack_count=1)
    high = _make_amazon(asin="B0HIGHROI1", amazon_price=130.0)  # ROI 30% > 10%
    ok, reason = _validate_match_quality(high, wp)
    assert ok is True and reason == "ok"


def test_rank_candidates_drops_below_floor_and_keeps_passing():
    wp = _make_wholesale(wholesale_price=90.0, pack_count=1)
    below = _make_amazon(asin="B0BELOW001", brand="Nicorette", amazon_price=97.0)
    above = _make_amazon(asin="B0ABOVE001", brand="Nicorette", amazon_price=180.0)
    ranked = rank_candidates([below, above], wp)
    asins = [m.asin for m in ranked if m.asin == "B0ABOVE001"]
    assert asins == ["B0ABOVE001"]
    assert "B0BELOW001" not in [m.asin for m in ranked]


def test_price_sanity_bounds_still_guard():
    wp = _make_wholesale(wholesale_price=10.0, pack_count=1)
    absurd = _make_amazon(asin="B0ABSURD01", amazon_price=10_000.0)  # 1000x cogs
    ok, reason = _validate_match_quality(absurd, wp)
    assert ok is False and "price_ratio" in reason
    assert MATCH_ROI_FLOOR_PCT == 10.0