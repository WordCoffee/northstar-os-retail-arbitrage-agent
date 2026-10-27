"""Tests for Chrome Connect site adapters (P6-T3)."""

import os
import sys
import json
import tempfile

import sys, os
_RUNNER_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _RUNNER_DIR not in sys.path:
    sys.path.insert(0, _RUNNER_DIR)
_TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
if _TESTS_DIR not in sys.path:
    sys.path.insert(0, _TESTS_DIR)

from adapter_base import SiteAdapter
# Import adapter modules directly to avoid package resolution issues
import importlib.util
def _load_adapter(name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(_RUNNER_DIR, 'adapters', name + '.py'))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

_costco_mod = _load_adapter('costco')
_amazon_mod = _load_adapter('amazon_public')
_vendor_mod = _load_adapter('vendor_dashboards')
CostcoAdapter = _costco_mod.CostcoAdapter
AmazonPublicAdapter = _amazon_mod.AmazonPublicAdapter
VendorDashboardsAdapter = _vendor_mod.VendorDashboardsAdapter


COSTCO_HTML = """
<html><body>
  <h1>Kirkland Signature Olive Oil 2L</h1>
  <span class="price">$14.99</span>
  <span class="item-number">Item #1234567</span>
  <p class="description">Cold-pressed olive oil from Italy.</p>
  <span class="availability">In Stock</span>
</body></html>
"""

AMAZON_HTML = """
<html><body>
  <span id="productTitle">Turmeric Powder 16oz Organic</span>
  <span class="a-price-whole">12</span>
  <div id="SalesRank">BSR: 5,432 in Grocery</div>
  <span class="a-icon-alt">4.5 out of 5 stars</span>
  <span id="acrCustomerReviewText">234 ratings</span>
  <div id="availability">In Stock</div>
</body></html>
"""

VENDOR_HTML = """
<html><body>
  <h1>API Key Management</h1>
  <input name="api_key" placeholder="Enter API key" />
  <button type="submit">Create Key</button>
  <span class="status">Active</span>
</body></html>
"""


def test_costco_adapter_extract():
    adapter = CostcoAdapter()
    result = adapter.extract(COSTCO_HTML, url="https://www.costco.com/p/1")
    assert result.status == "OK"
    assert result.fields.get("title") == "Kirkland Signature Olive Oil 2L"
    assert result.fields.get("price") == "$14.99"
    assert result.confidence == 1.0


def test_costco_adapter_allowed_tasks():
    adapter = CostcoAdapter()
    assert adapter.is_allowed_task("read")
    assert adapter.is_allowed_task("extract")
    assert adapter.is_allowed_task("costco_scan")
    assert not adapter.is_allowed_task("purchase")


def test_costco_adapter_signed_in_check():
    adapter = CostcoAdapter()
    signed_in_html = "<html><body><a>Sign Out</a><p>Member since 2020</p></body></html>"
    assert adapter.check_signed_in(signed_in_html) is True
    assert adapter.check_signed_in(COSTCO_HTML) is False


def test_costco_adapter_from_json():
    data = {"origin": "costco.com", "selectors": {"title": "h1", "price": ".price"}, "version": "2.0"}
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        import json
        json.dump(data, f)
        path = f.name
    try:
        adapter = CostcoAdapter.from_json(path)
        assert adapter.origin == "costco.com"
        assert adapter.selectors == {"title": "h1", "price": ".price"}
    finally:
        os.remove(path)


def test_amazon_public_adapter_extract():
    adapter = AmazonPublicAdapter()
    result = adapter.extract(AMAZON_HTML, url="https://www.amazon.com/dp/B0ABC123")
    assert result.status in ("OK", "DEGRADED")  # some fields may be missing
    assert result.fields.get("title") is not None


def test_amazon_public_is_amazon_url():
    assert AmazonPublicAdapter.is_amazon_url("https://www.amazon.com/dp/B0ABC123") is True
    assert AmazonPublicAdapter.is_amazon_url("https://www.costco.com/p/1") is False


def test_amazon_public_allowed_tasks():
    adapter = AmazonPublicAdapter()
    assert adapter.is_allowed_task("read")
    assert adapter.is_allowed_task("spot_verify")
    assert not adapter.is_allowed_task("purchase")


def test_vendor_dashboards_adapter_extract():
    adapter = VendorDashboardsAdapter()
    result = adapter.extract(VENDOR_HTML, url="https://vendor.com/api/keys")
    assert result.status in ("OK", "DEGRADED")
    assert result.fields.get("page_title") == "API Key Management"


def test_vendor_dashboards_is_key_creation():
    assert VendorDashboardsAdapter.is_key_creation_page("https://vendor.com/api/keys") is True
    assert VendorDashboardsAdapter.is_key_creation_page("https://vendor.com/home") is False


def test_vendor_dashboards_allowed_tasks():
    adapter = VendorDashboardsAdapter()
    assert adapter.is_allowed_task("navigate")
    assert adapter.is_allowed_task("read")
    assert adapter.is_allowed_task("stop_for_owner")
    assert not adapter.is_allowed_task("submit")


def test_adapter_to_dict():
    adapter = CostcoAdapter()
    d = adapter.to_dict()
    assert "origin" in d
    assert "selectors" in d
    assert "allowed_tasks" in d
    assert "version" in d
    assert "state" in d


def test_adapter_from_dict():
    data = {"origin": "example.com", "selectors": {"title": "h1"}, "allowed_tasks": ["read"], "version": "2.0"}
    adapter = SiteAdapter.from_dict(data)
    assert adapter.origin == "example.com"
    assert adapter.selectors == {"title": "h1"}


def test_adapter_mark_degraded():
    adapter = CostcoAdapter()
    adapter.mark_degraded("selector miss")
    assert adapter.state == "degraded"


def test_adapter_max_pages():
    adapter = CostcoAdapter()
    assert adapter.max_pages_per_run == 10
    adapter2 = AmazonPublicAdapter()
    assert adapter2.max_pages_per_run == 5
