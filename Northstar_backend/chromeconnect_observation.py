"""Chrome Connect observation layer (Phase 1, behind flag).

Pruned accessibility snapshot with element refs, token budget, and viewport paging.
Default OFF via CHROMECONNECT_OBSERVATION_ENABLED (must be '1' to activate).

Design (Chrome Connect 3.0 plan, section 3):
- Default observation: accessibility snapshot with stable element refs.
- Pruning: drop non-interactive/off-topic nodes, collapse repeated rows
  (show first N + count), cap total at token budget (start 4K).
- Viewport-aware: snapshot visible region first, scroll for more.
- Vision is last resort (local VL model) — not handled here.

Privacy: this module processes HTML only. It never receives or logs
credentials, cookies, or page content from signed-in pages. Callers must
ensure the HTML passed in is from an allowlisted, non-sensitive source.

Provenance: ADAPTED from Playwright MCP accessibility snapshot patterns
(MIT, @playwright/mcp) and Stagehand DOM pruning concepts (MIT, Browserbase).
No code copied; patterns reimplemented in stdlib Python.
"""

from __future__ import annotations

import hashlib
import html
import json
import os
import re
from html.parser import HTMLParser
from typing import Any, Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Feature flag (default OFF — live path must not change during baseline)
# ---------------------------------------------------------------------------
OBSERVATION_ENABLED: bool = os.environ.get(
    "CHROMECONNECT_OBSERVATION_ENABLED", ""
).strip() == "1"

# ---------------------------------------------------------------------------
# Tunables (env-overridable)
# ---------------------------------------------------------------------------
TOKEN_BUDGET: int = int(os.environ.get("CHROMECONNECT_SNAPSHOT_TOKEN_BUDGET", "4000"))
MAX_ELEMENTS: int = int(os.environ.get("CHROMECONNECT_SNAPSHOT_MAX_ELEMENTS", "200"))
REPEAT_COLLAPSE_THRESHOLD: int = int(
    os.environ.get("CHROMECONNECT_REPEAT_COLLAPSE_THRESHOLD", "5")
)
REPEAT_COLLAPSE_SHOW: int = int(
    os.environ.get("CHROMECONNECT_REPEAT_COLLAPSE_SHOW", "3")
)
CHARS_PER_TOKEN: int = 4  # rough heuristic; tune in Phase 2

# Interactive element tags / roles
_INTERACTIVE_TAGS = {
    "a", "button", "input", "select", "textarea", "details", "summary",
}
_INTERACTIVE_ROLES = {
    "button", "link", "textbox", "combobox", "checkbox", "radio",
    "menuitem", "tab", "searchbox", "spinbutton", "slider",
}


def _token_estimate(text: str) -> int:
    """Rough token count (chars / 4). Good enough for budget gating."""
    return max(1, len(text) // CHARS_PER_TOKEN)


class _ElementExtractor(HTMLParser):
    """Extract interactive elements from HTML with stable refs."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.elements: List[Dict[str, Any]] = []
        self._counter = 0
        self._stack: List[str] = []
        self._text_buf: List[str] = []
        self._current: Optional[Dict[str, Any]] = None

    def handle_starttag(self, tag: str, attrs: List[Tuple[str, str]]) -> None:
        tag = tag.lower()
        attr_dict = {k.lower(): (v or "") for k, v in attrs}
        role = attr_dict.get("role", "").lower()
        is_interactive = tag in _INTERACTIVE_TAGS or role in _INTERACTIVE_ROLES

        # Flush text to current element
        if self._current is not None and self._text_buf:
            self._current["text"] = (self._current.get("text", "") + " " + " ".join(self._text_buf)).strip()
            self._text_buf = []

        if is_interactive:
            self._counter += 1
            ref = f"e{self._counter}"
            el = {
                "ref": ref,
                "tag": tag,
                "role": role or tag,
                "text": attr_dict.get("aria-label", "") or attr_dict.get("title", "") or attr_dict.get("placeholder", ""),
                "href": attr_dict.get("href", ""),
                "name": attr_dict.get("name", ""),
                "type": attr_dict.get("type", ""),
                "value": attr_dict.get("value", ""),
                "disabled": "disabled" in attr_dict,
                "depth": len(self._stack),
            }
            # Clean empty fields
            el = {k: v for k, v in el.items() if v not in ("", False, None)}
            self.elements.append(el)
            self._current = el
        self._stack.append(tag)

    def handle_data(self, data: str) -> None:
        text = data.strip()
        if text and self._current is not None:
            self._text_buf.append(text)

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if self._current is not None and self._text_buf:
            self._current["text"] = (self._current.get("text", "") + " " + " ".join(self._text_buf)).strip()
            self._text_buf = []
        # Pop stack
        if self._stack and self._stack[-1] == tag:
            self._stack.pop()
        elif tag in self._stack:
            # Handle mismatched tags gracefully
            while self._stack and self._stack[-1] != tag:
                self._stack.pop()
            if self._stack:
                self._stack.pop()
        self._current = None


def extract_accessibility_tree(html_text: str) -> List[Dict[str, Any]]:
    """Parse HTML and extract interactive elements with stable refs.

    Returns a list of element dicts, each with a 'ref' (e1, e2, ...) and
    metadata (tag, role, text, href, etc.).
    """
    parser = _ElementExtractor()
    try:
        parser.feed(html_text)
    except Exception:
        pass  # Partial parse is acceptable
    # Flush any remaining text
    if parser._current is not None and parser._text_buf:
        parser._current["text"] = (
            parser._current.get("text", "") + " " + " ".join(parser._text_buf)
        ).strip()
    return parser.elements


def _fingerprint(el: Dict[str, Any]) -> str:
    """Compute a fingerprint for repeat-row detection."""
    parts = [el.get("tag", ""), el.get("role", ""), el.get("text", "")[:50]]
    return "|".join(parts)


def prune_snapshot(
    elements: List[Dict[str, Any]],
    token_budget: int = TOKEN_BUDGET,
    max_elements: int = MAX_ELEMENTS,
) -> Tuple[List[Dict[str, Any]], int, bool]:
    """Prune elements to fit within token budget.

    Returns (pruned_elements, estimated_token_count, was_truncated).
    - Drops elements beyond max_elements.
    - Collapses repeated rows (same fingerprint appearing > threshold).
    - Truncates to token budget.
    """
    if not elements:
        return [], 0, False

    # Step 1: Collapse repeated rows
    collapsed: List[Dict[str, Any]] = []
    fingerprint_counts: Dict[str, int] = {}
    fingerprint_first: Dict[str, int] = {}

    for el in elements:
        fp = _fingerprint(el)
        if fp not in fingerprint_counts:
            fingerprint_counts[fp] = 0
            fingerprint_first[fp] = len(collapsed)
        fingerprint_counts[fp] += 1

    # Rebuild with collapse
    seen_fps: Dict[str, int] = {}
    for el in elements:
        fp = _fingerprint(el)
        seen_fps[fp] = seen_fps.get(fp, 0) + 1
        count = fingerprint_counts[fp]
        if count >= REPEAT_COLLAPSE_THRESHOLD:
            # Only keep first REPEAT_COLLAPSE_SHOW
            if seen_fps[fp] <= REPEAT_COLLAPSE_SHOW:
                collapsed.append(el)
            elif seen_fps[fp] == REPEAT_COLLAPSE_SHOW + 1:
                # Add a summary element
                collapsed.append({
                    "ref": f"...",
                    "tag": "repeat",
                    "role": "summary",
                    "text": f"({count - REPEAT_COLLAPSE_SHOW} more similar elements collapsed)",
                    "_collapsed_count": count - REPEAT_COLLAPSE_SHOW,
                    "_fingerprint": fp,
                })
        else:
            collapsed.append(el)

    # Step 2: Cap at max_elements
    truncated = len(collapsed) > max_elements
    if len(collapsed) > max_elements:
        collapsed = collapsed[:max_elements]

    # Step 3: Truncate to token budget
    result: List[Dict[str, Any]] = []
    token_count = 0
    was_truncated = truncated
    for el in collapsed:
        el_text = json.dumps(el, ensure_ascii=False)
        el_tokens = _token_estimate(el_text)
        if token_count + el_tokens > token_budget and result:
            was_truncated = True
            break
        result.append(el)
        token_count += el_tokens

    return result, token_count, was_truncated


def snapshot(
    html_text: str,
    token_budget: int = TOKEN_BUDGET,
    viewport_elements: Optional[int] = None,
) -> Dict[str, Any]:
    """Full observation pipeline: extract + prune + budget.

    Returns a dict with:
        - elements: list of pruned element dicts with refs
        - token_count: estimated tokens used
        - truncated: whether the snapshot was truncated
        - total_elements: total interactive elements found
        - budget: the token budget used
    """
    elements = extract_accessibility_tree(html_text)
    total = len(elements)
    pruned, token_count, truncated = prune_snapshot(elements, token_budget)
    return {
        "elements": pruned,
        "token_count": token_count,
        "truncated": truncated,
        "total_elements": total,
        "budget": token_budget,
        "enabled": OBSERVATION_ENABLED,
    }


def snapshot_hash(html_text: str) -> str:
    """Compute a hash of the HTML for fixture identity."""
    return hashlib.sha256(html_text.encode("utf-8")).hexdigest()[:16]


def viewport_snapshot(
    html_text: str,
    offset: int = 0,
    limit: int = 50,
    token_budget: int = TOKEN_BUDGET,
) -> Dict[str, Any]:
    """Viewport-aware snapshot: return elements[offset:offset+limit] within budget.

    For large pages, call repeatedly with increasing offset.
    """
    elements = extract_accessibility_tree(html_text)
    total = len(elements)
    page_elements = elements[offset:offset + limit]
    pruned, token_count, truncated = prune_snapshot(page_elements, token_budget)
    return {
        "elements": pruned,
        "token_count": token_count,
        "truncated": truncated,
        "total_elements": total,
        "offset": offset,
        "limit": limit,
        "has_more": offset + limit < total,
        "budget": token_budget,
    }


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------

FIXTURE_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "tests", "fixtures", "chromeconnect",
)


def save_fixture(name: str, html_text: str) -> str:
    """Save an HTML snapshot as a fixture. Returns the file path."""
    os.makedirs(FIXTURE_DIR, exist_ok=True)
    safe_name = re.sub(r"[^a-zA-Z0-9_-]", "_", name)
    path = os.path.join(FIXTURE_DIR, f"{safe_name}.html")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(html_text)
    return path


def load_fixture(name: str) -> Optional[str]:
    """Load an HTML fixture by name."""
    safe_name = re.sub(r"[^a-zA-Z0-9_-]", "_", name)
    path = os.path.join(FIXTURE_DIR, f"{safe_name}.html")
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as fh:
        return fh.read()


def list_fixtures() -> List[str]:
    """List available fixture names."""
    if not os.path.exists(FIXTURE_DIR):
        return []
    return sorted(
        f.replace(".html", "")
        for f in os.listdir(FIXTURE_DIR)
        if f.endswith(".html")
    )
