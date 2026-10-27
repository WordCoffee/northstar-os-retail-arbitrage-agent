"""Costco adapter (P6-T3).

Public catalog/prices. Member pricing needs sign-in (signed-in task).
Selectors are data-driven JSON so fixes need no code change.

Provenance: In-house implementation based on NORTHSTAROS_MASTER_BUILD_PLAN.md P6-T3.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional

try:
    from ..adapter_base import SiteAdapter
except ImportError:
    import sys, os
    _p = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if _p not in sys.path:
        sys.path.insert(0, _p)
    from adapter_base import SiteAdapter


class CostcoAdapter(SiteAdapter):
    """Costco public catalog adapter.

    Public catalog and prices (no sign-in needed).
    Member pricing requires sign-in (signed-in task, not in default allowed_tasks).
    """

    def __init__(self, selectors: Optional[Dict[str, str]] = None) -> None:
        default_selectors = {
            "title": "h1",
            "price": ".price",
            "item_number": ".item-number",
            "description": ".description",
            "availability": ".availability",
        }
        super().__init__(
            origin="costco.com",
            selectors=selectors or default_selectors,
            allowed_tasks=["read", "extract", "costco_scan"],
            max_pages_per_run=10,
            signed_in_check=self._is_signed_in,
            login_url="https://www.costco.com/LogonForm",
            version="1.0.0",
        )

    @staticmethod
    def _is_signed_in(html: str) -> bool:
        """Check if the page indicates a signed-in Costco session."""
        low = html.lower()
        return "sign out" in low or "my account" in low or "member since" in low

    @classmethod
    def from_json(cls, path: str) -> "CostcoAdapter":
        """Load adapter from a JSON selector file."""
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh) if (json := __import__("json")) else {}
        return cls(selectors=data.get("selectors"))

    def to_json(self, path: str) -> None:
        """Save adapter selectors to JSON."""
        import json
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(self.to_dict(), fh, indent=2)
