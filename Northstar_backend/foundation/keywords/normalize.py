"""Canonical keyword/search-term normalization (1C-05 / C02).

Deterministic and idempotent. Preserves the original phrase; never
over-normalizes distinct commercial intent (e.g. "dog leash" vs
"leash for dogs" stay distinct). Unknowns remain null.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Optional

_WHITESPACE = re.compile(r"\s+")
_PUNCTUATION = re.compile(r"[^\w\s'-]")  # keep letters, digits, space, hyphen, apostrophe
_HYPHENS = re.compile(r"\s*-\s*")         # collapse spaced hyphens
_APOSTROPHES = re.compile(r"[\u2018\u2019\u02BC]")  # curly apostrophes -> '
_MULTI_WS = re.compile(r"\s+")
ASIN_RE = re.compile(r"^[0-9A-Z]{10}$")

_ALIASES = {
    "u.s.": "us", "u.s": "us", "uk": "uk", "u.k.": "uk",
    "bluetooth": "bluetooth",
}

# Minimal stop words for phrases of 3+ tokens (kept for short commercial terms
# where removal would change intent).
_STOP_WORDS = frozenset({"the", "a", "an", "for", "and", "of", "to", "in", "on"})


@dataclass(frozen=True)
class Normalized:
    value: str
    original: str
    was_modified: bool
    rules_applied: tuple[str, ...]


def _apply_aliases(tokens: list[str]) -> list[str]:
    return [_ALIASES.get(t, t) for t in tokens]


def normalize_phrase(phrase: Optional[str], *, stop_words: bool = False) -> Normalized:
    """Deterministic phrase normalization. Returns the original when empty."""
    original = phrase or ""
    rules: list[str] = []
    if not original:
        return Normalized("", original, False, tuple(rules))
    # Unicode normalization
    value = unicodedata.normalize("NFKC", original)
    rules.append("unicode_nfkc")
    # curly apostrophes to straight
    value = _APOSTROPHES.sub("'", value)
    # strip punctuation (keep hyphen/apostrophe)
    value = _PUNCTUATION.sub("", value)
    # collapse spaced hyphens, then collapse whitespace, then lowercase
    value = _HYPHENS.sub("-", value)
    value = _MULTI_WS.sub(" ", value).strip()
    value = value.lower()
    # tokenization + alias mapping
    tokens = value.split()
    mapped = _apply_aliases(tokens)
    if mapped != tokens:
        rules.append("alias_map")
    if stop_words and len(mapped) >= 3:
        filtered = [t for t in mapped if t not in _STOP_WORDS]
        if filtered:
            mapped = filtered
            rules.append("stop_words")
    value = " ".join(mapped)
    modified = value != original.lower().strip()
    return Normalized(value, original, modified, tuple(rules))


def normalize_match_type(raw: Optional[str]) -> str:
    """Canonical match type: broad | phrase | exact | negative."""
    if not raw:
        return "broad"
    v = str(raw).strip().lower()
    if v in ("exact", "exact match", "exact-match"):
        return "exact"
    if v in ("phrase", "phrase match", "phrase-match"):
        return "phrase"
    if v in ("negative", "negative exact", "negative phrase", "negative broad"):
        return "negative"
    if v in ("broad", "broad match", "broad-match"):
        return "broad"
    return "broad"


def normalize_marketplace(raw: Optional[str]) -> Optional[str]:
    if not raw:
        return None
    v = str(raw).strip().lower()
    v = v.replace("www.", "").replace("https://", "").replace("http://", "")
    v = v.rstrip("/")
    if v in ("amazon", "amazon.com", "us", "amazon us"):
        return "amazon.com"
    if v in ("amazon.co.uk", "uk", "amazon uk"):
        return "amazon.co.uk"
    if v in ("amazon.de", "de", "amazon de"):
        return "amazon.de"
    if v in ("amazon.ca", "ca", "amazon ca"):
        return "amazon.ca"
    if v in ("amazon.com.mx", "mx"):
        return "amazon.com.mx"
    return v or None


def normalize_language(raw: Optional[str]) -> str:
    if not raw:
        return "en"
    v = str(raw).strip().lower()
    aliases = {"english": "en", "en-us": "en", "en_gb": "en", "en": "en",
               "german": "de", "de-de": "de", "de": "de",
               "french": "fr", "fr-fr": "fr", "fr": "fr",
               "spanish": "es", "es-es": "es", "es-mx": "es", "es": "es",
               "italian": "it", "it-it": "it", "it": "it"}
    return aliases.get(v, v)


def is_asin_like(value: Optional[str]) -> bool:
    """True for values that look like an Amazon ASIN (10 alnum, no leading zero
    digit in position 3 per Amazon's checksum rule — we only check shape here)."""
    if not value:
        return False
    return bool(ASIN_RE.match(str(value).strip().upper()))


def normalize_asin(raw: Optional[str]) -> Optional[str]:
    if not is_asin_like(raw):
        return None
    return str(raw).strip().upper()


def extract_brand_terms(phrase: Optional[str], brands: Optional[list[str]]) -> list[str]:
    """Brand terms present in the phrase (case-insensitive containment)."""
    if not phrase or not brands:
        return []
    low = phrase.lower()
    found = []
    for b in brands:
        if b and b.strip() and b.strip().lower() in low:
            found.append(b.strip())
    return found


def normalize_idempotent(phrase: Optional[str]) -> bool:
    """Normalization must be idempotent: normalize(normalize(x)) == normalize(x)."""
    once = normalize_phrase(phrase)
    twice = normalize_phrase(once.value)
    return once.value == twice.value