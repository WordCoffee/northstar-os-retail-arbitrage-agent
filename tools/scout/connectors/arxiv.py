"""arXiv connector (A18/A20).  Public Atom API, no token.

arXiv does not publish a per-paper licence in the API, so every hit is
``unknown`` and can never be adopted — a paper is research input for the gap
list, not a component.  Spacing is self-imposed at 3 s, not a provider quota.
"""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from typing import Any, Dict, List

from .. import http
from .base import Connector, raw_hit

ATOM = "{http://www.w3.org/2005/Atom}"
ARXIV = "{http://arxiv.org/schemas/atom}"
_SPACE = re.compile(r"\s+")


def _clean(text: str) -> str:
    return _SPACE.sub(" ", (text or "")).strip()


class ArxivConnector(Connector):
    name = "arxiv"
    kind = "paper"
    ecosystem = None

    def fetch(self, query: str, limit: int) -> Dict[str, Any]:
        url = ("https://export.arxiv.org/api/query?search_query=all:"
               + http.quote(query)
               + f"&start=0&max_results={max(1, min(int(limit), 20))}&sortBy=relevance")
        response = http.request(url, timeout=30.0)
        return {
            "source": self.name,
            "query": query,
            "request_url": url,
            "status": response.status,
            "xml": response.text(),
        }

    def parse(self, payload: Any, query: str = "") -> List[Dict[str, Any]]:
        text = payload.get("xml") if isinstance(payload, dict) else payload
        if not text:
            return []
        try:
            root = ET.fromstring(text)
        except ET.ParseError as exc:
            raise http.ScoutTransport(f"arxiv_bad_xml: {exc}") from exc
        hits: List[Dict[str, Any]] = []
        for entry in root.findall(f"{ATOM}entry"):
            raw_id = _clean(entry.findtext(f"{ATOM}id") or "")
            title = _clean(entry.findtext(f"{ATOM}title") or "")
            if not raw_id or not title:
                continue
            match = re.search(r"abs/([^/]+?)(v\d+)?$", raw_id)
            identity = match.group(1) if match else raw_id
            version = match.group(2) if match and match.group(2) else None
            authors = [_clean(author.findtext(f"{ATOM}name") or "")
                       for author in entry.findall(f"{ATOM}author")]
            primary = entry.find(f"{ARXIV}primary_category")
            hits.append(raw_hit(
                source=self.name,
                identity=identity.lower(),
                url=f"https://arxiv.org/abs/{identity}{version or ''}",
                title=title,
                licence="unknown",  # not published by the API
                stars=None,
                downloads=None,
                description=_clean(entry.findtext(f"{ATOM}summary") or "")[:400],
                version=version,
                kind=self.kind,
                ecosystem=None,
                authors=authors[:6],
                published_at=_clean(entry.findtext(f"{ATOM}published") or "") or None,
                updated_at=_clean(entry.findtext(f"{ATOM}updated") or "") or None,
                primary_category=(primary.get("term") if primary is not None else None),
                query=query,
            ))
        return hits

    def trim(self, payload: Any, keep: int = 3) -> Any:
        text = payload.get("xml") if isinstance(payload, dict) else payload
        if not text:
            return payload
        parts = str(text).split("<entry>")
        head, entries = parts[0], parts[1:keep + 1]
        trimmed = head + "".join("<entry>" + entry for entry in entries)
        if entries:
            trimmed = trimmed[:trimmed.rfind("</entry>") + len("</entry>")] + "</feed>"
        result = dict(payload) if isinstance(payload, dict) else {}
        result["xml"] = trimmed
        return result
