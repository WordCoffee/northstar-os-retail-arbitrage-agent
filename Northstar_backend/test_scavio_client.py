import importlib
import test_network_guard  # noqa: F401  (blocks real network calls)
import unittest
from unittest import mock
from requests.exceptions import Timeout
import scavio_client


class SearchKirklandProductsTests(unittest.TestCase):
    def setUp(self):
        self.keywords = ["test keyword"]

    @mock.patch("scavio_client.requests.post")
    def test_timeout_returns_empty_list(self, mock_post):
        mock_post.side_effect = Timeout("timed out")
        with mock.patch.object(scavio_client, "LAST_SEARCH_ERROR", None):
            result = scavio_client.search_kirkland_products(keywords=self.keywords, pages=1)
            self.assertEqual(result, [])
            self.assertIsNotNone(scavio_client.LAST_SEARCH_ERROR)
        mock_post.assert_called_once()
        self.assertEqual(mock_post.call_args.kwargs["timeout"], 30)

    @mock.patch("scavio_client.requests.post")
    def test_non_200_sets_upstream_error_flag(self, mock_post):
        resp = mock.Mock()
        resp.status_code = 500
        resp.text = "boom"
        mock_post.return_value = resp
        with mock.patch.object(scavio_client, "LAST_SEARCH_ERROR", None):
            result = scavio_client.search_kirkland_products(keywords=self.keywords, pages=1)
            self.assertEqual(result, [])
            self.assertIsNotNone(scavio_client.LAST_SEARCH_ERROR)

    @mock.patch("scavio_client.requests.post")
    def test_success_clears_upstream_error_flag(self, mock_post):
        resp = mock.Mock()
        resp.status_code = 200
        resp.json.return_value = {"data": {"products": []}}
        mock_post.return_value = resp
        with mock.patch.object(scavio_client, "LAST_SEARCH_ERROR", "stale error"):
            result = scavio_client.search_kirkland_products(keywords=self.keywords, pages=1)
        self.assertEqual(result, [])
        self.assertIsNone(scavio_client.LAST_SEARCH_ERROR)

    @mock.patch("scavio_client.requests.post")
    def test_parses_products(self, mock_post):
        resp = mock.Mock()
        resp.status_code = 200
        resp.json.return_value = {
            "data": {
                "products": [
                    {
                        "asin": "B000000001",
                        "title": "Item One",
                        "price": {"value": "12.34"},
                        "url": "http://x",
                    },
                    {
                        "asin": "B000000002",
                        "name": "Item Two",
                        "price": 9.99,
                        "link": "http://y",
                    },
                ]
            }
        }
        mock_post.return_value = resp
        result = scavio_client.search_kirkland_products(keywords=self.keywords, pages=1)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["asin"], "B000000001")
        self.assertEqual(result[0]["amazon_price"], 12.34)
        self.assertEqual(result[1]["amazon_price"], 9.99)

    @mock.patch("scavio_client.requests.post")
    def test_missing_price_stays_none_not_zero(self, mock_post):
        resp = mock.Mock()
        resp.status_code = 200
        resp.json.return_value = {
            "data": {
                "products": [
                    {
                        "asin": "B000000003",
                        "title": "No Price Item",
                        "url": "http://z",
                    },
                    {
                        "asin": "B000000004",
                        "title": "Zero Price Item",
                        "price": 0,
                        "url": "http://w",
                    },
                ]
            }
        }
        mock_post.return_value = resp
        result = scavio_client.search_kirkland_products(keywords=self.keywords, pages=1)
        self.assertEqual(len(result), 2)
        self.assertIsNone(result[0]["amazon_price"], "missing price stays None, never 0")
        self.assertIsNone(result[1]["amazon_price"], "zero price stays None, never 0")

    @mock.patch("scavio_client.requests.post")
    def test_missing_api_key_skips_search(self, mock_post):
        with mock.patch.object(scavio_client, "SCAVIO_API_KEY", ""):
            with mock.patch.object(scavio_client, "LAST_SEARCH_ERROR", None):
                result = scavio_client.search_kirkland_products(keywords=["k"], pages=1)
                self.assertEqual(result, [])
                self.assertIsNotNone(scavio_client.LAST_SEARCH_ERROR)
        mock_post.assert_not_called()

    def test_import_without_api_key_does_not_crash(self):
        with mock.patch.dict("os.environ", {"SCAVIO_API_KEY": ""}):
            with mock.patch("scavio_client.load_dotenv"):
                reloaded = importlib.reload(scavio_client)
                result = reloaded.search_kirkland_products(keywords=["k"], pages=1)
        self.assertIsNotNone(reloaded)
        self.assertEqual(result, [])
        importlib.reload(scavio_client)


if __name__ == "__main__":
    unittest.main()
