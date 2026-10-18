"""Brand SEO Profile body validation (V3 S7).

Kept separate from the data layer so the rule set is one source of truth and
unit-testable in isolation. Honesty rules:

  • A profile body is a JSON object.
  • Known sections must have the right CONTAINER shape when present (we do not
    invent values; we refuse a shape we cannot honour).
  • Unknown top-level keys are PRESERVED (forward-compatible), never dropped or
    coerced — a silent drop would be a lie about what the profile contains.
  • Nothing is ever filled in for the operator: absence stays absence.
"""

from __future__ import annotations

from typing import Any, Dict, Tuple

# Sections the SEO engine reads by name (S7 §5.1). Extra keys ride along.
OBJECT_OR_LIST = ("entities", "keyword_clusters", "prohibited_claims", "provenance")
STRING_FIELDS = ("name", "notes")


def normalize_body(body: Any) -> Tuple[bool, Any]:
    """Return (ok, normalized_dict) or (False, error_message)."""
    if body is None:
        return True, {}
    if not isinstance(body, dict):
        return False, "profile body must be a JSON object"
    for k in STRING_FIELDS:
        if k in body and body[k] is not None and not isinstance(body[k], str):
            return False, f"'{k}' must be a string"
    for k in OBJECT_OR_LIST:
        if k in body and body[k] is not None and not isinstance(body[k], (dict, list)):
            return False, f"'{k}' must be an object or a list"
    # voice_rules are naturally prose OR a structured object/list.
    if "voice_rules" in body and body["voice_rules"] is not None \
            and not isinstance(body["voice_rules"], (str, dict, list)):
        return False, "'voice_rules' must be text, an object, or a list"
    if "competitors" in body and body["competitors"] is not None \
            and not isinstance(body["competitors"], list):
        return False, "'competitors' must be a list"
    out: Dict[str, Any] = {}
    out.update(body)  # shallow copy: keep every supplied key
    return True, out
