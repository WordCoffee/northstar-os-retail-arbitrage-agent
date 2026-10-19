"""High-thinking self-check (Thorn v5.0 §Multi-Step Reasoning & High-Thinking).

A second pass over a proposed answer, in two layers:

    checklist()   deterministic, always runs, calls nothing
    critique()    checklist + an OPTIONAL local-model pass via an injected caller

Honesty contract
----------------
* Every deterministic finding QUOTES the span it is complaining about. A checker
  that asserts "there is an unsupported claim" without showing it is theatre.
* The model layer is optional. With no caller — or an offline lane — it reports
  `available: False` with the real reason. It never fabricates a critique and
  never invents findings the deterministic layer did not produce.
* `refine()` returns an OUTLINE of what must change. It does not write a polished
  final answer, because a checker that rewrites the thing it is checking is not a
  check.
"""
from __future__ import annotations

import re
from typing import Any, Callable, Dict, List, Optional, Sequence

ABSOLUTE_CLAIMS = {
    "guaranteed": "high", "guarantee": "high", "certified": "high",
    "100%": "high", "fda approved": "high", "usda organic": "high",
    "always": "medium", "never": "medium", "definitely": "medium",
    "no risk": "high", "proven to": "medium",
}

VERIFICATION_WORDS = ("verify", "confirm", "check", "measure", "test", "audit",
                      "inspect", "reconcile", "double-check")
RISKY_TOPIC_WORDS = ("price", "cost", "margin", "listing", "supplier", "compliance",
                     "claim", "nutrition", "allergen", "certif")

_NUM = re.compile(r"(?<![\w.])(\d[\d,]*\.?\d*)\s?([a-z%]{0,8})", re.I)
_QUESTION_STOP = {"what", "which", "should", "would", "could", "does", "is", "are",
                  "the", "and", "for", "with", "that", "this", "from", "about"}


def _content_words(text: str, min_len: int = 4) -> List[str]:
    return [w.lower() for w in re.findall(r"[A-Za-z][A-Za-z0-9'-]+", text or "")
            if len(w) >= min_len and w.lower() not in _QUESTION_STOP]


def _spans(text: str, needle: str) -> List[str]:
    low, out, start = (text or "").lower(), [], 0
    while True:
        i = low.find(needle, start)
        if i < 0:
            break
        out.append(text[max(0, i - 30):i + len(needle) + 30].strip())
        start = i + len(needle)
    return out


def checklist(task: str, answer: str, *, context: str = "",
              constraints: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Deterministic checks. Every finding quotes the span it refers to."""
    findings: List[Dict[str, Any]] = []
    ans = answer or ""
    low = ans.lower()

    for phrase, severity in ABSOLUTE_CLAIMS.items():
        for span in _spans(ans, phrase):
            findings.append({
                "kind": "unhedged_claim", "severity": severity,
                "detail": f"'{phrase}' is an absolute claim; it needs evidence or a hedge.",
                "quote": span,
            })
            break

    known = {v.rstrip(".,%") for v, _ in _NUM.findall((task or "") + " " + (context or ""))}
    for value, unit in _NUM.findall(ans):
        if value.rstrip(".,%") not in known:
            findings.append({
                "kind": "unsourced_number", "severity": "medium",
                "detail": (f"'{value}{(' ' + unit) if unit else ''}' does not appear in the "
                           "task or the provided context — it needs a source or a hedge."),
                "quote": _spans(ans, value)[0] if _spans(ans, value) else value,
            })
            break

    if "?" in (task or ""):
        asked = set(_content_words(task))
        answered = set(_content_words(ans))
        shared = asked & answered
        if asked and not shared:
            findings.append({
                "kind": "possible_topic_drift", "severity": "high",
                "detail": "the answer shares no content word with the question asked.",
                "quote": sorted(asked)[:6],
            })

    if any(w in (task or "").lower() for w in RISKY_TOPIC_WORDS):
        if not any(w in low for w in VERIFICATION_WORDS):
            findings.append({
                "kind": "missing_verification_step", "severity": "medium",
                "detail": ("the task touches price/listings/compliance but the answer names no "
                           "verification step."),
                "quote": "",
            })

    c = constraints or {}
    if isinstance(c.get("max_words"), int):
        n = len(ans.split())
        if n > c["max_words"]:
            findings.append({"kind": "constraint_violation", "severity": "high",
                             "detail": f"answer is {n} words; limit is {c['max_words']}.",
                             "quote": f"{n} > {c['max_words']}"})
    for phrase in c.get("must_not_include", ()) or ():
        if phrase and phrase.lower() in low:
            findings.append({"kind": "constraint_violation", "severity": "high",
                             "detail": f"answer contains forbidden phrase '{phrase}'.",
                             "quote": _spans(ans, phrase.lower())[0] if _spans(ans, phrase.lower()) else phrase})
    for phrase in c.get("must_include", ()) or ():
        if phrase and phrase.lower() not in low:
            findings.append({"kind": "constraint_violation", "severity": "high",
                             "detail": f"answer is missing required phrase '{phrase}'.",
                             "quote": phrase})

    if ans.count("```") % 2 == 1:
        findings.append({"kind": "unclosed_code_fence", "severity": "medium",
                         "detail": "an odd number of ``` fences — the block never closes.",
                         "quote": "```"})
    if len(re.findall(r"\*\*[^*]*$", ans)) or len(re.findall(r"(?<!\*)\*(?!\*)[^*\n]*$", ans)):
        findings.append({"kind": "unclosed_emphasis", "severity": "low",
                         "detail": "an emphasis marker opens and never closes.",
                         "quote": "*"})

    counts = {"high": 0, "medium": 0, "low": 0}
    for f in findings:
        counts[f["severity"]] += 1
    return {
        "findings": findings,
        "counts": counts,
        "verdict": "issues" if counts["high"] else ("warnings" if counts["medium"] else "clean"),
        "method": "deterministic span-quoting checks; no model, no network",
    }


def critique(task: str, answer: str, *, context: str = "",
             constraints: Optional[Dict[str, Any]] = None,
             caller: Optional[Callable[[str], str]] = None) -> Dict[str, Any]:
    """Checklist first, then an optional model pass. Fails soft, never invents."""
    base = checklist(task, answer, context=context, constraints=constraints)
    model_pass: Dict[str, Any]
    if caller is None:
        model_pass = {
            "available": False,
            "reason": ("no model caller was supplied — the deterministic checklist ran "
                       "alone, and the model layer is reported as not run."),
        }
    else:
        prompt = (
            "You are reviewing an answer for defects. Reply with at most 3 short lines, "
            "each of the form 'DEFECT: <what> | FIX: <what to change>'. If you find "
            "nothing, reply 'NO_DEFECTS'. Do not rewrite the answer.\n\n"
            f"TASK:\n{task[:1500]}\n\nANSWER:\n{answer[:3000]}\n"
        )
        try:
            text = str(caller(prompt) or "").strip()
            lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
            defects = [ln for ln in lines if ln.upper().startswith("DEFECT")]
            model_pass = {
                "available": True,
                "defects": defects[:3],
                "clean": (not defects) or text.upper().startswith("NO_DEFECTS"),
            }
        except Exception as exc:  # noqa: BLE001 - an offline lane is reported, not hidden
            model_pass = {"available": False, "reason": f"{type(exc).__name__}: {exc}"[:200]}

    return {
        "task": task,
        "verdict": base["verdict"],
        "findings": base["findings"],
        "counts": base["counts"],
        "model_pass": model_pass,
        "summary": (f"deterministic: {base['counts']['high']} high / "
                    f"{base['counts']['medium']} medium / {base['counts']['low']} low"
                    + ("; model pass: not run" if not model_pass.get("available")
                       else f"; model pass found {len(model_pass.get('defects') or [])} defect line(s)")),
    }


def refine(critique_result: Dict[str, Any]) -> Dict[str, Any]:
    """An outline of what must change. Deliberately NOT a rewritten answer."""
    steps: List[str] = []
    for f in critique_result.get("findings", []):
        steps.append(f"[{f['severity']}] {f['detail']}")
    for d in (critique_result.get("model_pass") or {}).get("defects") or []:
        steps.append(str(d))
    return {
        "outline": steps,
        "empty": not steps,
        "note": ("This is a list of things to change, not a rewritten answer: the model "
                 "that produced the answer (or the operator) makes the edit."),
    }
