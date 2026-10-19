"""Corpus Learner — the static-fetch-only "learn from public sites" lane.

This is the sanctioned replacement for the interactive REA breadth job (the
operator decision 2026-10-19): it reads PUBLIC, SIGNED-OUT pages with a plain
HTTP client (httpx) + trafilatura extraction and files provenance-labelled
records into the local corpus index. It never drives a browser, never logs in,
never enters a credential, never solves a CAPTCHA, and never touches a page a
site's robots.txt disallows.

Supported content: HTML (trafilatura) and PDF (pypdf — a scanned PDF with no
text layer is reported as a failure with the reason, never stored as an empty
document).

Compliance posture (non-negotiable, enforced here):
  • robots.txt is fetched per host and honoured (cached); on a fetch error the
    RFC-9309 "unavailable" convention applies (allow) but the error is recorded
  • one identifiable User-Agent, no cookies, no auth headers, no referrer spoof
  • per-host throttle (default 3.0 s between requests) + hard byte cap
  • content is stored as *knowledge* with provenance — patterns, not assets
  • every record carries url / fetched_at / bytes / extractor / status

The learner writes through ``corpus_ingest.ingest_records`` so runs, counts and
content-hash idempotency are identical to every other corpus source.

Usage:
  python corpus_learner.py --urls urls.txt --tags design,packaging
  python corpus_learner.py --seed https://example.com/blog --max 20 --tags mockups
  python corpus_learner.py --sitemap https://example.com/sitemap.xml --max 50
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import time
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Set, Tuple
from urllib import robotparser

import httpx

try:  # trafilatura is the extractor; keep the import soft so tests can stub it
    import trafilatura
except Exception:  # pragma: no cover - exercised only on a broken install
    trafilatura = None  # type: ignore

DEFAULT_UA = ("NorthstarOS-CorpusLearner/1.0 (local research; static fetch only; "
              "+public-pages)")
DEFAULT_TIMEOUT = 25.0
DEFAULT_MAX_BYTES = 4_000_000
DEFAULT_THROTTLE_S = 3.0
MAX_CONTENT_CHARS = 200_000
SUMMARY_CHARS = 400

_ALLOWED_SCHEMES = ("http", "https")
_SKIP_EXT = (".pdf", ".zip", ".png", ".jpg", ".jpeg", ".gif", ".webp", ".mp4",
             ".mp3", ".svg", ".ico", ".woff", ".woff2", ".ttf", ".otf", ".dmg",
             ".exe", ".msi", ".rss", ".atom")


# ── small utilities ─────────────────────────────────────────────────────────

def normalize_url(url: str, base: Optional[str] = None) -> Optional[str]:
    """Canonicalise a URL: absolute, scheme-checked, fragment dropped, host
    lower-cased, default ports dropped, tracking params stripped."""
    if not url:
        return None
    url = url.strip()
    if base:
        url = urllib.parse.urljoin(base, url)
    try:
        parts = urllib.parse.urlsplit(url)
    except ValueError:
        return None
    if parts.scheme not in _ALLOWED_SCHEMES:
        return None
    host = (parts.hostname or "").lower()
    if not host:
        return None
    netloc = host if parts.port in (None, 80, 443) else f"{host}:{parts.port}"
    query = urllib.parse.urlencode(sorted(
        (k, v) for k, v in urllib.parse.parse_qsl(parts.query, keep_blank_values=True)
        if not k.lower().startswith(("utm_", "fbclid", "gclid", "mc_"))))
    path = parts.path or "/"
    return urllib.parse.urlunsplit((parts.scheme, netloc, path, query, ""))


def is_probably_html(url: str) -> bool:
    path = urllib.parse.urlsplit(url).path.lower()
    return not path.endswith(_SKIP_EXT)


def is_probably_pdf(url: str) -> bool:
    return urllib.parse.urlsplit(url).path.lower().endswith(".pdf")


def extract_pdf_text(data: bytes, *, max_pages: int = 80) -> Dict[str, Any]:
    """Text + metadata of a PDF via pypdf (already a dependency). Local only.

    Returns an honest record: ``ok`` False with a reason when the text layer is
    missing (a scanned PDF has no extractable text - that is reported, not
    silently recorded as an empty document).
    """
    try:
        import io as _io

        from pypdf import PdfReader
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": f"pypdf unavailable: {str(exc)[:120]}",
                "title": "", "text": "", "pages": 0, "pages_read": 0}
    try:
        reader = PdfReader(_io.BytesIO(data))
        if getattr(reader, "is_encrypted", False):
            try:
                reader.decrypt("")     # an empty owner password is common
            except Exception:  # noqa: BLE001
                return {"ok": False, "error": "pdf is encrypted", "title": "",
                        "text": "", "pages": len(reader.pages), "pages_read": 0}
        meta = (reader.metadata or {})
        title = str(meta.get("/Title") or "").strip()
        author = str(meta.get("/Author") or "").strip()
        total = len(reader.pages)
        parts: List[str] = []
        read = 0
        for page in reader.pages[:max_pages]:
            try:
                parts.append(page.extract_text() or "")
            except Exception:  # noqa: BLE001 - one bad page must not kill the doc
                parts.append("")
            read += 1
        text = "\n".join(parts).strip()
        return {"ok": bool(text), "title": title[:300], "author": author[:200],
                "text": text, "pages": total, "pages_read": read,
                "error": None if text else "no extractable text layer (scanned PDF?)"}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": str(exc)[:200], "title": "", "text": "",
                "pages": 0, "pages_read": 0}


def content_hash(text: str) -> str:
    return hashlib.sha256((text or "").encode("utf-8", "replace")).hexdigest()


# ── robots + throttle ───────────────────────────────────────────────────────

class RobotsCache:
    """Per-host robots.txt parser. ``fetch`` is injectable for offline tests."""

    def __init__(self, fetch: Callable[[str], Optional[str]], user_agent: str = DEFAULT_UA):
        self._fetch = fetch
        self._ua = user_agent
        self._cache: Dict[str, Optional[robotparser.RobotFileParser]] = {}
        self.notes: List[Dict[str, str]] = []

    def _parser(self, scheme: str, host: str) -> Optional[robotparser.RobotFileParser]:
        if host in self._cache:
            return self._cache[host]
        robots_url = f"{scheme}://{host}/robots.txt"
        try:
            body = self._fetch(robots_url)
        except Exception as exc:  # noqa: BLE001 - unavailable robots.txt per RFC 9309
            self.notes.append({"host": host, "error": str(exc)[:120]})
            self._cache[host] = None
            return None
        if not body:
            self._cache[host] = None
            return None
        rp = robotparser.RobotFileParser()
        rp.parse(body.splitlines())
        self._cache[host] = rp
        return rp

    def allowed(self, url: str) -> bool:
        parts = urllib.parse.urlsplit(url)
        rp = self._parser(parts.scheme, (parts.hostname or "").lower())
        if rp is None:
            return True  # no robots.txt (or unavailable) -> allowed
        try:
            return bool(rp.can_fetch(self._ua, url))
        except Exception:  # noqa: BLE001 - malformed robots.txt -> be conservative
            return False


class HostThrottle:
    """Minimum interval between consecutive requests to one host."""

    def __init__(self, interval: float = DEFAULT_THROTTLE_S,
                 clock: Callable[[], float] = time.monotonic,
                 sleep: Callable[[float], None] = time.sleep):
        self.interval = float(interval)
        self._clock = clock
        self._sleep = sleep
        self._last: Dict[str, float] = {}
        self.waited = 0.0

    def wait(self, url: str) -> float:
        host = (urllib.parse.urlsplit(url).hostname or "").lower()
        now = self._clock()
        last = self._last.get(host)
        delay = 0.0
        if last is not None:
            delay = max(0.0, self.interval - (now - last))
        if delay > 0:
            self._sleep(delay)
            self.waited += delay
            now = self._clock()
        self._last[host] = now
        return delay


# ── fetch + extract ─────────────────────────────────────────────────────────

def _http_get(url: str, *, timeout: float = DEFAULT_TIMEOUT,
              max_bytes: int = DEFAULT_MAX_BYTES,
              client: Optional[httpx.Client] = None) -> Dict[str, Any]:
    """One GET. Returns {ok, status, final_url, content_type, text, bytes}.

    Never follows a non-http(s) redirect; never sends auth or cookies."""
    owns = client is None
    c = client or httpx.Client(follow_redirects=True, timeout=timeout,
                               headers={"User-Agent": DEFAULT_UA,
                                        "Accept": "text/html,application/xhtml+xml,"
                                                  "application/xml;q=0.9,*/*;q=0.5",
                                        "Accept-Language": "en"})
    try:
        with c.stream("GET", url) as resp:
            status = resp.status_code
            ctype = (resp.headers.get("content-type") or "").split(";")[0].strip().lower()
            chunks: List[bytes] = []
            total = 0
            for chunk in resp.iter_bytes():
                total += len(chunk)
                if total > max_bytes:
                    break
                chunks.append(chunk)
            raw = b"".join(chunks)
        enc = "utf-8"
        m = re.search(r"charset=([\w\-]+)", (ctype or ""), re.I)
        if m:
            enc = m.group(1)
        try:
            text = raw.decode(enc, errors="replace")
        except LookupError:
            text = raw.decode("utf-8", errors="replace")
        return {"ok": 200 <= status < 300, "status": status,
                "final_url": str(resp.url), "content_type": ctype,
                "text": text, "bytes": len(raw), "raw": raw}
    except Exception as exc:  # noqa: BLE001 - a fetch failure is data, not a crash
        return {"ok": False, "status": 0, "final_url": url, "content_type": "",
                "text": "", "bytes": 0, "error": str(exc)[:200]}
    finally:
        if owns:
            c.close()


def extract_page(html: str, url: str) -> Dict[str, Any]:
    """Extract title/text/links with trafilatura (+ lxml for links)."""
    title, text, author, date = "", "", "", ""
    if trafilatura is not None and html:
        try:
            doc = trafilatura.bare_extraction(html, url=url, with_metadata=True,
                                              include_tables=True,
                                              favor_precision=False)
            if doc is not None:
                title = getattr(doc, "title", "") or ""
                text = getattr(doc, "text", "") or ""
                author = getattr(doc, "author", "") or ""
                date = getattr(doc, "date", "") or ""
        except Exception:  # noqa: BLE001 - fall back to a crude strip below
            pass
    if not text:
        text = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", html or "")
        text = re.sub(r"(?s)<[^>]+>", " ", text)
        text = re.sub(r"\s+", " ", text).strip()
    if not title:
        m = re.search(r"(?is)<title[^>]*>(.*?)</title>", html or "")
        if m:
            title = re.sub(r"\s+", " ", m.group(1)).strip()
    links = extract_links(html, url)
    return {"title": title[:300], "text": text, "author": author[:200],
            "date": str(date)[:40], "links": links}


def extract_links(html: str, base_url: str) -> List[str]:
    """All http(s) links on the page, canonicalised + de-duplicated (order kept)."""
    out: List[str] = []
    seen: Set[str] = set()
    for href in re.findall(r'(?is)<a[^>]+href=["\']([^"\']+)["\']', html or ""):
        n = normalize_url(href, base=base_url)
        if n and n not in seen and is_probably_html(n):
            seen.add(n)
            out.append(n)
    return out


def fetch_page(url: str, *, robots: Optional[RobotsCache] = None,
               throttle: Optional[HostThrottle] = None,
               client: Optional[httpx.Client] = None,
               timeout: float = DEFAULT_TIMEOUT,
               max_bytes: int = DEFAULT_MAX_BYTES) -> Dict[str, Any]:
    """Fetch + extract one page. Honours robots; returns a page dict."""
    canon = normalize_url(url)
    fetched_at = datetime.now(timezone.utc).isoformat()
    if not canon:
        return {"url": url, "ok": False, "status": 0, "error": "invalid or non-http url",
                "fetched_at": fetched_at}
    if not is_probably_html(canon) and not is_probably_pdf(canon):
        return {"url": canon, "ok": False, "status": 0, "error": "unsupported content type",
                "fetched_at": fetched_at}
    if robots is not None and not robots.allowed(canon):
        return {"url": canon, "ok": False, "status": 0, "error": "disallowed by robots.txt",
                "fetched_at": fetched_at}
    if throttle is not None:
        throttle.wait(canon)
    resp = _http_get(canon, timeout=timeout, max_bytes=max_bytes, client=client)
    page = {"url": canon, "final_url": normalize_url(resp.get("final_url") or canon) or canon,
            "ok": bool(resp.get("ok")), "status": resp.get("status"),
            "content_type": resp.get("content_type", ""), "bytes": resp.get("bytes", 0),
            "fetched_at": fetched_at}
    if resp.get("error"):
        page["error"] = resp["error"]
    if not resp.get("ok"):
        page.setdefault("error", f"http {resp.get('status')}")
        return page
    ctype = resp.get("content_type") or ""
    if "pdf" in ctype or is_probably_pdf(canon):
        # PDF lane: extract with the dependency already present (pypdf). A
        # scanned PDF has no text layer - that is recorded as a failure with the
        # reason, never stored as an empty document.
        pdf = extract_pdf_text(resp.get("raw") or b"")
        page["content_kind"] = "pdf"
        page["title"] = pdf.get("title") or urllib.parse.urlsplit(canon).path.rsplit("/", 1)[-1]
        page["text"] = pdf.get("text") or ""
        page["author"] = pdf.get("author") or ""
        page["links"] = []
        page["pages"] = pdf.get("pages")
        page["pages_read"] = pdf.get("pages_read")
        page["content_hash"] = content_hash(page["text"])
        if not pdf.get("ok"):
            page["ok"] = False
            page["error"] = f"pdf: {pdf.get('error')}"
        return page
    if ctype and "html" not in ctype and "xml" not in ctype and "text" not in ctype:
        page["ok"] = False
        page["error"] = f"unsupported content-type {ctype}"
        return page
    ex = extract_page(resp.get("text") or "", page["final_url"])
    page["content_kind"] = "html"
    page.update(ex)
    page["content_hash"] = content_hash(ex["text"])
    return page


# ── records + ingest ────────────────────────────────────────────────────────

def page_record(page: Dict[str, Any], *, tags: Optional[Sequence[str]] = None,
                source: str = "web") -> Dict[str, Any]:
    """Turn a fetched page into a corpus record (provenance-heavy, honest)."""
    text = (page.get("text") or "").strip()
    title = (page.get("title") or "").strip() or (page.get("url") or "")
    summary = " ".join(text[:SUMMARY_CHARS].split())
    return {
        "source": source,
        "source_id": page.get("url") or page.get("final_url") or "",
        "kind": ("pdf_document" if page.get("content_kind") == "pdf" else "web_page"),
        "title": title[:300],
        "url": page.get("url"),
        "license": None,          # a crawled page's license is UNKNOWN until read
        "summary": summary,
        "content": text[:MAX_CONTENT_CHARS],
        "tags": list(tags or []),
        "provenance": {
            "final_url": page.get("final_url"),
            "host": urllib.parse.urlsplit(page.get("url") or "").hostname,
            "status": page.get("status"),
            "content_type": page.get("content_type"),
            "content_kind": page.get("content_kind") or "html",
            "pages": page.get("pages"),
            "pages_read": page.get("pages_read"),
            "bytes": page.get("bytes"),
            "fetched_at": page.get("fetched_at"),
            "extractor": ("pypdf" if page.get("content_kind") == "pdf"
                          else "trafilatura/2.3.1"),
            "user_agent": DEFAULT_UA,
            "author": page.get("author") or None,
            "published": page.get("date") or None,
            "method": "static-http",
        },
    }


def learn_urls(db: Any, urls: Iterable[str], *, tags: Optional[Sequence[str]] = None,
               source: str = "web", throttle_s: float = DEFAULT_THROTTLE_S,
               robots: Optional[RobotsCache] = None,
               client: Optional[httpx.Client] = None,
               max_pages: int = 50) -> Dict[str, Any]:
    """Fetch public pages and ingest them as corpus records. Returns honest counts."""
    from corpus_ingest import ingest_records  # local import: keeps CLI light

    robots = robots or RobotsCache(fetch=lambda u: (
        _http_get(u, timeout=10.0, max_bytes=200_000, client=client).get("text") or ""))
    throttle = HostThrottle(throttle_s)
    records: List[Dict[str, Any]] = []
    skipped: List[Dict[str, str]] = []
    for raw in list(urls)[:max_pages]:
        page = fetch_page(raw, robots=robots, throttle=throttle, client=client)
        if not page.get("ok"):
            skipped.append({"url": raw, "reason": page.get("error") or "fetch failed"})
            continue
        rec = page_record(page, tags=tags, source=source)
        if len((rec.get("content") or "")) < 200:
            skipped.append({"url": raw, "reason": "extracted text too thin (<200 chars)"})
            continue
        records.append(rec)
    result = ingest_records(db, source, records,
                            source_path=f"static-crawl x{len(records)}")
    result["skipped"] = skipped[:50]
    result["skipped_count"] = len(skipped)
    result["robots_notes"] = robots.notes[:20]
    return result


def crawl_site(db: Any, seed: str, *, max_pages: int = 25,
               same_host_only: bool = True,
               tags: Optional[Sequence[str]] = None,
               throttle_s: float = DEFAULT_THROTTLE_S,
               client: Optional[httpx.Client] = None) -> Dict[str, Any]:
    """Breadth-first crawl from a seed, same-host by default, robots-honoured."""
    seed_c = normalize_url(seed)
    if not seed_c:
        raise ValueError(f"invalid seed url {seed!r}")
    host = urllib.parse.urlsplit(seed_c).hostname or ""
    robots = RobotsCache(fetch=lambda u: _http_get(
        u, timeout=10.0, max_bytes=200_000, client=client).get("text") or "")
    throttle = HostThrottle(throttle_s)

    queue: List[str] = [seed_c]
    visited: Set[str] = set()
    pages: List[Dict[str, Any]] = []
    while queue and len(visited) < max_pages:
        url = queue.pop(0)
        if url in visited:
            continue
        visited.add(url)
        page = fetch_page(url, robots=robots, throttle=throttle, client=client)
        if page.get("ok"):
            pages.append(page)
            for link in page.get("links") or []:
                if link in visited:
                    continue
                if same_host_only and (urllib.parse.urlsplit(link).hostname or "") != host:
                    continue
                queue.append(link)

    records = [page_record(p, tags=tags) for p in pages
               if len((p.get("text") or "")) >= 200]
    from corpus_ingest import ingest_records
    result = ingest_records(db, "web", records,
                            source_path=f"crawl {seed_c} x{len(records)}")
    result["visited"] = len(visited)
    result["pages_ok"] = len(pages)
    result["seed"] = seed_c
    result["robots_notes"] = robots.notes[:20]
    return result


def sitemap_urls(sitemap_url: str, *, client: Optional[httpx.Client] = None,
                 limit: int = 500) -> List[str]:
    """Read a sitemap (or sitemap index) and return canonical page URLs."""
    resp = _http_get(sitemap_url, timeout=20.0, max_bytes=2_000_000, client=client)
    if not resp.get("ok"):
        return []
    locs = re.findall(r"(?is)<loc>\s*([^<\s]+)\s*</loc>", resp.get("text") or "")
    out: List[str] = []
    seen: Set[str] = set()
    for loc in locs:
        n = normalize_url(loc)
        if not n or n in seen:
            continue
        if n.endswith(".xml") or "sitemap" in n.split("/")[-1].lower():
            continue
        seen.add(n)
        out.append(n)
        if len(out) >= limit:
            break
    return out


# ── CLI ─────────────────────────────────────────────────────────────────────

def _main() -> int:
    ap = argparse.ArgumentParser(description="Static-fetch corpus learner")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--urls", help="file with one URL per line")
    g.add_argument("--seed", help="crawl breadth-first from this URL")
    g.add_argument("--sitemap", help="read this sitemap and learn its pages")
    ap.add_argument("--tags", default="", help="comma-separated tags")
    ap.add_argument("--max", type=int, default=25)
    ap.add_argument("--throttle", type=float, default=DEFAULT_THROTTLE_S)
    ap.add_argument("--dry-run", action="store_true",
                    help="fetch + report, but do not touch the corpus index")
    args = ap.parse_args()

    tags = [t.strip() for t in args.tags.split(",") if t.strip()]
    if args.dry_run:
        robots = RobotsCache(fetch=lambda u: _http_get(u, timeout=10.0,
                                                       max_bytes=200_000).get("text") or "")
        throttle = HostThrottle(args.throttle)
        urls = ([ln.strip() for ln in Path(args.urls).read_text(encoding="utf-8").splitlines()
                 if ln.strip()] if args.urls else
                sitemap_urls(args.sitemap) if args.sitemap else [args.seed])
        for u in urls[:args.max]:
            page = fetch_page(u, robots=robots, throttle=throttle)
            print(json.dumps({"url": u, "ok": page.get("ok"),
                              "status": page.get("status"),
                              "title": (page.get("title") or "")[:80],
                              "chars": len(page.get("text") or ""),
                              "error": page.get("error")}, ensure_ascii=False))
        return 0

    from data_layer import get_northstar_db
    db = get_northstar_db()
    if args.urls:
        urls = [ln.strip() for ln in Path(args.urls).read_text(encoding="utf-8").splitlines()
                if ln.strip()]
        out = learn_urls(db, urls, tags=tags, max_pages=args.max, throttle_s=args.throttle)
    elif args.sitemap:
        urls = sitemap_urls(args.sitemap, limit=args.max)
        out = learn_urls(db, urls, tags=tags, max_pages=args.max, throttle_s=args.throttle)
    else:
        out = crawl_site(db, args.seed, max_pages=args.max, tags=tags,
                         throttle_s=args.throttle)
    print(json.dumps(out, indent=2)[:4000])
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
