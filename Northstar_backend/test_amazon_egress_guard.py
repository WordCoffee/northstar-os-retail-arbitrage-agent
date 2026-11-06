"""The Amazon boundary at the provider egress, not in a docstring.

Found by the boundary-mapping review (2026-11-06): `_fetch` forwarded any URL to
the Web Unlocker, and `agents/golden_goose_finder/amazon_adapters.py` builds
`https://www.amazon.com/dp/{asin}` for it. A live Amazon fetch was one call away
with no gate anywhere on the path.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

import bright_data_client as bdc  # noqa: E402


@pytest.mark.parametrize("url", [
    "https://www.amazon.com/dp/B01FYY3M38",
    "https://amazon.co.uk/gp/offer-listing/X",
    "https://smile.amazon.com/",
    "https://www.amazon.com.evil.test/dp/X",
    "https://amzn.to/3xyz",
    "https://a.co/d/xyz",
    "https://media-amazon.com/images/I/x.jpg",
    "https://images-amazon.com/images/I/x.jpg",
    "https://amazon-adsystem.com/x",
])
def test_amazon_urls_are_refused(url):
    assert bdc._amazon_refusal(url), url


@pytest.mark.parametrize("url", [
    "https://www.costco.com/x",
    "https://github.com/block/goose",
    "https://notamazon.com.evil.test/",     # not Amazon: a different registrable domain
    "https://example.com/amazon.com/dp",    # amazon in the path, not the host
])
def test_non_amazon_urls_pass(url):
    assert bdc._amazon_refusal(url) is None, url


def test_the_refusal_happens_before_the_api_key_check(monkeypatch):
    """Order matters: the boundary must not depend on credentials being present."""
    monkeypatch.setattr(bdc, "BRIGHTDATA_UNLOCKER_API_KEY", "")
    with pytest.raises(RuntimeError) as exc:
        bdc._fetch("https://www.amazon.com/dp/B01FYY3M38")
    assert "amazon_refused" in str(exc.value)
    assert bdc.LAST_ERROR["type"] == "policy_refused"


def test_a_missing_key_still_raises_value_error_for_allowed_hosts(monkeypatch):
    monkeypatch.setattr(bdc, "BRIGHTDATA_UNLOCKER_API_KEY", "")
    with pytest.raises(ValueError):
        bdc._fetch("https://www.costco.com/x")
