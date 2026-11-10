"""One transport-level Amazon refusal, instead of seven per-site checks.

Measured 2026-11-06: the repo has seven Amazon checks and they cover a handful of
call sites. A read-only map found **44 caller-supplied URL sites with no host
check at all** - including an API-supplied `callback_url` reaching `urlopen`, and a
provider adapter that validates the URL's path but never its host.

The lesson is the same one a "jailbroken agent" video demonstrates from the other
direction: a rule that each call site has to remember is not a control. This module
installs the rule once, at the transport:

    from egress_guard import install
    install()          # once, at service start, before any request is made

After that every `urllib.request.urlopen` and `requests` call is checked against
the same hardcoded Amazon list before a socket is opened, and every refusal is
appended to ``logs/egress.jsonl`` with the caller's file:line.

Deliberate limits, stated so nobody over-trusts it:
  * it covers `urllib.request.urlopen` and the `requests` API/Session entry points;
    it does not cover `httpx`, raw sockets, or a provider SDK with its own client
  * it is an *in-process* guard; a subprocess that never imports it is not covered
  * it refuses Amazon, not "all bad hosts" - SSRF and allowlists are separate
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
AUDIT = ROOT / "logs" / "egress.jsonl"

#: Hardcoded, first, never overridable - the same order the policy files use.
AMAZON_SUFFIXES = (
    "amazon.com", "amazon.co.uk", "amazon.ca", "amazon.de", "amazon.fr", "amazon.it",
    "amazon.es", "amazon.nl", "amazon.se", "amazon.pl", "amazon.com.mx",
    "amazon.com.br", "amazon.com.au", "amazon.co.jp", "amazon.in", "amazon.ae",
    "amazon.sa", "amazon.sg", "amazon.com.tr", "amazon.eg", "amazon.ie",
    "amazon.be", "amazon-adsystem.com", "media-amazon.com", "images-amazon.com",
    "ssl-images-amazon.com", "amzn.to", "amzn.com", "amzn.eu", "a.co", "a2z.com",
    "primevideo.com", "audible.com", "wholefoodsmarket.com", "zappos.com",
    "twitch.tv", "imdb.com", "goodreads.com",
)

_installed: Dict[str, Any] = {}


class EgressRefused(RuntimeError):
    """A request the process will not make. Never a result."""


def host_of(url: Any) -> str:
    text = str(url)
    try:
        return (urlsplit(text).hostname or "").lower().rstrip(".")
    except ValueError:
        return ""


def is_amazon(url: Any) -> bool:
    host = host_of(url)
    if not host:
        return False
    for blocked in AMAZON_SUFFIXES:
        if host == blocked or host.endswith("." + blocked):
            return True
    # A label equal to a blocked first label (amazon, amzn, twitch, ...) is a
    # lookalike and gets the same refusal.
    labels = set(host.split("."))
    firsts = {b.split(".")[0] for b in AMAZON_SUFFIXES}
    return bool(labels & firsts)


def _caller() -> str:
    import inspect

    try:
        for frame in inspect.stack()[2:8]:
            file = str(frame.filename)
            if "egress_guard" in file:
                continue
            try:
                rel = str(Path(file).relative_to(ROOT)).replace("\\", "/")
            except ValueError:
                rel = file
            return f"{rel}:{frame.lineno}"
    except Exception:  # noqa: BLE001 - attribution is a bonus, not a gate
        pass
    return "unknown"


def _journal(url: Any, caller: str, decision: str) -> None:
    try:
        AUDIT.parent.mkdir(parents=True, exist_ok=True)
        with AUDIT.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps({"at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                                 "url": str(url)[:400], "host": host_of(url),
                                 "caller": caller, "decision": decision}) + "\n")
    except OSError:
        pass


def check(url: Any, *, caller: Optional[str] = None) -> Any:
    """Refuse Amazon before any socket is opened. Returns the url when allowed."""
    who = caller or _caller()
    if is_amazon(url):
        _journal(url, who, "amazon_refused")
        raise EgressRefused(f"amazon_refused: {host_of(url)} (from {who})")
    _journal(url, who, "allowed")
    return url


def _wrap(fn: Callable[..., Any], url_position: int) -> Callable[..., Any]:
    def guarded(*args: Any, **kwargs: Any) -> Any:
        url = None
        if len(args) > url_position:
            url = args[url_position]
        else:
            for name in ("url", "fullurl"):
                if name in kwargs:
                    url = kwargs[name]
                    break
        if url is not None:
            check(url)
        return fn(*args, **kwargs)
    guarded.__name__ = getattr(fn, "__name__", "guarded")
    guarded.__doc__ = getattr(fn, "__doc__", None)
    return guarded


def install() -> Dict[str, Any]:
    """Patch the two clients this repo uses. Idempotent."""
    if _installed:
        return {"installed": False, "already": True, **_installed}
    import urllib.request

    import requests

    originals = {
        "urllib": urllib.request.urlopen,
        "requests_api": requests.api.request,
        "requests_session": requests.sessions.Session.request,
    }
    urllib.request.urlopen = _wrap(originals["urllib"], 0)
    requests.api.request = _wrap(originals["requests_api"], 1)
    requests.sessions.Session.request = _wrap(originals["requests_session"], 1)
    _installed.update(originals)
    return {"installed": True, "clients": sorted(originals)}


def uninstall() -> Dict[str, Any]:
    if not _installed:
        return {"installed": False}
    import urllib.request

    import requests

    urllib.request.urlopen = _installed["urllib"]
    requests.api.request = _installed["requests_api"]
    requests.sessions.Session.request = _installed["requests_session"]
    _installed.clear()
    return {"installed": False}


def installed() -> bool:
    return bool(_installed)


def main(argv: Optional[List[str]] = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Refuse Amazon at the transport.")
    parser.add_argument("--check", default="", help="evaluate one URL and exit")
    parser.add_argument("--json", action="store_true")
    ns = parser.parse_args(argv)
    if ns.check:
        try:
            check(ns.check, caller="cli")
        except EgressRefused as exc:
            print(json.dumps({"allowed": False, "reason": str(exc)}))
            return 1
        print(json.dumps({"allowed": True}))
        return 0
    print(json.dumps({"installed": installed(), "audit": str(AUDIT)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
