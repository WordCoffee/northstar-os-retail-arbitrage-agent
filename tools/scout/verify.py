"""URL resolution check (D11 requirement 5).

Each finding's ``where`` URL is requested (HEAD, GET on 400/403/405) and the
status is recorded.  When the public web host refuses a non-browser client —
github.com answers 504 to this network, www.npmjs.com answers 403 — the
identity is then confirmed at the source's authoritative machine endpoint
(GitHub API, npm registry, PyPI JSON, Hugging Face API, arXiv API) and that
status is recorded too.  A finding is only ``url_ok`` when one of the two
checks is a 2xx.

Host refusals are memoised: proving github.com refuses this client once is
enough, and re-proving it for 30 URLs would only slow the run down.  The API
check is still done per finding, so every URL is individually verified.
"""
from __future__ import annotations

import urllib.parse
from typing import Any, Dict, Optional

from . import http
from .http import Refused, ScoutTransport

#: Statuses that mean "this host will not answer this client", not "dead link".
_HOST_BLOCKED = (401, 403, 405, 429, 500, 502, 503, 504)


def host_of(url: str) -> str:
    try:
        return (urllib.parse.urlsplit(url).hostname or "").lower()
    except ValueError:
        return ""


def _direct(url: str, *, timeout: float, prefer_get: bool = False) -> Dict[str, Any]:
    """One URL check.  Returns status/method/ok; never raises."""
    method = "GET" if prefer_get else "HEAD"
    try:
        response = http.request(url, method=method, timeout=timeout,
                                allow_status=(400, 403, 405))
        if not prefer_get and response.status >= 400:
            response = http.request(url, method="GET", timeout=timeout)
            method = "GET"
    except Refused as exc:
        return {"ok": False, "status": None, "method": None,
                "error": f"refused: {exc}"}
    except ScoutTransport as exc:
        return {"ok": False, "status": exc.status, "method": method, "error": str(exc)}
    return {"ok": 200 <= response.status < 400, "status": response.status,
            "method": method}


def _fallback_url(finding: Dict[str, Any]) -> Optional[str]:
    source = str(finding.get("source") or "")
    url = str(finding.get("url") or "")
    if source == "github" and finding.get("identity"):
        return "https://api.github.com/repos/" + str(finding["identity"]).strip("/")
    if source == "npm":
        name = str(finding.get("title") or finding.get("identity") or "").strip()
        if not name:
            return None
        quoted = urllib.parse.quote(name, safe="@").replace("/", "%2F")
        return f"https://registry.npmjs.org/{quoted}/latest"
    if source == "pypi":
        name = str(finding.get("title") or "").strip()
        return f"https://pypi.org/pypi/{urllib.parse.quote(name)}/json" if name else None
    if source == "huggingface":
        path = urllib.parse.urlsplit(url).path.strip("/")
        return f"https://huggingface.co/api/models/{path}" if path else None
    if source == "arxiv":
        identity = str(finding.get("identity") or "").strip()
        return f"https://export.arxiv.org/api/query?id_list={identity}" if identity else None
    return None


def verify_url(url: str, *, timeout: float = 20.0) -> Dict[str, Any]:
    """Direct check only.  Kept for callers that have a URL and nothing else."""
    if not url:
        return {"url": url, "ok": False, "status": None, "method": None, "error": "empty_url"}
    result = _direct(url, timeout=timeout)
    return {"url": url, "ok": result["ok"], "status": result.get("status"),
            "method": result.get("method"), **({"error": result["error"]}
                                               if result.get("error") else {})}


def verify_finding(finding: Dict[str, Any], *,
                   memo: Optional[Dict[str, Dict[str, Any]]] = None,
                   timeout: float = 20.0) -> Dict[str, Any]:
    """Verify one finding: direct URL first, authoritative endpoint second."""
    memo = {} if memo is None else memo
    url = str(finding.get("url") or "")
    source = str(finding.get("source") or "")
    if not url:
        return {"url": url, "ok": False, "status": None, "method": None,
                "via": None, "error": "empty_url"}
    host = host_of(url)
    cached = memo.get(host)
    direct = cached or _direct(url, timeout=timeout)
    if cached is None and not direct["ok"] and (
            direct.get("status") in _HOST_BLOCKED or direct.get("status") is None):
        memo[host] = direct  # this host will not answer us; do not re-probe it
    result: Dict[str, Any] = {
        "url": url,
        "source": source,
        "ok": bool(direct["ok"]),
        "status": direct.get("status"),
        "method": direct.get("method"),
        "direct_ok": bool(direct["ok"]),
        "direct_error": direct.get("error"),
        "via": "direct" if direct["ok"] else None,
    }
    if direct["ok"]:
        result["via_url"] = url
        result["via_status"] = direct.get("status")
        return result
    fallback = _fallback_url(finding)
    if fallback:
        second = _direct(fallback, timeout=timeout, prefer_get=True)
        result["via_url"] = fallback
        result["via_status"] = second.get("status")
        result["via"] = "api" if second["ok"] else None
        result["fallback_ok"] = bool(second["ok"])
        result["ok"] = bool(second["ok"])
        if second.get("error"):
            result["fallback_error"] = second["error"]
    return result
