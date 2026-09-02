"""Shared Kirkland relevance filter for the Kirkland Product Scout.

Single source of truth for "is this a genuine Kirkland Signature listing?"
used by every Amazon data provider (Bright Data Web Unlocker, ChocoData,
Scavio) so no source can reintroduce non-Kirkland noise (unrelated apparel,
generic supplements, used/recycled goods).

Structured `brand` field match is preferred over title keyword match, and
used/recycled/refurbished items are always dropped.
"""

import re
from typing import Dict, Optional

USED_TOKENS = re.compile(
    r"\b(used|recycled|refurbished|remanufactured|pre-?owned|open\s*box|refurb|renewed)\b",
    re.IGNORECASE,
)


def is_genuine_kirkland_candidate(product: Optional[Dict]) -> bool:
    """True if the product dict is a genuine Kirkland Signature listing.

    Matches the structured `brand` field first (preferred), falls back to
    the title, and drops used/recycled/refurbished items. Missing or empty
    dicts are never Kirkland.
    """
    if not product or not isinstance(product, dict):
        return False
    brand = product.get("brand")
    name = product.get("name") or product.get("title")
    text = " ".join(x for x in (name, brand) if x and str(x).strip())
    if not text.strip():
        return False
    if "kirkland" not in text.lower():
        return False
    if USED_TOKENS.search(text):
        return False
    return True