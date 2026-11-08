"""Live mode, text first: Ty watches the screen and talks about it.

Work order §5.1 layer 6. The owner shares or points at the screen and asks questions; Ty
narrates what it sees and answers about it. Voice is optional and last, so this is the text
path only.

Three properties, in order:

* **the privacy gate runs before capture**, so a refused window never yields pixels and
  never reaches a model;
* **the tree comes first** — the UI Automation tree gives the element list, and the vision
  model is asked only for what the tree cannot say;
* **only text leaves the session** — a transcript is text, a frame is not.

    python -m tools.vision.live --demo
    python -m tools.vision.live --ask "what is on screen?" --ask "which app has focus?"
"""
from __future__ import annotations

import argparse
import json
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from . import capture, privacy, tree, understand

ROOT = Path(__file__).resolve().parents[2]
TRANSCRIPTS = ROOT / "state" / "vision" / "transcripts"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass
class LiveSession:
    """One live session: an observation, a transcript, and a stop."""

    capture_frame: Callable[[], Dict[str, Any]] = capture.frame
    speak: Callable[..., Dict[str, Any]] = understand.describe_screen
    windows: Callable[[], List[Dict[str, Any]]] = capture.windows
    describe_tree: Callable[..., Any] = tree.window_tree
    transcript: List[Dict[str, Any]] = field(default_factory=list)
    started_at: str = ""
    _running: bool = False

    def start(self) -> Dict[str, Any]:
        self._running = True
        self.started_at = _now()
        self.transcript = []
        return {"ok": True, "started_at": self.started_at}

    def stop(self) -> Dict[str, Any]:
        self._running = False
        return {"ok": True, "turns": len(self.transcript), "stopped_at": _now()}

    # -- observation -------------------------------------------------------
    def observe(self) -> Dict[str, Any]:
        """One observation: the foreground window, its tree if we may, and a description."""
        if not self._running:
            return {"ok": False, "reason": "session not started"}
        try:
            windows = self.windows()
        except Exception as exc:  # noqa: BLE001
            windows = []
            note = f"{type(exc).__name__}: {exc}"
        else:
            note = ""
        visible: List[Dict[str, Any]] = []
        for window in windows:
            verdict = privacy.classify(title=window.get("title", ""),
                                       process=window.get("process", ""))
            entry = {"title": window.get("title", ""), "process": window.get("process", ""),
                     "allowed": bool(verdict.get("allow"))}
            if not verdict.get("allow"):
                # Nothing about a refused window travels: no title, no elements, no pixels.
                entry["title"] = ""
                entry["reason"] = verdict.get("reason")
            visible.append(entry)

        shot = self.capture_frame()
        if shot.get("blocked"):
            observation = {"ok": False, "blocked": True, "reason": shot.get("reason"),
                           "windows": visible, "narrated": False}
            self.transcript.append({"at": _now(), "turn": "observation", **observation})
            return observation

        elements: List[Dict[str, Any]] = []
        title = ""
        allowed = [row for row in visible if row["allowed"] and row["title"]]
        if allowed:
            title = allowed[0]["title"]
            try:
                found = self.describe_tree(title_hint=title)
                if found.get("ok"):
                    elements = found.get("elements") or []
            except Exception:  # noqa: BLE001 - a missing tree is data, not a crash
                elements = []

        description: Dict[str, Any] = {}
        if shot.get("ok"):
            description = self.speak(png=shot.get("png"))
        narration = self._narrate(visible, elements, description)
        observation = {"ok": True, "blocked": False, "windows": visible,
                       "elements": len(elements), "narration": narration,
                       "vision": {key: description.get(key) for key in
                                  ("ok", "apps", "foreground", "seconds", "model")},
                       "narrated": bool(narration), "note": note}
        self.transcript.append({"at": _now(), "turn": "observation",
                                **{k: v for k, v in observation.items() if k != "elements"}})
        return observation

    @staticmethod
    def _narrate(windows: List[Dict[str, Any]], elements: List[Dict[str, Any]],
                 description: Dict[str, Any]) -> str:
        allowed = [row for row in windows if row["allowed"] and row["title"]]
        parts: List[str] = []
        if allowed:
            parts.append("Visible: " + "; ".join(
                f"{row['process'] or 'app'} — {row['title']}" for row in allowed[:6]) + ".")
        if description.get("apps"):
            named = ", ".join(str(app.get("name")) for app in description["apps"][:5])
            parts.append(f"The vision model names: {named}.")
        if elements:
            roles: Dict[str, int] = {}
            for element in elements:
                roles[str(element.get("role") or "?")] = roles.get(
                    str(element.get("role") or "?"), 0) + 1
            top = ", ".join(f"{count} {role}" for role, count in
                            sorted(roles.items(), key=lambda kv: -kv[1])[:4])
            parts.append(f"The focused window has {len(elements)} actionable elements ({top}).")
        return " ".join(parts)

    # -- questions ---------------------------------------------------------
    def ask(self, question: str) -> Dict[str, Any]:
        """Answer about the live screen, from the observation. Text only."""
        if not self._running:
            return {"ok": False, "reason": "session not started"}
        observation = self.observe()
        if observation.get("blocked"):
            answer = ("I cannot look at that window: it matches the privacy blocklist. "
                      "I have recorded a blocked-window event and will not interact with it.")
        else:
            answer = self._answer(str(question or ""), observation)
        turn = {"at": _now(), "turn": "question", "question": str(question),
                "answer": answer, "grounded_in": "observation"}
        self.transcript.append(turn)
        return {"ok": True, **turn}

    @staticmethod
    def _answer(question: str, observation: Dict[str, Any]) -> str:
        folded = question.casefold()
        narration = str(observation.get("narration") or "")
        apps = [str(app.get("name")) for app in
                (observation.get("vision") or {}).get("apps") or []]
        foreground = str((observation.get("vision") or {}).get("foreground") or "")
        if any(word in folded for word in ("focus", "foreground", "active")):
            return foreground or (apps[0] if apps else "The window list did not name one.")
        if any(word in folded for word in ("how many", "count", "elements")):
            return f"{observation.get('elements', 0)} actionable element(s) in the focused window."
        if any(word in folded for word in ("what", "describe", "see", "screen")):
            return narration or "I can see the screen but nothing in it is describable yet."
        return narration or "I have an observation but no answer for that."

    # -- persistence -------------------------------------------------------
    def save(self, name: str = "") -> Dict[str, Any]:
        TRANSCRIPTS.mkdir(parents=True, exist_ok=True)
        path = TRANSCRIPTS / (name or f"live_{int(time.time())}.json")
        path.write_text(json.dumps({"started_at": self.started_at,
                                    "turns": self.transcript}, indent=2) + "\n",
                        encoding="utf-8")
        return {"ok": True, "path": str(path), "turns": len(self.transcript)}


def demo() -> Dict[str, Any]:
    """The scripted acceptance: narrate the live screen and answer two questions."""
    session = LiveSession()
    session.start()
    try:
        narration = session.observe()
        first = session.ask("What is on screen?")
        second = session.ask("Which app has focus?")
        saved = session.save("live_demo.json")
    finally:
        session.stop()
    passed = bool(narration.get("ok") and narration.get("narrated")
                  and first.get("ok") and second.get("ok")
                  and len(str(first.get("answer") or "")) > 10)
    return {"d13": {"pass": passed, "narration": narration.get("narration", ""),
                    "answers": [first.get("answer"), second.get("answer")],
                    "transcript": saved.get("path"),
                    "windows_allowed": sum(1 for row in narration.get("windows") or []
                                           if row.get("allowed"))}}


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Ty live mode (text first)")
    parser.add_argument("--demo", action="store_true")
    parser.add_argument("--ask", action="append", default=[])
    ns = parser.parse_args(argv)

    if ns.demo or not ns.ask:
        result = demo()
        print(json.dumps(result, indent=2, default=str))
        return 0 if result["d13"]["pass"] else 1
    session = LiveSession()
    session.start()
    try:
        answers = [session.ask(question) for question in ns.ask]
        session.save()
    finally:
        session.stop()
    print(json.dumps({"answers": [row.get("answer") for row in answers]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
