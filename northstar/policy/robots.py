"""robots.txt enforcement (Phase 2).

Deterministic and offline: robots text is SUPPLIED (by the gateway's own
controlled fetch pipeline); this module never fetches anything. Fail-closed:
when robots text is unknown and ``require_robots`` is True (default), the
request is denied.
"""
from __future__ import annotations

import urllib.parse
import urllib.robotparser
from typing import Callable, Mapping, Optional, Union

from .errors import PolicyDenied

DEFAULT_AGENT = "NorthstarBot"

RobotsSource = Union[Mapping[str, str], Callable[[str], Optional[str]], None]


class RobotsGate:
    def __init__(
        self,
        robots_text: RobotsSource = None,
        *,
        user_agent: str = DEFAULT_AGENT,
        require_robots: bool = True,
    ) -> None:
        self._source = robots_text if robots_text is not None else {}
        self.user_agent = user_agent
        self.require_robots = require_robots
        self._cache: dict[str, Optional[urllib.robotparser.RobotFileParser]] = {}

    def _parser(self, host: str):
        if host in self._cache:
            return self._cache[host]
        if callable(self._source):
            text = self._source(host)
        else:
            text = self._source.get(host)
        parser = None
        if isinstance(text, str) and text.strip():
            parser = urllib.robotparser.RobotFileParser()
            parser.parse(text.splitlines())
        self._cache[host] = parser
        return parser

    def check(self, url: str) -> None:
        host = (urllib.parse.urlsplit(url).hostname or "").lower()
        parser = self._parser(host)
        if parser is None:
            if self.require_robots:
                raise PolicyDenied("robots_unknown", host)
            return
        if not parser.can_fetch(self.user_agent, url):
            raise PolicyDenied("robots_denied", url)
