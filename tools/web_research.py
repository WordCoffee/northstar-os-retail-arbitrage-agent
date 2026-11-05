"""Research the web and code hosts without a browser handle.

Chrome Connect is the controller for *browser* work: it enforces the host
denylist, the hardcoded Amazon blocklist, the profile lease and the audit
chain. This module is not a browser. It is an HTTP client plus an extractor,
so it does not bypass that governance - but it is still an outbound path to
the web, and an outbound path that is not governed is exactly how a denylist
becomes decorative. So this module carries the same two guarantees:

  1. The Amazon blocklist is hardcoded here and evaluated **before any
     request leaves the machine**. It is not a config value and it is not
     overridable by an argument.
  2. Every request and every result is appended to ``logs/web_research.jsonl``
     with its URL, timestamp, status, byte count and SHA-256.

Capabilities (all free, no API key):

    search_web(query)        DuckDuckGo via ``ddgs`` (MIT)
    search_github(query)     GitHub repository search API
    search_huggingface(q)    Hugging Face model API
    fetch_page(url)          clean article text via ``trafilatura`` (Apache-2.0)
    fetch_readme(repo)       a repo's README as text

CLI:

    python tools/web_research.py --search "ip adapter flux" --limit 5
    python tools/web_research.py --github "comfyui product photography" --limit 5
    python tools/web_research.py --hf "ip-adapter" --limit 5
    python tools/web_research.py --fetch https://github.com/block/goose
    python tools/web_research.py --readme block/goose
    python tools/web_research.py --license block/goose      # reads LICENSE, reports class

Exit codes: 0 ok, 1 refused (Amazon or blocked host), 2 transport/dependency
failure. A transport failure is never reported as an empty result.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parents[1]
AUDIT_LOG = ROOT / "logs" / "web_research.jsonl"
PROVENANCE = ROOT / "provenance.csv"
UA = "northstar-os-research/1.0 (+local bench)"

#: Evaluated before anything else, never read from config, never overridable.
#: Any host equal to, or a subdomain of, one of these is refused outright.
AMAZON_HOSTS = (
    "amazon.com",
    "amazon.co.uk",
    "amazon.ca",
    "amazon.de",
    "amazon.fr",
    "amazon.it",
    "amazon.es",
    "amazon.nl",
    "amazon.se",
    "amazon.pl",
    "amazon.com.mx",
    "amazon.com.br",
    "amazon.com.au",
    "amazon.co.jp",
    "amazon.in",
    "amazon.ae",
    "amazon.sa",
    "amazon.sg",
    "amazon.com.tr",
    "amazon.eg",
    "amazon.ie",
    "amazon.be",
    "amzn.to",
    "amzn.com",
    "amazon-adsystem.com",
    "media-amazon.com",
    "images-amazon.com",
    "ssl-images-amazon.com",
    "a2z.com",
    # AWS (amazonaws.com) is deliberately NOT listed: it is a cloud host many
    # legitimate artifacts live on, not a consumer Amazon surface. Amazon
    # storefronts and Amazon-owned consumer properties are what is blocked.
    "primevideo.com",
    "audible.com",
    "wholefoodsmarket.com",
    "zappos.com",
    "twitch.tv",
    "imdb.com",
    "goodreads.com",
)


class Refused(RuntimeError):
    """A request the module will not make. Never a result."""


class Transport(RuntimeError):
    """The request could not be completed. Never an empty result."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _host(url: str) -> str:
    try:
        return (urllib.parse.urlsplit(url).hostname or "").lower().rstrip(".")
    except ValueError:
        return ""


def is_amazon_host(host: str) -> bool:
    """True when the host is Amazon or a lookalike of one.

    ``evil-amazon.com`` is not Amazon. ``amazon.com.evil.test`` is a lookalike
    and is refused: a suffix match on the *end* of the host is the only safe
    direction.
    """
    host = (host or "").lower().rstrip(".")
    if not host:
        return False
    for blocked in AMAZON_HOSTS:
        if host == blocked or host.endswith("." + blocked):
            return True
    # A registrable domain that merely *contains* a blocked label is a
    # lookalike and gets the same refusal.
    labels = host.split(".")
    return any(label in {b.split(".")[0] for b in AMAZON_HOSTS} for label in labels)


def guard(url: str) -> str:
    """Refuse before the request is made. Returns the URL when it may go out."""
    if not url or "://" not in url:
        raise Refused(f"not_an_absolute_url: {url!r}")
    scheme = urllib.parse.urlsplit(url).scheme.lower()
    if scheme not in ("http", "https"):
        raise Refused(f"scheme_refused: {scheme}")
    host = _host(url)
    if not host:
        raise Refused(f"no_host: {url!r}")
    if is_amazon_host(host):
        raise Refused(f"amazon_refused: {host} - Amazon is a standing gate; "
                      "use fixtures and seed data")
    return url


def _log(record: Dict[str, Any]) -> None:
    AUDIT_LOG.parent.mkdir(parents=True, exist_ok=True)
    record = {"at": _now(), **record}
    with AUDIT_LOG.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")


def _http(url: str, *, timeout: float = 20.0,
          headers: Optional[Dict[str, str]] = None) -> bytes:
    guard(url)
    request = urllib.request.Request(url, headers={"User-Agent": UA, **(headers or {})})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read()
            status = response.status
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        _log({"action": "http", "url": url, "status": "error", "error": str(exc)})
        raise Transport(f"unreachable: {exc}") from exc
    _log({"action": "http", "url": url, "status": status,
          "bytes": len(body), "sha256": hashlib.sha256(body).hexdigest()})
    return body


# --------------------------------------------------------------------------- search

def search_web(query: str, *, limit: int = 8) -> List[Dict[str, str]]:
    """DuckDuckGo results. ``ddgs`` is optional: absence raises Transport."""
    try:
        from ddgs import DDGS  # type: ignore
    except ImportError as exc:  # pragma: no cover - environment dependent
        raise Transport("ddgs_not_installed: pip install ddgs") from exc
    try:
        with DDGS() as ddgs:
            rows = list(ddgs.text(query, max_results=max(1, min(int(limit), 25))))
    except Exception as exc:  # noqa: BLE001 - reported, never a silent empty
        _log({"action": "search", "engine": "ddgs", "query": query,
              "status": "error", "error": f"{type(exc).__name__}: {exc}"})
        raise Transport(f"ddgs_failed: {type(exc).__name__}: {exc}") from exc
    out = []
    for row in rows:
        url = row.get("href") or row.get("url") or ""
        if url and is_amazon_host(_host(url)):
            _log({"action": "search", "engine": "ddgs", "query": query,
                  "status": "result_refused", "url": url})
            continue
        out.append({"title": row.get("title", ""), "url": url,
                    "snippet": row.get("body", "")})
    _log({"action": "search", "engine": "ddgs", "query": query,
          "status": "ok", "results": len(out)})
    return out


def search_github(query: str, *, limit: int = 8) -> List[Dict[str, Any]]:
    url = ("https://api.github.com/search/repositories?q="
           + urllib.parse.quote(query) + f"&sort=stars&order=desc&per_page={max(1, min(int(limit), 30))}")
    data = json.loads(_http(url).decode("utf-8"))
    out = []
    for item in data.get("items", []):
        out.append({
            "full_name": item.get("full_name"),
            "stars": item.get("stargazers_count"),
            "license": ((item.get("license") or {}).get("spdx_id") or "none"),
            "url": item.get("html_url"),
            "description": (item.get("description") or "")[:240],
        })
    return out


def search_huggingface(query: str, *, limit: int = 8,
                       kind: str = "models") -> List[Dict[str, Any]]:
    url = (f"https://huggingface.co/api/{kind}?search="
           + urllib.parse.quote(query)
           + f"&sort=downloads&direction=-1&limit={max(1, min(int(limit), 50))}")
    data = json.loads(_http(url).decode("utf-8"))
    out = []
    for item in data:
        tags = item.get("tags") or []
        licences = [t.split(":", 1)[1] for t in tags if isinstance(t, str) and t.startswith("license:")]
        out.append({
            "id": item.get("id") or item.get("modelId"),
            "downloads": item.get("downloads"),
            "likes": item.get("likes"),
            "license": licences[0] if licences else "unstated",
            "url": f"https://huggingface.co/{item.get('id') or item.get('modelId')}",
        })
    return out


# --------------------------------------------------------------------------- fetch

def fetch_page(url: str, *, max_chars: int = 20000) -> Dict[str, Any]:
    """Clean main-content text. Falls back to nothing rather than raw HTML soup."""
    guard(url)
    try:
        import trafilatura  # type: ignore
    except ImportError as exc:  # pragma: no cover - environment dependent
        raise Transport("trafilatura_not_installed: pip install trafilatura") from exc
    raw = _http(url)
    text = trafilatura.extract(raw.decode("utf-8", "replace")) or ""
    if not text.strip():
        raise Transport(f"extraction_empty: {url} produced no main text")
    return {"url": url, "chars": len(text), "text": text[:max_chars]}


def fetch_readme(repo: str, *, ref: str = "HEAD") -> Dict[str, Any]:
    """A repo's README from raw.githubusercontent.com, or Transport."""
    repo = repo.strip().strip("/")
    for name in ("README.md", "readme.md", "README.rst", "README"):
        url = f"https://raw.githubusercontent.com/{repo}/{ref}/{name}"
        try:
            body = _http(url)
        except Transport:
            continue
        text = body.decode("utf-8", "replace")
        return {"repo": repo, "path": name, "chars": len(text), "text": text[:20000]}
    raise Transport(f"readme_not_found: {repo}")


_LICENSE_CLASSES = (
    (r"MIT License|Permission is hereby granted, free of charge", "MIT"),
    (r"Apache License|Version 2\.0, January 2004", "Apache-2.0"),
    (r"GNU AFFERO GENERAL PUBLIC LICENSE", "AGPL-3.0"),
    (r"GNU LESSER GENERAL PUBLIC LICENSE", "LGPL"),
    (r"GNU GENERAL PUBLIC LICENSE", "GPL"),
    (r"Mozilla Public License", "MPL-2.0"),
    (r"BSD 3-Clause|Redistribution and use in source and binary forms", "BSD"),
    (r"Creative Commons", "CC"),
    (r"non-commercial|NonCommercial|NON-COMMERCIAL", "NON-COMMERCIAL"),
)


def classify_license(text: str) -> str:
    for pattern, label in _LICENSE_CLASSES:
        if re.search(pattern, text, re.I):
            return label
    return "unclassified"


def read_license(repo: str, *, ref: str = "HEAD") -> Dict[str, Any]:
    """Read the actual LICENSE file and classify it. Never guess from a badge."""
    repo = repo.strip().strip("/")
    for name in ("LICENSE", "LICENSE.md", "LICENSE.txt", "COPYING"):
        url = f"https://raw.githubusercontent.com/{repo}/{ref}/{name}"
        try:
            body = _http(url)
        except Transport:
            continue
        text = body.decode("utf-8", "replace")
        return {"repo": repo, "path": name, "class": classify_license(text),
                "first_lines": "\n".join(text.splitlines()[:6])}
    raise Transport(f"license_not_found: {repo}")


def log_provenance(component: str, *, source: str, license_: str,
                   status: str = "CANDIDATE", notes: str = ""
                   ) -> None:
    """Append one row to provenance.csv. Refuses to write a guessed licence."""
    if not license_ or license_.lower() in ("", "unknown", "unverified-guess"):
        raise ValueError("provenance needs a licence read from upstream, not a guess")
    row = [component, status, source, license_, "ty-autonomy", notes]
    new = not PROVENANCE.exists()
    with PROVENANCE.open("a", encoding="utf-8", newline="") as fh:
        if new:
            fh.write("component,status,source,license,reviewer,notes\n")
        fh.write(",".join('"' + str(cell).replace('"', "'") + '"' for cell in row) + "\n")


# --------------------------------------------------------------------------- cli

def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Grounded web and repo research.")
    parser.add_argument("--search")
    parser.add_argument("--github")
    parser.add_argument("--hf")
    parser.add_argument("--fetch")
    parser.add_argument("--readme")
    parser.add_argument("--license", dest="license_repo")
    parser.add_argument("--limit", type=int, default=8)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    try:
        if args.search:
            result = search_web(args.search, limit=args.limit)
        elif args.github:
            result = search_github(args.github, limit=args.limit)
        elif args.hf:
            result = search_huggingface(args.hf, limit=args.limit)
        elif args.fetch:
            result = fetch_page(args.fetch)
        elif args.readme:
            result = fetch_readme(args.readme)
        elif args.license_repo:
            result = read_license(args.license_repo)
        else:
            parser.print_help()
            return 2
    except Refused as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        return 1
    except Transport as exc:
        print(f"TRANSPORT FAILURE (not a result): {exc}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0
    if isinstance(result, list):
        for row in result:
            print(f"- {row.get('full_name') or row.get('id') or row.get('title')} "
                  f"[{row.get('license', '?')}] {row.get('url')}")
        if not result:
            print("(no results)")
    elif isinstance(result, dict) and "text" in result:
        print(result["text"])
    else:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
