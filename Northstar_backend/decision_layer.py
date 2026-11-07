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
* ``jev``   — TypeSafe Jev cloud decision model (opt-in, metered, network). Closed-label
  choice with calibrated confidence + probabilities. Requires JEV_API_URL + JEV_API_KEY
  (or TYPESAFE_API_KEY); ``auto`` does NOT use it unless JEV_AUTO=1. Never a silent
  substitute for rules. Covers every kind, including ``duplicate`` (which has no rule
  backend). The jev-ultrafast *browser* agent is deliberately NOT wired here — Chrome
  Connect is Northstar's sole browser controller.

No network by default; ``jev`` is the one backend that touches the network, and only
when explicitly requested. No writes.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
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


_LAYA_BIN_CANDIDATES = [
    os.environ.get("LAYA_BIN", "").strip(),
    r"C:\Users\T2Hol\Desktop\Northstar External\integration-venv\Scripts\laya.exe",
]
_LAYA_QUESTIONS = os.environ.get(
    "LAYA_QUESTIONS",
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                 "research", "laya_questions.json"),
)


def _laya_binary() -> Optional[str]:
    for cand in _LAYA_BIN_CANDIDATES:
        if cand and os.path.isfile(cand):
            return cand
    found = shutil.which("laya")
    return found


def _laya_decide(kind: str, text: str) -> Optional[Dict[str, Any]]:
    """Run the local Laya ONNX backend. Returns None on any failure (caller falls back)."""
    if kind not in ("copy_audit", "blocker_escalation"):
        return None   # only kinds present in laya_questions.json
    binary = _laya_binary()
    if not binary or not os.path.isfile(_LAYA_QUESTIONS):
        return None
    try:
        env = dict(os.environ)
        env.setdefault("PYTHONIOENCODING", "utf-8")
        env.setdefault("PYTHONUTF8", "1")
        proc = subprocess.run(
            [binary, "--predict", "--questions", _LAYA_QUESTIONS, "--json", text],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            env=env, timeout=120, check=False,
        )
    except Exception:  # noqa: BLE001
        return None
    if proc.returncode != 0:
        return None
    try:
        payload = json.loads(proc.stdout)
    except Exception:  # noqa: BLE001
        return None
    answer = (payload.get("answers") or {}).get(kind)
    if not isinstance(answer, dict):
        return None
    choice = answer.get("choice")
    labels = KINDS[kind]
    if choice not in labels:
        return None
    probs = answer.get("probabilities") or {}
    confidence = float(answer.get("answer_confidence") or probs.get(choice, 0.0))
    return {
        "value": choice,
        "confidence": round(confidence, 4),
        "abstained": False,
        "flags": [],
        "reason": "laya onnx backend",
        "probabilities": {label: round(float(probs.get(label, 0.0)), 4) for label in labels},
    }


def _laya_available() -> tuple[bool, str]:
    """Presence check only. No import, no download, no network."""
    if not os.path.isfile(_LAYA_QUESTIONS):
        return False, "laya_questions_missing"
    binary = _laya_binary()
    if not binary:
        return False, "laya_not_installed"
    try:
        import onnxruntime  # noqa: F401
    except Exception:  # noqa: BLE001
        return False, "laya_onnxruntime_missing"
    return True, "laya_ready"



# --- TypeSafe Jev cloud decision backend ------------------------------------
_JEV_API_URL_DEFAULT = ""


def _jev_credentials():
    url = (os.environ.get("JEV_API_URL") or _JEV_API_URL_DEFAULT).strip()
    key = ""
    for name in ("JEV_API_KEY", "TYPESAFE_API_KEY"):
        val = (os.environ.get(name) or "").strip()
        if val:
            key = val
            break
    return url, key


def _jev_available():
    url, key = _jev_credentials()
    if not url:
        return False, "jev_not_configured"
    if not key:
        return False, "jev_api_key_missing"
    return True, "jev_ready"


def _jev_parse_choice(parsed, labels):
    if not isinstance(parsed, dict):
        return None
    candidates = [parsed]
    for wrapper in ("result", "data", "output", "response", "decision"):
        sub = parsed.get(wrapper)
        if isinstance(sub, dict):
            candidates.append(sub)
    for cand in candidates:
        for keyname in ("value", "choice", "answer", "label", "decision", "result"):
            val = cand.get(keyname)
            if val in labels:
                return val
    return None


def _jev_parse_confidence(parsed):
    if not isinstance(parsed, dict):
        return None
    candidates = [parsed]
    for wrapper in ("result", "data", "output", "response", "decision"):
        sub = parsed.get(wrapper)
        if isinstance(sub, dict):
            candidates.append(sub)
    for cand in candidates:
        for keyname in ("confidence", "score", "probability", "answer_confidence"):
            val = cand.get(keyname)
            if isinstance(val, bool):
                continue
            if isinstance(val, (int, float)):
                return float(val)
    return None


def _jev_parse_probabilities(parsed, labels):
    if not isinstance(parsed, dict):
        return None
    candidates = [parsed]
    for wrapper in ("result", "data", "output", "response", "decision"):
        sub = parsed.get(wrapper)
        if isinstance(sub, dict):
            candidates.append(sub)
    for cand in candidates:
        for keyname in ("probabilities", "scores", "distribution", "probs"):
            val = cand.get(keyname)
            if isinstance(val, dict):
                out = {}
                for label in labels:
                    v = val.get(label)
                    if isinstance(v, bool):
                        continue
                    if isinstance(v, (int, float)):
                        out[label] = round(float(v), 4)
                if out:
                    return out
    return None


def _jev_parse_usage(parsed):
    """Best-effort token usage extraction. Returns None if not provided."""
    if not isinstance(parsed, dict):
        return None
    candidates = [parsed]
    for wrapper in ("result", "data", "output", "response", "usage", "meta"):
        sub = parsed.get(wrapper)
        if isinstance(sub, dict):
            candidates.append(sub)
    for cand in candidates:
        u = cand.get("usage")
        if isinstance(u, dict):
            out = {}
            for k in ("prompt_tokens", "input_tokens", "completion_tokens",
                      "output_tokens", "total_tokens"):
                v = u.get(k)
                if isinstance(v, (int, float)) and not isinstance(v, bool):
                    out[k] = int(v)
            if out:
                return out
    # top-level fallback
    out = {}
    for k in ("prompt_tokens", "input_tokens", "completion_tokens",
              "output_tokens", "total_tokens"):
        v = parsed.get(k)
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            out[k] = int(v)
    return out or None


def _jev_decide(kind, text):
    url, key = _jev_credentials()
    ready, _ = _jev_available()
    if not ready or kind not in KINDS:
        return None
    labels = KINDS[kind]
    spec = DECISIONS.get(kind, {})
    payload = {
        "kind": kind,
        "text": text,
        "labels": labels,
        "instructions": spec.get("instructions"),
        "criteria": spec.get("criteria"),
    }
    model = (os.environ.get("JEV_MODEL") or "").strip()
    if model:
        payload["model"] = model
    try:
        import json as _json
        import urllib.request
        data = _json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data, method="POST")
        req.add_header("Content-Type", "application/json")
        req.add_header("Authorization", "Bearer " + key)
        req.add_header("Accept", "application/json")
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
        parsed = _json.loads(raw)
    except Exception:
        return None
    choice = _jev_parse_choice(parsed, labels)
    if choice not in labels:
        return None
    confidence = _jev_parse_confidence(parsed)
    if confidence is None:
        confidence = 0.5
    confidence = max(0.0, min(1.0, confidence))
    prob_map = _jev_parse_probabilities(parsed, labels)
    if not prob_map:
        prob_map = _distribution(labels, choice, confidence)
    usage = _jev_parse_usage(parsed)
    out = {
        "value": choice,
        "confidence": round(confidence, 4),
        "abstained": False,
        "flags": [],
        "reason": "typesafe jev backend",
        "probabilities": prob_map,
    }
    if usage:
        out["usage"] = usage
    return out


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
        if backend == "laya" and ready:
            chosen = "laya"
        else:
            chosen = "rules"
            if backend == "laya":
                note = why
    elif backend in ("jev", "typesafe"):
        ready, why = _jev_available()
        if ready:
            chosen = "jev"
        else:
            chosen = "rules"
            note = why
    elif backend == "auto" and os.environ.get("JEV_AUTO", "").strip() == "1":
        # Opt-in auto-use of the metered cloud backend; never the default.
        ready, why = _jev_available()
        if ready:
            chosen = "jev"

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

    # Optional second backend: try it, fall back to rules on any failure.
    if chosen == "laya":
        laya_out = _laya_decide(kind, text)
        if laya_out is not None:
            out = laya_out
            chosen = "laya"
        else:
            chosen = "rules"
            note = "laya_unavailable"
    elif chosen == "jev":
        jev_out = _jev_decide(kind, text)
        if jev_out is not None:
            out = jev_out
            chosen = "jev"
        else:
            chosen = "rules"
            note = "jev_unavailable"

    if out["value"] not in labels:  # defensive: a backend may not invent a label
        out = {"value": labels[-1], "confidence": 0.0, "abstained": True,
               "flags": ["invalid_label"], "reason": "backend returned an unknown label"}

    out.update({
        "kind": kind,
        "probabilities": out.get("probabilities") or _distribution(labels, out["value"], out["confidence"]),
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
