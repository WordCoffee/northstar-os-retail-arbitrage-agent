"""robots.txt enforcement (Phase 2).

Deterministic and offline: robots text is SUPPLIED (by the gateway's own
controlled fetch pipeline); this module never fetches anything. Fail-closed:
when robots text is unknown and ``require_robots`` is True (default), the
request is denied.

Parsing (Phase-3 adoption): ``protego`` - the Google-spec-compatible parser -
when installed; falls back to the stdlib ``urllib.robotparser`` otherwise.
"""
from __future__ import annotations

import urllib.parse
import urllib.robotparser
from typing import Callable, Mapping, Optional, Union

from .errors import PolicyDenied

try:  # preferred parser: Google robots.txt spec (protego, BSD-3-Clause)
    from protego import Protego as _Protego
except Exception:  # pragma: no cover - optional dependency
    _Protego = None

DEFAULT_AGENT = "NorthstarBot"

ROBOTS_PARSER_PREFERRED = "protego"
ROBOTS_PARSER_FALLBACK = "urllib"

RobotsSource = Union[Mapping[str, str], Callable[[str], Optional[str]], None]

_ParsedRobots = Optional[tuple[str, object]]


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
        self._cache: dict[str, _ParsedRobots] = {}

    def _parser(self, host: str) -> _ParsedRobots:
        if host in self._cache:
            return self._cache[host]
        if callable(self._source):
            text = self._source(host)
        else:
            text = self._source.get(host)
        parser: _ParsedRobots = None
        if isinstance(text, str) and text.strip():
            if _Protego is not None:
                try:
                    parser = (ROBOTS_PARSER_PREFERRED, _Protego.parse(text))
                except Exception:
                    parser = None
            if parser is None:
                fallback = urllib.robotparser.RobotFileParser()
                fallback.parse(text.splitlines())
                parser = (ROBOTS_PARSER_FALLBACK, fallback)
        self._cache[host] = parser
        return parser

    def parser_kind(self, host: str) -> Optional[str]:
        """Which parser was used for ``host`` (None when robots is unknown)."""
        parser = self._parser(host)
        return parser[0] if parser is not None else None

    def check(self, url: str) -> None:
        host = (urllib.parse.urlsplit(url).hostname or "").lower()
        parser = self._parser(host)
        if parser is None:
            if self.require_robots:
                raise PolicyDenied("robots_unknown", host)
            return
        kind, obj = parser
        if kind == ROBOTS_PARSER_PREFERRED:
            allowed = obj.can_fetch(url, self.user_agent)
        else:
            allowed = obj.can_fetch(self.user_agent, url)
        if not allowed:
            raise PolicyDenied("robots_denied", url)
