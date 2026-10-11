"""NorthstarOS Lightpanda Connect gateway (Phase 3).

Agents NEVER touch Lightpanda or CDP directly — they get exactly three tools
from this package: ``fetch_page``, ``extract``, ``markdown_dump``. Every call
runs the fixed pipeline:

    policy check → isolated fetch (fresh context, no shared cookies)
    → sanitize → snapshot record → audit → untrusted-data envelope

The gateway is the only component that talks to the pinned Lightpanda
(AGPL-3.0, unmodified, separate process). Page content is DATA — it is never
placed into an instruction channel and never executed.
"""
from .driver import DockerLightpandaDriver, FakeDriver, FetchResult
from .gateway import GatewayResult, LightpandaGateway
from .sanitize import (
    SanitizedContent,
    cap_content,
    sanitize_markdown,
    strip_scripts_and_comments,
    wrap_untrusted,
)

__all__ = [
    "DockerLightpandaDriver",
    "FakeDriver",
    "FetchResult",
    "GatewayResult",
    "LightpandaGateway",
    "SanitizedContent",
    "cap_content",
    "sanitize_markdown",
    "strip_scripts_and_comments",
    "wrap_untrusted",
]
