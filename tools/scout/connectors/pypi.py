"""PyPI connector (A18).  Public APIs, no token.

PyPI has no keyless JSON *search* endpoint: ``pypi.org/search`` is a JavaScript
client challenge (a 200 response containing "Client Challenge" and no results)
and the XML-RPC ``search`` method was removed.  The honest route is:

1. read the Simple index once (cached 24 h under ``state/intel/cache/``),
2. filter project names by the query tokens locally,
3. read ``/pypi/<name>/json`` for the best few candidates (licence + version).

That is 1 index GET per day plus one small GET per candidate.  No quota is
asserted because PyPI publishes none for these endpoints.
"""
from __future__ import annotations

import json
import re
import time
import urllib.parse
from pathlib import Path
from typing import Any, Dict, List, Optional

from .. import config, http
from ..licence import from_classifiers, normalise
from .base import Connector, _int, raw_hit

_INDEX_TTL = 24 * 3600
_ANCHOR = re.compile(r'href="/simple/([^/"]+)/"')
_STOP = {"with", "from", "that", "this", "your", "over", "into"}
_CANONICAL = re.compile(r"[-_.]+")


def canonical_name(name: str) -> str:
    """PEP 503 normalisation: case-insensitive, runs of -_. collapse to '-'."""
    return _CANONICAL.sub("-", str(name).strip()).lower()


class PyPiConnector(Connector):
    name = "pypi"
    kind = "package"
    ecosystem = "PyPI"

    # ------------------------------------------------------------------ index
    def _simple_names(self) -> List[str]:
        cache = config.CACHE_DIR / "pypi-simple-names.txt"
        try:
            if cache.is_file() and (time.time() - cache.stat().st_mtime) < _INDEX_TTL:
                cached = [line for line in cache.read_text(encoding="utf-8").splitlines() if line]
                if len(cached) >= 1000:  # a truncated/empty cache is not an index
                    return cached
        except OSError:
            pass
        response = http.request("https://pypi.org/simple/",
                                headers={"Accept": "text/html"}, timeout=60.0)
        names = sorted({urllib.parse.unquote(match) for match in _ANCHOR.findall(response.text())})
        if not names:
            raise http.ScoutTransport("pypi_simple_index_empty", url=response.url,
                                      status=response.status)
        try:
            cache.parent.mkdir(parents=True, exist_ok=True)
            temp = cache.with_suffix(".tmp")
            temp.write_text("\n".join(names) + "\n", encoding="utf-8")
            temp.replace(cache)  # a failed write can never leave a poisoned cache
        except OSError:
            pass
        return names

    @staticmethod
    def _tokens(query: str) -> List[str]:
        return [token for token in re.split(r"[^a-z0-9]+", query.lower())
                if len(token) >= 4 and token not in _STOP]

    @classmethod
    def _name_score(cls, name: str, tokens: List[str], query: str) -> float:
        lowered = name.lower()
        score = 0.0
        phrase = re.sub(r"[^a-z0-9]+", "-", query.lower()).strip("-")
        if phrase and (lowered == phrase or lowered.startswith(phrase + "-")):
            score += 3.0
        for token in tokens:
            # Word-boundary match only: "firetail" is not a "retail" package.
            if re.search(r"(?:^|[-_.])" + re.escape(token) + r"(?:[-_.]|$)", lowered):
                score += 1.0
        return score

    def _candidates(self, query: str, limit: int) -> List[str]:
        tokens = self._tokens(query)
        if not tokens:
            return []
        scored = []
        for name in self._simple_names():
            score = self._name_score(name, tokens, query)
            if score > 0:
                scored.append((score, len(name), name))
        scored.sort(key=lambda row: (-row[0], row[1], row[2]))
        return [name for _, _, name in scored[:max(1, int(limit))]]

    # ------------------------------------------------------------------ fetch
    def fetch(self, query: str, limit: int) -> Dict[str, Any]:
        projects: List[Dict[str, Any]] = []
        for name in self._candidates(query, limit):
            quoted = urllib.parse.quote(name)
            try:
                response = http.request(f"https://pypi.org/pypi/{quoted}/json")
                projects.append(response.json())
            except http.ScoutTransport as exc:
                # One dead project must not hide the rest of the source.
                projects.append({"_error": str(exc), "_name": name})
            time.sleep(0.4)
        return {
            "source": self.name,
            "query": query,
            "status": 200 if projects else 0,
            "projects": projects,
        }

    def parse(self, payload: Any, query: str = "") -> List[Dict[str, Any]]:
        projects = (payload or {}).get("projects") if isinstance(payload, dict) else payload
        hits: List[Dict[str, Any]] = []
        for project in projects or []:
            info = (project or {}).get("info") or {}
            name = str(info.get("name") or (project or {}).get("_name") or "").strip()
            if not name:
                continue
            licence_raw = (info.get("license_expression")
                           or info.get("license")
                           or "")
            licence = normalise(licence_raw)
            if licence == "unknown":
                licence = from_classifiers(info.get("classifiers") or [])
            hits.append(raw_hit(
                source=self.name,
                identity=canonical_name(name),
                url=str(info.get("package_url")
                        or f"https://pypi.org/project/{name}/"),
                title=name,
                licence=licence,
                downloads=None,  # PyPI's JSON API publishes no download count
                stars=None,
                description=str(info.get("summary") or "").strip(),
                version=info.get("version"),
                kind=self.kind,
                ecosystem=self.ecosystem,
                requires_python=info.get("requires_python"),
                classifiers=[c for c in (info.get("classifiers") or [])
                             if "License ::" in str(c)][:4],
                home_page=info.get("home_page") or None,
                project_urls=list((info.get("project_urls") or {}).items())[:4],
                yanked=bool(info.get("yanked")),
                query=query,
            ))
        return hits

    def trim(self, payload: Any, keep: int = 2) -> Any:
        projects = (payload or {}).get("projects") if isinstance(payload, dict) else payload
        keys = ("name", "version", "summary", "license", "license_expression",
                "classifiers", "package_url", "home_page", "project_urls",
                "requires_python", "yanked")
        trimmed_payload = dict(payload or {}) if isinstance(payload, dict) else {}
        trimmed_payload["projects"] = [
            {"info": {key: info.get(key) for key in keys}}
            for info in ((project or {}).get("info") or {}
                         for project in (projects or [])[:keep])
        ]
        return trimmed_payload
