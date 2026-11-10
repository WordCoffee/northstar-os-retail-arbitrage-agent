"""The claims lint: three rules, and the reason each one exists.

The A+ family grew by cloning module shapes across brands and the clone carried the other brand's
claims with it. A renderer that prints a benefit is making a claim, so the rules are mechanical.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from seller_tester import claims_lint as C  # noqa: E402


def _brief(brand: str, *lines: str, sources: dict | None = None):
    return {"id": "AP-T", "product_line": brand,
            "modules": [{"id": "hero", "text_required": list(lines)},
                        {"id": "strip", "text_required": list(lines)}],
            "text_sources": sources or {}}


def test_a_disease_or_treatment_claim_is_refused():
    for line in ("IMMUNE SUPPORT", "CURES ANXIETY", "clinically proven to lower blood pressure"):
        findings = C.lint_brief(_brief("lions-mane", line))
        assert any(f["rule"] == "disease-claim" for f in findings), line


def test_a_cross_brand_line_is_refused():
    # the helper puts the line in two modules, so a finding per module is expected
    findings = C.lint_brief(_brief("word-coffee", "MOGRA VS OTHER BRANDS"))
    assert {f["rule"] for f in findings} == {"cross-brand"}
    findings = C.lint_brief(_brief("lions-mane", "WORD COFFEE"))
    assert {f["rule"] for f in findings} == {"cross-brand"}


def test_a_number_without_a_source_is_refused():
    findings = C.lint_brief(_brief("lions-mane", "1500MG PER SERVING"))
    assert {f["rule"] for f in findings} == {"unsourced-number"}


def test_a_number_with_a_named_source_passes():
    brief = _brief("lions-mane", "1500MG PER SERVING",
                   sources={"1500MG PER SERVING": "owner-stated, needs_you A3"})
    assert C.lint_brief(brief) == []


def test_plain_copy_and_numbers_without_units_pass():
    brief = _brief("lions-mane", "DAILY FOCUS", "MUSHROOM POWDER", "ONE MESSAGE AT A TIME")
    assert C.lint_brief(brief) == []


def test_the_shipped_family_is_clean():
    """The regression that matters: the catalog as committed must pass its own lint."""
    import json

    payload = json.loads((ROOT / "ty" / "seller_briefs.json").read_text(encoding="utf-8"))
    assert C.lint_catalog(payload) == []
