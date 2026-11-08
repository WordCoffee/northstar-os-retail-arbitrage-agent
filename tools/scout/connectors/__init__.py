"""Connector registry (D11 / A18).  One place that knows which sources exist."""
from __future__ import annotations

from typing import Dict, List

from .arxiv import ArxivConnector
from .base import Connector
from .github import GithubConnector
from .huggingface import HuggingFaceConnector
from .npm import NpmConnector
from .pypi import PyPiConnector

_REGISTRY: Dict[str, Connector] = {
    connector.name: connector
    for connector in (
        GithubConnector(),
        HuggingFaceConnector(),
        PyPiConnector(),
        NpmConnector(),
        ArxivConnector(),
    )
}


def get(name: str) -> Connector:
    try:
        return _REGISTRY[name]
    except KeyError as exc:
        raise KeyError(f"unknown_source: {name!r} is not one of "
                       f"{', '.join(sorted(_REGISTRY))}") from exc


def names() -> List[str]:
    return sorted(_REGISTRY)


def all_connectors() -> Dict[str, Connector]:
    return dict(_REGISTRY)


__all__ = ["Connector", "get", "names", "all_connectors"]
