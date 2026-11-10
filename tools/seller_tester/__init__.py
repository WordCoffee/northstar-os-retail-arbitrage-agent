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
    FIDELITIES,
    MIN_PER_MODE,
    REFERENCE_MODES,
    ROUTES,
    SITUATIONS,
    SOURCE_MODES,
    brief_fidelity,
    briefs_by_mode,
    brief_mode,
    load_catalog,
    mode_counts,
    route_for_brief,
    validate_catalog,
)
from .aplus import (
    APLUS_KEY,
    CONTENT_TYPES,
    MIN_APLUS_BRIEFS,
    declared_page_height,
    load_aplus_briefs,
    module_grid,
    produce_module,
    produce_page,
    run_aplus_family,
    score_aplus_page,
    validate_aplus_briefs,
)
from .escalate import EscalationLog, escalate
from .gaps import build_gap, file_gap, gap_id
from .generators import (
    CompositeGenerator,
    ComfyGenerator,
    GeneratorUnavailable,
    StoredGenerator,
)
from .harness import run_pass, score_image, select_briefs
from .judge import FakeJudge, get_judge, local_judge
from .reference_check import (
    check_reference_for_brief,
    colour_agreement,
    cosine,
    dominant_hue,
    embed,
    key_tokens,
    load_reference_rgb,
    normalise_reference_path,
    ocr_text,
    reference_check_for_brief,
    semantic_agreement,
    silhouette_aspect,
    subject_mask,
    text_match,
)

__all__ = [
    "APLUS_KEY",
    "CONTENT_TYPES",
    "MIN_APLUS_BRIEFS",
    "declared_page_height",
    "load_aplus_briefs",
    "module_grid",
    "produce_module",
    "produce_page",
    "run_aplus_family",
    "score_aplus_page",
    "validate_aplus_briefs",
    "CATEGORIES",
    "SITUATIONS",
    "SOURCE_MODES",
    "REFERENCE_MODES",
    "FIDELITIES",
    "ROUTES",
    "MIN_PER_MODE",
    "DEFAULT_CATALOG_PATH",
    "load_catalog",
    "validate_catalog",
    "brief_mode",
    "brief_fidelity",
    "route_for_brief",
    "briefs_by_mode",
    "mode_counts",
    "EscalationLog",
    "escalate",
    "build_gap",
    "file_gap",
    "gap_id",
    "StoredGenerator",
    "ComfyGenerator",
    "CompositeGenerator",
    "GeneratorUnavailable",
    "score_image",
    "run_pass",
    "select_briefs",
    "FakeJudge",
    "get_judge",
    "local_judge",
    "check_reference_for_brief",
    "colour_agreement",
    "cosine",
    "embed",
    "key_tokens",
    "ocr_text",
    "semantic_agreement",
    "text_match",
    "dominant_hue",
    "silhouette_aspect",
    "subject_mask",
    "load_reference_rgb",
    "normalise_reference_path",
    "reference_check_for_brief",
]
