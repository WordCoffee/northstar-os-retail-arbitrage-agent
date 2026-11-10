"""Product identity resolution tests (owner decision 2)."""
from __future__ import annotations

from Northstar_backend.foundation.identity import (
    IdentityResolver, IdentitySubmission, normalize_asin, valid_asin,
    normalize_digit_identifier,
)
from Northstar_backend.foundation.enums import IdentityResolution, IdentifierKind


def _mp(repo_state):
    mp = repo_state.repos.marketplaces.by_code("amazon.com")
    return mp["id"]


def test_normalize_asin_uppercases_and_trims():
    assert normalize_asin("  b0abcd1234 ") == "B0ABCD1234"


def test_valid_asin_requires_ten_chars():
    assert valid_asin("B0ABCD1234")
    assert not valid_asin("B0ABCD123")
    assert not valid_asin("B0ABCD123!")


def test_digit_identifier_normalization():
    assert normalize_digit_identifier("012-345-678-901") == "012345678901"


def test_new_product_created_for_valid_asin(seeded_state):
    res = IdentityResolver(seeded_state.repos).submit(IdentitySubmission(
        marketplace_id=_mp(seeded_state), asin="B0ABCD1234", title="Sample"))
    assert res.resolution == IdentityResolution.NEW_PRODUCT.value
    assert res.product_id


def test_existing_product_matched(seeded_state):
    resolver = IdentityResolver(seeded_state.repos)
    r1 = resolver.submit(IdentitySubmission(marketplace_id=_mp(seeded_state),
                                            asin="B0ABCD1234", title="X"))
    r2 = resolver.submit(IdentitySubmission(marketplace_id=_mp(seeded_state),
                                            asin="b0abcd1234", title="X"))
    assert r2.resolution == IdentityResolution.EXISTING_PRODUCT.value
    assert r2.product_id == r1.product_id


def test_invalid_asin_becomes_unresolved_candidate(seeded_state):
    res = IdentityResolver(seeded_state.repos).submit(IdentitySubmission(
        marketplace_id=_mp(seeded_state), asin="NOTANASIN", title="Bad"))
    assert res.resolution == IdentityResolution.UNRESOLVED_CANDIDATE.value
    assert res.candidate_id


def test_ambiguous_pack_requires_review_not_merge(seeded_state):
    res = IdentityResolver(seeded_state.repos).submit(IdentitySubmission(
        marketplace_id=_mp(seeded_state), asin="B0PACK0001", pack_ambiguous=True))
    assert res.resolution == IdentityResolution.PACK_REVIEW_REQUIRED.value
    # no canonical product created
    assert seeded_state.repos.products.count() == 0


def test_cross_identifier_duplicate_is_possible_duplicate_not_merge(seeded_state):
    resolver = IdentityResolver(seeded_state.repos)
    resolver.submit(IdentitySubmission(
        marketplace_id=_mp(seeded_state), asin="B0FIRST001",
        identifiers=[(IdentifierKind.UPC.value, "012345678905")]))
    # second product shares the UPC but has a different ASIN
    res = resolver.submit(IdentitySubmission(
        marketplace_id=_mp(seeded_state), asin="B0SECOND02",
        identifiers=[(IdentifierKind.UPC.value, "012345678905")]))
    assert res.resolution == IdentityResolution.POSSIBLE_DUPLICATE.value
    assert res.conflict_id
    # still only one canonical product (no silent merge, no second create)
    assert seeded_state.repos.products.count() == 1


def test_no_asin_becomes_unresolved(seeded_state):
    res = IdentityResolver(seeded_state.repos).submit(IdentitySubmission(
        marketplace_id=_mp(seeded_state), title="No ASIN here"))
    assert res.resolution == IdentityResolution.UNRESOLVED_CANDIDATE.value


def test_duplicate_amazon_identity_detected_as_conflict(seeded_state):
    # Simulate a pre-existing duplicate by inserting two rows with same identity.
    from Northstar_backend.foundation.models import CatalogProduct
    mp = _mp(seeded_state)
    seeded_state.repos.products.add(CatalogProduct(marketplace_id=mp, asin="B0DUPE0001"))
    seeded_state.repos.products.add(CatalogProduct(marketplace_id=mp, asin="B0DUPE0001"))
    res = IdentityResolver(seeded_state.repos).submit(IdentitySubmission(
        marketplace_id=mp, asin="B0DUPE0001"))
    assert res.resolution == IdentityResolution.IDENTITY_CONFLICT.value
    assert res.conflict_id