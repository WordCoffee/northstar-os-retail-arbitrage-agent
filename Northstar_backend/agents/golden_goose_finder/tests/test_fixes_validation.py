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


# --- FIXES_50 #17: BSR freshness hard reject ---

def test_bsr_stale_hard_reject():
    wp = _make_wholesale(wholesale_price=10.0, pack_count=1)
    stale = _make_amazon(asin="B0STALE001", brand="Nicorette", amazon_price=40.0, bsr=1_500_000)
    ok, reason = _validate_match_quality(stale, wp)
    assert ok is False and "bsr_stale_or_phantom" in reason


def test_bsr_in_band_accepted():
    wp = _make_wholesale(wholesale_price=10.0, pack_count=1)
    good = _make_amazon(asin="B0GOODBSR1", brand="Nicorette", amazon_price=40.0, bsr=5_000)
    ok, reason = _validate_match_quality(good, wp)
    assert ok is True and reason == "ok"


# --- FIXES_50 #18: review-count plausibility ---

def test_review_count_implausible_rejected():
    wp = _make_wholesale(wholesale_price=10.0, pack_count=1)
    bad = _make_amazon(asin="B0RVC00001", brand="Nicorette", amazon_price=40.0,
                       review_count=150_000, bsr=500_000)
    ok, reason = _validate_match_quality(bad, wp)
    assert ok is False and "review_count_implausible" in reason


def test_review_count_high_but_consistent_ok():
    wp = _make_wholesale(wholesale_price=10.0, pack_count=1)
    good = _make_amazon(asin="B0RVC00002", brand="Nicorette", amazon_price=40.0,
                        review_count=150_000, bsr=5_000)
    ok, reason = _validate_match_quality(good, wp)
    assert ok is True and reason == "ok"


# --- FIXES_50 #19: weight/size oversize validation ---

def test_oversize_weight_rejected():
    wp = _make_wholesale(wholesale_price=10.0, pack_count=1)
    heavy = _make_amazon(asin="B0WGT00001", brand="Nicorette", amazon_price=40.0, weight_oz=800.0)
    ok, reason = _validate_match_quality(heavy, wp)
    assert ok is False and "oversize_weight" in reason


def test_standard_weight_accepted():
    wp = _make_wholesale(wholesale_price=10.0, pack_count=1)
    light = _make_amazon(asin="B0WGT00002", brand="Nicorette", amazon_price=40.0, weight_oz=32.0)
    ok, reason = _validate_match_quality(light, wp)
    assert ok is True and reason == "ok"


def test_oversize_dimensions_rejected():
    wp = _make_wholesale(wholesale_price=10.0, pack_count=1)
    big = _make_amazon(asin="B0DIM00001", brand="Nicorette", amazon_price=40.0,
                       dimensions_in=[20.0, 10.0, 7.0])
    ok, reason = _validate_match_quality(big, wp)
    assert ok is False and "oversize_dimensions" in reason


def test_null_measures_pass_through():
    wp = _make_wholesale(wholesale_price=10.0, pack_count=1)
    unknown = _make_amazon(asin="B0NUL00001", brand="Nicorette", amazon_price=40.0,
                           weight_oz=None, dimensions_in=None, bsr=None, review_count=None)
    ok, reason = _validate_match_quality(unknown, wp)
    assert ok is True and reason == "ok"