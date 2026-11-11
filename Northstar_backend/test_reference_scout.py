"""The reference-library scout: licence discipline, not a download loop.

PATCH 2 of the work order adds Openverse as a **rubric** source: openly licensed,
no key, and every work's licence verified before use. These tests pin the policy —
which licences are kept, what is refused and counted, and that nothing is recorded
without a source URL a person could check.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import reference_scout  # noqa: E402


def item(**overrides):
    row = {
        "id": "abc123",
        "title": "Kraft coffee bag",
        "creator": "Someone",
        "license": "by",
        "license_version": "4.0",
        "license_url": "https://creativecommons.org/licenses/by/4.0/",
        "foreign_landing_url": "https://example.org/photo/1",
        "url": "https://example.org/photo/1.jpg",
        "width": 1600,
        "height": 1200,
    }
    row.update(overrides)
    return row


def payload(*rows):
    return {"result_count": len(rows), "results": list(rows)}


def test_a_commercially_usable_licence_is_kept():
    assert reference_scout.keep(item()) is None
    for licence in ("cc0", "by-sa"):
        assert reference_scout.keep(item(license=licence)) is None


def test_noncommercial_and_noderivatives_are_refused_by_name():
    assert "licence_refused" in reference_scout.keep(item(license="by-nc"))
    assert "licence_refused" in reference_scout.keep(item(license="by-nd"))
    assert "licence_refused" in reference_scout.keep(item(license=None))


def test_a_row_without_a_source_url_cannot_be_verified():
    assert "landing url" in reference_scout.keep(item(foreign_landing_url=""))
    assert "image url" in reference_scout.keep(item(url=""))


def test_a_tiny_image_is_not_a_reference():
    assert "too small" in reference_scout.keep(item(width=320, height=200))


def test_the_run_records_licence_url_and_usage_for_every_row(tmp_path):
    import io

    from PIL import Image

    buffer = io.BytesIO()
    import random

    pixels = Image.new("RGB", (900, 900))
    random.seed(1)
    pixels.putdata([(random.randint(0, 255), random.randint(0, 255),
                     random.randint(0, 255)) for _ in range(900 * 900)])
    pixels.save(buffer, format="PNG")
    blob = buffer.getvalue()
    assert len(blob) > 8_000

    def fake_json(url):
        assert "license=" in url and "by" in url
        return payload(item(id="a1", title="Kraft coffee bag"),
                       item(id="a2", license="by-nc", title="Coffee bag"),
                       item(id="a3", title="Jar of preserves", license="cc0"))

    def fake_bytes(url):
        return blob

    result = reference_scout.run(queries=("coffee bag packaging",), out_dir=tmp_path,
                                 manifest=tmp_path / "lib.json", per_query=2,
                                 fetch_json=fake_json, fetch_bytes=fake_bytes)
    assert result["counts"]["kept"] == 2          # a1 and a3; a2 is NC
    assert result["counts"]["refused"] == 1
    for row in result["rows"]:
        assert row["source_url"].startswith("https://")
        assert row["licence_url"].startswith("https://creativecommons.org/")
        assert row["usage"].startswith("rubric reference only")
        assert row["sha256"]
        assert Path(row["file"]).is_file()
        assert row["file_size"] == [900, 900]
    written = json.loads((tmp_path / "lib.json").read_text(encoding="utf-8"))
    assert written["policy"]["usage"].startswith("rubric references only")
    assert written["policy"]["amazon"] == "never contacted"


def test_a_network_failure_is_recorded_not_hidden(tmp_path):
    def broken(url):
        raise TimeoutError("no route")

    result = reference_scout.run(queries=("coffee bag packaging",), out_dir=tmp_path,
                                 manifest=tmp_path / "lib.json",
                                 fetch_json=broken, fetch_bytes=lambda url: b"")
    assert result["counts"]["kept"] == 0
    assert result["refused"] and "TimeoutError" in result["refused"][0]["reason"]


def test_a_download_that_is_too_small_is_refused(tmp_path):
    result = reference_scout.run(queries=("coffee bag packaging",), out_dir=tmp_path,
                                 manifest=tmp_path / "lib.json",
                                 fetch_json=lambda url: payload(item(id="a1")),
                                 fetch_bytes=lambda url: b"x" * 10)
    assert result["counts"]["kept"] == 0
    assert "too small" in result["refused"][0]["reason"]


def test_the_query_carries_the_licence_filter():
    url = reference_scout.search_url("gift box packaging", page_size=8)
    assert "license=" in url and "mature=false" in url
    assert "page_size=8" in url
