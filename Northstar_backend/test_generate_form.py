"""The requested form is a schema field and survives the prompt sanitizer.

Same defect class as the suppression phrase: a system-level clause must never
override what the user asked for.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import design_studio_api as ds
from text_fidelity import SUPPRESSION_PHRASE, sanitize_brief_for_render


def test_every_form_has_a_clause():
    assert set(ds.FORM_CLAUSES) == {"pouch", "box", "bottle", "tube", "jar"}


def test_the_form_survives_the_sanitizer():
    for form, clause in ds.FORM_CLAUSES.items():
        composed = f"The product container is {clause}. A 6 oz sample. Only a {clause} is shown."
        out = sanitize_brief_for_render(composed)["render_prompt"]
        assert clause in out, form
        assert out.count(clause) == 2, form


def test_the_suppression_phrase_names_no_form():
    """The old phrase named a medium; it must never name a container either."""
    low = str(SUPPRESSION_PHRASE).lower()
    for noun in ("pouch", "box", "bottle", "tube", "jar", "carton", "botanical"):
        assert noun not in low, noun


def test_the_form_is_a_schema_field_not_prose():
    assert "form" in ds.GenerateIn.model_fields
    spec = ds.GenerateIn.model_fields["form"]
    # optional, bounded, so an unknown form is simply not applied
    assert spec.is_required() is False
