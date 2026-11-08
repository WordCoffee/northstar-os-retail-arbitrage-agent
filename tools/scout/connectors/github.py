"""GitHub connector (A18).  Public repository search, no token.

Quota is real: 10 searches/minute unauthenticated.  ``fetch`` returns the
``X-RateLimit-Remaining`` value with the payload so the run records measured
quota instead of asserting it.
"""
from __future__ import annotations

from typing import Any, Dict, List

from .. import http
from ..licence import normalise
from .base import Connector, _int, raw_hit


class GithubConnector(Connector):
    name = "github"
    kind = "repository"
    ecosystem = None

    def fetch(self, query: str, limit: int) -> Dict[str, Any]:
        url = ("https://api.github.com/search/repositories?q="
               + http.quote(query)
               + f"&sort=stars&order=desc&per_page={max(1, min(int(limit), 30))}")
        response = http.request(url, headers={"Accept": "application/vnd.github+json"})
        data = response.json()
        return {
            "source": self.name,
            "query": query,
            "request_url": url,
            "status": response.status,
            "quota_remaining": _int(response.header("x-ratelimit-remaining")),
            "quota_limit": _int(response.header("x-ratelimit-limit")),
            "total_count": _int(data.get("total_count")),
            "items": data.get("items") or [],
        }

    def parse(self, payload: Any, query: str = "") -> List[Dict[str, Any]]:
        hits: List[Dict[str, Any]] = []
        for item in (payload or {}).get("items") or []:
            full_name = str(item.get("full_name") or "").strip()
            html_url = str(item.get("html_url") or "").strip()
            if not full_name or not html_url:
                continue
            spdx = ((item.get("license") or {}).get("spdx_id") or "unknown")
            hits.append(raw_hit(
                source=self.name,
                identity=full_name.lower(),
                url=html_url,
                title=full_name,
                licence=normalise(spdx),
                stars=_int(item.get("stargazers_count")),
                downloads=None,
                description=(item.get("description") or "").strip(),
                version=None,
                kind=self.kind,
                ecosystem=None,
                forks=_int(item.get("forks_count")),
                language=item.get("language"),
                topics=list(item.get("topics") or [])[:8],
                updated_at=item.get("pushed_at") or item.get("updated_at"),
                archived=bool(item.get("archived")),
                homepage=item.get("homepage") or None,
                query=query,
            ))
        return hits

    def trim(self, payload: Dict[str, Any], keep: int = 3) -> Dict[str, Any]:
        trimmed = dict(payload or {})
        keep_keys = ("full_name", "html_url", "description", "stargazers_count",
                     "forks_count", "license", "topics", "language", "pushed_at",
                     "archived", "homepage")
        trimmed["items"] = [
            {key: item.get(key) for key in keep_keys}
            for item in (payload or {}).get("items", [])[:keep]
        ]
        return trimmed
