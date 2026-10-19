"""Curated corpus tests (V3 S8): loaders, store, ingest, tool, router.

Offline: in-memory SQLite + temp fixture files, no server, no network.
"""

from __future__ import annotations

import json
import os
import sqlite3
import sys
from unittest import mock

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)
_REPO = os.path.dirname(_HERE)
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)

import chat_tools  # noqa: E402
import corpus_ingest  # noqa: E402
import corpus_router  # noqa: E402
import corpus_schema  # noqa: E402
import data_layer  # noqa: E402


class _FakeDataLayer:
    def __init__(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(corpus_schema.CORPUS_TABLES_SQL)

    def execute(self, sql, params=()):
        return self.conn.execute(sql, params)

    def commit(self):
        self.conn.commit()


class _FakeNorthstarDB:
    def __init__(self):
        self.layer = _FakeDataLayer()
        self.corpus = data_layer.CorpusDB(self.layer)


@pytest.fixture()
def db():
    return _FakeNorthstarDB()


def _ctx(db):
    return {"db": db, "account_id": "acct-1"}


# ── Loaders ─────────────────────────────────────────────────────────────────

def test_load_github_sweep_handles_bom_dict_items_and_bad_lines(tmp_path):
    p = tmp_path / "github_sweep.jsonl"
    lines = [
        json.dumps({"q": "topic:comfyui", "items": [
            {"full_name": "a/b", "stars": 10, "license": "MIT", "lang": "Python",
             "desc": "wow | desc", "topics": ["ai", "comfy"]},
            {"full_name": "c/d", "stars": 5, "license": None, "desc": "x", "topics": []},
        ]}),
        "{ not json",
        json.dumps({"q": "topic:mcp", "items": {
            "k1": {"full_name": "e/f", "stars": 1, "license": "Apache-2.0", "topics": ["mcp"]}}}),
    ]
    p.write_text("\n".join(lines), encoding="utf-8-sig")
    recs = corpus_ingest.load_github_sweep(str(p))
    by_id = {r["source_id"]: r for r in recs}
    assert set(by_id) == {"a/b", "c/d", "e/f"}
    assert by_id["a/b"]["url"] == "https://github.com/a/b"
    assert by_id["a/b"]["license"] == "MIT"
    assert "|" not in by_id["a/b"]["summary"]          # mojibake/pipe stripped
    assert by_id["c/d"]["license"] is None             # null preserved, not invented
    assert by_id["a/b"]["source"] == "github"


def test_load_github_csv(tmp_path):
    p = tmp_path / "SOURCES_GITHUB.csv"
    p.write_text("full_name,url,stars,description,language,pushed_at,topics,query\n"
                 "g/h,https://github.com/g/h,42,hello,Python,2026,t1;t2,q\n",
                 encoding="utf-8")
    recs = corpus_ingest.load_github_csv(str(p))
    assert recs[0]["source_id"] == "g/h" and recs[0]["tags"] == ["t1", "t2"]
    assert recs[0]["provenance"]["stars"] == "42"


def test_load_hf_datasets(tmp_path):
    p = tmp_path / "hf_datasets.json"
    p.write_text(json.dumps([{"term": "amazon", "items": [
        {"id": "x/y", "downloads": 5, "likes": 1, "tags": ["a", "b"]}]}]), encoding="utf-8")
    recs = corpus_ingest.load_hf_datasets(str(p))
    assert recs[0]["source"] == "hf" and recs[0]["kind"] == "dataset"
    assert recs[0]["url"] == "https://huggingface.co/datasets/x/y"


def test_load_sources_csv(tmp_path):
    p = tmp_path / "SOURCES.csv"
    p.write_text("source_id,publisher,url,label,notes\n"
                 "P1,Acme,http://x,Label text,some note\n", encoding="utf-8")
    recs = corpus_ingest.load_sources_csv(str(p))
    assert recs[0]["source"] == "registry" and recs[0]["source_id"] == "P1"
    assert recs[0]["title"] == "Label text"


def test_load_docs_titles_from_heading(tmp_path):
    d = tmp_path / "research"
    d.mkdir()
    (d / "note.md").write_text("# My Heading\nthe body text", encoding="utf-8")
    (d / "skip.csv").write_text("a,b\n1,2\n", encoding="utf-8")
    recs = corpus_ingest.load_docs(str(d))
    assert len(recs) == 1 and recs[0]["title"] == "My Heading"
    assert recs[0]["kind"] == "doc" and "the body text" in recs[0]["content"]


# ── Store ───────────────────────────────────────────────────────────────────

def test_upsert_is_idempotent_by_content(db):
    rec = {"source": "github", "source_id": "a/b", "title": "a/b", "summary": "hi"}
    assert db.corpus.upsert(rec) == "inserted"
    assert db.corpus.upsert(dict(rec)) == "skipped"          # unchanged
    assert db.corpus.upsert({**rec, "summary": "changed"}) == "updated"


def test_upsert_requires_source_and_source_id(db):
    with pytest.raises(ValueError):
        db.corpus.upsert({"source": "github"})


def test_search_ranks_title_matches_first(db):
    db.corpus.upsert({"source": "github", "source_id": "a/b", "title": "ssg bomber",
                      "summary": "nothing"})
    db.corpus.upsert({"source": "doc", "source_id": "d1", "title": "notes",
                      "content": "a note about ssg"})
    hits = db.corpus.search("ssg")
    assert [h["source_id"] for h in hits][0] == "a/b"       # title match ranks first


def test_search_filters_by_source_and_empty_query(db):
    db.corpus.upsert({"source": "github", "source_id": "a/b", "title": "ssg"})
    db.corpus.upsert({"source": "doc", "source_id": "d1", "title": "ssg doc"})
    assert [h["source_id"] for h in db.corpus.search("ssg", source="doc")] == ["d1"]
    assert db.corpus.search("   ") == []


def test_stats_counts_by_source(db):
    db.corpus.upsert({"source": "github", "source_id": "a", "title": "x", "kind": "repo"})
    db.corpus.upsert({"source": "github", "source_id": "b", "title": "y", "kind": "repo"})
    db.corpus.upsert({"source": "doc", "source_id": "c", "title": "z", "kind": "doc"})
    s = db.corpus.stats()
    assert s["total"] == 3 and s["by_source"] == {"github": 2, "doc": 1}


def test_ingest_run_lifecycle(db):
    rid = db.corpus.start_run("github_sweep", "path/x")
    db.corpus.finish_run(rid, "done", counts={"inserted": 3}, errors=[])
    runs = db.corpus.list_runs()
    assert runs[0]["status"] == "done" and runs[0]["counts_json"] == {"inserted": 3}


# ── Ingest driver ───────────────────────────────────────────────────────────

def test_ingest_records_counts_and_errors(db):
    recs = [{"source": "github", "source_id": "a/b", "title": "t"},
            {"source": "", "source_id": "bad", "title": "t"}]   # 2nd raises ValueError
    out = corpus_ingest.ingest_records(db, "github", recs, "p")
    assert out["status"] == "done"
    assert out["counts"]["records"] == 2 and out["counts"]["inserted"] == 1
    assert out["counts"]["errors"] == 1 and out["errors"]


def test_ingest_source_unknown_raises(db):
    with pytest.raises(ValueError):
        corpus_ingest.ingest_source(db, "nope")


def test_ingest_source_missing_path_is_an_honest_error(db, tmp_path):
    out = corpus_ingest.ingest_source(db, "github_sweep", repo_root=str(tmp_path))
    assert out["status"] == "error" and "missing path" in out["errors"][0]


def test_ingest_source_real_hf_file_end_to_end(db):
    path = os.path.join(corpus_ingest._REPO_ROOT,
                        corpus_ingest.SOURCES["hf_datasets"]["path"])
    if not os.path.exists(path):
        pytest.skip("hf_datasets fixture not present")
    out = corpus_ingest.ingest_source(db, "hf_datasets")
    assert out["status"] == "done" and out["counts"]["inserted"] > 0
    assert db.corpus.stats()["by_source"].get("hf", 0) == out["counts"]["inserted"]


# ── Tool ────────────────────────────────────────────────────────────────────

def test_corpus_tool_registered_and_in_focus():
    import shell_focus
    assert "corpus_search" in chat_tools.TOOLS
    assert "corpus_search" in shell_focus.tools_for_focus("research")
    assert "corpus_search" in shell_focus.tools_for_focus("grow")


def test_corpus_tool_returns_matches(db):
    db.corpus.upsert({"source": "github", "source_id": "Comfy-Org/ComfyUI",
                      "title": "Comfy-Org/ComfyUI", "license": "GPL-3.0", "summary": "diffusion GUI"})
    out = chat_tools.run_tool("corpus_search", {"query": "ComfyUI"}, _ctx(db))
    assert out["ok"] is True and out["data"]["card"]["title"] == "Corpus search"
    assert out["data"]["matches"][0]["source_id"] == "Comfy-Org/ComfyUI"


def test_corpus_tool_is_honest_when_empty(db):
    out = chat_tools.run_tool("corpus_search", {"query": "zzzznope"}, _ctx(db))
    assert out["ok"] is True and out["data"]["matches"] == []
    assert "No corpus matches" in out["summary"]


def test_corpus_tool_needs_a_query(db):
    out = chat_tools.run_tool("corpus_search", {"query": "  "}, _ctx(db))
    assert out["ok"] is False


# ── Router ──────────────────────────────────────────────────────────────────

def test_router_search_and_stats(db):
    db.corpus.upsert({"source": "doc", "source_id": "d1", "title": "intel notes"})
    with mock.patch.object(corpus_router, "get_northstar_db", return_value=db):
        found = corpus_router.search("intel", acct="acct-1")
        empty = corpus_router.search("", acct="acct-1")
        st = corpus_router.stats(acct="acct-1")
    assert found["count"] == 1 and empty["count"] == 0
    assert st["total"] == 1 and "github_sweep" in st["sources"]


def test_router_ingest_unknown_source_is_400(db):
    with mock.patch.object(corpus_router, "get_northstar_db", return_value=db):
        with pytest.raises(Exception) as ei:
            corpus_router.ingest(corpus_router.IngestIn(source="nope"), acct="acct-1")
    assert "400" in str(getattr(ei.value, "status_code", "")) + str(ei.value)

# -- Research Wave 2 loaders (2026-10-19) --------------------------------------

def test_load_hf_csv_models_and_spaces(tmp_path):
    p = tmp_path / "hf_models.csv"
    p.write_text("id,kind,downloads,likes,pipeline_tag,license,last_modified,tags,query\n"
                 "Qwen/Qwen-Image-Edit-2511,models,1000,50,image-to-image,apache-2.0,"
                 "2026-10-01T00:00:00,\"image-to-image,license:apache-2.0\",qwen image edit\n",
                 encoding="utf-8")
    recs = corpus_ingest.load_hf_csv(str(p))
    assert len(recs) == 1
    r = recs[0]
    assert r["source"] == "hf" and r["kind"] == "models"
    assert r["url"] == "https://huggingface.co/Qwen/Qwen-Image-Edit-2511"
    assert r["license"] == "apache-2.0"
    assert r["provenance"]["downloads"] == "1000"
    assert r["provenance"]["origin"] == "hf_models.csv"

    q = tmp_path / "hf_spaces.csv"
    q.write_text("id,kind,downloads,likes,pipeline_tag,license,last_modified,tags,query\n"
                 "org/demo-space,spaces,,,,,,demo\n", encoding="utf-8")
    s = corpus_ingest.load_hf_csv(str(q))
    assert s[0]["url"] == "https://huggingface.co/spaces/org/demo-space"


def test_load_youtube_csv_uses_unknown_license(tmp_path):
    p = tmp_path / "videos_index.csv"
    p.write_text("id,title,channel,duration,view_count,upload_date,query,url\n"
                 "abc123,How to design a dieline,Some Channel,600,12345,20260101,"
                 "dieline design,https://www.youtube.com/watch?v=abc123\n", encoding="utf-8")
    recs = corpus_ingest.load_youtube_csv(str(p))
    assert len(recs) == 1 and recs[0]["kind"] == "video"
    assert recs[0]["license"] is None, "a video licence must stay UNKNOWN"
    assert recs[0]["provenance"]["views"] == "12345"


def test_load_transcripts_reads_whisper_sidecars(tmp_path):
    (tmp_path / "vid1.whisper.json").write_text(json.dumps({
        "id": "vid1", "title": "Packaging 101", "channel": "Ch", "url": "https://y/vid1",
        "model": "small", "device": "cuda", "detected_language": "en",
        "segments": [{"start": 0, "end": 2, "text": "Dielines are the cut lines."},
                     {"start": 2, "end": 4, "text": "Creases are the fold lines."}],
        "transcribed_at": "2026-10-19T00:00:00Z",
    }), encoding="utf-8")
    (tmp_path / "ignore.txt").write_text("not a transcript", encoding="utf-8")
    recs = corpus_ingest.load_transcripts(str(tmp_path))
    assert len(recs) == 1
    r = recs[0]
    assert r["source_id"] == "vid1#transcript" and r["kind"] == "transcript"
    assert "cut lines" in r["content"] and "fold lines" in r["content"]
    assert r["provenance"]["model"] == "small"


def test_load_transcripts_missing_dir_is_empty_not_an_error(tmp_path):
    assert corpus_ingest.load_transcripts(str(tmp_path / "nope")) == []


def test_wave2_sources_are_registered():
    for name in ("wave2_repos", "wave2_hf_models", "wave2_hf_datasets",
                 "wave2_hf_spaces", "wave2_videos", "wave2_transcripts"):
        assert name in corpus_ingest.SOURCES, name
        assert corpus_ingest.SOURCES[name]["loader"] in corpus_ingest.LOADERS
