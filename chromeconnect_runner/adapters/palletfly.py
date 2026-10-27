"""PalletFly adapter (P6-T3).

Reference export. May need sign-in for full access.

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


class PalletFlyAdapter(SiteAdapter):
    """PalletFly reference export adapter.

    Reference export (may be public). Full access may need sign-in.
    """

    def __init__(self, selectors: Optional[Dict[str, str]] = None) -> None:
        default_selectors = {
            "title": "h1",
            "price": ".price",
            "lot_size": ".lot-size",
            "manifest": ".manifest-link",
            "export_button": "button.export",
        }
        super().__init__(
            origin="palletfly.com",
            selectors=selectors or default_selectors,
            allowed_tasks=["read", "extract", "reference_export"],
            max_pages_per_run=5,
            signed_in_check=self._is_signed_in,
            login_url="https://www.palletfly.com/login",
            version="1.0.0",
        )

    @staticmethod
    def _is_signed_in(html: str) -> bool:
        low = html.lower()
        return "logout" in low or "my account" in low or "dashboard" in low

    @classmethod
    def from_json(cls, path: str) -> "PalletFlyAdapter":
        import json
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        return cls(selectors=data.get("selectors"))
