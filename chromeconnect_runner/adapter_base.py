"""Site adapter base class (P6-T3).

Each adapter declares: origin, signed_in_check, login_url, allowed_tasks,
selectors (data-driven JSON), extract() returning fields with provenance,
max_pages_per_run.

Provenance: In-house implementation based on NORTHSTAROS_MASTER_BUILD_PLAN.md P6-T3.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

import sys, os
_nb = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "Northstar_backend")
if _nb not in sys.path:
    sys.path.insert(0, _nb)
try:
    from Northstar_backend.chromeconnect_observation import extract_accessibility_tree
except ImportError:
    from chromeconnect_observation import extract_accessibility_tree


@dataclass
class AdapterResult:
    """Result of an adapter extraction."""
    fields: Dict[str, Any] = field(default_factory=dict)
    source_url: str = ""
    observed_at: str = ""
    selector_version: str = "1.0.0"
    confidence: float = 0.0
    status: str = "OK"  # OK | UNKNOWN | DEGRADED
    screenshot_hash: Optional[str] = None
    errors: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "fields": self.fields,
            "source_url": self.source_url,
            "observed_at": self.observed_at,
            "selector_version": self.selector_version,
            "confidence": self.confidence,
            "status": self.status,
            "screenshot_hash": self.screenshot_hash,
            "errors": self.errors,
        }


class SiteAdapter:
    """Base class for site adapters."""

    def __init__(
        self,
        origin: str,
        selectors: Optional[Dict[str, str]] = None,
        allowed_tasks: Optional[List[str]] = None,
        max_pages_per_run: int = 5,
        signed_in_check: Optional[Callable[[str], bool]] = None,
        login_url: Optional[str] = None,
        version: str = "1.0.0",
    ) -> None:
        self.origin = origin
        self.selectors = selectors or {}
        self.allowed_tasks = allowed_tasks or ["read", "extract"]
        self.max_pages_per_run = max_pages_per_run
        self.signed_in_check = signed_in_check
        self.login_url = login_url
        self.version = version
        self.state = "active"  # active | degraded | disabled

    def is_allowed_task(self, task: str) -> bool:
        return task in self.allowed_tasks

    def check_signed_in(self, html: str) -> bool:
        """Check if the page indicates a signed-in state."""
        if self.signed_in_check:
            return self.signed_in_check(html)
        return False

    def extract(self, html: str, url: str = "") -> AdapterResult:
        """Extract fields from HTML using selectors.

        Returns AdapterResult with fields, provenance, status.
        """
        from datetime import datetime, timezone

        result = AdapterResult(
            source_url=url,
            observed_at=datetime.now(timezone.utc).isoformat(),
            selector_version=self.version,
        )

        elements = extract_accessibility_tree(html)
        missing = []

        for field_name, selector in self.selectors.items():
            value = self._extract_field(field_name, selector, elements, html)
            if value is None:
                missing.append(field_name)
                result.fields[field_name] = None
            else:
                result.fields[field_name] = value

        if missing:
            result.status = "DEGRADED" if len(missing) < len(self.selectors) else "UNKNOWN"
            result.errors.append(f"missing fields: {missing}")
            result.confidence = max(0.0, 1.0 - len(missing) / max(len(self.selectors), 1))
        else:
            result.status = "OK"
            result.confidence = 1.0

        return result

    def _extract_field(
        self, field_name: str, selector: str, elements: List[Dict], html: str
    ) -> Optional[Any]:
        """Extract a single field using the selector.

        Strategies:
        1. CSS-like tag match (selector is a tag name)
        2. Text contains field name
        3. First element with text
        """
        # Strategy 1: tag match
        for el in elements:
            if el.get("tag", "").lower() == selector.lower():
                text = el.get("text", "")
                if text:
                    return text
                href = el.get("href", "")
                if href:
                    return href

        # Strategy 2: text contains field name
        for el in elements:
            text = el.get("text", "")
            if text and field_name.lower() in text.lower():
                return text

        # Strategy 3: CSS selector match in raw HTML
        import re as _re
        sel = selector.strip()
        tag = None
        cls = None
        id_val = None
        if sel.startswith("#"):
            id_val = sel[1:]
        elif sel.startswith("."):
            cls = sel[1:]
        elif "#" in sel and "." in sel:
            # tag#id.class or tag.class#id
            for part in sel.replace("#", " #").replace(".", " .").split():
                if part.startswith("#"):
                    id_val = part[1:]
                elif part.startswith("."):
                    cls = part[1:]
                else:
                    tag = part
        elif "#" in sel:
            tag, id_val = sel.split("#", 1)
        elif "." in sel:
            tag, cls = sel.split(".", 1)
        else:
            tag = sel

        # Build regex pattern using string concatenation (avoid f-string quote issues)
        q = chr(34)  # double quote
        sq = chr(39)  # single quote
        if tag and id_val and cls:
            pat = "<" + tag + "[^>]*id=[" + q + sq + "]?" + id_val + "[" + q + sq + "]?[^>]*class=[" + q + sq + "][^" + q + sq + "]*" + cls + "[^" + q + sq + "]*[" + q + sq + "][^>]*>(.*?)</" + tag + ">"
        elif tag and id_val:
            pat = "<" + tag + "[^>]*id=[" + q + sq + "]?" + id_val + "[" + q + sq + "]?[^>]*>(.*?)</" + tag + ">"
        elif tag and cls:
            pat = "<" + tag + "[^>]*class=[" + q + sq + "][^" + q + sq + "]*" + cls + "[^" + q + sq + "]*[" + q + sq + "][^>]*>(.*?)</" + tag + ">"
        elif id_val:
            pat = "<[^>]*id=[" + q + sq + "]?" + id_val + "[" + q + sq + "]?[^>]*>(.*?)</[^>]+>"
        elif cls:
            pat = "<[^>]*class=[" + q + sq + "][^" + q + sq + "]*" + cls + "[^" + q + sq + "]*[" + q + sq + "][^>]*>(.*?)</[^>]+>"
        elif tag:
            pat = "<" + tag + "[^>]*>(.*?)</" + tag + ">"
        else:
            pat = None

        if pat:
            match = _re.search(pat, html, _re.I | _re.S)
            if match:
                text = _re.sub(r"<[^>]+>", "", match.group(1)).strip()
                if text:
                    return text

        # Also try matching in interactive elements by class/id
        for el in elements:
            el_cls = el.get("class", "")
            el_id = el.get("id", "")
            if cls and cls in el_cls:
                text = el.get("text", "")
                if text:
                    return text
            if id_val and el_id == id_val:
                text = el.get("text", "")
                if text:
                    return text

        # Strategy 4: first element with text
        for el in elements:
            text = el.get("text", "")
            if text:
                return text

        return None

    def mark_degraded(self, reason: str) -> None:
        self.state = "degraded"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "origin": self.origin,
            "selectors": self.selectors,
            "allowed_tasks": self.allowed_tasks,
            "max_pages_per_run": self.max_pages_per_run,
            "version": self.version,
            "state": self.state,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SiteAdapter":
        return cls(
            origin=data.get("origin", ""),
            selectors=data.get("selectors", {}),
            allowed_tasks=data.get("allowed_tasks", ["read", "extract"]),
            max_pages_per_run=data.get("max_pages_per_run", 5),
            version=data.get("version", "1.0.0"),
        )
