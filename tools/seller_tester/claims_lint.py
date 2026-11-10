"""Claims lint for A+ copy: the three ways a page can say something it cannot support.

The A+ family was extended by cloning module shapes between brands, and the clone carried the other
brand's claims with it — "1500MG PER SERVING" on a box of greeting cards. A renderer that prints a
benefit is making a claim; so the rules are mechanical and unforgiving:

1. **no disease or treatment claims** — a supplement page may not say it cures, treats, prevents or
   heals anything, nor name a condition;
2. **no cross-brand copy** — a Word Coffee page may not carry Mogra's lines, or vice versa;
3. **no unsourced numbers** — "1500MG", "30 SERVINGS", "95%" are claims about the product; each
   needs a source recorded in the brief (`text_sources`), or it does not go on a page.

This lints *copy in the brief*, not the rendered image: the image is only as honest as the brief.

    python -m tools.seller_tester.claims_lint --catalog ty/seller_briefs.json
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List

#: Disease, treatment and structure/function claims. Deliberately blunt: a false positive here is a
#: sentence to rewrite, a false negative is a regulatory problem.
DISEASE_TERMS = (
    "cure", "cures", "cured", "treat", "treats", "treated", "treatment", "prevent", "prevents",
    "heal", "heals", "healing", "clinically proven", "diagnose", "diagnoses",
    "anti-inflammatory", "anti inflammatory", "immune support", "boosts immunity",
    "lowers blood pressure", "blood pressure", "diabetes", "cancer", "tumour", "tumor",
    "anxiety", "depression", "insomnia", "adhd", "arthritis", "inflammation",
)
#: Brands whose names must not appear on another brand's page.
BRANDS = {
    "mogra": ("MOGRA", "LION'S MANE", "LIONS MANE", "SHIITAKE"),
    "word-coffee": ("WORD COFFEE", "FOR MOM", "MODERN WOMAN"),
}
#: A number with a unit is a factual claim about the product.
NUMBER = re.compile(r"\b\d+(?:\.\d+)?\s*(mg|g|oz|ml|l|servings?|capsules?|count|%|x)\b",
                    re.IGNORECASE)


def _texts(brief: Dict[str, Any]) -> Iterable[str]:
    for key in ("copy", "heading", "subhead", "note"):
        value = brief.get(key)
        if isinstance(value, str) and value.strip():
            yield value
    for module in brief.get("modules") or []:
        if not isinstance(module, dict):
            continue
        for key in ("text_required", "text", "lines", "copy"):
            value = module.get(key)
            if isinstance(value, str):
                yield value
            elif isinstance(value, list):
                for item in value:
                    if isinstance(item, str):
                        yield item


def brand_of(brief: Dict[str, Any]) -> str:
    line = str(brief.get("product_line") or "").lower()
    if "coffee" in line:
        return "word-coffee"
    if "mogra" in line or "lions" in line:
        return "mogra"
    path = str(((brief.get("reference") or {}).get("path")) or "").lower()
    if "word-coffee" in path:
        return "word-coffee"
    if "mogra" in path:
        return "mogra"
    return line or "unknown"


def lint_brief(brief: Dict[str, Any]) -> List[Dict[str, Any]]:
    findings: List[Dict[str, Any]] = []
    brand = brand_of(brief)
    sources = brief.get("text_sources") or {}
    for text in _texts(brief):
        low = text.lower()
        for term in DISEASE_TERMS:
            if term in low:
                findings.append({"brief": brief.get("id"), "rule": "disease-claim",
                                 "text": text, "term": term})
                break
        for other, names in BRANDS.items():
            if other == brand:
                continue
            for name in names:
                if name.lower() in low:
                    findings.append({"brief": brief.get("id"), "rule": "cross-brand",
                                     "text": text, "term": name})
                    break
        for match in NUMBER.finditer(text):
            token = match.group(0).strip()
            if not any(token.lower() in str(key).lower() for key in sources):
                findings.append({"brief": brief.get("id"), "rule": "unsourced-number",
                                 "text": text, "term": token})
    return findings


def lint_catalog(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for brief in payload.get("aplus_briefs") or []:
        out.extend(lint_brief(brief))
    return out


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Claims lint for A+ copy")
    parser.add_argument("--catalog", default=str(Path(__file__).resolve().parents[2] / "ty"
                                                / "seller_briefs.json"))
    parser.add_argument("--json", action="store_true")
    ns = parser.parse_args(argv)
    payload = json.loads(Path(ns.catalog).read_text(encoding="utf-8"))
    findings = lint_catalog(payload)
    if ns.json:
        print(json.dumps({"findings": findings}, indent=2))
    else:
        if not findings:
            print("claims lint: clean")
        for finding in findings:
            print(f"{finding['brief']}: {finding['rule']} [{finding['term']}] "
                  f"-> {finding['text'][:80]!r}")
    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
