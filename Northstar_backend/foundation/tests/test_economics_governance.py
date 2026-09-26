"""Economics authority governance (Phase 1C-03R).

Proves the canonical stack depends ONLY on foundation/economics and never on the
legacy fee modules, so the canonical path has a single authoritative engine.
"""
from __future__ import annotations

import ast
from pathlib import Path

FOUNDATION_ROOT = Path(__file__).resolve().parents[1]  # .../foundation
LEGACY_ECON = {
    "pricing", "fee_engine", "fee_calculator", "finance", "unit_economics",
    "enricher", "product_analysis", "scanner_data", "ad_pilot", "word_coffee",
}


def _imports(path: Path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for n in node.names:
                yield n.name
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                yield node.module


def test_foundation_never_imports_legacy_economics():
    offenders = []
    for p in FOUNDATION_ROOT.rglob("*.py"):
        if "tests" in p.parts or "__pycache__" in p.parts:
            continue
        for name in _imports(p):
            if name.split(".")[0] in LEGACY_ECON:
                offenders.append(f"{p.relative_to(FOUNDATION_ROOT)} -> {name}")
    assert not offenders, f"foundation depends on legacy economics: {offenders}"


def test_canonical_engine_is_importable_and_versioned():
    from Northstar_backend.foundation.economics import compute, EconomicsInput
    from Northstar_backend.foundation.economics.versions import FORMULA_VERSION
    out = compute(EconomicsInput(selling_price="10.00", acquisition_cost="4.00",
                                 referral_fee_amount="1.50", fba_fulfillment_fee="3.00",
                                 advertising_cost="0"))
    assert out.formula_version == FORMULA_VERSION
    assert out.contribution_profit_after_ads is not None


def test_faire_adapter_delegates_to_canonical():
    src = (FOUNDATION_ROOT.parent / "faire_research" / "economics.py").read_text(encoding="utf-8")
    # adapter must import the canonical engine and must not define its own fee table
    assert "from foundation.economics" in src or "foundation.economics" in src
    assert "0.15" not in src  # no hidden referral default


def test_no_hardcoded_referral_default_in_canonical_inputs():
    src = (FOUNDATION_ROOT / "economics" / "engine.py").read_text(encoding="utf-8")
    # canonical engine must never silently assume a 15% referral fee
    assert "0.15" not in src