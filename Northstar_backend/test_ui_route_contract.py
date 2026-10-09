"""UI-to-API route contract (P0-02, closed 2026-10-09).

The hosted-reasoning UI called `/api/v1/foundation/reasoning/*` while the
server serves `/api/v1/reasoning/*`, so the whole hosted lane 404'd from the
browser and only from the browser. This test reads the real UI source, pulls
out every API path it can call, and asserts each one resolves against the
running app's route table — so a spelling drift fails in CI instead of in a
user's network tab.

Path parameters written as `${...}` or `{...}` are filled with deterministic
sample values.
"""

from __future__ import annotations

import os
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import main  # noqa: E402

_REPO_ROOT = Path(__file__).resolve().parent.parent
_UI_SRC = _REPO_ROOT / "northstar-os-ui" / "src"

# A path parameter placeholder, either a template literal `${expr}` or a
# documented placeholder `{name}`.
_PLACEHOLDER = re.compile(r"\$\{[^}]*\}|\{[A-Za-z_][A-Za-z0-9_]*\}")

_SAMPLE_VALUES = {
    "id": "SAMPLE-ID",
    "code": "invite_sample",
    "orgId": "SAMPLE-ORG",
    "org_id": "SAMPLE-ORG",
    "run_id": "atrun_sample",
    "limit": "5",
    "account_id": "default",
    "intent": "pricing",
    "file_name": "sample.csv",
    "name": "sample",
}

_DEFAULT_SAMPLE = "sample"

# String literals that mention an API path inside prose ("route=..." labels,
# explanatory copy, comments) rather than a call site. Those are documentation,
# not requests, and are excluded — but ONLY when they carry a placeholder,
# which a real endpoint path never does.
_PROSE_MARKERS = ("route=", "<span", "docs", "TODO", "NOTE")


def _fill(path_template: str) -> str:
    def _sub(match: "re.Match[str]") -> str:
        raw = match.group(0)
        if raw.startswith("${"):
            inner = raw[2:-1].strip()
            key = inner.split(".")[0].split("[")[0].strip("'\"` ")
            return _SAMPLE_VALUES.get(key, _DEFAULT_SAMPLE)
        key = raw[1:-1]
        return _SAMPLE_VALUES.get(key, _DEFAULT_SAMPLE)

    path = _PLACEHOLDER.sub(_sub, path_template)
    # A query string is not part of the route contract.
    return path.split("?", 1)[0]


# Literals that are prefixes or documentation, never a real endpoint.
_NON_ENDPOINTS = {
    "/api/",
    "/api/...",
    "/api/v1/foundation",   # the client's BASE constant
}


def _iter_ui_sources():
    if not _UI_SRC.is_dir():
        return []
    return sorted(p for p in _UI_SRC.rglob("*") if p.suffix in (".js", ".jsx"))


def _extract_api_paths(text: str):
    """Every distinct `/api/...` path literal in one source file."""
    found = set()
    # Quoted literals, including backtick template literals.
    for match in re.finditer(r"""(['"`])(/api/[^'"`]*)\1""", text):
        literal = match.group(2)
        if any(marker in literal for marker in _PROSE_MARKERS):
            continue
        candidate = _fill(literal)
        if candidate in _NON_ENDPOINTS:
            continue
        found.add(candidate)
    # Bare template-literal bodies: `.../api/x/${id}`
    for match in re.finditer(r"`(/api/[^`]*)`", text):
        literal = match.group(1)
        if any(marker in literal for marker in _PROSE_MARKERS):
            continue
        candidate = _fill(literal)
        if candidate in _NON_ENDPOINTS:
            continue
        found.add(candidate)
    return found


def _template_pattern(template: str) -> "re.Pattern[str]":
    """`/api/x/{id}` -> a regex that matches one path segment per parameter."""
    parts = []
    for segment in template.split("/"):
        if segment.startswith("{") and segment.endswith("}"):
            parts.append(r"[^/]+")
        else:
            parts.append(re.escape(segment))
    return re.compile("^" + "/".join(parts) + "$")


def _app_route_templates():
    """{path_template: set(methods)} for every route registered on the app.

    FastAPI 0.140 keeps an included router as a lazy ``_IncludedRouter``
    wrapper rather than copying routes onto the app, so the wrapper is expanded
    into its effective routes here.
    """
    routes = {}

    def _add(path, methods):
        if not path or not path.startswith("/api"):
            return
        routes.setdefault(path, set()).update(methods)

    def _walk(items):
        for route in items:
            path = getattr(route, "path", None)
            methods = {m.upper() for m in (getattr(route, "methods", None) or ())}
            if path and methods:
                _add(path, methods)
            # Lazy included routers (FastAPI >= 0.140).
            effective = getattr(route, "effective_candidates", None)
            if callable(effective):
                try:
                    for candidate in effective():
                        candidate_path = getattr(candidate, "path", None)
                        candidate_methods = {
                            m.upper() for m in (getattr(candidate, "methods", None) or ())
                        }
                        if candidate_path and candidate_methods:
                            _add(candidate_path, candidate_methods)
                except Exception:  # pragma: no cover - defensive
                    pass
            # Classic starlette Mount of another app.
            inner = getattr(route, "app", None)
            inner_routes = getattr(inner, "routes", None)
            if inner_routes:
                mount_path = path or ""
                for sub in inner_routes:
                    sub_path = getattr(sub, "path", None)
                    sub_methods = {
                        m.upper() for m in (getattr(sub, "methods", None) or ())
                    }
                    if sub_path and sub_methods:
                        _add(mount_path.rstrip("/") + sub_path, sub_methods)

    _walk(main.app.routes)
    return routes


class UiRouteContractTests(unittest.TestCase):
    """Every API path the UI can call resolves against the app's route table."""

    @classmethod
    def setUpClass(cls):
        cls.routes = _app_route_templates()
        cls.patterns = {_template_pattern(t) for t in cls.routes}
        cls.missing = []
        cls.checked = 0
        sources = _iter_ui_sources()
        cls.sources_checked = len(sources)
        for source in sources:
            try:
                text = source.read_text(encoding="utf-8", errors="replace")
            except OSError:  # pragma: no cover - defensive
                continue
            for path in _extract_api_paths(text):
                cls.checked += 1
                if path in cls.routes:
                    continue
                if any(pattern.match(path) for pattern in cls.patterns):
                    continue
                cls.missing.append((source.name, path))

    def test_ui_sources_were_found(self):
        """Guard against the test silently passing because it read nothing."""
        self.assertGreater(self.sources_checked, 0, "no UI sources were read")

    def test_at_least_the_known_surfaces_are_checked(self):
        self.assertGreaterEqual(self.checked, 25, self.checked)

    def test_every_ui_api_path_resolves(self):
        self.assertEqual(
            self.missing, [],
            "UI calls API paths the server does not serve: %s" % (self.missing,),
        )

    def test_reasoning_routes_resolve_under_both_spellings(self):
        """P0-02: the fix works for the canonical AND the legacy spelling."""
        for path in (
            "/api/v1/reasoning/models",
            "/api/v1/reasoning/run",
            "/api/v1/foundation/reasoning/models",
            "/api/v1/foundation/reasoning/run",
        ):
            self.assertIn(path, self.routes, path)

    def test_autothink_surface_is_present(self):
        for path in (
            "/api/autothink/models",
            "/api/autothink/run",
            "/api/autothink/history",
            "/api/autothink/cancel",
            "/api/autothink/jobs/{run_id}",
            "/api/autothink/usage",
        ):
            self.assertIn(path, self.routes, path)


class UiRouteLiveProbeTests(unittest.TestCase):
    """The routes the UI calls answer — never 404 (P0-02's exact symptom).

    Auth is not satisfied here, so 401/403/422 are all acceptable answers;
    only 404 (and 405 for a GET on a POST route) means the wiring is broken.
    """

    ROUTES = [
        ("get", "/api/v1/reasoning/models"),
        ("get", "/api/v1/foundation/reasoning/models"),
        ("get", "/api/v1/foundation/creative/readiness"),
        ("get", "/api/v1/status"),
        ("get", "/api/v1/foundation/health"),
        ("get", "/api/v1/foundation/me"),
        ("get", "/api/autothink/history"),
        ("get", "/api/autothink/models"),
        ("get", "/api/sourcescout"),
        ("get", "/api/monitoring/error-alerts"),
        ("get", "/api/golden-goose/health"),
    ]

    @classmethod
    def setUpClass(cls):
        import tempfile
        from fastapi.testclient import TestClient
        from unittest.mock import patch as _patch

        tmp = tempfile.mkdtemp(prefix="ui-route-probe-")
        env = {
            "SCANNER_LIVE_ALLOWED": "0",
            "NORTHSTAR_DISABLE_RATE_LIMIT": "1",
            "ENVIRONMENT": "development",
            "SCANNER_SEARCH_CACHE_PATH": os.path.join(tmp, "s.json"),
            "COSTCO_CATALOG_SOURCE": "OFF",
        }
        cls._env = _patch.dict(os.environ, env, clear=True)
        cls._env.start()
        cls.client = TestClient(main.app)

    @classmethod
    def tearDownClass(cls):
        cls._env.stop()

    def test_no_ui_route_404s(self):
        for method, path in self.ROUTES:
            with self.subTest(route=(method, path)):
                response = getattr(self.client, method)(path)
                self.assertNotEqual(response.status_code, 404, response.text[:200])
                self.assertNotEqual(response.status_code, 405, response.text[:200])


if __name__ == "__main__":
    unittest.main()
