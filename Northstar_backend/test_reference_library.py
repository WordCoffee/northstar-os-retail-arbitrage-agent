"""The stored-reference library: bytes on a shelf, with honest retrieval.

No test calls Ollama. The embedder is injected, which is also how the lane
behaves in production when the embedding model is not resident (it reports
`keyword_fallback` instead of pretending to be semantic).
"""
from __future__ import annotations

import sys
from io import BytesIO
from pathlib import Path

import pytest
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))

import reference_library as rl  # noqa: E402


def _png(colour=(190, 160, 120), size=(64, 64), stripe: int = 0) -> bytes:
    im = Image.new("RGB", size, colour)
    if stripe:
        px = im.load()
        for x in range(size[0]):
            for y in range(stripe):
                px[x, y] = (10, 10, 10)
    buf = BytesIO()
    im.save(buf, format="PNG")
    return buf.getvalue()


@pytest.fixture()
def store(tmp_path):
    def _save(data, **kw):
        return rl.save(data, db_path=tmp_path / "refs.db",
                       store_root=tmp_path / "refs",
                       embedder=lambda _t: [1.0, 0.0], **kw)
    return _save, tmp_path


def test_save_stores_bytes_and_a_row(store):
    save, tmp = store
    row = save(_png(), brand="mogra", product="lions mane", kind="product_photo",
               prompt="a kraft pouch, front")
    assert row["ok"] and not row["deduplicated"]
    path = tmp / row["path"].replace("renders/references/", "refs/")
    assert path.is_file()
    assert row["width"] == 64 and row["height"] == 64
    assert row["phash"]


def test_identical_bytes_are_stored_once(store):
    save, tmp = store
    data = _png()
    first = save(data, brand="mogra", product="p", kind="generated")
    second = save(data, brand="mogra", product="p", kind="generated")
    assert second["deduplicated"] is True
    assert first["id"] == second["id"]
    assert len(rl.find(brand="mogra", product="p", db_path=tmp / "refs.db")) == 1


def test_find_filters_by_brand_product_and_kind(store):
    save, tmp = store
    save(_png((10, 20, 30)), brand="mogra", product="p", kind="product_photo")
    save(_png((30, 40, 50)), brand="mogra", product="p", kind="generated")
    save(_png((60, 70, 80)), brand="other", product="q", kind="generated")
    db = tmp / "refs.db"
    assert len(rl.find(brand="mogra", product="p", db_path=db)) == 2
    assert len(rl.find(brand="mogra", product="p", kind="generated", db_path=db)) == 1


def test_resolve_returns_bytes_and_reports_a_deleted_file(store):
    save, tmp = store
    row = save(_png(), brand="mogra", product="p", kind="generated")
    db = tmp / "refs.db"
    assert rl.resolve(row["id"], db_path=db) is not None
    (tmp / row["path"].replace("renders/references/", "refs/")).unlink()
    assert rl.resolve(row["id"], db_path=db) is None


def test_unknown_kind_is_refused(store):
    save, _tmp = store
    with pytest.raises(ValueError):
        save(_png(), kind="not-a-kind")


def test_perceptual_nearest_prefers_the_similar_image(store):
    save, tmp = store
    near = save(_png((200, 200, 200)), brand="b", product="p", kind="generated")
    save(_png((200, 200, 200), stripe=40), brand="b", product="p", kind="generated")
    db = tmp / "refs.db"
    hits = rl.nearest(_png((200, 200, 200)), brand="b", product="p", db_path=db)
    assert hits and hits[0]["id"] == near["id"]


def test_semantic_search_ranks_by_the_injected_embedding(store):
    save, tmp = store
    save(_png((1, 2, 3)), brand="b", product="p", kind="generated", prompt="front",
         embedder=None) if False else None
    db = tmp / "refs.db"
    # Two rows with deliberately different vectors.
    a = rl.save(_png((5, 5, 5)), brand="b", product="p", kind="generated",
                prompt="blue bottle", db_path=db, store_root=tmp / "refs",
                embedder=lambda _t: [1.0, 0.0])
    rl.save(_png((9, 9, 9), stripe=20), brand="b", product="p", kind="generated",
            prompt="red pouch", db_path=db, store_root=tmp / "refs",
            embedder=lambda _t: [0.0, 1.0])
    out = rl.search("blue bottle", db_path=db, embedder=lambda _t: [0.99, 0.01])
    assert out["mode"] == "embedding"
    assert out["matches"][0]["id"] == a["id"]


def test_search_falls_back_to_keywords_and_says_so(store):
    save, tmp = store
    save(_png((5, 5, 5)), brand="mogra", product="p", kind="generated",
         prompt="kraft pouch front")
    out = rl.search("kraft", db_path=tmp / "refs.db", embedder=lambda _t: None)
    assert out["mode"] == "keyword_fallback"
    assert out["matches"]
    assert "keyword" in out["note"]


def test_brand_and_product_cannot_escape_the_store(store):
    save, tmp = store
    row = save(_png(), brand="../../etc", product="..\\..\\windows", kind="generated")
    assert ".." not in row["path"]
    stored = Path(row["path"])
    assert stored.parent.parent.parent == (tmp / "refs").resolve() or \
        (tmp / "refs") in stored.parents


def test_stats_counts_rows_and_vectors(store):
    save, tmp = store
    save(_png(), brand="mogra", product="p", kind="generated")
    s = rl.stats(db_path=tmp / "refs.db")
    assert s["total"] == 1 and s["with_embedding"] == 1
