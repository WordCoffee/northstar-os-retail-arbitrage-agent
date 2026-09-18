"""Tests for the generalized (category-agnostic) search path.

Covers `amazon_search.search_products(match_all=...)` and the provider
pass-through: the Kirkland relevance filter stays in force for the default
path, and is bypassed when match_all=True. No real network call is made.
"""

import os
from unittest import mock
from unittest.mock import patch

import pytest

import amazon_search
import bright_data_client


LIVE_ENV = "SCANNER_LIVE_ALLOWED"


@pytest.fixture()
def live_gate(monkeypatch):
    monkeypatch.setenv(LIVE_ENV, "1")
    yield
    monkeypatch.delenv(LIVE_ENV, raising=False)


def _chocodata_response(products):
    return mock.Mock(
        status_code=200,
        text="",
        json=lambda: {"page": 1, "products": products, "html": ""},
    )


def _kirkland_product(asin="B000000001"):
    return {"asin": asin, "title": "Kirkland Signature Coffee", "price": 20.0}


def _other_brand_product(asin="B000000002"):
    return {"asin": asin, "title": "Acme Pain Relief 200 ct", "brand": "Acme", "price": 12.0}


# ---------------------------------------------------------------------------
# Gate containment
# ---------------------------------------------------------------------------

def test_search_products_blocked_when_gate_off(monkeypatch):
    monkeypatch.delenv(LIVE_ENV, raising=False)
    with patch.object(bright_data_client, "search_products") as bd:
        assert amazon_search.search_products(keywords=["x"], match_all=True) == []
        bd.assert_not_called()


def test_gate_off_clears_no_error_flag(monkeypatch):
    monkeypatch.delenv(LIVE_ENV, raising=False)
    amazon_search.LAST_SEARCH_ERROR = "stale"
    amazon_search.search_products(keywords=["x"], match_all=True)
    assert amazon_search.LAST_SEARCH_ERROR == "stale"


# ---------------------------------------------------------------------------
# Delegation / backward compatibility
# ---------------------------------------------------------------------------

def test_search_kirkland_products_delegates_match_all_false(live_gate):
    with patch.object(amazon_search, "search_products", return_value=[]) as sp:
        amazon_search.search_kirkland_products(keywords=["kirkland"], pages=2)
    sp.assert_called_once_with(keywords=["kirkland"], pages=2, match_all=False)


def test_brightdata_passes_match_all_through(live_gate):
    with patch.object(amazon_search, "SCANNER_SEARCH_SOURCE", "BRIGHTDATA"), \
         patch.object(bright_data_client, "search_products", return_value=[]) as bd:
        amazon_search.search_products(keywords=["acme"], pages=1, match_all=True)
    bd.assert_called_once_with("acme", 1, match_all=True)


# ---------------------------------------------------------------------------
# CHOCODATA match_all behavior
# ---------------------------------------------------------------------------

def test_chocodata_default_filters_to_kirkland(live_gate):
    response = _chocodata_response([_kirkland_product(), _other_brand_product()])
    with patch.object(amazon_search, "SCANNER_SEARCH_SOURCE", "CHOCODATA"), \
         patch.object(amazon_search, "CHOCODATA_API_KEY", "cd_test"), \
         patch.object(amazon_search, "requests", mock.Mock(get=mock.Mock(return_value=response))):
        result = amazon_search.search_products(keywords=["x"], pages=1, match_all=False)
    assert [r["asin"] for r in result] == ["B000000001"]


def test_chocodata_match_all_keeps_every_brand(live_gate):
    response = _chocodata_response([_kirkland_product(), _other_brand_product()])
    with patch.object(amazon_search, "SCANNER_SEARCH_SOURCE", "CHOCODATA"), \
         patch.object(amazon_search, "CHOCODATA_API_KEY", "cd_test"), \
         patch.object(amazon_search, "requests", mock.Mock(get=mock.Mock(return_value=response))):
        result = amazon_search.search_products(keywords=["x"], pages=1, match_all=True)
    assert {r["asin"] for r in result} == {"B000000001", "B000000002"}


# ---------------------------------------------------------------------------
# Bright Data client match_all behavior
# ---------------------------------------------------------------------------

def test_bright_data_client_match_all_bypasses_kirkland_filter(live_gate):
    card = _other_brand_product()
    html = 'data-asin="B000000002"'
    with patch.object(bright_data_client, "_fetch", return_value=html), \
         patch.object(bright_data_client, "_parse_card", return_value=card):
        filtered = bright_data_client.search_products("acme", 1, match_all=False)
        all_cards = bright_data_client.search_products("acme", 1, match_all=True)
    assert filtered == []
    assert [c["asin"] for c in all_cards] == ["B000000002"]
