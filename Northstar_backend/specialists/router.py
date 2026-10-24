"""Bojo's router — classify, find gaps, hand off. No specialist work here.

Blueprint §7: "Bojo = router and conversation layer … Bojo never does specialist
work itself."

The blueprint also warns about a specific failure mode of naive routing: a
negated request, a quoted example, a question, or an A+/video request must not
be treated as a generic image-generation command. This router therefore:

  • strips quoted spans before scoring (an example is not an instruction),
  • drops negated clauses ("don't make a video", "no A+ content"),
  • requires a margin between the top two agents before it commits,
  • and returns `unclear` with ONE clarifying question when it is not confident.

It is deterministic on purpose: the same request must always route the same way,
and the routing test suite can assert it without a model in the loop.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

from specialists import registry

#: Words that flip the clause that follows them.
_NEGATOR_RE = re.compile(
    r"\b(don't|dont|do not|doesn't|does not|no|not|without|skip|avoid|never|"
    r"isn't|aren't|cancel|instead of)\b", re.IGNORECASE)


def _drop_negated(text: str) -> str:
    """Blank everything AFTER a negator within its clause.

    "I don't need a video, just the A+ modules" must not route to video: the
    negated span dies, the rest of the sentence survives. Dropping the whole
    clause was too blunt — it also deleted the agent the operator DID want.
    """
    keep: List[str] = []
    for clause in _CLAUSE_SPLIT.split(text):
        if not clause.strip():
            continue
        m = _NEGATOR_RE.search(clause)
        keep.append(clause[:m.start()] if m else clause)
    return " ".join(keep)

# Only strip a QUOTED span. A straight apostrophe inside a product name
# ("Lion's Mane") must not be mistaken for a quote, or the router silently eats
# the words that follow it - which is exactly how the weight and dimensions
# disappeared from a complete brief during testing.
_QUOTED = re.compile(
    r'("[^"]*"|`[^`]*`|“[^”]*”|(?<![\w])\'[^\']{2,}\'(?![\w]))')
_CLAUSE_SPLIT = re.compile(r"[,.;:!?\n]+")

_UNIT_WEIGHT = re.compile(
    r"(?:net\s*wt\.?\s*)?(\d+(?:\.\d+)?)\s*(oz|ounce|ounces|g|gram|grams)\b",
    re.IGNORECASE)
_DIMS = re.compile(r"(\d+(?:\.\d+)?)\s*(?:mm)?\s*[x×]\s*(\d+(?:\.\d+)?)\s*(?:mm)?"
                   r"(?:\s*[x×]\s*(\d+(?:\.\d+)?))?", re.IGNORECASE)


def _strip_quoted(text: str) -> str:
    return _QUOTED.sub(" ", text)


def _score(text: str) -> Dict[str, int]:
    low = text.lower()
    scores: Dict[str, int] = {}
    for name, spec in registry.AGENTS.items():
        total = 0
        for kw in spec.get("keywords") or []:
            if not kw:
                continue
            hits = low.count(kw.lower())
            if hits:
                # longer, more specific phrases weigh more than single words
                total += hits * (3 if " " in kw else 1)
        if total:
            scores[name] = total
    return scores


def _weights_from_text(text: str) -> Dict[str, Any]:
    found: Dict[str, Any] = {}
    m = _UNIT_WEIGHT.search(text)
    if m:
        value, unit = m.group(1), m.group(2).lower()
        if unit.startswith("o"):
            grams = round(float(value) * 28.3495)
            found["weight"] = f"NET WT {m.group(1)} OZ ({grams} g)"
        else:
            found["weight"] = f"NET WT {m.group(1)} {unit.upper()}"
    d = _DIMS.search(text)
    if d:
        dims = {"width_mm": float(d.group(1)), "height_mm": float(d.group(2))}
        if d.group(3):
            dims["gusset_mm"] = float(d.group(3))
        found["dims"] = dims
    return found


def classify(request: str) -> Dict[str, Any]:
    """Route one request. Returns {agent, confidence, scores, reason}."""
    cleaned = _drop_negated(_strip_quoted(str(request or "")))
    scores = _score(cleaned)
    if not scores:
        return {
            "agent": None,
            "status": "unclear",
            "confidence": 0.0,
            "scores": {},
            "question": ("Tell me which job this is: a packaging design, a listing "
                         "rewrite, PPC work, images/A+, social, video, or content?"),
            "reason": "no specialist matched the wording",
        }
    ranked: List[Tuple[str, int]] = sorted(scores.items(), key=lambda kv: kv[1],
                                           reverse=True)
    top, top_score = ranked[0]
    second = ranked[1][1] if len(ranked) > 1 else 0
    # Ambiguity: two agents within one point of each other is a coin flip.
    if second and (top_score - second) <= 1:
        tied = [ranked[0][0], ranked[1][0]]
        return {
            "agent": None,
            "status": "unclear",
            "confidence": 0.0,
            "scores": scores,
            "candidates": tied,
            "question": (f"Did you want the {registry.AGENTS[tied[0]]['label']} or the "
                         f"{registry.AGENTS[tied[1]]['label']}?"),
            "reason": "two specialists scored within one point",
        }
    confidence = round(top_score / max(1, sum(scores.values())), 3)
    if top_score < 2 and confidence < 0.6:
        return {
            "agent": None,
            "status": "unclear",
            "confidence": confidence,
            "scores": scores,
            "question": ("I don't want to guess which specialist this belongs to — "
                         "say a bit more about the deliverable."),
            "reason": "signal too weak to commit",
        }
    return {"agent": top, "status": "routed", "confidence": confidence,
            "scores": scores, "reason": f"{top} scored {top_score}"}


def plan(request: str, *, known: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Full router decision: agent + the inputs still needed before work starts.

    `known` is what the Brand Kit already supplies (brand, logo, address, facts).
    Anything in the request is extracted; the remainder becomes questions.
    """
    decision = classify(request)
    if decision["status"] != "routed":
        return decision
    name = decision["agent"]
    spec = dict(known or {})
    spec.update(_weights_from_text(_strip_quoted(str(request or ""))))
    from specialists import package_designer
    if name == "package_designer":
        gaps = package_designer.missing_inputs(spec)
    else:
        gaps = [{"field": f, "question": f"I need the {f.replace('_', ' ')}"}
                for f in (registry.AGENTS[name].get("inputs_required") or [])
                if not spec.get(f)]
    decision["spec"] = spec
    decision["questions"] = gaps
    decision["ready"] = not gaps
    return decision


def route_and_describe(request: str, *, known: Optional[Dict[str, Any]] = None) -> str:
    """One-line, model-facing hand-off line (kept terse on purpose)."""
    d = plan(request, known=known)
    if d["status"] != "routed":
        return f"[router] unclear: {d.get('question')}"
    label = registry.AGENTS[d["agent"]]["label"]
    if d.get("ready"):
        return f"[router] {label} — inputs complete, proceed."
    missing = ", ".join(q["field"] for q in d.get("questions") or [])
    return f"[router] {label} — ask for: {missing}."


# ── Bojo vs Autothink scope boundary (blueprint §11B.1) ────────────────────
# Bojo is a broad seller assistant. Serious coding and task management are
# Autothink's. The boundary is deterministic so it can be tested, and a handoff
# always carries a brief instead of Bojo attempting the work badly.

_AUTOTHINK = re.compile(
    r"\b(refactor|re-?architect|migrat(e|ion)|unit tests?|test suite|integration tests?|"
    r"ci pipeline|github actions|docker|kubernetes|orm|schema migration|multi-file|"
    r"codebase|pull request|\bpr\b|commit|deploy(ment)? pipeline|typescript migration|"
    r"dependency upgrade|monorepo|thread pool|concurrency bug|memory leak|"
    r"queue worker|worker pool|importer|api endpoint|backend service|microservice|"
    r"database|schema)\b", re.I)

_UTILITY = re.compile(
    r"\b(calculator|convert(er|or)?|checklist|timer|stopwatch|countdown|formula|"
    r"percentage|unit conversion|tip calculator|profit calculator|break-?even sheet|"
    r"template letter|quick tool|spreadsheet formula)\b", re.I)


def scope(request: str) -> Dict[str, Any]:
    """Decide who owns the request: Bojo or Autothink.

    Autothink is a PREMIUM service (Perplexity-Computer class). Bojo must never
    send work there on its own. When a request looks like engineering, Bojo
    stops and OFFERS the handoff with a token estimate and the charge, and waits
    for the operator to say yes.
    """
    text = _strip_quoted(str(request or ""))
    low = text.lower()
    if _AUTOTHINK.search(text):
        estimate = _handoff_estimate(text)
        return {
            "scope": "bojo",
            "offer_handoff": True,
            "requires_user_approval": True,
            "reason": ("this is engineering work — Autothink is a premium service, so I am "
                       "offering the handoff instead of sending it"),
            "handoff": {
                "target": "autothink",
                "request": text.strip()[:600],
                "why": "multi-file code or test work, not a seller task",
                "estimated_tokens": estimate.get("estimated_tokens"),
                "estimated_cost_usd": estimate.get("estimated_cost_usd"),
                "estimated_charge_usd": estimate.get("estimated_charge_usd"),
                "priced_on": estimate.get("priced_on"),
                "acceptance": [
                    "the change is scoped in one short plan before editing",
                    "existing tests still pass; new behaviour has a test",
                    "no production data is touched without approval",
                ],
                "note": ("Nothing has been sent. Say 'send it to Autothink' to proceed, or "
                         "I can keep it here if it turns out to be small."),
            },
        }
    if _UTILITY.search(text):
        return {"scope": "bojo", "reason": "small utility Bojo builds itself",
                "kind": "utility"}
    if re.search(r"\b(make|build|create|write|generate)\b", low):
        return {"scope": "bojo", "reason": "seller-facing build request"}
    return {"scope": "bojo", "reason": "default: Bojo owns seller work"}


def _handoff_estimate(text: str) -> Dict[str, Any]:
    """Price the handoff on the CLOUD lane, because Autothink is premium.

    Estimating against the local lane returned 0.00, which would tell the
    operator a premium handoff is free. `stub_cloud` is the cloud-class price
    line, so the number shown is the number they would pay.
    """
    try:
        from gateway import ledger
        tokens_in = max(1, len(text) // 4)
        tokens_out = max(1, tokens_in // 2)
        usage = {"tokens_in": tokens_in, "tokens_out": tokens_out, "gpu_seconds": 0.0}
        cost = ledger.raw_cost("stub_cloud", usage)
        margin = ledger.margin_for("", "autothink")
        return {
            "estimated_tokens": tokens_in + tokens_out,
            "estimated_cost_usd": cost,
            "estimated_charge_usd": ledger.charge_for(cost, margin),
            "priced_on": "cloud lane",
        }
    except Exception:  # noqa: BLE001 - an estimate must never block the offer
        return {"estimated_tokens": None, "estimated_cost_usd": None,
                "estimated_charge_usd": None, "priced_on": None}
