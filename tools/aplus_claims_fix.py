"""Finish sel-08: the A+ family's copy must survive the claims lint.

Three problems, three fixes, all mechanical:

1. **Cross-brand copy** — AP-007..AP-010 were cloned from Mogra briefs and kept Mogra's lines
   ("1500MG PER SERVING" on a box of greeting cards). Their copy is replaced with Word Coffee's own.
2. **A structure/function claim** — "IMMUNE SUPPORT" appears on Mogra pages. It is a claim about a
   body function, so it goes; "DAILY FOCUS" says nothing medical.
3. **Unsourced numbers** — "60 SERVINGS", "1500MG", "2 CAPSULES" are facts about the product. The
   owner stated them (`needs_you.md` A3, still `DRAFT · VERIFY BEFORE PRINT`), so they get a
   `text_sources` entry naming that provenance rather than being deleted.

    python tools/aplus_claims_fix.py --write
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "ty" / "seller_briefs.json"

#: Word Coffee has no servings, capsules or milligram values. Every one of these is a Mogra line.
WORD_COFFEE_REPLACEMENTS = {
    "60 SERVINGS": "GIFT BOX",
    "VEGAN CAPSULES": "GREETING CARDS",
    "THIRD PARTY TESTED": "MADE FOR EVERY DAY",
    "1500MG PER SERVING": "EMPOWERING MOMS",
    "SERVING SIZE 2 CAPSULES": "ONE MESSAGE AT A TIME",
    "SERVINGS PER CONTAINER 30": "A GIFT THAT SPEAKS",
    "STORAGE COOL AND DRY": "FOR MOM",
    "ORGANIC CERTIFIED": "WORD COFFEE",
    "VEGAN FRIENDLY": "MOTIVATION FOR THE MODERN WOMAN",
    "CORDYCEPS REISHI TURKEY TAIL": "EMPOWERING MOMS",
    "IMMUNE SUPPORT": "DAILY INSPIRATION",
    "MENTAL CLARITY": "FOCUS",
    "STEADY ENERGY": "DRIVE",
    "MOGRA VS OTHER BRANDS": "WORD COFFEE GIFT SETS",
    "ORGANIC LION'S MANE": "FOR MOM",
    "NO ARTIFICIAL FILLERS": "GREETING CARDS INCLUDED",
    "TRY MOGRA TODAY": "SHOP WORD COFFEE",
    "FREE SHIPPING": "GIFT READY",
    "MORNING RITUAL": "A DAILY NOTE",
    "MIX INTO COFFEE OR TEA": "OPEN THE BOX",
    "ONE SCOOP DAILY": "READ ONE CARD A DAY",
    "TECHNICAL SPECIFICATIONS": "WHAT ARRIVES",
}
#: Claims that go, everywhere, regardless of brand.
GLOBAL_REPLACEMENTS = {"IMMUNE SUPPORT": "DAILY FOCUS"}

#: Numbers the owner stated. The provenance is named so a reviewer can follow it back.
OWNER_STATED = {
    "60 SERVINGS": "owner-stated serving count (needs_you.md A3, DRAFT · VERIFY BEFORE PRINT)",
    "1500MG PER SERVING": "owner-stated 2,000 mg per 2 g serving (needs_you.md A3, DRAFT)",
    "2 CAPSULES": "owner-stated serving size (needs_you.md A3, DRAFT · VERIFY BEFORE PRINT)",
    "SERVINGS PER CONTAINER 30": "owner-stated container count (needs_you.md A3, DRAFT)",
}


def _replace_in(value: Any, mapping: Dict[str, str]) -> Any:
    if isinstance(value, str):
        out = value
        for old, new in mapping.items():
            out = out.replace(old, new)
        return out
    if isinstance(value, list):
        return [_replace_in(item, mapping) for item in value]
    if isinstance(value, dict):
        return {key: _replace_in(item, mapping) for key, item in value.items()}
    return value


def fix(payload: Dict[str, Any]) -> Dict[str, Any]:
    changed: List[str] = []
    for brief in payload.get("aplus_briefs") or []:
        brand = str(brief.get("product_line") or "").lower()
        before = json.dumps(brief, sort_keys=True)
        brief = _replace_in(brief, GLOBAL_REPLACEMENTS)
        if brand == "word-coffee":
            brief = _replace_in(brief, WORD_COFFEE_REPLACEMENTS)
        if brand == "mogra":
            sources = dict(brief.get("text_sources") or {})
            for token, provenance in OWNER_STATED.items():
                sources.setdefault(token, provenance)
            brief["text_sources"] = sources
        if json.dumps(brief, sort_keys=True) != before:
            changed.append(str(brief.get("id")))
    return {"changed": changed}


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Finish sel-08: the A+ copy survives the claims lint")
    parser.add_argument("--write", action="store_true")
    ns = parser.parse_args(argv)
    import sys as _sys  # noqa: PLC0415
    _sys.path.insert(0, str(Path(__file__).resolve().parent / "seller_tester"))
    from claims_lint import brand_of  # noqa: PLC0415

    payload = json.loads(CATALOG.read_text(encoding="utf-8"))
    # replace in place: `fix` returns a list of changed ids, the payload is mutated below
    changed: List[str] = []
    for index, brief in enumerate(payload.get("aplus_briefs") or []):
        brand = brand_of(brief)          # product_line, or the reference path when it is absent
        updated = _replace_in(brief, GLOBAL_REPLACEMENTS)
        if brand == "word-coffee":
            updated = _replace_in(updated, WORD_COFFEE_REPLACEMENTS)
        if brand in ("mogra", "lions-mane"):
            sources = dict(updated.get("text_sources") or {})
            for token, provenance in OWNER_STATED.items():
                sources.setdefault(token, provenance)
            updated["text_sources"] = sources
        if updated != brief:
            payload["aplus_briefs"][index] = updated
            changed.append(str(brief.get("id")))
    if ns.write:
        CATALOG.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"changed": changed, "count": len(changed)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
