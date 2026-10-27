"""SellerSprite adapter (P6-T3).

Export download, signed-in required. Extracts product research data.

Provenance: In-house implementation based on NORTHSTAROS_MASTER_BUILD_PLAN.md P6-T3.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

try:
    from ..adapter_base import SiteAdapter
except ImportError:
    import sys, os
    _p = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if _p not in sys.path:
        sys.path.insert(0, _p)
    from adapter_base import SiteAdapter


class SellerSpriteAdapter(SiteAdapter):
    """SellerSprite product research adapter.

    Export download requires sign-in. Extracts ASIN, title, price, BSR, sales.
    """

    def __init__(self, selectors: Optional[Dict[str, str]] = None) -> None:
        default_selectors = {
            "asin": "td.asin",
            "title": "td.title",
            "price": "td.price",
            "bsr": "td.bsr",
            "sales": "td.sales",
            "export_button": "button.export",
        }
        super().__init__(
            origin="sellersprite.com",
            selectors=selectors or default_selectors,
            allowed_tasks=["read", "extract", "export_download"],
            max_pages_per_run=5,
            signed_in_check=self._is_signed_in,
            login_url="https://www.sellersprite.com/login",
            version="1.0.0",
        )

    @staticmethod
    def _is_signed_in(html: str) -> bool:
        low = html.lower()
        return "logout" in low or "my account" in low or "dashboard" in low

    @classmethod
    def from_json(cls, path: str) -> "SellerSpriteAdapter":
        import json
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        return cls(selectors=data.get("selectors"))

    @staticmethod
    def is_export_page(url: str) -> bool:
        return "export" in url.lower() or "download" in url.lower()
