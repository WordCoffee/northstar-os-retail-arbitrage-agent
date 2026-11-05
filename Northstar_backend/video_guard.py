"""Human-feature guardrail for generated video.

Wan-class video models produce unreliable faces, hands and bodies. The product
rule is: product-centric visuals by default; a prompt that asks for human
features is intercepted with a warning, and only an explicit acknowledgement
lets it through. This is an advisory gate with an override, not a silent
refusal — the owner decides when the risk is acceptable.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import time
import uuid
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

WARNING = ("Generations with human features and hands may generate poor results. "
           "We recommend ads that do not have these types of generations for a "
           "better overall product.")

AUDIT_DIR = Path(os.environ.get("NORTHSTAR_AUDIT_DIR")
                 or Path(__file__).resolve().parents[1] / "state" / "audit")

HUMAN_FEATURE_TERMS: tuple = (
    "face", "faces", "facial", "hand", "hands", "finger", "fingers", "arm", "arms",
    "leg", "legs", "body", "bodies", "person", "people", "human", "humans",
    "man", "men", "woman", "women", "child", "children", "baby", "babies",
    "model", "models", "actor", "actress", "dancer", "crowd", "portrait",
    "selfie", "skin", "smile", "eyes", "mouth",
)

_PATTERNS = tuple((term, re.compile(rf"\b{re.escape(term)}\b", re.IGNORECASE))
                  for term in HUMAN_FEATURE_TERMS)


def matched_terms(prompt: str) -> List[str]:
    text = str(prompt or "")
    return sorted({term for term, pattern in _PATTERNS if pattern.search(text)})


def check_prompt(prompt: str, *, acknowledged: bool = False) -> Dict[str, Any]:
    """Decide whether a video prompt needs the human-feature warning.

    ``blocked`` is true only when human terms are present and the caller has not
    acknowledged the warning. The warning is returned either way so a client can
    display it before asking for the override.
    """
    matched = matched_terms(prompt)
    requires = bool(matched)
    return {
        "requires_override": requires,
        "acknowledged": bool(acknowledged),
        "blocked": bool(requires and not acknowledged),
        "matched": matched,
        "warning": WARNING if requires else "",
    }


def guard_detail(prompt: str, *, acknowledged: bool = False) -> Dict[str, Any]:
    """The 422 body for an unacknowledged human-feature prompt."""
    report = check_prompt(prompt, acknowledged=acknowledged)
    report["code"] = "human_features_warning"
    return report


def audit_override(account: str, surface: str, prompt: str, matched: List[str],
                   acknowledged: bool, *, audit_dir: Optional[Path] = None) -> Dict[str, Any]:
    """Append one audit record for a human-feature decision (best effort).

    The prompt is stored as a hash plus a short prefix: enough to audit the
    decision without keeping a full customer brief in a second place. A failed
    audit write never blocks the render.
    """
    directory = Path(audit_dir or AUDIT_DIR)
    record = {
        "id": "hf_" + uuid.uuid4().hex[:12],
        "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "account": str(account or "operator"),
        "surface": str(surface or "video"),
        "acknowledged": bool(acknowledged),
        "matched": list(matched or []),
        "prompt_sha256": hashlib.sha256(str(prompt or "").encode("utf-8")).hexdigest(),
        "prompt_prefix": str(prompt or "")[:200],
    }
    try:
        directory.mkdir(parents=True, exist_ok=True)
        with (directory / "human_features_overrides.jsonl").open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
        record["written"] = True
    except OSError as exc:  # noqa: BLE001 - never block the render
        record["written"] = False
        record["error"] = str(exc)[:200]
    return record


__all__ = ["WARNING", "HUMAN_FEATURE_TERMS", "check_prompt", "guard_detail",
           "audit_override", "matched_terms"]
