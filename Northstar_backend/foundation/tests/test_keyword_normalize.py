"""Normalization tests (1C-05 / C02)."""
from __future__ import annotations

import pytest

from Northstar_backend.foundation.keywords.normalize import (
    normalize_phrase, normalize_match_type, normalize_marketplace,
    normalize_language, is_asin_like, normalize_asin, extract_brand_terms,
    normalize_idempotent,
)


def test_unicode_nfkc_and_whitespace():
    n = normalize_phrase("  Dog   Leash\u2003with\u00a0Handle  ")
    assert n.value == "dog leash with handle"
    assert n.original == "  Dog   Leash\u2003with\u00a0Handle  "
    assert n.was_modified


def test_case_collapse():
    assert normalize_phrase("DOG LEASH").value == "dog leash"


def test_punctuation_removed_keeping_hyphen_apostrophe():
    assert normalize_phrase("dog-leash!").value == "dog-leash"
    assert normalize_phrase("women's shoes").value == "women's shoes"
    assert normalize_phrase("dog\u2019s bed").value == "dog's bed"


def test_hyphen_handling():
    assert normalize_phrase("dog  -  leash").value == "dog-leash"


def test_alias_mapping():
    assert normalize_phrase("u.s.").value == "us"


def test_stop_words_only_for_long_phrases():
    n = normalize_phrase("the best dog leash for large dogs", stop_words=True)
    assert "the" not in n.value and "for" not in n.value
    # short commercial terms keep their intent
    assert normalize_phrase("a dog", stop_words=True).value == "a dog"


def test_idempotent():
    for phrase in ("  DOG   Leash  ", "women's shoes", "u.s. patent",
                   "dog\u2019s bed 2024"):
        assert normalize_idempotent(phrase) is True


def test_distinct_commercial_intent_preserved():
    a = normalize_phrase("dog leash")
    b = normalize_phrase("leash for dogs")
    assert a.value != b.value  # not over-normalized


def test_empty_phrase_returns_empty():
    n = normalize_phrase(None)
    assert n.value == "" and n.original == ""


@pytest.mark.parametrize("raw,expected", [
    ("Exact", "exact"), ("EXACT MATCH", "exact"), ("exact-match", "exact"),
    ("Phrase", "phrase"), ("phrase match", "phrase"),
    ("Broad", "broad"), ("broad-match", "broad"),
    ("Negative Exact", "negative"), ("negative phrase", "negative"),
    (None, "broad"), ("", "broad"),
])
def test_match_type_canonicalization(raw, expected):
    assert normalize_match_type(raw) == expected


@pytest.mark.parametrize("raw,expected", [
    ("amazon.com", "amazon.com"), ("www.amazon.com", "amazon.com"),
    ("https://www.amazon.com", "amazon.com"), ("US", "amazon.com"),
    ("amazon.co.uk", "amazon.co.uk"), (None, None), ("", None),
])
def test_marketplace_normalization(raw, expected):
    assert normalize_marketplace(raw) == expected


@pytest.mark.parametrize("raw,expected", [
    ("english", "en"), ("en-US", "en"), ("de-de", "de"), (None, "en"),
])
def test_language_normalization(raw, expected):
    assert normalize_language(raw) == expected


def test_asin_detection_and_normalization():
    assert is_asin_like("B0EXAMPLE1") is True
    assert is_asin_like("b0example1") is True
    assert normalize_asin("b0example1") == "B0EXAMPLE1"
    assert is_asin_like("not-an-asin") is False
    assert normalize_asin("123") is None


def test_brand_terms_extraction():
    found = extract_brand_terms("Acme dog leash pro", ["Acme", "ProPet"])
    assert found == ["Acme"]


def test_normalized_metadata():
    n = normalize_phrase("Women's SHOES")
    assert n.original == "Women's SHOES"
    assert n.value == "women's shoes"
    assert "unicode_nfkc" in n.rules_applied