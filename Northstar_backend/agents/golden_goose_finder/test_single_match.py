"""Offline single-match test (Phase F/S3 rewrite of the legacy live probe).

The former file flipped GOLDEN_GOOSE_LIVE_OPERATOR_APPROVED at import and ran
a LIVE match at import time (leaking the §3 gate into the whole pytest
process). This rewrite:

  * has NO import-time side effects — no env flips, no dotenv, no top-level
    execution (asserted by test_import_has_no_side_effects);
  * provides a deterministic OFFLINE pytest test that exercises the
    matching→economics path through the mock pipeline (zero provider calls);
  * keeps the original live probe behind ``if __name__ == "__main__"`` so it
    is never collected and requires explicit invocation + both §3 gates.
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

import pytest

_BACKEND = Path(__file__).resolve().parent.parent.parent
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

GATE_OPERATOR = "GOLDEN_GOOSE_LIVE_OPERATOR_APPROVED"


# ---------------------------------------------------------------------------
# Hygiene guards
# ---------------------------------------------------------------------------

def test_import_has_no_side_effects(capsys):
    """Importing this module must not flip the §3 gate nor run live discovery."""
    assert os.environ.get(GATE_OPERATOR) is None
    out = capsys.readouterr().out
    assert "Fetching Costco products" not in out


# ---------------------------------------------------------------------------
# Offline single-match smoke (mock pipeline, zero provider calls)
# ---------------------------------------------------------------------------

def test_offline_single_match_mock_pipeline():
    from agents.golden_goose_finder.amazon_matcher import find_individual_listing
    from agents.golden_goose_finder.wholesale_scanner import WholesaleProduct

    wp = WholesaleProduct(
        source_store="Costco",
        product_title="Nicorette Nicotine Gum 2mg, 200 Count",
        brand="Nicorette",
        category_slug="nicotine-cessation",
        pack_count=200,
        wholesale_price=89.99,
    )
    # live_armed=False → deterministic OFFLINE mock matching (no provider call)
    matches = asyncio.run(find_individual_listing(wp, max_candidates=3, live_armed=False))
    assert isinstance(matches, list) and matches
    assert all(getattr(m, "asin", None) for m in matches)
    # individual (non-wholesale-size) listings only
    for m in matches:
        assert "200 Count" not in (m.title or "")


# ---------------------------------------------------------------------------
# Original live probe — explicit invocation only (never collected)
# ---------------------------------------------------------------------------

async def _live_probe():
    print("Step 1: Fetching Costco products...")
    from costco_api_client import search_page
    items = search_page("vitamins", 1).get("items", [])
    if not items:
        print("  No items found. Aborting.")
        return

    print("Step 2: Parsing wholesale product...")
    from agents.golden_goose_finder.wholesale_scanner import parse_wholesale_product
    wp = parse_wholesale_product(items[0], source_store="Costco", category_slug="vitamins_supplements")
    print(f"  Title: {wp.product_title[:60]} / Brand: {wp.brand} / Price: ${wp.wholesale_price}")

    print("Step 3: Amazon matching (live_armed=True)...")
    from agents.golden_goose_finder.amazon_matcher import find_individual_listing
    result = await find_individual_listing(wp, live_armed=True)
    listing = result[0] if isinstance(result, list) and result else result
    if listing:
        print(f"  Found: ASIN={listing.asin}, price=${listing.amazon_price}")
    else:
        print("  No listing found")


if __name__ == "__main__":
    # Explicit §3 gates required; never auto-armed (B1).
    from agents.golden_goose_finder.live_scan_gate import LIVE_AUTH_PHRASE, LIVE_AUTH_PHRASE_ENV, LIVE_OPERATOR_ENV
    import os as _os
    approved = _os.getenv(LIVE_OPERATOR_ENV, "").strip() == "1"
    phrase_ok = _os.getenv(LIVE_AUTH_PHRASE_ENV, "").strip() == LIVE_AUTH_PHRASE
    if not (approved and phrase_ok):
        print("ERROR: live probe requires both §3 gates (operator-set env vars).")
        print("       %s=1 and %s=\"%s\"" % (LIVE_OPERATOR_ENV, LIVE_AUTH_PHRASE_ENV, LIVE_AUTH_PHRASE))
        sys.exit(2)
    asyncio.run(_live_probe())