"""Fetch drivers for the gateway (Phase 3).

``DockerLightpandaDriver`` runs the PINNED Lightpanda 1.0.0 container
(multi-platform digest pinned in docker-compose.lightpanda.yml) — each fetch is
a fresh ``lightpanda fetch`` process inside the container: a new browser
context with no shared cookies and no persistent state. ``--obey-robots`` is
always passed.

``FakeDriver`` is the deterministic test double (no network).
"""
from __future__ import annotations

import subprocess
import time
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional


@dataclass(frozen=True)
class FetchResult:
    url: str
    ok: bool
    markdown: str = ""
    exit_code: int = 0
    stderr_tail: str = ""
    elapsed_ms: int = 0


class DockerLightpandaDriver:
    """Executes fetches via ``docker exec`` into the pinned container."""

    def __init__(
        self,
        *,
        container: str = "northstar-lightpanda",
        binary: str = "/bin/lightpanda",
        timeout_seconds: int = 30,
        obey_robots: bool = True,
        runner: Optional[Callable[..., "subprocess.CompletedProcess"]] = None,
    ) -> None:
        self.container = container
        self.binary = binary
        self.timeout_seconds = timeout_seconds
        self.obey_robots = obey_robots
        self._runner = runner or subprocess.run

    def fetch(self, url: str) -> FetchResult:
        cmd = [
            "docker",
            "exec",
            self.container,
            self.binary,
            "fetch",
            "--dump",
            "markdown",
        ]
        if self.obey_robots:
            cmd.append("--obey-robots")
        cmd.append(url)
        started = time.monotonic()
        try:
            proc = self._runner(
                cmd,
                capture_output=True,
                encoding="utf-8",
                errors="replace",
                timeout=self.timeout_seconds,
            )
        except Exception as exc:  # timeout, docker missing, container down…
            return FetchResult(
                url=url,
                ok=False,
                exit_code=-1,
                stderr_tail=f"{type(exc).__name__}: {str(exc)[:200]}",
                elapsed_ms=int((time.monotonic() - started) * 1000),
            )
        elapsed = int((time.monotonic() - started) * 1000)
        ok = proc.returncode == 0 and bool((proc.stdout or "").strip())
        return FetchResult(
            url=url,
            ok=ok,
            markdown=proc.stdout or "",
            exit_code=proc.returncode,
            stderr_tail=(proc.stderr or "")[-400:],
            elapsed_ms=elapsed,
        )


@dataclass
class FakeDriver:
    """Deterministic driver for tests: canned responses, call log, no network."""

    responses: Dict[str, str] = field(default_factory=dict)
    fail_urls: List[str] = field(default_factory=list)
    calls: List[str] = field(default_factory=list)

    def fetch(self, url: str) -> FetchResult:
        self.calls.append(url)
        if url in self.fail_urls:
            return FetchResult(url=url, ok=False, exit_code=1, stderr_tail="boom")
        if url not in self.responses:
            return FetchResult(url=url, ok=False, exit_code=1, stderr_tail="no canned response")
        return FetchResult(url=url, ok=True, markdown=self.responses[url])
