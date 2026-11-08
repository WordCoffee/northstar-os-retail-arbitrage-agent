"""npm connector (A18).  Public registry, no token.

Search result objects do not carry a licence, so each hit reads
``/<name>/latest`` (small) and ``api.npmjs.org`` for last-month downloads.  If
either auxiliary call fails the hit still exists, with the field left ``None``
and the failure noted in the run health — an absent value is not a zero.
"""
from __future__ import annotations

import time
import urllib.parse
from typing import Any, Dict, List, Optional

from .. import http
from ..licence import normalise
from .base import Connector, _int, raw_hit


def _package_url(name: str) -> str:
    return "https://www.npmjs.com/package/" + urllib.parse.quote(name, safe="@/")


class NpmConnector(Connector):
    name = "npm"
    kind = "package"
    ecosystem = "npm"

    @staticmethod
    def _registry_path(name: str) -> str:
        return urllib.parse.quote(name, safe="@").replace("/", "%2F")

    def fetch(self, query: str, limit: int) -> Dict[str, Any]:
        size = max(1, min(int(limit), 20))
        url = ("https://registry.npmjs.org/-/v1/search?text="
               + http.quote(query) + f"&size={size}")
        search = http.request(url).json()
        objects = (search.get("objects") or [])[:size]
        latest: Dict[str, Any] = {}
        downloads: Dict[str, int] = {}
        failures: List[str] = []
        for obj in objects:
            name = ((obj.get("package") or {}).get("name") or "").strip()
            if not name:
                continue
            try:
                latest[name] = http.request(
                    f"https://registry.npmjs.org/{self._registry_path(name)}/latest").json()
            except http.ScoutTransport as exc:
                failures.append(f"latest:{name}:{exc}")
            try:
                point = http.request(
                    "https://api.npmjs.org/downloads/point/last-month/"
                    + urllib.parse.quote(name, safe="@/")).json()
                value = _int(point.get("downloads"))
                if value is not None:
                    downloads[name] = value
            except http.ScoutTransport as exc:
                failures.append(f"downloads:{name}:{exc}")
            time.sleep(0.2)
        return {
            "source": self.name,
            "query": query,
            "request_url": url,
            "status": 200,
            "search": search,
            "latest": latest,
            "downloads": downloads,
            "failures": failures,
        }

    def parse(self, payload: Any, query: str = "") -> List[Dict[str, Any]]:
        payload = payload or {}
        latest = payload.get("latest") or {}
        downloads = payload.get("downloads") or {}
        hits: List[Dict[str, Any]] = []
        for obj in (payload.get("search") or {}).get("objects") or []:
            package = obj.get("package") or {}
            name = str(package.get("name") or "").strip()
            if not name:
                continue
            meta = latest.get(name) or {}
            licence = normalise(meta.get("license"))
            description = str(meta.get("description") or package.get("description") or "").strip()
            hits.append(raw_hit(
                source=self.name,
                identity=name.lower(),
                url=_package_url(name),
                title=name,
                licence=licence,
                downloads=downloads.get(name),
                stars=None,
                description=description,
                version=meta.get("version") or package.get("version"),
                kind=self.kind,
                ecosystem=self.ecosystem,
                npm_score=round(float((obj.get("score") or {}).get("final") or 0.0), 4),
                publisher=(package.get("publisher") or {}).get("username"),
                published_at=package.get("date"),
                repository=((meta.get("repository") or {}).get("url")
                            if isinstance(meta.get("repository"), dict)
                            else meta.get("repository")),
                homepage=meta.get("homepage") or None,
                query=query,
            ))
        return hits

    def trim(self, payload: Any, keep: int = 3) -> Any:
        payload = payload or {}
        objects = ((payload.get("search") or {}).get("objects") or [])[:keep]
        keep_keys = ("name", "version", "description", "date", "publisher", "links")
        names = [((obj.get("package") or {}).get("name")) for obj in objects]
        latest = {name: {key: (payload.get("latest") or {}).get(name, {}).get(key)
                         for key in ("name", "version", "license", "description",
                                     "repository", "homepage")}
                  for name in names if name}
        return {
            "source": payload.get("source") or self.name,
            "query": payload.get("query"),
            "request_url": payload.get("request_url"),
            "status": payload.get("status"),
            "search": {"objects": [
                {"package": {key: (obj.get("package") or {}).get(key) for key in keep_keys},
                 "score": obj.get("score")}
                for obj in objects
            ]},
            "latest": latest,
            "downloads": {name: (payload.get("downloads") or {}).get(name) for name in names},
        }
