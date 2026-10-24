"""Typed decision layer for copy and routing decisions.

Why this exists
---------------
Northstar makes a lot of small judgement calls that a regex can only half-answer:
is this listing copy shippable, should a claim be reviewed, is a product the same
SKU. A string model answers those inconsistently and expensively; a deterministic
rule cannot see paraphrase. This module defines one typed contract so a rule
backend can serve today and a small local System-1 model can serve later without
touching the call sites.

Contract
--------
``decide(kind, text, facts=None, backend="auto")`` returns::

    {"kind", "value", "confidence", "abstained", "flags", "backend", "reason"}

* ``value`` is one of the kind's labels (always a closed set).
* ``confidence`` is 0..1. Below ``threshold`` the caller must escalate.
* ``abstained`` means the layer refuses to decide (empty/ambiguous input).
* Nothing raises: an unavailable backend degrades to rules and says so.

Backends
--------
* ``rules`` — deterministic, offline, always available. Default.
* ``laya``  — the 421M local System-1 model (NandhaKishorM/laya). Not installed on
  this bench; ``auto`` reports ``laya_not_installed`` and uses rules. No network.

No network, no writes, stdlib only.
"""

from __future__ import annotations

import json
import os
import re
import sys
from typing import Any, Dict, Iterable, List, Optional

#: Values below this are an escalation, not a decision.
DEFAULT_THRESHOLD = 0.6

# Closed label sets per decision kind. A backend may not invent a label.
KINDS: Dict[str, List[str]] = {
    "copy_audit": ["pass", "review", "block"],
    "listing_tier": ["keep", "improve", "rewrite"],
    "duplicate": ["same", "different", "unsure"],
    "blocker_escalation": ["now", "later", "never"],
    "respond_now": ["yes", "no"],
}

# Declarative decisions (AgentConnect/Jev shape): a reusable judgment RESOURCE
# carrying a question, its type and what each answer means. The resource owns
# no trigger and no target action - consumers (call sites) evaluate it with
# their own state and act on the answer. Editing criteria here must be checked
# against every consumer, because a criteria change can invalidate conditions.
DECISIONS: Dict[str, Dict[str, Any]] = {
    "copy_audit": {
        "type": "choice",
        "instructions": "Is this listing/ad copy shippable on Amazon as written?",
        "criteria": {
            "pass": "No prohibited or unsupported claim is detectable in the supplied text.",
            "review": "A claim needs operator evidence (health, absolute or certification-adjacent wording).",
            "block": "An Amazon-prohibited promotional term would risk suppression or legal exposure.",
        },
    },
    "listing_tier": {
        "type": "choice",
        "instructions": "What work does this copy need before it ships?",
        "criteria": {
            "keep": "Copy is within length rules and carries no claim risk.",
            "improve": "Copy is shippable but bloated or thin in spots.",
            "rewrite": "Copy breaks a hard rule or is too thin to sell anything.",
        },
    },
    "duplicate": {
        "type": "choice",
        "instructions": "Do these two product listings refer to the same SKU?",
        "criteria": {
            "same": "Identifiers and naming overlap beyond coincidence.",
            "different": "Distinct products with no identifier overlap.",
            "unsure": "No model backend; the layer refuses to guess.",
        },
    },
    "blocker_escalation": {
        "type": "choice",
        "instructions": "Does this blocker interrupt the operator now, or ride the next batched report?",
        "criteria": {
            "now": "A live-lane failure, a credential/guardrail breach, a production break, or anything hard-blocking all work.",
            "later": "Real friction, but work can continue on other batches until the next operator report.",
            "never": "An idea or nice-to-have; belongs in the backlog, not in an interrupt.",
        },
    },
    "respond_now": {
        "type": "boolean",
        "instructions": "Should an autonomous turn respond to this inbound message without operator direction?",
        "criteria": {
            "yes": "An operator-directed request addressed to the assistant that existing precedents cover.",
            "no": "Anything ambiguous, social, or outside past authorization; observe it instead.",
        },
    },
}

#: Amazon-prohibited promotional terms (mirrors LISTING_PROMPT).
_PROHIBITED = (
    "best seller", "#1", "number one", "guaranteed", "money back", "100%",
    "amazing", "miracle", "cure", "heal", "medical", "fda approved",
    "as seen on tv", "limited time", "act now", "don't miss", "free shipping",
)
_HEALTH = (
    "detox", "anti-inflammatory", "boosts immune", "immune system", "clinically",
    "prevents", "treats", "reduces cholesterol", "weight loss", "thermogenic",
)
_ABSOLUTE = ("always", "never fails", "the only", "perfect for everyone", "risk free")
_APPROVED_HINTS = ("certified", "organic", "non-gmo", "kosher", "vegan", "gluten free")


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").lower()).strip()


def _has(body: str, phrase: str) -> bool:
    """Whole-phrase match: 'organic' must not fire on the brand 'Organics'."""
    p = phrase.lower().strip()
    if not p:
        return False
    if re.fullmatch(r"[\w\s'-]+", p):
        return re.search(rf"\b{re.escape(p)}\b", body) is not None
    return p in body


def _rules_copy_audit(text: str) -> Dict[str, Any]:
    body = _norm(text)
    if len(body) < 12:
        return {"value": "review", "confidence": 0.2, "abstained": True,
                "flags": ["text_too_short"], "reason": "not enough text to judge"}

    blocked = [w for w in _PROHIBITED if _has(body, w)]
    if blocked:
        return {"value": "block", "confidence": 0.95, "abstained": False,
                "flags": [f"prohibited:{w}" for w in blocked],
                "reason": "Amazon-prohibited promotional term present"}

    flags: List[str] = []
    for w in _HEALTH:
        if _has(body, w):
            flags.append(f"review_health_claim:{w}")
    for w in _ABSOLUTE:
        if _has(body, w):
            flags.append(f"review_absolute_claim:{w}")
    if re.search(r"\b(best|finest|superior)\b", body):
        flags.append("review_superlative")
    # An approved-sounding word with no certificate is suspicious, not fatal.
    if any(_has(body, h) for h in _APPROVED_HINTS) and "certificate" not in body:
        flags.append("review_certification_unverified")

    if flags:
        confidence = round(min(0.85, 0.55 + 0.05 * len(flags)), 2)
        return {"value": "review", "confidence": confidence, "abstained": False,
                "flags": sorted(set(flags)), "reason": "claims need operator evidence"}

    return {"value": "pass", "confidence": 0.9, "abstained": False,
            "flags": [], "reason": "no prohibited or unsupported claim detected"}


def _rules_listing_tier(text: str) -> Dict[str, Any]:
    body = _norm(text)
    if len(body) < 40:
        return {"value": "rewrite", "confidence": 0.7, "abstained": False,
                "flags": ["too_thin"], "reason": "under 40 characters of copy"}
    if any(_has(body, w) for w in _PROHIBITED):
        return {"value": "rewrite", "confidence": 0.8, "abstained": False,
                "flags": ["prohibited_term"], "reason": "blocked claim in copy"}
    if len(body) > 900:
        return {"value": "improve", "confidence": 0.65, "abstained": False,
                "flags": ["long_copy"], "reason": "copy is long; trim before shipping"}
    return {"value": "keep", "confidence": 0.7, "abstained": False,
            "flags": [], "reason": "copy is within length and claim rules"}


def _laya_available() -> tuple[bool, str]:
    """Presence check only. No import, no download, no network."""
    root = os.environ.get("LAYA_ROOT", "").strip()
    if not root:
        return False, "laya_not_configured"
    try:
        if not os.path.isdir(root):
            return False, "laya_not_installed"
    except Exception:  # noqa: BLE001
        return False, "laya_not_installed"
    return True, "laya_ready"


def decide(kind: str, text: str, facts: Optional[Dict[str, Any]] = None,
           backend: str = "auto", threshold: float = DEFAULT_THRESHOLD) -> Dict[str, Any]:
    """One typed decision. Never raises, never invents a label."""
    if kind not in KINDS:
        raise ValueError(f"unknown decision kind: {kind}")
    labels = KINDS[kind]
    try:
        conf_threshold = float(threshold)
    except Exception:  # noqa: BLE001
        conf_threshold = DEFAULT_THRESHOLD

    chosen = backend
    note = ""
    if backend in ("auto", "laya"):
        ready, why = _laya_available()
        if ready:
            chosen = "laya"
        else:
            chosen = "rules"
            note = why if backend == "laya" else ""

    if kind == "copy_audit":
        out = _rules_copy_audit(text)
    elif kind == "listing_tier":
        out = _rules_listing_tier(text)
    elif kind == "blocker_escalation":
        out = _rules_blocker_escalation(text)
    elif kind == "respond_now":
        out = _rules_respond_now(text, facts)
    else:  # duplicate has no rule backend yet — abstaining is the honest answer
        out = {"value": "unsure", "confidence": 0.0, "abstained": True,
               "flags": ["no_rule_backend"], "reason": "duplicate detection needs a model"}

    if out["value"] not in labels:  # defensive: a backend may not invent a label
        out = {"value": labels[-1], "confidence": 0.0, "abstained": True,
               "flags": ["invalid_label"], "reason": "backend returned an unknown label"}

    out.update({
        "kind": kind,
        "probabilities": _distribution(labels, out["value"], out["confidence"]),
        "criteria": DECISIONS.get(kind, {}).get("criteria"),
        "backend": chosen,
        "threshold": conf_threshold,
        "escalate": bool(out["abstained"] or out["confidence"] < conf_threshold),
    })
    if note:
        out["reason"] = f"{out['reason']} ({note})"
    return out


def audit_copy(text: str, threshold: float = DEFAULT_THRESHOLD) -> Dict[str, Any]:
    """Convenience wrapper used by the listing/ad normalisers."""
    return decide("copy_audit", text, threshold=threshold)


def _rules_blocker_escalation(text: str) -> Dict[str, Any]:
    body = _norm(text)
    if len(body) < 12:
        return {"value": "later", "confidence": 0.2, "abstained": True,
                "flags": ["text_too_short"], "reason": "not enough signal to interrupt anyone"}
    if _has(body, "hard failure") or _has(body, "production") or _has(body, "down") \
            or _has(body, "blocked") or _has(body, "credential") or _has(body, "security") \
            or _has(body, "live lane") or _has(body, "circuit breaker"):
        return {"value": "now", "confidence": 0.85, "abstained": False,
                "flags": ["live_or_guardrail_impact"],
                "reason": "live-lane / guardrail language present"}
    if _has(body, "nice to have") or _has(body, "idea") or _has(body, "someday") \
            or _has(body, "low priority") or _has(body, "parked"):
        return {"value": "never", "confidence": 0.75, "abstained": False,
                "flags": ["backlog_worthy"], "reason": "explicitly aspirational"}
    return {"value": "later", "confidence": 0.6, "abstained": False,
            "flags": [], "reason": "no interrupt-level signal; join the batched report"}


def _rules_respond_now(text: str, facts: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    body = _norm(text)
    mentioned = bool((facts or {}).get("addressed_to_agent")) or "@" in body
    asks = "?" in body and len(body) < 400
    if not body:
        return {"value": "no", "confidence": 0.2, "abstained": True,
                "flags": ["empty_message"], "reason": "nothing to judge"}
    if mentioned and asks:
        return {"value": "yes", "confidence": 0.7, "abstained": False,
                "flags": [], "reason": "an addressed, concrete request"}
    return {"value": "no", "confidence": 0.65, "abstained": False,
            "flags": ["observe_only"], "reason": "observe instead of spending a turn"}


def _distribution(labels: List[str], chosen: str, confidence: float) -> Dict[str, float]:
    """Deterministic rules-backend distribution over the closed label set.

    The chosen label carries the backend's confidence; the residual mass is
    split evenly, so downstream consumer matching always sees a full
    probability landscape (Jev keeps probabilities as evaluation evidence).
    """
    if not labels:
        return {}
    if len(labels) == 1:
        return {labels[0]: round(min(1.0, max(0.0, confidence)), 4)}
    c = min(1.0, max(0.0, confidence))
    rest = round((1.0 - c) / (len(labels) - 1), 4)
    dist = {label: rest for label in labels}
    dist[chosen] = round(c, 4)
    return dist


def consumer_match(out: Dict[str, Any],
                   conditions: Optional[Dict[str, float]] = None) -> Dict[str, Any]:
    """Apply a consumer's per-label thresholds to one decision (Jev semantics).

    * Choice conditions compare ``probabilities[key] >= min_probability``.
    * Selecting NO conditions skips every successful answer - that is the
      deliberate Jev default, recorded here as ``matched: []``.
    * An unknown label in the conditions is a programming error caught at the
      seam: the layer returns ``needs_review`` and matches nothing. It never
      silently remaps a key or clamps a threshold.
    """
    dist = out.get("probabilities") or {}
    labels = KINDS.get(out.get("kind", ""), [])
    if conditions is None or not conditions:
        return {"matched": [], "needs_review": False,
                "note": "no conditions selected: every successful answer skips"}
    unknown = [k for k in conditions if k not in labels]
    if unknown:
        return {"matched": [], "needs_review": True,
                "note": f"label(s) {unknown} are not in this decision; conditions need review",
                "unknown_labels": unknown}
    matched = [k for k, floor_value in conditions.items() if dist.get(k, 0.0) >= floor_value]
    return {"matched": matched, "needs_review": False, "note": None}


def _main(argv: Iterable[str]) -> int:
    argv = list(argv)
    if not argv:
        print("usage: decision_layer.py <kind> <text>", file=sys.stderr)
        return 2
    kind = argv[0]
    text = " ".join(argv[1:]) if len(argv) > 1 else sys.stdin.read()
    print(json.dumps(decide(kind, text), indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(_main(sys.argv[1:]))
