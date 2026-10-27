"""Chrome Connect runner package (P6-T2).

Python package for browser job execution via Chrome Connect controller.
Uses Chrome Connect's MCP tools (not Playwright directly) for all browser actions.

Provenance: In-house implementation. No external code.
License: In-repo.
"""

__version__ = "0.1.0"
__all__ = [
    "job_protocol",
    "runner",
    "adapter_base",
    "adapters",
    "evidence",
    "health",
]
