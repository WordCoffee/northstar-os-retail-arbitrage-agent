"""Ty's Vision - capture, privacy and control.

Deterministic before pixels: the UI Automation tree and the browser DevTools protocol
are the primary read (D7); this package is the part that must exist before any of that
can be trusted - the gate that decides whether a pixel is allowed to exist at all.
"""
from . import capture, control, privacy  # noqa: F401

__all__ = ["capture", "control", "privacy"]
