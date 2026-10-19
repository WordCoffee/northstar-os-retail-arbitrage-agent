"""Corpus Learner tests — static-fetch lane, fully offline.

The HTTP layer is injected: no test touches the network. Every assertion maps
to one compliance or behaviour guarantee:
  URL canonicalisation · robots honouring · fail-open on missing robots ·
  host throttling · extraction + content hash · non-HTML rejection ·
  provenance-complete records · ingest counts + idempotency · same-host crawl ·
  sitemap parsing.
"""

from __future__ import annotations

import json
import os
import sqlite3
import sys
from pathlib import Path

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import corpus_learner as cl  # noqa: E402
import corpus_schema  # noqa: E402
import data_layer  # noqa: E402


# ── fakes ───────────────────────────────────────────────────────────────────

class _FakeDataLayer:
    def __init__(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(corpus_schema.CORPUS_TABLES_SQL)

    def execute(self, sql, params=()):
        return self.conn.execute(sql, params)

    def commit(self):
        self.conn.commit()


class _FakeDB:
    def __init__(self):
        self.layer = _FakeDataLayer()
        self.corpus = data_layer.CorpusDB(self.layer)


PAGE_TMPL = """<!doctype html><html><head><title>{title}</title></head>
<body><article><h1>{title}</h1><p>{body}</p>
<a href="{link}">next</a><a href="https://other.example/x">offsite</a>
<a href="/abs/path">abs</a><a href="mailto:x@y.z">mail</a>
</article></body></html>"""

BODY = ("Packaging dielines and mockups are a typesetting problem first; "
        "diffusion models should never draw the label copy. " * 6)


def _site(pages: dict) -> callable:
    """A fake _http_get serving a dict {url: (status, ctype, body)}."""
    def fake(url, *, timeout=25.0, max_bytes=4_000_000, client=None):
        rec = pages.get(url)
        if rec is None:
            return {"ok": False, "status": 404, "final_url": url,
                    "content_type": "text/html", "text": "", "bytes": 0}
        status, ctype, body = rec
        return {"ok": 200 <= status < 300, "status": status, "final_url": url,
                "content_type": ctype, "text": body, "bytes": len(body)}
    return fake


def _make_pages() -> dict:
    pages = {}
    for i in range(1, 8):
        url = f"https://site.example/page{i}"
        link = f"/page{i + 1}" if i < 7 else "/page1"
        pages[url] = (200, "text/html",
                      PAGE_TMPL.format(title=f"Page {i}", body=BODY, link=link))
    pages["https://site.example/robots.txt"] = (
        200, "text/plain", "User-agent: *\nDisallow: /private\n")
    pages["https://site.example/private"] = (200, "text/html",
                                             PAGE_TMPL.format(title="Secret", body=BODY,
                                                              link="/page1"))
    pages["https://site.example/img.png"] = (200, "image/png", "not-html")
    return pages


# ── URL canonicalisation ────────────────────────────────────────────────────

def test_normalize_url_canonicalises_and_strips_tracking():
    n = cl.normalize_url("HTTPS://Site.Example:443/a/b?utm_source=x&b=2&a=1#frag")
    assert n == "https://site.example/a/b?a=1&b=2"
    assert cl.normalize_url("/rel", base="https://site.example/dir/page") == \
        "https://site.example/rel"
    assert cl.normalize_url("ftp://x.example/y") is None
    assert cl.normalize_url("mailto:a@b.c") is None
    assert cl.normalize_url("") is None


def test_is_probably_html_filters_binary_assets():
    assert cl.is_probably_html("https://x.example/a")
    assert cl.is_probably_html("https://x.example/a.html")
    assert not cl.is_probably_html("https://x.example/a.pdf")
    assert not cl.is_probably_html("https://x.example/a.PNG")


# ── robots ──────────────────────────────────────────────────────────────────

def test_robots_disallow_is_honoured():
    rc = cl.RobotsCache(fetch=lambda u: "User-agent: *\nDisallow: /private\n")
    assert rc.allowed("https://site.example/public")
    assert not rc.allowed("https://site.example/private")


def test_robots_unavailable_fails_open_with_a_note():
    def boom(_u):
        raise RuntimeError("connection refused")
    rc = cl.RobotsCache(fetch=boom)
    assert rc.allowed("https://site.example/anything")
    assert rc.notes and rc.notes[0]["error"]


def test_robots_is_cached_per_host():
    calls = []

    def fetch(u):
        calls.append(u)
        return ""
    rc = cl.RobotsCache(fetch=fetch)
    rc.allowed("https://site.example/a")
    rc.allowed("https://site.example/b")
    rc.allowed("https://other.example/c")
    assert calls.count("https://site.example/robots.txt") == 1
    assert calls.count("https://other.example/robots.txt") == 1


# ── throttle ────────────────────────────────────────────────────────────────

def test_throttle_enforces_per_host_interval():
    now = {"t": 0.0}
    slept = []

    def clock():
        return now["t"]

    def sleep(s):
        slept.append(s)
        now["t"] += s

    th = cl.HostThrottle(3.0, clock=clock, sleep=sleep)
    assert th.wait("https://a.example/1") == 0.0
    now["t"] += 1.0                      # 1s later, same host
    d = th.wait("https://a.example/2")
    assert d == pytest.approx(2.0)
    # another host is not delayed
    assert th.wait("https://b.example/1") == 0.0


# ── fetch + extract ─────────────────────────────────────────────────────────

def test_fetch_page_extracts_title_text_links_and_hash(monkeypatch):
    pages = _make_pages()
    monkeypatch.setattr(cl, "_http_get", _site(pages))
    page = cl.fetch_page("https://site.example/page1",
                         robots=cl.RobotsCache(fetch=lambda u: pages[u][2]))
    assert page["ok"] and page["status"] == 200
    assert page["title"] == "Page 1"
    assert "typesetting problem" in page["text"]
    assert "https://site.example/page2" in page["links"]
    assert all(not l.startswith("mailto") for l in page["links"])
    assert len(page["content_hash"]) == 64


def test_fetch_page_blocks_disallowed_path(monkeypatch):
    pages = _make_pages()
    monkeypatch.setattr(cl, "_http_get", _site(pages))
    robots = cl.RobotsCache(fetch=lambda u: pages["https://site.example/robots.txt"][2])
    page = cl.fetch_page("https://site.example/private", robots=robots)
    assert not page["ok"] and "robots" in page["error"]


def test_fetch_page_rejects_non_html_content(monkeypatch):
    pages = {"https://site.example/img.png": (200, "image/png", "x")}
    monkeypatch.setattr(cl, "_http_get", _site(pages))
    # even when the extension does not give it away, the content-type does
    page = cl.fetch_page("https://site.example/img.png")
    assert not page["ok"]


def test_fetch_page_handles_404_and_network_error(monkeypatch):
    monkeypatch.setattr(cl, "_http_get", _site({}))
    p404 = cl.fetch_page("https://site.example/missing")
    assert not p404["ok"] and p404["status"] == 404

    def boom(url, **kw):
        return {"ok": False, "status": 0, "final_url": url, "content_type": "",
                "text": "", "bytes": 0, "error": "read timeout"}
    monkeypatch.setattr(cl, "_http_get", boom)
    p = cl.fetch_page("https://site.example/slow")
    assert not p["ok"] and "timeout" in p["error"]


# ── records + ingest ────────────────────────────────────────────────────────

def test_page_record_carries_provenance_and_no_assumed_license(monkeypatch):
    pages = _make_pages()
    monkeypatch.setattr(cl, "_http_get", _site(pages))
    page = cl.fetch_page("https://site.example/page1")
    rec = cl.page_record(page, tags=["design", "mockups"])
    assert rec["source"] == "web" and rec["kind"] == "web_page"
    assert rec["license"] is None, "a crawled page's license must stay UNKNOWN"
    assert rec["tags"] == ["design", "mockups"]
    prov = rec["provenance"]
    for key in ("host", "status", "bytes", "fetched_at", "extractor", "user_agent",
                "method"):
        assert key in prov, key
    assert prov["method"] == "static-http"
    assert prov["host"] == "site.example"


def test_learn_urls_ingests_and_counts_skipped(monkeypatch):
    pages = _make_pages()
    monkeypatch.setattr(cl, "_http_get", _site(pages))
    db = _FakeDB()
    urls = ["https://site.example/page1", "https://site.example/page2",
            "https://site.example/private", "https://site.example/missing"]
    out = cl.learn_urls(db, urls, tags=["packaging"], max_pages=10, throttle_s=0.0)
    assert out["counts"]["records"] == 2
    assert out["counts"]["inserted"] == 2
    assert out["skipped_count"] == 2
    rows = db.corpus.list_records(source="web")
    assert len(rows) == 2
    assert all(r["kind"] == "web_page" for r in rows)


def test_learn_urls_is_idempotent(monkeypatch):
    pages = _make_pages()
    monkeypatch.setattr(cl, "_http_get", _site(pages))
    db = _FakeDB()
    urls = ["https://site.example/page1", "https://site.example/page2"]
    first = cl.learn_urls(db, urls, throttle_s=0.0)
    second = cl.learn_urls(db, urls, throttle_s=0.0)
    assert first["counts"]["inserted"] == 2
    assert second["counts"]["inserted"] == 0
    assert second["counts"]["skipped"] == 2


def test_learn_urls_skips_thin_pages(monkeypatch):
    pages = {"https://site.example/thin": (200, "text/html",
                                           "<html><title>T</title><p>too short</p></html>")}
    monkeypatch.setattr(cl, "_http_get", _site(pages))
    db = _FakeDB()
    out = cl.learn_urls(db, ["https://site.example/thin"], throttle_s=0.0)
    assert out["counts"]["records"] == 0
    assert out["skipped_count"] == 1


# ── crawl + sitemap ─────────────────────────────────────────────────────────

def test_crawl_site_stays_on_host_and_respects_max(monkeypatch):
    pages = _make_pages()
    monkeypatch.setattr(cl, "_http_get", _site(pages))
    db = _FakeDB()
    out = cl.crawl_site(db, "https://site.example/page1", max_pages=3,
                        throttle_s=0.0)
    assert out["visited"] <= 3
    assert out["pages_ok"] >= 1
    rows = db.corpus.list_records(source="web")
    assert all("site.example" in (r["url"] or "") for r in rows)


def test_sitemap_urls_parses_and_filters(monkeypatch):
    xml = """<?xml version="1.0"?>
    <urlset><url><loc>https://site.example/a</loc></url>
    <url><loc>https://site.example/b?utm_source=x</loc></url>
    <url><loc>https://site.example/nested.xml</loc></url>
    </urlset>"""
    monkeypatch.setattr(cl, "_http_get", _site(
        {"https://site.example/sitemap.xml": (200, "application/xml", xml)}))
    urls = cl.sitemap_urls("https://site.example/sitemap.xml")
    assert "https://site.example/a" in urls
    assert "https://site.example/b" in urls
    assert all(not u.endswith(".xml") for u in urls)
