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
    # True when the loop stopped without success but acceptance passed anyway
    # (p01). Callers surface this instead of re-deriving it from the summary.
    acceptance_recovered: bool = False

    def to_dict(self) -> dict:
        return {"ok": self.ok, "summary": self.summary, "steps": self.steps,
                "files": self.files, "error": self.error,
                "acceptance_recovered": self.acceptance_recovered,
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
        self._failing: List[str] = []
        self._reads = 0

    def run(self, task: str) -> CodingResult:
        history: List[Dict[str, Any]] = []
        files: set[str] = set()
        repairs = 0
        written = False
        # A failed acceptance run cannot change by running it again. Track it so the
        # loop refuses a no-op re-run: measured 2026-10-29, 17 of 24 steps were bare
        # `run` calls ("exit 2") with no edit between them, and the build never moved.
        failed_run = False
        changed_since_run = True
        stalls = 0
        for step in range(1, self.max_steps + 1):
            pressure = bool(self.required_artifact) and not written and step > 2
            prompt = self._prompt(task, history, pressure=pressure, stall=stalls > 0)
            try:
                raw = self.model(prompt)
            except Exception as exc:  # noqa: BLE001
                # Acceptance is the authority, even when the model call itself
                # fails: the work may already be on disk and green.
                if self.acceptance is not None:
                    try:
                        ok, detail = self.acceptance()
                    except Exception as check_exc:  # noqa: BLE001
                        ok, detail = False, str(check_exc)[:300]
                    if ok:
                        history.append({"role": "observation", "tool": "acceptance",
                                        "output": "PASS: " + str(detail)[:1000]})
                        return CodingResult(True, "acceptance passed after model error",
                                            step, sorted(files), history, "",
                                            acceptance_recovered=True)
                return CodingResult(False, "model call failed", step, sorted(files),
                                    history, str(exc)[:300])
            call = parse_tool_call(raw)
            if call is None:
                history.append({"role": "observation", "tool": "protocol",
                                "output": "Invalid response. Reply with ONE JSON object "
                                          "using the tool schema. No prose, no fences."})
                continue
            tool, args = call["tool"], call["args"]
            self._reads = self._reads + 1 if tool == "read" else 0
            if tool == "finish":
                summary = str(args.get("summary") or "finished")
                if self.acceptance is None:
                    return CodingResult(True, summary, step, sorted(files), history)
                ok, detail = self.acceptance()
                history.append({"role": "observation", "tool": "acceptance",
                                "output": ("PASS: " if ok else "FAIL: ") + str(detail)[:1000]})
                if ok:
                    return CodingResult(True, summary, step, sorted(files), history)
                self._note_failure(detail)
                repairs += 1
                if repairs > self.max_repairs:
                    return CodingResult(False, "acceptance failed after repairs", step,
                                        sorted(files), history, str(detail)[:300])
                continue
            if tool == "run" and failed_run and not changed_since_run:
                stalls += 1
                history.append({"role": "observation", "tool": "verify_stall",
                                "output": "Refused: acceptance already failed and no file "
                                          "has changed since. Running it again returns the "
                                          "same error. Edit a file first (write/write_many), "
                                          "then run it."})
                continue
            result: ToolResult = self.tools.execute(tool, args)
            files.update(result.files)
            if tool == "run":
                failed_run = not result.ok
                changed_since_run = False
            elif tool in ("write", "write_many", "apply_patch"):
                failed_run = False
                changed_since_run = True
            # The artifact clears the pressure, however it was produced: a `write`,
            # an `apply_patch`, or a command that generated it. Keying this off the
            # write tool alone kept the prompt in write-only pressure mode after a
            # successful patch and starved the model of its other tools.
            if self.required_artifact and self._artifact_present():
                written = True
            history.append({"role": "observation", "tool": tool,
                            "ok": result.ok,
                            "output": result.output if result.ok else result.error})
            # The artifact is the goal. If a write or a verification command
            # already satisfies acceptance, stop instead of burning the rest of
            # the step budget waiting for a `finish` the model may forget.
            if self.acceptance is not None and tool in ("write", "write_many", "run") and result.ok:
                ok, detail = self.acceptance()
                if ok:
                    history.append({"role": "observation", "tool": "acceptance",
                                    "output": "PASS: " + str(detail)[:1000]})
                    return CodingResult(True, f"acceptance passed after {tool}", step,
                                        sorted(files), history)
                self._note_failure(detail)
        # Defect p01: a loop that ran out of steps with the work already done is a
        # pass, not a `needs_human`. Acceptance is the authority; the stop reason
        # is not. Checked once more here so every caller (kernel or benchmark)
        # inherits the rule instead of re-implementing it.
        if self.acceptance is not None:
            try:
                ok, detail = self.acceptance()
            except Exception as exc:  # noqa: BLE001 - a raising check is a failed check
                ok, detail = False, str(exc)[:300]
            if ok:
                history.append({"role": "observation", "tool": "acceptance",
                                "output": "PASS: " + str(detail)[:1000]})
                return CodingResult(True, "acceptance passed after the step budget",
                                    self.max_steps, sorted(files), history,
                                    acceptance_recovered=True)
        return CodingResult(False, "step budget exhausted", self.max_steps,
                            sorted(files), history, "max_steps")

    def _artifact_present(self) -> bool:
        """True when the declared artifact exists on disk and is not empty."""
        if not self.required_artifact:
            return False
        try:
            p = self.tools.resolve(self.required_artifact)
        except ValueError:
            return False
        try:
            return p.is_file() and p.stat().st_size > 0
        except OSError:
            return False

    def _note_failure(self, detail: str) -> None:
        """Remember the files a failed acceptance named, so the next prompt shows them."""
        found = re.findall(
            r"([A-Za-z0-9_./\\-]+\.(?:ts|tsx|js|jsx|py|json|md))", str(detail or ""))
        for rel in found:
            clean = rel.replace("\\", "/").lstrip("./")
            if clean and clean not in self._failing:
                self._failing.append(clean)
        self._failing = self._failing[:4]

    def _failing_block(self) -> str:
        """Current content of the failing files, injected so repair cannot skip the read."""
        parts = []
        for rel in self._failing:
            try:
                p = self.tools.resolve(rel)
                if not p.is_file():
                    continue
                text = p.read_text(encoding="utf-8", errors="replace")[:6000]
            except Exception:  # noqa: BLE001 - a missing file is simply not shown
                continue
            parts.append(f"--- {rel} (current content) ---\n{text}\n--- END {rel} ---")
        if not parts:
            return ""
        return ("FAILING FILES (acceptance named these; fix them directly):\n"
                + "\n".join(parts) + "\n\n")

    def _prompt(self, task: str, history: List[Dict[str, Any]],
                *, pressure: bool = False, stall: bool = False) -> str:
        schema = (
            '{"tool":"list","args":{"path":"."}}\n'
            '{"tool":"read","args":{"path":"calc.py"}}\n'
            '{"tool":"grep","args":{"pattern":"assert","path":"."}}\n'
            '{"tool":"write","args":{"path":"fix.patch","content":"..."}}\n'
            '{"tool":"write_many","args":{"files":[{"path":"a.ts","content":"..."},{"path":"b.ts","content":"..."}]}}\n'
            '{"tool":"apply_patch","args":{"patch":"--- a/calc.py\\n+++ b/calc.py\\n@@ -1,3 +1,3 @@\\n context\\n-old line\\n+new line\\n context\\n"}}\n'
            '{"tool":"ast_edit","args":{"path":"calc.py","op":"replace_function_body","target":"add","source":"return a + b"}}\n'
            '{"tool":"ast_edit_batch","args":{"batch":[{"path":"a.py","edits":[{"op":"replace_global","target":"LIMIT","source":"LIMIT = 20"}]}]}}\n'
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
            "SYSTEM DIRECTIVE: You are pre-authorized to run ['npx tsc', 'npm test', "
            "'npm run', 'npx jest']. NEVER read coding_tools.py to check tool permissions.\n\n"
            "TOOLS (one per turn):\n" + schema + "\n\n"
            "Rules:\n"
            "- Work only inside the workspace.\n"
            "- Use `run` only with the allowlisted commands.\n"
            "- For Python edits, prefer `ast_edit` / `ast_edit_batch`: name the "
            "function, method, class or global and supply the new body. Do not "
            "hand-write a unified diff for a Python symbol.\n"
            "- Before `finish`, the artifact and any test/build evidence must exist.\n"
            "- Write the declared artifact within the first two steps. An absent "
            "artifact is an automatic failure; improve it afterwards.\n"
            "- If acceptance fails, read the failure and repair; do not repeat the same write.\n"
            "- On a FAIL observation, first `read` every file named in the error, then "
            "rewrite those files with write_many. The error text is authoritative.\n\n"
            f"TASK:\n{task}\n\n"
            + (f"REQUIRED ARTIFACT: {self.required_artifact}\n"
               if self.required_artifact else "")
            + ("STOP READING. You have read several files without writing. Your next "
               "turn MUST be a write_many call that writes the corrected files. Do not "
               "read again.\n" if self._reads >= 2 else "")
            + (f"STEP PRESSURE: you have not written `{self.required_artifact}` yet. "
               "Only write and finish are available now. Write the artifact in your "
               "next JSON object.\n" if pressure else "")
            + ("VERIFY STALL: acceptance already failed and nothing changed since. "
               "Re-running it returns the same error, so it is refused. The only way "
               "forward is to change files: reply with write_many containing every "
               "file you are fixing, complete.\n" if stall else "")
            + f"WORKSPACE FILES:\n{self.tools.tree(60)}\n\n"
            + self._failing_block()
            + "RECENT TOOL RESULTS:\n" + ("\n".join(observed) or "(none)") + "\n\n"
            "Next JSON object:"
        )
