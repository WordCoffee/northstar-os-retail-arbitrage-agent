"""Reference coverage: the arithmetic that keeps a coverage claim honest.

Two failure modes are pinned here, because both have already happened on this project:

* a category counted as covered because *some* image is in it, when the image shows no product —
  the D-003 lesson (a folder of "product pictures" held quote cards);
* a synthetic image counted in a pass rate, which is the pipeline grading its own output.

No network: `fetch` is exercised with injected responses, and the report path is pure arithmetic.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "tools") not in sys.path:
    sys.path.insert(0, str(ROOT / "tools"))

from reference_coverage import _brief_split, _image_split, assign, fetch  # noqa: E402


def _image(sha: str, category: str, source_type: str = "public_licensed") -> dict:
    return {"sha256": sha, "category": category, "source_type": source_type,
            "file": f"renders/x/{sha}.jpg", "licence": "cc0"}


def test_the_split_is_deterministic_and_disjoint_in_practice():
    ids = [f"ST-{n:03d}" for n in range(1, 57)]
    splits = {_brief_split(i) for i in ids}
    assert splits == {"held_out", "tuning"}
    assert _brief_split("ST-001") == _brief_split("ST-001")
    held = sum(1 for i in ids if _brief_split(i) == "held_out")
    assert 8 <= held <= 28, held  # 30 % of 56 is ~17; allow sampling noise
    assert {_image_split(s) for s in ("a" * 16, "b" * 16)} <= {"held_out", "tuning"}


def test_synthetic_images_never_cover_a_brief():
    briefs = [{"id": "ST-001", "category": "ceramic_mug"}]
    rows = [_image("s1", "ceramic_mug", "synthetic")]
    result = assign(briefs, rows)
    assert result["assigned"] == []
    assert result["uncovered"] == ["ST-001"]


def test_a_category_without_an_image_is_uncovered_not_guessed():
    briefs = [{"id": "ST-001", "category": "pet_product"}]
    rows = [_image("m1", "ceramic_mug")]
    result = assign(briefs, rows)
    assert result["uncovered"] == ["ST-001"]


def test_coverage_counts_briefs_not_images():
    briefs = [{"id": f"ST-{n:03d}", "category": "ceramic_mug"} for n in range(1, 7)]
    rows = [_image("m1", "ceramic_mug"), _image("m2", "ceramic_mug")]
    result = assign(briefs, rows)
    assert len(result["assigned"]) == 6
    assert result["depth"]["ceramic_mug"] == 2


def _payload():
    return {"results": [
        {"id": "ok-1", "license": "cc0", "width": 1200, "height": 1200,
         "url": "https://example.test/ok.jpg",
         "foreign_landing_url": "https://example.test/page",
         "title": "ceramic mug on a table", "tags": [{"name": "mug"}]},
        {"id": "nc-1", "license": "by-nc", "width": 1200, "height": 1200,
         "url": "https://example.test/nc.jpg",
         "foreign_landing_url": "https://example.test/nc",
         "title": "ceramic mug", "tags": [{"name": "mug"}]},
        {"id": "small-1", "license": "cc0", "width": 300, "height": 300,
         "url": "https://example.test/small.jpg",
         "foreign_landing_url": "https://example.test/small",
         "title": "ceramic mug", "tags": [{"name": "mug"}]},
    ]}


def test_fetch_refuses_nc_licences_and_tiny_images():
    from io import BytesIO

    import numpy as np
    from PIL import Image

    buffer = BytesIO()
    rng = np.random.default_rng(0)
    noise = rng.integers(0, 255, (1200, 1200, 3), dtype=np.uint8)
    Image.fromarray(noise, "RGB").save(buffer, format="PNG")
    blob = buffer.getvalue()
    assert len(blob) > 8_000
    result = fetch("ceramic_mug", per_query=5, min_side=600,
                   get_json=lambda url: _payload(),
                   get_bytes=lambda url: blob)
    kept_ids = [row["id"] for row in result["rows"]]
    assert kept_ids == ["ok-1"]
    reasons = " ".join(r.get("reason", "") for r in result["refused"])
    assert "licence by-nc" in reasons
    assert "small 300x300" in reasons
