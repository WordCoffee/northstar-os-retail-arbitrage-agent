"""Listing-record schema: one model for both write paths.

`design_studio_api.py` defined `ListingRecordIn` twice. The bulk migration model
captured the first class (no `source` field), the single-record endpoint used the
second (with `source`). The module-level name was the second, so a bulk import
silently dropped `source` while a single create kept it - the same resource
accepting different fields depending on the route.
"""
from __future__ import annotations

import typing

import design_studio_api as dsa


def test_the_bulk_model_accepts_source():
    body = dsa.ListingMigrateIn(records=[{"asin": "B0TEST", "source": "listingforge"}])
    assert body.records[0].source == "listingforge"


def test_the_bulk_and_single_endpoints_share_one_record_model():
    nested = typing.get_args(dsa.ListingMigrateIn.model_fields["records"].annotation)[0]
    assert nested is dsa.ListingRecordIn
    # the single-create handler annotates its body with the same class
    handler = dsa.create_listing_record
    assert handler.__annotations__["body"] is dsa.ListingRecordIn


def test_source_survives_a_dump_for_both_paths():
    single = dsa.ListingRecordIn(asin="B0TEST", source="editor")
    bulk = dsa.ListingMigrateIn(records=[{"asin": "B0TEST", "source": "editor"}])
    assert single.model_dump()["source"] == "editor"
    assert bulk.records[0].model_dump()["source"] == "editor"
