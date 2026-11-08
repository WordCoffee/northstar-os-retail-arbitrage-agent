"""Seller-Tester harness (D9).

Behaves like a real Amazon seller asking Northstar OS for product pictures:
it picks a brief from a catalog, obtains an image from an injectable generator,
scores it with pure programmatic checks, optionally asks a local vision model,
files every failure as a gap, and escalates the brief after each pass.

No model is required for scoring. No pixels leave the machine: the only vision
path is the local Ollama verifier, and it is OFF unless explicitly enabled.
"""
from __future__ import annotations

from .briefs import (
    CATEGORIES,
    DEFAULT_CATALOG_PATH,
    SITUATIONS,
    load_catalog,
    validate_catalog,
)
from .escalate import EscalationLog, escalate
from .gaps import build_gap, file_gap, gap_id
from .generators import ComfyGenerator, GeneratorUnavailable, StoredGenerator
from .harness import run_pass, score_image
from .judge import FakeJudge, get_judge, local_judge

__all__ = [
    "CATEGORIES",
    "SITUATIONS",
    "DEFAULT_CATALOG_PATH",
    "load_catalog",
    "validate_catalog",
    "EscalationLog",
    "escalate",
    "build_gap",
    "file_gap",
    "gap_id",
    "StoredGenerator",
    "ComfyGenerator",
    "GeneratorUnavailable",
    "score_image",
    "run_pass",
    "FakeJudge",
    "get_judge",
    "local_judge",
]
