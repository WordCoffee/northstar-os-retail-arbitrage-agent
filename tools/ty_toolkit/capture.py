"""Turn an observed HTTP capture into a typed client. It never crawls.

The capture is what the operator already has: a HAR export, a browser "copy as cURL", or a
JSON list of requests. This module reads it and emits a small, typed Python (`httpx`) or
TypeScript (`fetch`) client. Nothing here opens a socket.

    python -m tools.ty_toolkit.capture --capture capture.har --lang python --out client.py
"""
from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple
from urllib.parse import parse_qs, urlsplit

METHODS = ("GET", "POST", "PUT", "PATCH", "DELETE")
_LANG = ("python", "typescript")


@dataclass(frozen=True)
class Endpoint:
    method: str
    path: str
    base_url: str
    name: str
    query: Tuple[str, ...]
    body: Tuple[str, ...]


def _snake(text: str) -> str:
    text = re.sub(r"[^A-Za-z0-9]+", "_", text or "").strip("_")
    text = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", text).lower()
    return text or "endpoint"


def _requests(doc: Dict[str, Any]) -> List[Dict[str, Any]]:
    if isinstance(doc.get("log"), dict):  # HAR
        return [entry.get("request") or {} for entry in doc["log"].get("entries") or []]
    if isinstance(doc.get("requests"), list):
        return [row for row in doc["requests"] if isinstance(row, dict)]
    if isinstance(doc.get("request"), dict):
        return [doc["request"]]
    return []


def _body_keys(raw: Dict[str, Any]) -> Tuple[str, ...]:
    body = raw.get("json")
    if body is None:
        body = raw.get("body")
    if isinstance(body, dict):
        return tuple(sorted(body))
    if isinstance(body, str):
        try:
            parsed = json.loads(body)
        except ValueError:
            parsed = None
        if isinstance(parsed, dict):
            return tuple(sorted(parsed))
    post = ((raw.get("postData") or {}).get("text") if isinstance(raw.get("postData"), dict) else None)
    if post:
        try:
            parsed = json.loads(post)
        except ValueError:
            parsed = None
        if isinstance(parsed, dict):
            return tuple(sorted(parsed))
    return ()


def _endpoint(raw: Dict[str, Any], fallback_base: str = "") -> Endpoint | None:
    method = str(raw.get("method") or "GET").upper()
    if method not in METHODS:
        return None
    url = str(raw.get("url") or raw.get("path") or "")
    if not url:
        return None
    parts = urlsplit(url)
    base = f"{parts.scheme}://{parts.netloc}" if parts.scheme and parts.netloc else fallback_base
    path = parts.path or "/"
    query = tuple(sorted(parse_qs(parts.query)))
    if isinstance(raw.get("queryString"), list):
        query = tuple(sorted({str(item.get("name")) for item in raw["queryString"] if item.get("name")}))
    body = _body_keys(raw)
    segments = [seg for seg in path.split("/") if seg]
    stem = "_".join(segments[-2:]) if segments else "root"
    name = _snake(f"{method}_{stem}")
    return Endpoint(method=method, path=path, base_url=base, name=name,
                    query=query, body=body)


def parse(doc: Dict[str, Any], *, base_url: str = "") -> List[Endpoint]:
    """Every usable request in the capture, deduped by method+path, names made unique."""
    seen: set = set()
    out: List[Endpoint] = []
    names: Dict[str, int] = {}
    for raw in _requests(doc):
        endpoint = _endpoint(raw, base_url)
        if endpoint is None or (endpoint.method, endpoint.path) in seen:
            continue
        seen.add((endpoint.method, endpoint.path))
        count = names.get(endpoint.name, 0)
        names[endpoint.name] = count + 1
        if count:
            endpoint = replace(endpoint, name=f"{endpoint.name}_{count + 1}")
        out.append(endpoint)
    return out


def python_client(endpoints: Iterable[Endpoint], *, class_name: str = "ApiClient",
                  base_url: str = "") -> str:
    rows = list(endpoints)
    root = base_url or (rows[0].base_url if rows else "")
    lines = [
        '"""Typed client generated from an observed capture. No crawling."""',
        "from __future__ import annotations", "",
        "from typing import Any, Dict, Optional", "",
        "import httpx", "", "",
        f"class {class_name}:",
        f'    """{len(rows)} endpoint(s) observed at {root or "(unknown base)"}."""', "",
        "    def __init__(self, base_url: Optional[str] = None, token: Optional[str] = None) -> None:",
        f'        self.base_url = (base_url or {root!r}).rstrip("/")',
        '        self._headers = {"Authorization": f"Bearer {token}"} if token else {}',
        "        self._client = httpx.Client(base_url=self.base_url, headers=self._headers)",
        "",
        "    def close(self) -> None:",
        "        self._client.close()",
        "",
        "    def _request(self, method: str, path: str, **kwargs: Any) -> Any:",
        "        response = self._client.request(method, path, **kwargs)",
        "        response.raise_for_status()",
        "        return response.json() if response.content else None",
        "",
    ]
    for endpoint in rows:
        args = ["self"]
        if endpoint.query:
            args.append("params: Optional[Dict[str, Any]] = None")
        if endpoint.body:
            args.append("json: Optional[Dict[str, Any]] = None")
        signature = ", ".join(args)
        lines += [
            f"    def {endpoint.name}({signature}) -> Any:",
            f'        """{endpoint.method} {endpoint.path}"""',
            f'        return self._request({endpoint.method!r}, {endpoint.path!r}'
            + (", params=params" if endpoint.query else "")
            + (", json=json" if endpoint.body else "") + ")",
            "",
        ]
    return "\n".join(lines).rstrip() + "\n"


def typescript_client(endpoints: Iterable[Endpoint], *, class_name: str = "ApiClient",
                      base_url: str = "") -> str:
    rows = list(endpoints)
    root = base_url or (rows[0].base_url if rows else "")
    lines = [
        "// Typed client generated from an observed capture. No crawling.",
        f'export class {class_name} {{',
        "  private baseUrl: string",
        "  private token?: string",
        "",
        f"  constructor(baseUrl = {json.dumps(root)}, token?: string) {{",
        '    this.baseUrl = baseUrl.replace(/\\/$/, "")',
        "    this.token = token",
        "  }",
        "",
        "  private async request(path: string, init: RequestInit = {}): Promise<unknown> {",
        "    const response = await fetch(`${this.baseUrl}${path}`, {",
        "      ...init,",
        "      headers: {",
        "        'Content-Type': 'application/json',",
        "        ...(this.token ? { Authorization: `Bearer ${this.token}` } : {}),",
        "        ...(init.headers as Record<string, string> | undefined),",
        "      },",
        "    })",
        "    if (!response.ok) throw new Error(`HTTP ${response.status} ${path}`)",
        "    return response.status === 204 ? null : response.json()",
        "  }",
        "",
    ]
    for endpoint in rows:
        args = ["params?: Record<string, string>"]
        if endpoint.body:
            args.append("body?: Record<string, unknown>")
        lines += [
            f"  async {endpoint.name}({' ,'.join(args)}): Promise<unknown> {{",
            f"    const query = params ? `?${{new URLSearchParams(params)}}` : ''",
            (f"    return this.request(`{endpoint.path}${{query}}`, {{ method: '{endpoint.method}',"
             + (" body: JSON.stringify(body)" if endpoint.body else "") + " })")
            if endpoint.method != "GET" else
            f"    return this.request(`{endpoint.path}${{query}}`, {{ method: '{endpoint.method}' }})",
            "  }",
            "",
        ]
    lines += ["}", ""]
    return "\n".join(lines)


def generate(capture: Dict[str, Any], *, language: str = "python",
             name: str = "ApiClient", base_url: str = "") -> Dict[str, Any]:
    language = str(language or "python").lower()
    if language not in _LANG:
        return {"ok": False, "reason": f"language must be one of {list(_LANG)}"}
    endpoints = parse(capture, base_url=base_url)
    if not endpoints:
        return {"ok": False, "reason": "the capture carries no usable HTTP request"}
    safe_name = re.sub(r"[^A-Za-z0-9_]", "", str(name or "ApiClient")) or "ApiClient"
    code = (python_client(endpoints, class_name=safe_name, base_url=base_url)
            if language == "python" else
            typescript_client(endpoints, class_name=safe_name, base_url=base_url))
    return {"ok": True, "language": language, "name": safe_name,
            "endpoints": [{"method": e.method, "path": e.path, "name": e.name,
                           "query": list(e.query), "body": list(e.body)} for e in endpoints],
            "code": code}


def status() -> Dict[str, Any]:
    """Whether the upstream reverse-engineering CLI is present, and what runs without it."""
    import shutil

    executable = shutil.which("reverse-api-engineer") or shutil.which("reverse_api_engineer")
    return {"ok": True, "upstream": "reverse-api-engineer",
            "upstream_installed": bool(executable),
            "upstream_license": "MIT (github.com/kalil0321/reverse-api-engineer)",
            "fallback": "builtin capture->typed client (no crawl, no credential storage)",
            "note": "The upstream is optional; the wrapper works from a capture the operator supplies."}


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate a typed client from an HTTP capture")
    parser.add_argument("--capture", default="")
    parser.add_argument("--lang", default="python", choices=list(_LANG))
    parser.add_argument("--name", default="ApiClient")
    parser.add_argument("--out", default="")
    parser.add_argument("--status", action="store_true")
    ns = parser.parse_args(argv)
    if ns.status or not ns.capture:
        print(json.dumps(status(), indent=2))
        return 0
    doc = json.loads(Path(ns.capture).read_text(encoding="utf-8"))
    result = generate(doc, language=ns.lang, name=ns.name)
    if not result["ok"]:
        print(result["reason"])
        return 2
    if ns.out:
        Path(ns.out).write_text(result["code"], encoding="utf-8")
        print(f"wrote {ns.out} ({len(result['endpoints'])} endpoint(s))")
    else:
        print(result["code"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
