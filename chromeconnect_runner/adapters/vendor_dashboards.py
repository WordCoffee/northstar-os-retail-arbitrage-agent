"""Vendor dashboards adapter (P6-T3).

Key creation pages: navigate and stop for the owner.
Signed-in (navigate and stop, never auto-fill credentials).

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


class VendorDashboardsAdapter(SiteAdapter):
    """Vendor dashboard adapter (key creation pages).

    Navigates to key creation pages and stops for owner.
    Never auto-fills credentials or submits forms.
    """

    def __init__(self, selectors: Optional[Dict[str, str]] = None) -> None:
        default_selectors = {
            "page_title": "h1",
            "api_key_field": "input[name='api_key']",
            "create_button": "button[type='submit']",
            "status": ".status",
        }
        super().__init__(
            origin="vendor",
            selectors=selectors or default_selectors,
            allowed_tasks=["navigate", "read", "stop_for_owner"],
            max_pages_per_run=3,
            signed_in_check=None,
            login_url=None,
            version="1.0.0",
        )

    @staticmethod
    def is_key_creation_page(url: str) -> bool:
        """Check if URL is a key creation page."""
        keywords = ["api", "key", "token", "credential", "secret"]
        return any(kw in url.lower() for kw in keywords)

    @classmethod
    def from_json(cls, path: str) -> "VendorDashboardsAdapter":
        import json
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        return cls(selectors=data.get("selectors"))
