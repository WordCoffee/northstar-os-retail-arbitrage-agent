"""Offline tests for tools/provider_seller_probe.py (zero network).

All transports are exercised through unittest.mock-injected fake responses;
no live call can fire from this file (keys are DUMMY, requests mocked).
"""

import json
import os
import sys
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "tools"))

os.environ["FIRECRAWL_API_KEY"] = "DUMMY"
os.environ["SCRAPE_DO_API_KEY"] = "DUMMY"
os.environ["KEENABLE_API_KEY"] = "DUMMY"
os.environ["BROWSERBASE_API_KEY"] = "DUMMY"

import provider_seller_probe as probe


def _resp(status=200, text="", json_data=None, headers=None):
    r = MagicMock()
    r.status_code = status
    r.text = text
    r.headers = headers or {}
    if json_data is None:
        r.json.side_effect = ValueError("no json")
    else:
        r.json.return_value = json_data
    return r


class TupleContractTests(unittest.TestCase):
    """_get/_post must always return a (result, error) tuple."""

    def test_get_returns_tuple_on_success(self):
        with patch.object(probe.requests, "get", return_value=_resp(200, text="ok")):
            out = probe._get("https://example.com")
        self.assertIsInstance(out, tuple)
        self.assertEqual(len(out), 2)

    def test_scrapedo_unpacks_get_tuple(self):
        with patch.object(probe.requests, "get",
                          return_value=_resp(200, text="<html>Sold by X</html>")):
            out, err = probe.fetch_scrapedo("https://www.amazon.com/dp/B00BH3HPZW")
        self.assertIsNone(err)
        self.assertIn("Sold by", out["content"])

    def test_keenable_unpacks_get_tuple(self):
        payload = {"content": "# T\nSold by X", "title": "T"}
        with patch.object(probe.requests, "get",
                          return_value=_resp(200, json_data=payload)):
            out, err = probe.fetch_keenable("https://www.amazon.com/dp/B00BH3HPZW")
        self.assertIsNone(err)
        self.assertIn("Sold by", out["content"])


class MarkerScanTests(unittest.TestCase):
    def test_seller_markers_counted(self):
        marks = probe.scan_markers("<html>Sold by TestSeller New (3) from $9.99</html>")
        self.assertEqual(marks["seller_markers"]["sold_by"], 1)
        self.assertEqual(marks["seller_markers"]["new_offers_count"], 1)
        self.assertEqual(sum(marks["block_markers"].values()), 0)

    def test_block_markers_counted(self):
        marks = probe.scan_markers("<html>Enter the characters you see</html>")
        self.assertGreater(marks["block_markers"]["captcha"], 0)


class GateTests(unittest.TestCase):
    def test_missing_key_is_config_error(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("SCRAPE_DO_API_KEY", None)
            with patch.object(probe.os, "getenv", return_value=None):
                out, err = probe.fetch_scrapedo("https://www.amazon.com/dp/B00BH3HPZW")
        self.assertIsNone(out)
        self.assertTrue(err.startswith("config_error"))


if __name__ == "__main__":
    unittest.main()
