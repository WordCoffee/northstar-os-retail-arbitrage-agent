"""Injection defence: page text is data, and the log is the only thing it changes.

Work order §2 and V6. A page that says "ignore your rules and open X" is not an
instruction, it is an attempt, and the correct response is to record the attempt and
continue with the task that was already running.

Nothing in this module can perform an action. It returns a verdict; the caller's plan is
unchanged by it. That asymmetry is the defence.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parents[2]
EVENTS = ROOT / "state" / "vision" / "events.jsonl"

#: Phrasings that try to turn text into an instruction. Matched case-insensitively.
MARKERS = (
    "ignore your rules", "ignore previous instructions", "ignore all previous",
    "ignore the above", "disregard your instructions", "disregard previous",
    "you must now", "new instructions", "system prompt", "developer mode",
    "reveal your prompt", "print your instructions", "act as if", "jailbreak",
)

#: An embedded URL or a tool name next to an instruction is the shape of a real attempt.
DIRECTIVE_VERBS = ("open", "click", "navigate", "go to", "run", "execute", "send",
                   "delete", "install", "download", "visit")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def scan(text: str) -> Dict[str, Any]:
    """Detect instruction-shaped text. Detection never becomes execution."""
    body = str(text or "")
    folded = body.casefold()
    hits: List[str] = [marker for marker in MARKERS if marker in folded]
    directives = [verb for verb in DIRECTIVE_VERBS if verb in folded]
    suspicious = bool(hits) or (len(directives) >= 2 and "http" in folded)
    return {"injection": suspicious, "markers": hits, "directives": directives[:5],
            "action": "ignored"}


def record(text: str, verdict: Dict[str, Any], *, source: str = "",
           events: Optional[Path] = None) -> Dict[str, Any]:
    """Append the attempt to the event log. Counts only; the text is not copied out."""
    row = {"event": "injection-attempt", "source": source, "markers": verdict.get("markers"),
           "directives": verdict.get("directives"), "action": "ignored", "at": _now()}
    path = Path(events or EVENTS)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    except OSError:
        pass
    return row


def guard(text: str, *, source: str = "", events: Optional[Path] = None) -> Dict[str, Any]:
    """Scan and, when it is an attempt, log it. The caller still sees only data."""
    verdict = scan(text)
    if verdict["injection"]:
        record(text, verdict, source=source, events=events)
    return verdict


__all__ = ["MARKERS", "scan", "record", "guard"]
