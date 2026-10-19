"""Privacy boundaries (Thorn v5.0 §Continuous Learning & Extreme Data Privacy).

Two hard, local, testable boundaries:

    external_routing_decision(payload, ...)   may this leave the machine at all?
    scrub_telemetry(metrics)                  the only shape operational metrics
                                              may be aggregated in

Honesty contract
----------------
* The consent gate **fails closed**: external routing is denied unless it is
  explicitly allowed for this call AND the payload carries no sensitive marker.
* A marker is reported by KIND and LENGTH only. The matched value is never
  returned, logged or previewed — a scanner that echoes the secret it found is a
  leak with extra steps.
* `scrub_telemetry` does redaction (drop identifiers) plus Laplace noise on
  numeric aggregates. The plan calls this "local differential privacy". What is
  actually implemented is redaction + noisy aggregation over data that never
  leaves the machine. It is **not** a formally guaranteed DP mechanism, and the
  report says so instead of borrowing the term.
* This module contains no network code. Nothing here transmits anything.
"""
from __future__ import annotations

import math
import random
import re
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

# ── sensitive markers (kind, pattern). Values are NEVER returned. ────────────
SENSITIVE: Sequence[Tuple[str, re.Pattern]] = (
    ("env_assignment", re.compile(r"\b[A-Z][A-Z0-9_]{2,}\s*=\s*\S+")),
    ("api_key_like", re.compile(r"\b(?:sk|pk|ghp|gho|xox[baprs])[-_][A-Za-z0-9._-]{12,}")),
    ("bearer_token", re.compile(r"\bbearer\s+[A-Za-z0-9._-]{12,}", re.I)),
    ("email", re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.]{2,}\b")),
    ("phone", re.compile(r"(?<!\d)(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}(?!\d)")),
    ("long_digit_run", re.compile(r"(?<!\d)\d{9,}(?!\d)")),
    ("windows_path", re.compile(r"[A-Za-z]:\\[^\s\"']{3,}")),
    ("secret_word", re.compile(r"\b(password|passwd|secret|credential|api[_-]?key|private[_-]?key)\b", re.I)),
    ("card_like", re.compile(r"(?<!\d)(?:\d[ -]?){13,19}(?!\d)")),
)

# Identifier-ish keys that must never appear in an aggregated metric surface.
IDENTIFIER_KEYS: frozenset = frozenset({
    "account_id", "org_id", "organization_id", "user_id", "tenant_id", "session_id",
    "email", "phone", "name", "customer", "brand", "product", "asin", "sku", "upc",
    "url", "uri", "path", "file", "filename", "query", "prompt", "content", "text",
    "message", "token", "key", "secret", "cookie", "header", "host", "ip",
})

_NUMERIC = (int, float)


def scan(payload: str) -> List[Dict[str, Any]]:
    """Kinds of sensitive marker present. Never returns a matched value."""
    text = payload or ""
    found: List[Dict[str, Any]] = []
    for kind, pattern in SENSITIVE:
        for m in pattern.finditer(text):
            found.append({"kind": kind, "length": len(m.group(0)), "at": m.start()})
            break                      # one report per kind is enough to block
    return sorted(found, key=lambda f: f["kind"])


def external_routing_decision(payload: str, *, allow_external: bool = False,
                              purpose: str = "") -> Dict[str, Any]:
    """May this payload be sent to an external model/provider? Fails closed."""
    markers = scan(payload)
    if not allow_external:
        return {
            "allowed": False,
            "reason": ("External routing is not enabled for this call. Local lanes are "
                       "the default; an external route needs explicit per-call consent."),
            "blocked_by": "consent_not_granted",
            "markers": markers,
            "purpose": purpose,
        }
    if markers:
        return {
            "allowed": False,
            "reason": ("Consent was granted but the payload carries "
                       f"{len(markers)} sensitive marker(s); it must be redacted first."),
            "blocked_by": "sensitive_content",
            "marker_kinds": [m["kind"] for m in markers],
            "markers": markers,
            "purpose": purpose,
        }
    return {
        "allowed": True,
        "reason": "Consent granted and no sensitive marker found.",
        "blocked_by": None,
        "markers": [],
        "purpose": purpose,
    }


def _laplace(scale: float, rng: random.Random) -> float:
    u = rng.random() - 0.5
    return -scale * math.copysign(math.log(1 - 2 * abs(u)), u)


def scrub_telemetry(metrics: Dict[str, Any], *, epsilon: float = 1.0,
                    sensitivity: float = 1.0,
                    rng: Optional[random.Random] = None) -> Dict[str, Any]:
    """Redact identifiers, bucket text, and add Laplace noise to numeric aggregates."""
    rnd = rng or random.Random(0)
    scale = max(sensitivity, 0.0) / max(epsilon, 0.01)
    scrubbed: Dict[str, Any] = {}
    dropped: List[str] = []
    noisy: List[str] = []

    for key, value in (metrics or {}).items():
        low = str(key).lower()
        if low in IDENTIFIER_KEYS or any(tok in low for tok in ("id", "email", "url", "name")):
            dropped.append(str(key))
            continue
        if isinstance(value, bool) or value is None:
            scrubbed[key] = value
        elif isinstance(value, _NUMERIC):
            n = float(value)
            if abs(n - round(n)) < 1e-9:                 # counts: bucket coarsely
                bucketed = int(round(n / 5.0) * 5)
                scrubbed[key] = max(0, bucketed)
            else:
                scrubbed[key] = round(n + _laplace(scale, rnd), 3)
                noisy.append(str(key))
        elif isinstance(value, str):
            if scan(value):
                dropped.append(str(key))
                continue
            scrubbed[key] = f"len:{min(len(value), 999)}"   # text becomes a shape
        elif isinstance(value, (list, tuple)):
            scrubbed[key] = f"items:{min(len(value), 999)}"
        elif isinstance(value, dict):
            scrubbed[key] = f"keys:{min(len(value), 999)}"
        else:
            dropped.append(str(key))

    return {
        "scrubbed": scrubbed,
        "dropped_keys": sorted(dropped),
        "noise_applied_to": sorted(noisy),
        "epsilon": epsilon,
        "method": ("identifier redaction + text bucketing + Laplace noise on non-integer "
                   "numeric aggregates; counts bucketed to the nearest 5"),
        "formal_dp": False,
        "note": ("This is redaction plus noisy aggregation over data that never leaves "
                 "the machine. It is NOT a formally guaranteed differential-privacy "
                 "mechanism and is not described as one."),
    }


def consent_report(payloads: Iterable[Tuple[str, str]]) -> Dict[str, Any]:
    """Batch view: (name, payload) pairs → per-item decision, no values echoed."""
    items = [{"name": name, **external_routing_decision(p, allow_external=False)}
             for name, p in payloads]
    blocked = [i["name"] for i in items if not i["allowed"]]
    return {
        "items": items,
        "blocked": blocked,
        "allowed": [i["name"] for i in items if i["allowed"]],
        "summary": f"{len(blocked)} of {len(items)} payload(s) blocked by default (local-only posture).",
    }
