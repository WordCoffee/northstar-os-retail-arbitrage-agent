"""FIXES_50 #38 — async Costco catalog fetch adapter (Phase G).

Fire all category queries in parallel instead of sequentially. The transport
(``fetch_one``) is INJECTED, so tests prove the async path with a fake
transport and no live call can escape this module. The live Costco path
(`_live_scan` in main.py) is gated by §3 operator approval; this adapter is
what that path should route its per-category fetch through.

Contract:
    fetch_categories_async(categories, fetch_one, concurrency=4)
      -> {"by_category": {cat: (ok, result_or_error)}, "ok_count", ...}
"""

from __future__ import annotations

import asyncio
from typing import Any, Awaitable, Callable, Dict, List

# Callable[category] -> Awaitable[Any]
FetchOne = Callable[[str], Awaitable[Any]]


async def fetch_categories_async(
    categories: List[str],
    fetch_one: FetchOne,
    *,
    concurrency: int = 4,
    timeout_seconds: float | None = None,
) -> Dict[str, Any]:
    """Fetch all categories in parallel under a semaphore.

    A failing category is recorded as ``(False, <error>)`` — it never
    propagates and never halts the other category fetches.
    """
    sem = asyncio.Semaphore(concurrency)

    async def work(cat: str):
        async with sem:
            try:
                if timeout_seconds is not None:
                    result = await asyncio.wait_for(fetch_one(cat), timeout_seconds)
                else:
                    result = await fetch_one(cat)
                return cat, True, result
            except Exception as exc:  # noqa: BLE001 - per-category isolation
                return cat, False, str(exc)

    results = await asyncio.gather(*(work(c) for c in categories))
    by_category: Dict[str, tuple] = {c: (ok, val) for c, ok, val in results}
    ok_count = sum(1 for _, ok, _ in results if ok)
    return {
        "categories": list(categories),
        "by_category": by_category,
        "ok_count": ok_count,
        "error_count": len(categories) - ok_count,
    }