"""Amazon public adapter (P6-T3).

Product page reads for spot verification only, low volume.
Public pages only (no sign-in). Reads product details, price, BSR.

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


class AmazonPublicAdapter(SiteAdapter):
    """Amazon public product page adapter.

    Low volume spot verification only. Public pages, no sign-in.
    """

    def __init__(self, selectors: Optional[Dict[str, str]] = None) -> None:
        default_selectors = {
            "title": "span#productTitle",
            "price": "span.a-price-whole",
            "bsr": "#SalesRank",
            "rating": "span.a-icon-alt",
            "review_count": "#acrCustomerReviewText",
            "availability": "#availability",
        }
        super().__init__(
            origin="amazon.com",
            selectors=selectors or default_selectors,
            allowed_tasks=["read", "extract", "spot_verify"],
            max_pages_per_run=5,
            signed_in_check=None,  # public, no sign-in needed
            login_url=None,
            version="1.0.0",
        )

    @staticmethod
    def is_amazon_url(url: str) -> bool:
        """Check if URL is an Amazon product page."""
        return "amazon.com" in url and "/dp/" in url

    @classmethod
    def from_json(cls, path: str) -> "AmazonPublicAdapter":
        import json
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        return cls(selectors=data.get("selectors"))
