"""D10 — visual regression gate for the Northstar UI.

Read-only by construction: this package never starts a server. It takes a
``--base-url``, refuses when that URL is not reachable, and refuses anything
that is not loopback (the browser path stays inside the localhost testing
exception in ``AGENTS.md``).

Entry points::

    python -m tools.visual_regression.gate --self-test
    python -m tools.visual_regression.gate --base-url http://127.0.0.1:8101

Layout::

    ty/visual_views.json                 view registry (routes, viewports, still params)
    tools/visual_regression/freeze.py    seeded still mode (Playwright init script)
    tools/visual_regression/capture.py   Playwright capture (desktop + iPhone 12 WebKit)
    tools/visual_regression/diff.py      perceptual diff (PIL + numpy)
    tools/visual_regression/baseline.py  gated baseline updates + CHANGELOG
    tools/visual_regression/fixtures/    synthetic prove-it pairs (no server needed)
    tools/visual_regression/baselines/   <view>/<viewport>.png
"""
from __future__ import annotations

__all__ = ["capture", "diff", "freeze", "views", "baseline", "gate"]

SCHEMA_VERSION = "northstar.visual_regression.v1"
