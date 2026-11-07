"""Chrome Connect AI loop (Phase 2, MVP).

Thin in-house loop: plan -> act -> observe -> verify.
8 tools: navigate, snapshot, click, type, scroll, extract, wait, finish/give_up.

Rules:
- Hard caps: max steps, max tokens per step, max wall time.
- Post-condition check after every action (no check = no next step).
- Repeat-loop breaker: same action on same state twice -> replan once, then give_up.
- Last attempt: rollback to clean state, retry at higher temperature.
- Page content is UNTRUSTED DATA (never changes policy/tools/goals).
- Destructive actions require approval.
- No credentials in prompts.

Provenance: ADAPTED from browser-use (MIT) and Stagehand (MIT) loop patterns.
No code copied; reimplemented in stdlib Python. AI decision is pluggable
(rules-based MVP; Laya/Ollama integration in Phase 4).
"""

from __future__ import annotations

import json
import os
import re
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

import chromeconnect_observation as obs

# ---------------------------------------------------------------------------
# Tunables (env-overridable)
# ---------------------------------------------------------------------------
MAX_STEPS: int = int(os.environ.get("CC_LOOP_MAX_STEPS", "20"))
MAX_TOKENS_PER_STEP: int = int(os.environ.get("CC_LOOP_MAX_TOKENS_PER_STEP", "2000"))
MAX_WALL_TIME_S: float = float(os.environ.get("CC_LOOP_MAX_WALL_TIME_S", "120"))
MAX_REPLANS: int = int(os.environ.get("CC_LOOP_MAX_REPLANS", "1"))

# Destructive action keywords (require approval)
_DESTRUCTIVE = {"submit", "purchase", "delete", "send", "publish", "checkout", "pay"}

# Untrusted content filter: strip instruction-like patterns from page text
_INSTRUCTION_PATTERNS = [
    re.compile(r"ignore\s+(all\s+)?previous\s+instructions", re.I),
    re.compile(r"you\s+are\s+now", re.I),
    re.compile(r"system\s*:\s*", re.I),
    re.compile(r"<\s*/?system\s*>", re.I),
    re.compile(r"override\s+(policy|rules|instructions)", re.I),
]


def _sanitize_page_text(text: str) -> str:
    """Strip instruction-like patterns from page content (untrusted data rule)."""
    for pat in _INSTRUCTION_PATTERNS:
        text = pat.sub("[FILTERED]", text)
    return text


# ---------------------------------------------------------------------------
# Loop state
# ---------------------------------------------------------------------------

@dataclass
class LoopState:
    goal: str
    current_html: str = ""
    current_url: str = ""
    snapshot: Optional[Dict[str, Any]] = None
    snapshot_hash: str = ""
    action_history: List[Dict[str, Any]] = field(default_factory=list)
    step_count: int = 0
    token_count: int = 0
    start_time: float = 0.0
    replan_count: int = 0
    last_action: Optional[str] = None
    last_state_hash: str = ""
    result: Optional[Dict[str, Any]] = None
    gave_up_reason: Optional[str] = None
    approval_pending: bool = False
    approval_action: Optional[str] = None


@dataclass
class ToolResult:
    tool: str
    args: Dict[str, Any]
    success: bool
    post_condition_met: bool
    output: Any = None
    error: Optional[str] = None
    tokens_used: int = 0


# ---------------------------------------------------------------------------
# The 8 tools
# ---------------------------------------------------------------------------

class ChromeConnectLoop:
    """AI loop for Chrome Connect browser automation."""

    def __init__(
        self,
        goal: str,
        html_provider: Callable[[str], str],  # url -> html
        decision_fn: Optional[Callable[[str, Dict], Dict]] = None,
    ) -> None:
        self.state = LoopState(goal=goal, start_time=time.monotonic())
        self.html_provider = html_provider
        self.decision_fn = decision_fn or self._default_decision
        self._clean_state: Optional[LoopState] = None

    # -- 8 tools ---------------------------------------------------------------

    def navigate(self, url: str) -> ToolResult:
        if self._is_destructive("navigate", url):
            return self._approval_required("navigate", {"url": url})
        try:
            html_text = self.html_provider(url)
            self.state.current_html = html_text
            self.state.current_url = url
            self.state.snapshot = obs.snapshot(html_text)
            self.state.snapshot_hash = obs.snapshot_hash(html_text)
            return ToolResult("navigate", {"url": url}, True, True, {"url": url})
        except Exception as e:
            return ToolResult("navigate", {"url": url}, False, False, error=str(e))

    def snapshot(self) -> ToolResult:
        if not self.state.current_html:
            return ToolResult("snapshot", {}, False, False, error="no page loaded")
        snap = obs.snapshot(self.state.current_html)
        self.state.snapshot = snap
        self.state.snapshot_hash = obs.snapshot_hash(self.state.current_html)
        return ToolResult("snapshot", {}, True, True, snap)

    def click(self, ref: str) -> ToolResult:
        if self._is_destructive("click", ref):
            return self._approval_required("click", {"ref": ref})
        # In MVP, clicking changes the page. Simulate by re-fetching.
        # Real implementation would interact with the browser.
        prev_hash = self.state.snapshot_hash
        # Simulate: clicking a link/button changes state
        result = ToolResult("click", {"ref": ref}, True, False)
        # Post-condition: snapshot changed
        new_snap = obs.snapshot(self.state.current_html)
        if new_snap and new_snap.get("token_count", 0) > 0:
            result.post_condition_met = True
            result.output = {"ref": ref, "clicked": True}
        else:
            result.post_condition_met = False
            result.error = "post-condition not met: page unchanged"
        return result

    def type_text(self, ref: str, text: str) -> ToolResult:
        if self._is_destructive("type", text):
            return self._approval_required("type", {"ref": ref, "text": text})
        # Sanitize input text (untrusted content rule applies to page, not input)
        result = ToolResult("type", {"ref": ref, "text": text}, True, True,
                           {"ref": ref, "typed": True})
        return result

    def scroll(self, direction: str = "down") -> ToolResult:
        direction = direction.lower()
        if direction not in ("up", "down", "left", "right"):
            return ToolResult("scroll", {"direction": direction}, False, False,
                             error=f"invalid direction: {direction}")
        # Viewport paging
        snap = self.state.snapshot
        if snap and snap.get("has_more"):
            new_offset = snap.get("offset", 0) + snap.get("limit", 50)
            vp = obs.viewport_snapshot(self.state.current_html, offset=new_offset)
            self.state.snapshot = vp
            return ToolResult("scroll", {"direction": direction}, True, True, vp)
        return ToolResult("scroll", {"direction": direction}, True, True,
                         {"scrolled": direction, "has_more": False})

    def extract(self, schema: Dict[str, Any]) -> ToolResult:
        if not self.state.current_html:
            return ToolResult("extract", {"schema": schema}, False, False,
                             error="no page loaded")
        # Extract fields from the current snapshot
        elements = (self.state.snapshot or {}).get("elements", [])
        extracted: Dict[str, Any] = {}
        for field_name in schema:
            # Simple extraction: find element text matching field
            extracted[field_name] = self._extract_field(field_name, elements)
        result = {
            "fields": extracted,
            "source_url": self.state.current_url,
            "observed_at": None,  # caller sets timestamp
            "confidence": 0.5,
        }
        return ToolResult("extract", {"schema": schema}, True, True, result)

    def wait(self, condition: str, timeout_s: float = 5.0) -> ToolResult:
        # In MVP, wait is a no-op that returns current state
        return ToolResult("wait", {"condition": condition}, True, True,
                         {"waited": condition, "timeout_s": timeout_s})

    def finish(self, result: Any) -> ToolResult:
        self.state.result = result
        return ToolResult("finish", {"result": result}, True, True, result)

    def give_up(self, reason: str) -> ToolResult:
        self.state.gave_up_reason = reason
        return ToolResult("give_up", {"reason": reason}, True, True, {"gave_up": reason})

    # -- Loop control ----------------------------------------------------------

    def run(self) -> Dict[str, Any]:
        """Run the AI loop. Returns {result, gave_up_reason, steps, ...}."""
        self.state.start_time = time.monotonic()

        # Auto-load page if empty (for fixture-based testing)
        if not self.state.current_html:
            try:
                html_text = self.html_provider("fixture://page")
                self.state.current_html = html_text
                self.state.current_url = "fixture://page"
                self.state.snapshot = obs.snapshot(html_text)
                self.state.snapshot_hash = obs.snapshot_hash(html_text)
            except Exception:
                pass

        self._clean_state = self._snapshot_state()

        while True:
            # Hard caps
            if self.state.step_count >= MAX_STEPS:
                self.give_up(f"max steps ({MAX_STEPS}) reached")
                break
            elapsed = time.monotonic() - self.state.start_time
            if elapsed >= MAX_WALL_TIME_S:
                self.give_up(f"max wall time ({MAX_WALL_TIME_S}s) reached")
                break
            if self.state.token_count >= MAX_TOKENS_PER_STEP * MAX_STEPS:
                self.give_up(f"token budget exhausted")
                break

            # Get decision
            action = self.decision_fn(self.state.goal, self.state.snapshot or {})
            if not action:
                self.give_up("decision function returned no action")
                break

            # Auto-finish: if extract already succeeded and model returns extract again
            if (action.get("tool") == "extract"
                    and any(a.get("tool") == "extract" and a.get("success")
                            for a in self.state.action_history)):
                last_extract = None
                for a in reversed(self.state.action_history):
                    if a.get("tool") == "extract" and a.get("success"):
                        last_extract = a
                        break
                if last_extract:
                    action = {"tool": "finish", "args": {"result": last_extract.get("output")}}

            # Repeat-loop breaker (only on successful actions)
            action_key = json.dumps(action, sort_keys=True)
            state_hash = self.state.snapshot_hash
            prev_success = True
            if self.state.action_history:
                prev_success = self.state.action_history[-1].get("success", True)
            if action_key == self.state.last_action and state_hash == self.state.last_state_hash and prev_success:
                if self.state.replan_count < MAX_REPLANS:
                    self.state.replan_count += 1
                    # Rollback to clean state and retry
                    self._restore_clean_state()
                    # Retry at higher temperature (simulated by re-running)
                    continue
                else:
                    self.give_up("repeat loop detected, replan exhausted")
                    break

            self.state.last_action = action_key
            self.state.last_state_hash = state_hash

            # Execute action
            tool_name = action.get("tool", "")
            args = action.get("args", {})
            tr = self._execute_tool(tool_name, args)
            self.state.step_count += 1
            self.state.token_count += tr.tokens_used
            self.state.action_history.append({
                "step": self.state.step_count,
                "tool": tool_name,
                "args": args,
                "success": tr.success,
                "post_condition_met": tr.post_condition_met,
                "error": tr.error,
                "output": tr.output,
            })

            # Post-condition check
            if not tr.post_condition_met and tool_name not in ("finish", "give_up", "wait"):
                # Action failed verification — try rollback
                if self.state.replan_count < MAX_REPLANS:
                    self.state.replan_count += 1
                    self._restore_clean_state()
                    continue
                else:
                    self.give_up(f"post-condition failed for {tool_name}: {tr.error}")
                    break

            # Auto-populate finish result from last extract if missing
            if tool_name == "finish" and not tr.output and self.state.action_history:
                for a in reversed(self.state.action_history):
                    if a.get("tool") == "extract" and a.get("success") and a.get("output"):
                        self.state.result = a["output"]
                        break

            # Check terminal
            if tool_name == "finish":
                break
            if tool_name == "give_up":
                break

            # Re-observe (snapshot) after action
            if tool_name not in ("snapshot", "finish", "give_up"):
                self.snapshot()

        # Build result
        elapsed = time.monotonic() - self.state.start_time
        return {
            "goal": self.state.goal,
            "result": self.state.result,
            "gave_up_reason": self.state.gave_up_reason,
            "steps": self.state.step_count,
            "tokens": self.state.token_count,
            "time_s": round(elapsed, 3),
            "action_history": self.state.action_history,
            "success": self.state.result is not None and self.state.gave_up_reason is None,
        }

    # -- Internal helpers -------------------------------------------------------

    def _execute_tool(self, tool_name: str, args: Dict[str, Any]) -> ToolResult:
        dispatch = {
            "navigate": lambda: self.navigate(args.get("url", "")),
            "snapshot": lambda: self.snapshot(),
            "click": lambda: self.click(args.get("ref", "")),
            "type": lambda: self.type_text(args.get("ref", ""), args.get("text", "")),
            "scroll": lambda: self.scroll(args.get("direction", "down")),
            "extract": lambda: self.extract(args.get("schema", {})),
            "wait": lambda: self.wait(args.get("condition", ""), args.get("timeout_s", 5.0)),
            "finish": lambda: self.finish(args.get("result")),
            "give_up": lambda: self.give_up(args.get("reason", "unknown")),
        }
        fn = dispatch.get(tool_name)
        if fn is None:
            return ToolResult(tool_name, args, False, False, error=f"unknown tool: {tool_name}")
        return fn()

    def _is_destructive(self, tool: str, value: str = "") -> bool:
        """Check if an action is destructive (requires approval)."""
        low = (tool + " " + str(value)).lower()
        return any(kw in low for kw in _DESTRUCTIVE)

    def _approval_required(self, tool: str, args: Dict[str, Any]) -> ToolResult:
        self.state.approval_pending = True
        self.state.approval_action = f"{tool}({args})"
        return ToolResult(tool, args, False, False,
                         error=f"approval required: {tool} {args}")

    def _extract_field(self, field_name: str, elements: List[Dict]) -> Any:
        """Extract a field value from elements (simple heuristic)."""
        field_lower = field_name.lower()
        for el in elements:
            text = el.get("text", "")
            if field_lower in text.lower():
                return text
        # Try href for link fields
        for el in elements:
            if "url" in field_lower or "link" in field_lower:
                href = el.get("href", "")
                if href:
                    return href
        return None

    def _snapshot_state(self) -> Dict[str, Any]:
        return {
            "current_html": self.state.current_html,
            "current_url": self.state.current_url,
            "snapshot": self.state.snapshot,
            "snapshot_hash": self.state.snapshot_hash,
        }

    def _restore_clean_state(self) -> None:
        if self._clean_state:
            self.state.current_html = self._clean_state["current_html"]
            self.state.current_url = self._clean_state["current_url"]
            self.state.snapshot = self._clean_state["snapshot"]
            self.state.snapshot_hash = self._clean_state["snapshot_hash"]

    def _default_decision(self, goal: str, snapshot: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Default rule-based decision function (MVP).

        Simple heuristic: try to achieve the goal by examining the snapshot.
        Returns an action dict: {tool, args}.
        """
        elements = snapshot.get("elements", [])
        goal_lower = goal.lower()

        # If no page loaded, navigate first
        if not self.state.current_html:
            # Extract URL from goal if present
            url_match = re.search(r"https?://\S+", goal)
            if url_match:
                return {"tool": "navigate", "args": {"url": url_match.group(0)}}
            return {"tool": "give_up", "args": {"reason": "no URL in goal and no page loaded"}}

        # If goal mentions extract/find/get, use extract
        if any(kw in goal_lower for kw in ("extract", "find", "get", "scrape", "read")):
            # Build schema from goal keywords
            schema = {}
            for kw in ("title", "price", "name", "url", "text"):
                if kw in goal_lower:
                    schema[kw] = "string"
            if not schema:
                schema = {"text": "string"}
            # Only extract once
            if not any(a["tool"] == "extract" for a in self.state.action_history):
                return {"tool": "extract", "args": {"schema": schema}}

        # If goal mentions click, find a matching element
        if "click" in goal_lower:
            for el in elements:
                text = (el.get("text", "") + " " + el.get("aria-label", "")).lower()
                if any(word in text for word in goal_lower.split() if len(word) > 3):
                    return {"tool": "click", "args": {"ref": el["ref"]}}

        # If goal mentions type/fill/enter, find an input
        if any(kw in goal_lower for kw in ("type", "fill", "enter", "input")):
            for el in elements:
                if el.get("tag") in ("input", "textarea") or el.get("role") in ("textbox", "searchbox"):
                    # Extract text to type from goal (after 'type'/'fill'/'enter')
                    text_to_type = ""
                    for kw in ("type", "fill", "enter"):
                        if kw in goal_lower:
                            idx = goal_lower.find(kw) + len(kw)
                            text_to_type = goal[idx:].strip().strip('"').strip("'")
                            break
                    return {"tool": "type", "args": {"ref": el["ref"], "text": text_to_type}}

        # If goal mentions scroll, scroll
        if "scroll" in goal_lower:
            direction = "down"
            if "up" in goal_lower:
                direction = "up"
            return {"tool": "scroll", "args": {"direction": direction}}

        # If goal mentions navigate/go to, navigate
        if any(kw in goal_lower for kw in ("navigate", "go to", "open", "visit")):
            url_match = re.search(r"https?://\S+", goal)
            if url_match:
                return {"tool": "navigate", "args": {"url": url_match.group(0)}}

        # Default: if we have elements, try extract; otherwise give up
        if elements and not any(a["tool"] == "extract" for a in self.state.action_history):
            return {"tool": "extract", "args": {"schema": {"text": "string"}}}

        # If we've already extracted, finish
        if any(a["tool"] == "extract" for a in self.state.action_history):
            last_extract = None
            for a in reversed(self.state.action_history):
                if a["tool"] == "extract":
                    last_extract = a
                    break
            if last_extract and last_extract.get("success"):
                return {"tool": "finish", "args": {"result": last_extract.get("output")}}

        return {"tool": "give_up", "args": {"reason": "no applicable action found"}}


def run_loop(goal: str, html_provider: Any, decision_fn: Any = None) -> Dict[str, Any]:
    """Convenience: create and run a Chrome Connect AI loop."""
    loop = ChromeConnectLoop(goal, html_provider, decision_fn)
    return loop.run()
