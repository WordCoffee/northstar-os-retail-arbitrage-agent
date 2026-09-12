import test_network_guard  # noqa: F401  (blocks real network calls)
from unittest.mock import patch
from fastapi import HTTPException

import main


def _fake_product(price):
    return {
        "source": "canopy",
        "asin": "B00GYZWNY6",
        "title": "Fake Product",
        "brand": "Fake Brand",
        "product_url": "https://www.amazon.com/dp/B00GYZWNY6",
        "amazon_price": price,
        "currency": "USD",
        "is_prime": True,
        "is_new": True,
        "is_in_stock": True,
        "image_url": None,
        "rating": 4.5,
        "reviews_count": 1000,
        "seller_id": "s1",
        "seller_name": "Seller One",
        "categories": None,
        "technical_specifications": None,
        "coupon": None,
        "seller_count": None,
        "offers_count": None,
        "fulfillment": None,
        "is_fba": None,
        "is_fbm": None,
        "amazon_is_seller": None,
        "buy_box_price": None,
        "buy_box_seller": None,
        "data_gaps": [],
    }


def test_valid_asin_calls_canopy_exactly_once():
    with patch("main.get_canopy_product", return_value=_fake_product(56.66)) as mocked:
        result = main.get_product_canopy("B00GYZWNY6")

    mocked.assert_called_once_with("B00GYZWNY6")
    assert result["enrichment_source"] == "canopy"
    assert result["enrichment_scope"] == "one_explicit_asin"
    assert result["live_price_verified"] is True
    assert result["amazon_price"] == 56.66
    assert result["seller_count"] is None
    assert result["is_fba"] is None
    assert result["buy_box_seller"] is None


def test_zero_price_not_verified():
    with patch("main.get_canopy_product", return_value=_fake_product(0)) as mocked:
        result = main.get_product_canopy("B00GYZWNY6")

    mocked.assert_called_once_with("B00GYZWNY6")
    assert result["live_price_verified"] is False


def test_invalid_asin_returns_400():
    with patch("main.get_canopy_product") as mocked:
        try:
            main.get_product_canopy("bad")
        except HTTPException as e:
            assert e.status_code == 400
            assert e.detail == "Invalid ASIN. Expected a 10-character alphanumeric Amazon ASIN."
        else:
            raise AssertionError("expected HTTPException for invalid ASIN")

    mocked.assert_not_called()


if __name__ == "__main__":
    test_valid_asin_calls_canopy_exactly_once()
    test_zero_price_not_verified()
    test_invalid_asin_returns_400()
    print("canopy route tests passed (0 live Canopy calls)")