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


def test_migration_is_idempotent_per_asin_not_only_per_legacy_key(tmp_path, monkeypatch):
    """Measured 2026-11-14: the browser migration cloned rows created elsewhere.

    The store deduped only on `legacy_key`, so a row without one (a contract probe, the
    editor) was re-created as a listingforge-local copy: ds_listing_records went 4 -> 7.
    """
    import data_layer
    from fastapi.testclient import TestClient
    from main import app

    monkeypatch.setattr(data_layer, "_SQLITE_PATH", tmp_path / "northstar.db")
    db = data_layer.NorthstarDB()
    monkeypatch.setattr(dsa, "get_northstar_db", lambda: db)
    app.dependency_overrides[dsa.studio_account] = lambda: "org-migrate"
    try:
        client = TestClient(app)
        first = client.post("/api/design-studio/listing-records",
                            json={"asin": "B0DUP00001", "title": "created elsewhere"})
        assert first.status_code == 200
        out = client.post("/api/design-studio/listing-records/migrate", json={"records": [
            {"asin": "B0DUP00001", "title": "browser copy", "legacy_key": "lf:B0DUP00001"},
            {"asin": "B0NEW00002", "title": "new one", "legacy_key": "lf:B0NEW00002"},
        ]}).json()
        rows = db.design_studio.listing_records.list_for_account("org-migrate")
    finally:
        app.dependency_overrides = {}

    assert out["created"] == 1
    assert out["skipped"] == 1
    assert sorted(row["asin"] for row in rows) == ["B0DUP00001", "B0NEW00002"]
