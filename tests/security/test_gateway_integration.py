"""Integration: gateway → PINNED Lightpanda 1.0.0 container → LOCAL fixture pages.

Local-only: fixtures are served from a loopback HTTP server on this host and
fetched through the container's host bridge. Skipped cleanly when Docker or the
pinned container is unavailable.

Policy note: host.docker.internal's real address is a Docker-NAT private IP, so
the kernel's resolver is STUBBED with a public test IP — SSRF policy correctness
is unit-tested elsewhere; this test exercises the driver + gateway path.
"""
from __future__ import annotations

import functools
import http.server
import subprocess
import threading
from pathlib import Path

import pytest

from northstar.gateway import DockerLightpandaDriver, LightpandaGateway
from northstar.policy import RobotsGate
from policy_helpers import PUBLIC_IP, make_kernel, make_resolver

FIXTURES = Path(__file__).resolve().parents[1] / "lightpanda_fixtures"


def _container_ready() -> bool:
    try:
        out = subprocess.run(
            ["docker", "inspect", "northstar-lightpanda"],
            capture_output=True,
            text=True,
            timeout=15,
        )
        return out.returncode == 0
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not _container_ready(), reason="pinned Lightpanda container not available"
)


class _LocalServer:
    def __init__(self, directory: Path) -> None:
        handler = functools.partial(
            http.server.SimpleHTTPRequestHandler, directory=str(directory)
        )
        self.httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
        self.port = self.httpd.server_address[1]
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *exc):
        self.httpd.shutdown()
        self.httpd.server_close()


def _gateway():
    robots = RobotsGate({"host.docker.internal": "User-agent: *\nAllow: /\n"})
    bundle = make_kernel(
        allowlist=("host.docker.internal",),
        resolve=make_resolver(PUBLIC_IP),
        robots=robots,
    )
    gateway = LightpandaGateway(kernel=bundle.kernel, driver=DockerLightpandaDriver())
    bundle.grants.issue("t1", ["fetch:host.docker.internal"])
    return gateway, bundle


def test_fetch_local_smoke_page_through_pinned_container():
    with _LocalServer(FIXTURES) as server:
        url = f"http://host.docker.internal:{server.port}/local_smoke_page.html"
        gateway, bundle = _gateway()
        result = gateway.markdown_dump(task_id="t1", url=url)
        assert result.ok, f"fetch failed: {result.reason} {result.detail}"
        assert "Local smoke page" in result.envelope
        assert "SMOKE" in result.envelope
        assert result.snapshot is not None
        assert bundle.audit.verify()


def test_injection_fixture_is_enveloped_data_only_end_to_end():
    with _LocalServer(FIXTURES) as server:
        url = f"http://host.docker.internal:{server.port}/prompt_injection_page.html"
        gateway, bundle = _gateway()
        result = gateway.markdown_dump(task_id="t1", url=url)
        assert result.ok, f"fetch failed: {result.reason} {result.detail}"
        assert result.envelope.startswith("----- BEGIN UNTRUSTED WEB CONTENT")
        assert "IGNORE ALL PREVIOUS INSTRUCTIONS" in result.envelope
        assert "amazon" in result.envelope.lower()  # present as INERT DATA
        assert bundle.audit.verify()
