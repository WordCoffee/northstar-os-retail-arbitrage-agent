"""Hugging Face connector (A18).  Public model search, no token.

Licence comes from the ``license:<id>`` model tag.  A card that only *says*
"MIT" in prose is not evidence; an untagged card is ``unknown``.
"""
from __future__ import annotations

from typing import Any, Dict, List

from .. import http
from ..licence import normalise
from .base import Connector, _int, raw_hit


class HuggingFaceConnector(Connector):
    name = "huggingface"
    kind = "model"
    ecosystem = None

    def fetch(self, query: str, limit: int) -> Dict[str, Any]:
        url = ("https://huggingface.co/api/models?search=" + http.quote(query)
               + f"&sort=downloads&direction=-1&limit={max(1, min(int(limit), 50))}")
        response = http.request(url)
        return {
            "source": self.name,
            "query": query,
            "request_url": url,
            "status": response.status,
            "items": response.json(),
        }

    def parse(self, payload: Any, query: str = "") -> List[Dict[str, Any]]:
        items = payload.get("items") if isinstance(payload, dict) else payload
        hits: List[Dict[str, Any]] = []
        for item in items or []:
            model_id = str(item.get("id") or item.get("modelId") or "").strip()
            if not model_id:
                continue
            tags = [str(tag) for tag in (item.get("tags") or [])]
            licences = [tag.split(":", 1)[1] for tag in tags
                        if tag.lower().startswith("license:")]
            hits.append(raw_hit(
                source=self.name,
                identity=model_id.lower(),
                url=f"https://huggingface.co/{model_id}",
                title=model_id,
                licence=normalise(licences[0] if licences else "unknown"),
                downloads=_int(item.get("downloads")),
                stars=None,
                description=str(item.get("pipeline_tag") or "").replace("-", " "),
                kind=self.kind,
                ecosystem=None,
                likes=_int(item.get("likes")),
                pipeline_tag=item.get("pipeline_tag"),
                tags=tags[:10],
                created_at=item.get("createdAt"),
                updated_at=item.get("lastModified"),
                query=query,
            ))
        return hits

    def trim(self, payload: Any, keep: int = 3) -> Any:
        if isinstance(payload, dict):
            trimmed = dict(payload)
            keys = ("id", "modelId", "downloads", "likes", "tags", "pipeline_tag",
                    "createdAt", "lastModified", "library_name")
            trimmed["items"] = [
                {key: item.get(key) for key in keys}
                for item in (payload.get("items") or [])[:keep]
            ]
            return trimmed
        return payload
