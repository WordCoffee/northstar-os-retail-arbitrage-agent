"""The research log: what was looked up, what was observed, and nothing computed.

The G1 gate for research is "query → persist → read back". These tests pin the three ways a store
like this goes wrong: it invents a metric, it loses an honest miss, or it keeps page state it was
never meant to own.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "Northstar_backend") not in sys.path:
    sys.path.insert(0, str(ROOT / "Northstar_backend"))

import research_store  # noqa: E402


def test_a_saved_lookup_round_trips(tmp_path):
    path = tmp_path / "research.json"
    record = research_store.save_item(
        {"asin": "b0zz9zz999", "status": "observed", "note": "read from cache",
         "row": {"asin": "B0ZZ9ZZ999", "title": "Lion's Mane pouch", "brand": "Mogra",
                 "price": 24.99}},
        path=path)
    assert record["asin"] == "B0ZZ9ZZ999"  # normalised
    assert record["row"]["title"] == "Lion's Mane pouch"
    assert research_store.get_item("B0ZZ9ZZ999", path=path)["asin"] == "B0ZZ9ZZ999"
    assert [row["asin"] for row in research_store.list_items(path=path)] == ["B0ZZ9ZZ999"]


def test_an_honest_miss_is_stored_as_a_fact_not_dropped(tmp_path):
    path = tmp_path / "research.json"
    record = research_store.save_item(
        {"asin": "B0ZZ9ZZ998", "status": "no_observation",
         "row": {"asin": "B0ZZ9ZZ998", "title": "No cached observation"}}, path=path)
    assert record["status"] == "no_observation"
    assert research_store.list_items(path=path)[0]["status"] == "no_observation"


def test_the_store_copies_fields_and_never_invents_one(tmp_path):
    path = tmp_path / "research.json"
    record = research_store.save_item(
        {"asin": "B0ZZ9ZZ997", "row": {"asin": "B0ZZ9ZZ997", "price": 12.5,
                                       "internal_debug_flag": True, "computed_margin": 99}},
        path=path)
    assert record["row"]["price"] == 12.5
    # fields outside the allowlist are dropped, so page state cannot leak into the record
    assert "internal_debug_flag" not in record["row"]
    assert "computed_margin" not in record["row"]


def test_saving_twice_keeps_one_record_per_asin(tmp_path):
    path = tmp_path / "research.json"
    research_store.save_item({"asin": "B0ZZ9ZZ996", "row": {"asin": "B0ZZ9ZZ996", "price": 1.0}},
                             path=path)
    research_store.save_item({"asin": "B0ZZ9ZZ996", "row": {"asin": "B0ZZ9ZZ996", "price": 2.0}},
                             path=path)
    items = research_store.list_items(path=path)
    assert len(items) == 1
    assert items[0]["row"]["price"] == 2.0


def test_delete_removes_and_reports_whether_it_did(tmp_path):
    path = tmp_path / "research.json"
    research_store.save_item({"asin": "B0ZZ9ZZ995", "row": {"asin": "B0ZZ9ZZ995"}}, path=path)
    assert research_store.delete_item("B0ZZ9ZZ995", path=path) is True
    assert research_store.delete_item("B0ZZ9ZZ995", path=path) is False
    assert research_store.list_items(path=path) == []


def test_an_empty_asin_is_refused(tmp_path):
    path = tmp_path / "research.json"
    try:
        research_store.save_item({"asin": "   "}, path=path)
    except ValueError as exc:
        assert "asin" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("an empty ASIN must be refused")


def test_the_file_is_valid_json_after_a_write(tmp_path):
    path = tmp_path / "research.json"
    research_store.save_item({"asin": "B0ZZ9ZZ994", "row": {"asin": "B0ZZ9ZZ994"}}, path=path)
    json.loads(path.read_text(encoding="utf-8"))  # a half-written file cannot exist
