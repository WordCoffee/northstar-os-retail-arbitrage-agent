"""Ty's Vision - capture, privacy, control, browser control, parity.

Deterministic before pixels: the UI Automation tree and the browser DevTools protocol
are the primary read (D7). D8 adds the part that can act, which is why every action goes
through `risk` first and `act.perform` second.
"""
from . import (act, browser, capture, computer, control, injection, lease, live,  # noqa: F401
               parity, privacy, quarantine, risk, scope, tree, understand)

__all__ = ["act", "browser", "capture", "computer", "control", "injection", "lease",
           "live", "parity", "privacy", "quarantine", "risk", "scope", "tree", "understand"]
