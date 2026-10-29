"""A bounded observe → act → verify → repair loop.

The model chooses one tool per turn and receives the tool's output. It never sees
a shell or an unbounded filesystem. `finish` is checked against the caller's
acceptance function; a failure becomes an observation, not a pass.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

from .coding_tools import ToolResult, Workspace

Model = Callable[[str], str]
Acceptance = Callable[[], Tuple[bool, str]]


@dataclass
class CodingResult:
    ok: bool
    summary: str
    steps: int
    files: List[str] = field(default_factory=list)
    transcript: List[Dict[str, Any]] = field(default_factory=list)
    error: str = ""

    def to_dict(self) -> dict:
        return {"ok": self.ok, "summary": self.summary, "steps": self.steps,
                "files": self.files, "error": self.error,
                "transcript": self.transcript[-20:]}


def parse_tool_call(text: str) -> Optional[Dict[str, Any]]:
    body = (text or "").strip()
    if body.startswith("```"):
        body = body.split("\n", 1)[1] if "\n" in body else body
        body = body.rsplit("```", 1)[0]
    start = body.find("{")
    if start < 0:
        return None
    try:
        obj, _ = json.JSONDecoder().raw_decode(body[start:])
    except Exception:  # noqa: BLE001
        return None
    if not isinstance(obj, dict) or not isinstance(obj.get("tool"), str):
        return None
    args = obj.get("args")
    if args is None:
        args = {}
    if not isinstance(args, dict):
        return None
    return {"tool": obj["tool"], "args": args}


class CodingAgent:
    def __init__(self, workspace: Workspace | str, model: Model, *,
                 max_steps: int = 12, max_repairs: int = 2,
                 acceptance: Optional[Acceptance] = None,
                 required_artifact: str = ""):
        self.tools = workspace if isinstance(workspace, Workspace) else Workspace(workspace)
        self.model = model
        self.max_steps = max(1, int(max_steps))
        self.max_repairs = max(0, int(max_repairs))
        self.acceptance = acceptance
        self.required_artifact = str(required_artifact or "").strip()

    def run(self, task: str) -> CodingResult:
        history: List[Dict[str, Any]] = []
        files: set[str] = set()
        repairs = 0
        written = False
        for step in range(1, self.max_steps + 1):
            pressure = bool(self.required_artifact) and not written and step > 2
            prompt = self._prompt(task, history, pressure=pressure)
            try:
                raw = self.model(prompt)
            except Exception as exc:  # noqa: BLE001
                return CodingResult(False, "model call failed", step, sorted(files),
                                    history, str(exc)[:300])
            call = parse_tool_call(raw)
            if call is None:
                history.append({"role": "observation", "tool": "protocol",
                                "output": "Invalid response. Reply with ONE JSON object "
                                          "using the tool schema. No prose, no fences."})
                continue
            tool, args = call["tool"], call["args"]
            if tool == "finish":
                summary = str(args.get("summary") or "finished")
                if self.acceptance is None:
                    return CodingResult(True, summary, step, sorted(files), history)
                ok, detail = self.acceptance()
                history.append({"role": "observation", "tool": "acceptance",
                                "output": ("PASS: " if ok else "FAIL: ") + str(detail)[:1000]})
                if ok:
                    return CodingResult(True, summary, step, sorted(files), history)
                repairs += 1
                if repairs > self.max_repairs:
                    return CodingResult(False, "acceptance failed after repairs", step,
                                        sorted(files), history, str(detail)[:300])
                continue
            result: ToolResult = self.tools.execute(tool, args)
            files.update(result.files)
            if tool == "write" and result.ok:
                written = True
            history.append({"role": "observation", "tool": tool,
                            "ok": result.ok,
                            "output": result.output if result.ok else result.error})
            # The artifact is the goal. If a write or a verification command
            # already satisfies acceptance, stop instead of burning the rest of
            # the step budget waiting for a `finish` the model may forget.
            if self.acceptance is not None and tool in ("write", "run") and result.ok:
                ok, detail = self.acceptance()
                if ok:
                    history.append({"role": "observation", "tool": "acceptance",
                                    "output": "PASS: " + str(detail)[:1000]})
                    return CodingResult(True, f"acceptance passed after {tool}", step,
                                        sorted(files), history)
        return CodingResult(False, "step budget exhausted", self.max_steps,
                            sorted(files), history, "max_steps")

    def _prompt(self, task: str, history: List[Dict[str, Any]],
                *, pressure: bool = False) -> str:
        schema = (
            '{"tool":"list","args":{"path":"."}}\n'
            '{"tool":"read","args":{"path":"calc.py"}}\n'
            '{"tool":"grep","args":{"pattern":"assert","path":"."}}\n'
            '{"tool":"write","args":{"path":"fix.patch","content":"..."}}\n'
            '{"tool":"apply_patch","args":{"patch":"--- a/calc.py\\n+++ b/calc.py\\n@@ -1,3 +1,3 @@\\n context\\n-old line\\n+new line\\n context\\n"}}\n'
            '{"tool":"run","args":{"cmd":["python","-m","pytest","-q"]}}\n'
            '{"tool":"finish","args":{"summary":"what changed and what passed"}}'
        )
        if pressure:
            schema = (
                '{"tool":"write","args":{"path":"' + self.required_artifact +
                '","content":"..."}}\n'
                '{"tool":"finish","args":{"summary":"what changed and what passed"}}'
            )
        recent = history[-6:]
        observed = []
        for h in recent:
            text = str(h.get("output") or "")[:1800]
            observed.append(f"[{h.get('tool')}] {text}")
        return (
            "You are the Northstar OS coding worker. You have tools. You MUST respond "
            "with exactly ONE JSON object per turn: no prose, no markdown fences.\n\n"
            "TOOLS (one per turn):\n" + schema + "\n\n"
            "Rules:\n"
            "- Work only inside the workspace.\n"
            "- Use `run` only with the allowlisted commands.\n"
            "- Before `finish`, the artifact and any test/build evidence must exist.\n"
            "- Write the declared artifact within the first two steps. An absent "
            "artifact is an automatic failure; improve it afterwards.\n"
            "- If acceptance fails, read the failure and repair; do not repeat the same write.\n\n"
            f"TASK:\n{task}\n\n"
            + (f"REQUIRED ARTIFACT: {self.required_artifact}\n"
               if self.required_artifact else "")
            + (f"STEP PRESSURE: you have not written `{self.required_artifact}` yet. "
               "Only write and finish are available now. Write the artifact in your "
               "next JSON object.\n" if pressure else "")
            + f"WORKSPACE FILES:\n{self.tools.tree(60)}\n\n"
            "RECENT TOOL RESULTS:\n" + ("\n".join(observed) or "(none)") + "\n\n"
            "Next JSON object:"
        )
