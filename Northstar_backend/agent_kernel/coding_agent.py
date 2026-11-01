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
from . import tool_protocol as protocol

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
    # Rejections are evidence, not noise: a model that never produced a usable
    # action is a different failure from one the executor refused on scope.
    protocol_errors: int = 0
    scope_rejections: int = 0

    def to_dict(self) -> dict:
        return {"ok": self.ok, "summary": self.summary, "steps": self.steps,
                "files": self.files, "error": self.error,
                "acceptance_recovered": self.acceptance_recovered,
                "protocol_errors": self.protocol_errors,
                "scope_rejections": self.scope_rejections,
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


# Prompt-history budget: fewer, shorter observations keep TTFT down on the
# 27B lane while error/failure text keeps a larger slice.
PROMPT_HISTORY_TURNS = 4
PROMPT_OBS_CHARS = 1200
PROMPT_ERROR_CHARS = 1800

class CodingAgent:
    def __init__(self, workspace: Workspace | str, model: Model, *,
                 max_steps: int = 12, max_repairs: int = 2,
                 acceptance: Optional[Acceptance] = None,
                 required_artifact: str = "",
                 max_protocol_errors: int = 3,
                 allowed_tools: Optional[Sequence[str]] = None):
        self.tools = workspace if isinstance(workspace, Workspace) else Workspace(workspace)
        self.model = model
        self.max_steps = max(1, int(max_steps))
        self.max_repairs = max(0, int(max_repairs))
        self.acceptance = acceptance
        self.required_artifact = str(required_artifact or "").strip()
        # Bounded repair: a turn that is not one usable action is answered once
        # with a protocol observation, and the run fails cleanly after N of them
        # instead of burning the whole step budget on malformed output.
        self.max_protocol_errors = max(0, int(max_protocol_errors))
        tools = [str(t) for t in (allowed_tools or ()) if str(t)]
        self.allowed_tools = tuple(t for t in tools if t in protocol.CANONICAL_ACTIONS) or None
        self._failing: List[str] = []
        self._reads = 0
        self._read_seen: set[str] = set()
        # A lane can loop on `read`. Reading the same file again without an edit
        # in between is refused, because the content is already in the prompt.
        self._read_since_edit: set[str] = set()

    def run(self, task: str) -> CodingResult:
        history: List[Dict[str, Any]] = []
        files: set[str] = set()
        repairs = 0
        written = False
        protocol_errors = 0
        scope_rejections = 0
        last_protocol = ""
        # A failed acceptance run cannot change by running it again. Track it so the
        # loop refuses a no-op re-run: measured 2026-10-29, 17 of 24 steps were bare
        # `run` calls ("exit 2") with no edit between them, and the build never moved.
        failed_run = False
        changed_since_run = True
        stalls = 0
        def _out(ok, summary, step, files_, history_, error='', acceptance_recovered=False):
            return CodingResult(ok, summary, step, files_, history_, error,
                                acceptance_recovered=acceptance_recovered,
                                protocol_errors=protocol_errors,
                                scope_rejections=scope_rejections)

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
                        return _out(True, "acceptance passed after model error",
                                            step, sorted(files), history, "",
                                            acceptance_recovered=True)
                return _out(False, "model call failed", step, sorted(files),
                                    history, str(exc)[:300])
            # One strict action per turn: parse, validate against the task scope and
            # policy, then execute. A refusal is answered once, then bounded.
            try:
                action = protocol.validate_action(protocol.parse_action(raw),
                                                  workspace=self.tools)
            except protocol.ActionError as exc:
                if protocol.rejection_kind(exc) == "model":
                    protocol_errors += 1
                else:
                    scope_rejections += 1
                last_protocol = exc.code
                history.append({"role": "observation", "tool": "protocol", "ok": False,
                                "output": exc.observation()})
                if protocol_errors > self.max_protocol_errors:
                    return _out(False, "protocol_failed", step, sorted(files), history,
                                f"protocol_failed: {exc.code}")
                continue
            tool, args = action.tool, action.args
            if tool == "read" and str(args.get("path") or "") in self._read_since_edit:
                protocol_errors += 1
                history.append({"role": "observation", "tool": "protocol", "ok": False,
                                "output": (f"PROTOCOL already_read: {args.get('path')!r} "
                                           "is in the conversation above. Hint: edit it with "
                                           "ast_edit (name the symbol you saw) or finish.")})
                if protocol_errors > self.max_protocol_errors:
                    return _out(False, "protocol_failed", step, sorted(files), history,
                                "protocol_failed: already_read")
                continue
            # A bounded edit needs the current file in front of it. A small lane
            # otherwise guesses a symbol name and "edits" a function that does not
            # exist (observed: target 'count_corrupt_records' not found). Reading is
            # one step; guessing costs the whole budget.
            if tool == "ast_edit" and str(args.get("path") or "") not in self._read_seen:
                protocol_errors += 1
                history.append({"role": "observation", "tool": "protocol", "ok": False,
                                "output": (f"PROTOCOL read_required: read "
                                           f"{args.get('path')!r} before editing it. "
                                           "Hint: call read first, then ast_edit with the "
                                           "symbol you actually saw.")})
                if protocol_errors > self.max_protocol_errors:
                    return _out(False, "protocol_failed", step, sorted(files), history,
                                "protocol_failed: read_required")
                continue
            self._reads = self._reads + 1 if tool == "read" else 0
            if tool == "finish":
                summary = str(args.get("summary") or "finished")
                if self.acceptance is None:
                    return _out(True, summary, step, sorted(files), history)
                ok, detail = self.acceptance()
                history.append({"role": "observation", "tool": "acceptance",
                                "output": ("PASS: " if ok else "FAIL: ") + str(detail)[:1000]})
                if ok:
                    return _out(True, summary, step, sorted(files), history)
                self._note_failure(detail)
                repairs += 1
                if repairs > self.max_repairs:
                    return _out(False, "acceptance failed after repairs", step,
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
            if tool == "read" and result.ok:
                rel = str(args.get("path") or "")
                self._read_seen.add(rel)
                self._read_since_edit.add(rel)
            elif tool in ("write", "write_many", "apply_patch", "ast_edit",
                          "ast_edit_batch") and result.ok:
                # A change makes a fresh read legitimate again.
                self._read_since_edit.clear()
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
                    return _out(True, f"acceptance passed after {tool}", step,
                                        sorted(files), history)
                self._note_failure(detail)
                # The model must SEE the verdict. Without this the loop reported
                # only "wrote 1 file(s)", so a model that cannot infer the failure
                # rewrote the same file blindly until the step budget ran out.
                history.append({"role": "observation", "tool": "acceptance", "ok": False,
                                "output": "FAIL: " + str(detail)[:1200]})
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
                return _out(True, "acceptance passed after the step budget",
                            self.max_steps, sorted(files), history,
                            acceptance_recovered=True)
        return _out(False, "step budget exhausted", self.max_steps,
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
            '{"tool":"read","args":{"path":"your_file.py"}}\n'
            '{"tool":"grep","args":{"pattern":"assert","path":"."}}\n'
            '{"tool":"write","args":{"path":"fix.patch","content":"..."}}\n'
            '{"tool":"write_many","args":{"files":[{"path":"a.ts","content":"..."},{"path":"b.ts","content":"..."}]}}\n'
            '{"tool":"apply_patch","args":{"patch":"--- a/calc.py\\n+++ b/calc.py\\n@@ -1,3 +1,3 @@\\n context\\n-old line\\n+new line\\n context\\n"}}\n'
            '{"tool":"ast_edit","args":{"path":"your_file.py","op":"replace_function_body","target":"the_symbol_you_read","source":"the new body"}}\n'
            '{"tool":"ast_edit_batch","args":{"batch":[{"path":"a.py","edits":[{"op":"replace_global","target":"LIMIT","source":"LIMIT = 20"}]}]}}\n'
            '{"tool":"run","args":{"cmd":["python","-m","pytest","-q"]}}\n'
            '{"tool":"finish","args":{"summary":"what changed and what passed"}}'
        )
        if self.allowed_tools:
            # A small lane does better with the three actions its task can use than
            # with the whole vocabulary. Unknown names are impossible when they are
            # never offered.
            lines = [ln for ln in schema.splitlines()
                     if any(f'"tool":"{name}"' in ln for name in self.allowed_tools)]
            schema = "\n".join(lines)
        if pressure:
            # Pressure used to shrink the schema to write/finish. That steered a
            # bounded-edit task straight into the one action the executor refuses
            # (whole-file write of an existing source). The full action list stays;
            # only the instruction becomes urgent.
            schema = schema + (
                '\n{"tool":"ast_edit","args":{"path":"your_file.py",'
                '"op":"replace_function_body","target":"the_symbol_you_read",'
                '"source":"the new body"}}')
        observed = self._compact_history(history)
        if self.allowed_tools:
            # Task-scoped protocol: a small lane gets the actions it can use, four
            # rules and the last two results - nothing else to dilute them.
            allowed = ", ".join(self.allowed_tools)
            allowlist = list(getattr(self.tools, "run_allowlist", ()) or ())
            commands = [" ".join(c) for c in allowlist][:3]
            # The schema example must show a command that will actually execute. A
            # 3B copies the example verbatim; advertising pytest on a task whose only
            # permitted command is a probe burned the first step of every task.
            if allowlist and "run" in self.allowed_tools:
                example = json.dumps(list(allowlist[0]))
                schema = "\n".join(
                    (f'{{"tool":"run","args":{{"cmd":{example}}}}}' if '"tool":"run"' in ln
                     else ln)
                    for ln in schema.splitlines())
            return (
                "You are the Northstar OS coding worker. Reply with exactly ONE JSON "
                "object per turn. No prose, no markdown fences.\n\n"
                f"ACTIONS (only these are accepted: {allowed}):\n" + schema + "\n\n"
                "RULES:\n"
                "- Use the exact action names and argument names above.\n"
                "- Never rewrite an existing source file: use ast_edit or apply_patch.\n"
                "- `run` takes an argv list; the only commands that will execute are: "
                + ("; ".join(commands) if commands else "(none)") + "\n"
                "- Start by reading the task's file, then edit it, then run the check.\n"
                + ("STOP READING: the file is already in the conversation. Your next JSON "
                   "object MUST be an ast_edit naming a symbol you saw. Do not read again.\n"
                   if self._reads >= 2 else "")
                + "- Stop with `finish` once the behaviour is correct.\n\n"
                f"TASK:\n{task}\n\n"
                + (self._failing_block()[:600] if self._failing else "")
                + "RECENT RESULTS:\n" + ("\n".join(observed[-2:]) or "(none)") + "\n\n"
                "Next JSON object:")
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
            "- Files outside your write scope are READ-ONLY. A refused write is never "
            "retried: to check your work, call `run` with the acceptance command.\n"
            "- On a FAIL observation, first `read` every file named in the error, then "
            "rewrite those files with write_many. The error text is authoritative.\n\n"
            f"TASK:\n{task}\n\n"
            + (f"REQUIRED ARTIFACT: {self.required_artifact}\n"
               if self.required_artifact else "")
            + ("STOP READING. You have read the file and the content is above. Your next "
               "turn MUST be an ast_edit on the function you saw - name the symbol "
               "exactly as it appears in the file. Do not read again.\n"
               if self._reads >= 2 else "")
            + (f"STEP PRESSURE: you have not produced `{self.required_artifact}` yet. "
               "Use ast_edit / apply_patch for an existing file; a whole-file write of a "
               "source file is refused. Then finish.\n" if pressure else "")
            + ("VERIFY STALL: acceptance already failed and nothing changed since. "
               "Re-running it returns the same error, so it is refused. The only way "
               "forward is to change files: reply with write_many containing every "
               "file you are fixing, complete.\n" if stall else "")
            + f"WORKSPACE FILES:\n{self.tools.tree(60)}\n\n"
            + self._failing_block()
            + "RECENT TOOL RESULTS:\n" + ("\n".join(observed) or "(none)") + "\n\n"
            "Next JSON object:"
        )

    def _compact_history(self, history: List[Dict[str, Any]]) -> List[str]:
        """Last N observations, deduped, with failure text given more room."""
        recent = list(history or [])[-PROMPT_HISTORY_TURNS:]
        observed: List[str] = []
        seen = set()
        for h in recent:
            tool = str(h.get("tool") or "")
            text = str(h.get("output") or "")
            key = (tool, text[:400])
            if key in seen:
                continue
            seen.add(key)
            low = text.lower()
            limit = (PROMPT_ERROR_CHARS if any(w in low for w in
                     ("error", "traceback", "fail", "exception")) else PROMPT_OBS_CHARS)
            observed.append(f"[{tool}] {text[:limit]}")
        return observed
