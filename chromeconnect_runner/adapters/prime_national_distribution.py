"""Prime National Distribution adapter (P6-T3).

UPC/wholesale list, signed-in required.

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


class PrimeNationalDistributionAdapter(SiteAdapter):
    """Prime National Distribution wholesale list adapter.

    UPC/wholesale list (signed-in required).
    """

    def __init__(self, selectors: Optional[Dict[str, str]] = None) -> None:
        default_selectors = {
            "upc": "td.upc",
            "title": "td.title",
            "wholesale_price": "td.wholesale-price",
            "case_qty": "td.case-qty",
            "availability": "td.availability",
        }
        super().__init__(
            origin="primenationaldistribution.com",
            selectors=selectors or default_selectors,
            allowed_tasks=["read", "extract", "wholesale_list"],
            max_pages_per_run=10,
            signed_in_check=self._is_signed_in,
            login_url="https://www.primenationaldistribution.com/login",
            version="1.0.0",
        )

    @staticmethod
    def _is_signed_in(html: str) -> bool:
        low = html.lower()
        return "logout" in low or "my account" in low or "dashboard" in low

    @classmethod
    def from_json(cls, path: str) -> "PrimeNationalDistributionAdapter":
        import json
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        return cls(selectors=data.get("selectors"))
