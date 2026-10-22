"""Deterministic graders for the improvement loop.

Most Amazon selling rules are checkable without a model: character limits,
required fields, banned claims, one-question, citation presence. Those run here.
A rubric judge exists only for tone, and it is never the sole basis for a
promotion.

Every grader is pure: text in, (score 0..1, failures) out. No network, no model,
so a cycle's evidence is reproducible.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple

_PREAMBLE = (
    "sure", "certainly", "great question", "of course", "absolutely",
    "i'd be happy", "i would be happy", "let me", "here's", "here is",
    "as an ai", "happy to help",
)
_CITE = re.compile(r"(https?://|source\s*:|source\s*=|eff\.|effective\s+\d{4})", re.I)
_CAPS_WORD = re.compile(r"\b[A-Z]{4,}\b")


def _terms(text: str, terms: Iterable[str]) -> List[str]:
    low = text.lower()
    return [t for t in terms if str(t).lower() in low]


def check_text(text: str, check: Dict[str, Any]) -> Optional[str]:
    """Return a failure string, or None when the check passes."""
    kind = str(check.get("type") or "")
    t = text or ""
    low = t.lower()
    words = re.findall(r"[A-Za-z0-9']+", t)

    if kind == "max_chars":
        limit = int(check["value"])
        return None if len(t) <= limit else f"length {len(t)} > {limit}"
    if kind == "min_chars":
        limit = int(check["value"])
        return None if len(t) >= limit else f"length {len(t)} < {limit}"
    if kind == "max_words":
        limit = int(check["value"])
        return None if len(words) <= limit else f"{len(words)} words > {limit}"
    if kind == "min_words":
        limit = int(check["value"])
        return None if len(words) >= limit else f"{len(words)} words < {limit}"
    if kind == "max_lines":
        limit = int(check["value"])
        lines = [ln for ln in t.splitlines() if ln.strip()]
        return None if len(lines) <= limit else f"{len(lines)} lines > {limit}"
    if kind == "forbidden_terms":
        hits = _terms(t, check.get("terms") or [])
        return None if not hits else f"forbidden terms present: {hits}"
    if kind == "required_terms_any":
        terms = check.get("terms") or []
        return None if _terms(t, terms) else f"none of {terms} present"
    if kind == "required_terms_all":
        terms = check.get("terms") or []
        missing = [x for x in terms if str(x).lower() not in low]
        return None if not missing else f"missing required terms: {missing}"
    if kind == "max_questions":
        limit = int(check.get("value", 1))
        q = t.count("?")
        return None if q <= limit else f"{q} questions > {limit}"
    if kind == "no_preamble":
        head = low.strip()[:80]
        hit = next((p for p in _PREAMBLE if head.startswith(p)), None)
        return None if hit is None else f"preamble opener: {hit!r}"
    if kind == "no_all_caps":
        hits = [w for w in _CAPS_WORD.findall(t)]
        # A short brand token is fine; four or more caps words is shouting.
        return None if len(hits) < 4 else f"all-caps words: {hits[:5]}"
    if kind == "citation_required":
        return None if _CITE.search(t) else "no source/citation"
    if kind == "regex_required":
        pattern = str(check["value"])
        return None if re.search(pattern, t, re.I) else f"missing /{pattern}/"
    if kind == "regex_forbidden":
        pattern = str(check["value"])
        return None if not re.search(pattern, t, re.I) else f"matched forbidden /{pattern}/"
    return None  # unknown checks never fail a candidate silently


def grade(text: str, checks: Iterable[Dict[str, Any]]) -> Tuple[float, List[str]]:
    checks = list(checks or [])
    if not checks:
        return 1.0, []
    failures = [f for f in (check_text(text, c) for c in checks) if f]
    return round(1.0 - len(failures) / len(checks), 4), failures


def load_suite(path: str | Path) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    p = Path(path)
    if not p.exists():
        return items
    with p.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                items.append(json.loads(line))
            except ValueError:
                continue
    return items


def run_suite(items: Iterable[Dict[str, Any]],
              answer_fn: Callable[[Dict[str, Any]], str]) -> Dict[str, Any]:
    """Grade every item; aggregate is the mean item score."""
    results = []
    for item in items:
        text = answer_fn(item) or ""
        score, failures = grade(text, item.get("checks") or [])
        results.append({"id": item.get("id"), "domain": item.get("domain"),
                        "score": score, "failures": failures})
    total = len(results)
    agg = round(sum(r["score"] for r in results) / total, 4) if total else 0.0
    return {"total": total, "score": agg, "results": results,
            "failed": [r["id"] for r in results if r["score"] < 1.0]}
