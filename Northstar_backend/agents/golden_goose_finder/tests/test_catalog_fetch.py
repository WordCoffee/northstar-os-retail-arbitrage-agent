"""Phase G — FIXES_50 #38 async catalog fetch tests (fake transport, offline)."""

from __future__ import annotations

import asyncio
import sys
import time
from pathlib import Path

import pytest

_BACKEND = Path(__file__).resolve().parents[3]
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from agents.golden_goose_finder.catalog_fetch import fetch_categories_async  # noqa: E402

CATEGORIES = ["vitamins-supplements", "baby-formula", "coffee", "snacks"]


async def _fake_fetch(cat: str, delay: float = 0.05):
    await asyncio.sleep(delay)
    return {"category": cat, "items": [1, 2, 3]}


def test_all_categories_fetched():
    async def run():
        return await fetch_categories_async(
            CATEGORIES, lambda c: _fake_fetch(c, delay=0.0)
        )
    out = asyncio.run(run())
    assert out["ok_count"] == 4 and out["error_count"] == 0
    assert set(out["by_category"].keys()) == set(CATEGORIES)


def test_parallel_faster_than_sequential():
    """With 4 categories each sleeping 0.05s, concurrency=4 must finish in
    ~1x the sleep; the sequential baseline would cost 4x."""
    async def run():
        t0 = time.monotonic()
        await fetch_categories_async(CATEGORIES, lambda c: _fake_fetch(c, delay=0.05), concurrency=4)
        return time.monotonic() - t0
    elapsed = asyncio.run(run())
    assert elapsed < 0.18, "parallel fetch took %.3fs (expected ~0.05-0.10s)" % elapsed


def test_semaphore_limits_concurrency():
    """concurrency=1 forces sequential: elapsed ~= 4 x per-category sleep."""
    async def run():
        t0 = time.monotonic()
        await fetch_categories_async(CATEGORIES, lambda c: _fake_fetch(c, delay=0.05), concurrency=1)
        return time.monotonic() - t0
    elapsed = asyncio.run(run())
    assert elapsed >= 0.18


def test_failing_category_isolated():
    async def flaky(cat):
        if cat == "coffee":
            raise RuntimeError("boom")
        return {"category": cat}

    out = asyncio.run(fetch_categories_async(CATEGORIES, flaky))
    assert out["error_count"] == 1 and out["ok_count"] == 3
    ok, val = out["by_category"]["coffee"]
    assert ok is False and "boom" in val


def test_timeout_marks_category_failed():
    async def slow(cat):
        await asyncio.sleep(0.2)
        return {"category": cat}

    out = asyncio.run(fetch_categories_async(["a"], slow, timeout_seconds=0.01))
    assert out["error_count"] == 1 and out["ok_count"] == 0