"""Strict action protocol for the Ty executor.

The model answers with ONE JSON object per turn. This module decides whether that
object is a usable action and refuses everything else with a bounded, readable
reason the model can repair in its next turn.

It is deliberately NOT a code generator: it only normalises envelopes (one fence,
case-insensitive tool names, a small alias table, optional arguments) and rejects
the rest. Every rejection names a stable code so the ledger and the task state can
tell a MODEL failure (never produced valid output) from an EXECUTOR rejection
(produced output the task scope does not allow).

Rules enforced before any tool runs:

* exactly one JSON object per turn - two actions are rejected, never "first wins";
* canonical action names and declared arguments only;
* every path is resolved inside the workspace and inside the task scope;
* ``run`` is an argv list of allowlisted executables, never a shell string;
* a whole-file ``write`` of an existing source file is refused: a bounded edit
  (``ast_edit`` / ``apply_patch``) must be used instead. This is the rule that
  stops a small lane truncating a module it cannot reproduce;
* a batch is validated atomically - one bad file rejects the whole batch.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Dict, Optional, Sequence, Tuple

CANONICAL_ACTIONS: Tuple[str, ...] = (
    "list", "read", "grep", "write", "write_many", "apply_patch",
    "ast_edit", "ast_edit_batch", "run", "finish",
)

#: small, explicit aliases. Nothing is inferred from prose.
ALIASES: Dict[str, str] = {
    "ls": "list", "dir": "list",
    "cat": "read", "open": "read", "view": "read",
    "search": "grep", "find": "grep",
    "create": "write", "save": "write",
    "patch": "apply_patch", "diff": "apply_patch",
    "edit": "ast_edit", "replace_function_body": "ast_edit",
    "exec": "run", "shell": "run", "command": "run",
    "done": "finish", "stop": "finish", "complete": "finish",
}

SOURCE_SUFFIXES = (".py", ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs")
MAX_ARG_CHARS = 200_000
#: Commands are executed as an argv list with `shell=False`, so `;` or `|` inside a
#: legitimate `python -c` snippet is not a shell injection. Only control characters
#: are refused: they exist to break line-oriented evidence, not to run a command.
FORBIDDEN_ARG_CHARS = set("\n\r\x00")

#: required and optional arguments per action; values are the expected types.
_SCHEMA: Dict[str, Dict[str, Tuple[type, bool]]] = {
    "list": {"path": (str, False)},
    "read": {"path": (str, True)},
    "grep": {"pattern": (str, True), "path": (str, False), "max_hits": (int, False)},
    "write": {"path": (str, True), "content": (str, True)},
    "write_many": {"files": (list, True)},
    "apply_patch": {"patch": (str, True)},
    "ast_edit": {"path": (str, True), "op": (str, True), "target": (str, False),
                 "source": (str, False)},
    "ast_edit_batch": {"batch": (list, True)},
    "run": {"cmd": (list, True)},
    "finish": {"summary": (str, False)},
}

_PATH_ARG = {"read": "path", "write": "path", "ast_edit": "path",
             "apply_patch": None, "list": "path", "grep": "path"}

#: Argument-name aliases a small lane actually emits. Only names that map to an
#: existing schema key are accepted; anything else is still rejected.
ARG_ALIASES: Dict[str, str] = {
    "paths": "path", "file": "path", "filename": "path", "filepath": "path",
    "path_name": "path", "target_file": "path",
    "target_symbol": "target", "function": "target", "symbol": "target",
    "new_body": "source", "body": "source", "code": "source", "content_body": "source",
    "command": "cmd", "argv": "cmd", "args_list": "cmd",
    "file_list": "files", "list_of_files": "files",
    "pattern_text": "pattern", "query": "pattern",
    "patch_text": "patch", "diff": "patch",
}

#: AST op names a small lane mangles. Value-level normalisation only: the op is
#: still the model's choice, and the tool re-validates it.
OP_ALIASES: Dict[str, str] = {
    "replaceuser_body": "replace_function_body",
    "replace_body": "replace_function_body",
    "replace_func_body": "replace_function_body",
    "replacefunctionbody": "replace_function_body",
    "set_body": "replace_function_body",
    "body": "replace_function_body",
}


class ActionError(ValueError):
    """A refused action. ``code`` is stable and safe to record in the ledger."""

    def __init__(self, code: str, message: str, hint: str = ""):
        self.code = str(code)
        self.message = str(message)
        self.hint = str(hint or "")
        super().__init__(f"{self.code}: {self.message}")

    def observation(self) -> str:
        """One bounded line for the model's next turn: what, and what to do."""
        text = f"PROTOCOL {self.code}: {self.message}"
        if self.hint:
            text += f" Hint: {self.hint}"
        return text


@dataclass(frozen=True)
class Action:
    tool: str
    args: Dict[str, Any]
    notes: Tuple[str, ...] = ()

    def to_dict(self) -> Dict[str, Any]:
        return {"tool": self.tool, "args": dict(self.args), "notes": list(self.notes)}


def _strip_one_fence(text: str) -> str:
    body = (text or "").strip()
    if not body.startswith("```"):
        return body
    first = body.find("\n")
    if first < 0:
        return body
    body = body[first + 1:]
    end = body.rfind("```")
    return body[:end].strip() if end >= 0 else body.strip()


def parse_action(text: str) -> Action:
    """Parse exactly one JSON action, or raise ActionError."""
    body = _strip_one_fence(text)
    if not body:
        raise ActionError("empty_output", "the turn was empty",
                          'reply with one JSON object: {"tool":"read","args":{...}}')
    start = body.find("{")
    if start < 0:
        raise ActionError("not_json", "no JSON object found",
                          "reply with JSON only, no prose")
    try:
        obj, end = json.JSONDecoder().raw_decode(body[start:])
    except ValueError as exc:
        raise ActionError("invalid_json", f"JSON did not parse ({exc.msg})",
                          "one complete JSON object, no trailing text") from exc
    tail = body[start + end:].strip()
    if "{" in tail:
        raise ActionError("multiple_actions", "more than one JSON object in the turn",
                          "exactly one action per turn")
    if not isinstance(obj, dict):
        raise ActionError("not_object", "the JSON value is not an object",
                          'use {"tool":...,"args":{...}}')
    tool = obj.get("tool", obj.get("action", obj.get("name")))
    if not isinstance(tool, str) or not tool.strip():
        raise ActionError("missing_tool", "no tool name",
                          f"one of {', '.join(CANONICAL_ACTIONS)}")
    name = tool.strip().lower()
    name = ALIASES.get(name, name)
    if name not in CANONICAL_ACTIONS:
        # A lane sometimes appends commentary to the name ("ast_edit not
        # recognized"). Take the canonical prefix only; the name is still the
        # model's choice and the action is still validated.
        for canonical in CANONICAL_ACTIONS:
            if name.startswith(canonical) and not name[len(canonical)].isalnum():
                name = canonical
                break
    if name not in CANONICAL_ACTIONS:
        raise ActionError("unknown_tool", f"unknown tool {tool!r}",
                          f"one of {', '.join(CANONICAL_ACTIONS)}")
    args = obj.get("args")
    if args is None:
        args = obj.get("arguments")
    if isinstance(args, str):
        # Small lanes double-encode the envelope: "args": "{\"path\": ...}".
        # Unwrapping a JSON string is normalisation of the envelope, not invention.
        try:
            args = json.loads(args)
        except ValueError:
            raise ActionError("bad_args", "args was a string that is not JSON",
                              '{"tool":"read","args":{"path":"file.py"}}')
    if args is None:
        # ... and they often lift the arguments to the top level.
        lifted = {k: v for k, v in obj.items()
                  if k not in ("tool", "action", "name", "args", "arguments")}
        args = lifted
    if not isinstance(args, dict):
        raise ActionError("bad_args", "args must be an object",
                          '{"tool":"read","args":{"path":"file.py"}}')
    return Action(name, dict(args))


def _normalise_args(tool: str, args: Dict[str, Any]) -> Tuple[Dict[str, Any], Tuple[str, ...]]:
    """Rename the argument keys a small lane gets wrong, only when unambiguous.

    Two deterministic rules, both recorded in the action's notes:

    * a known alias (``paths`` -> ``path``);
    * a single unknown key for an action with exactly one required argument - this
      covers the empty-string key a lane emits as ``{"":"file.py"}``.
    """
    schema = _SCHEMA[tool]
    notes: list = []
    for key in list(args):
        if key in schema:
            continue
        target = ARG_ALIASES.get(str(key).strip().lower())
        if target and target in schema and target not in args:
            args[target] = args.pop(key)
            notes.append(f"arg_normalised:{key}->{target}")
    unknown = [k for k in args if k not in schema]
    required = [k for k, (_, req) in schema.items() if req]
    if len(unknown) == 1 and len(required) == 1 and len(args) == 1:
        value = args[unknown[0]]
        if isinstance(value, (str, list, int)) and not isinstance(value, bool):
            args[required[0]] = value
            args.pop(unknown[0])
            notes.append(f"arg_normalised:{unknown[0] or '<empty>'}->{required[0]}")
    # An empty key is never meaningful. Drop it once the action already carries a
    # required argument; it is noise, not a second instruction.
    if any(str(k).strip() == "" for k in args) and any(k in args for k in required):
        for key in [k for k in args if str(k).strip() == ""]:
            args.pop(key)
            notes.append("arg_normalised:<empty>->dropped")
    return args, tuple(notes)


def validate_action(action: Action, *, workspace: Any,
                    bounded_edit: bool = True) -> Action:
    """Validate one parsed action against the schema and the task scope."""
    schema = _SCHEMA[action.tool]
    args, notes = _normalise_args(action.tool, dict(action.args))
    for key in list(args):
        if key not in schema:
            raise ActionError("unknown_argument", f"{action.tool} has no argument {key!r}",
                              f"allowed: {', '.join(sorted(schema))}")
    for key, (want, required) in schema.items():
        if key not in args:
            if required:
                raise ActionError("missing_argument", f"{action.tool} needs {key!r}",
                                  f'{{"tool":"{action.tool}","args":{{"{key}":...}}}}')
            continue
        value = args[key]
        if want is int and isinstance(value, bool):
            raise ActionError("bad_argument", f"{key!r} must be an integer")
        if action.tool == "run" and key == "cmd" and isinstance(value, str):
            raise ActionError("bad_command", "cmd must be an argv list, not a string",
                              '{"tool":"run","args":{"cmd":["python","-m","pytest","-q"]}}')
        if not isinstance(value, want):
            raise ActionError("bad_argument",
                              f"{key!r} must be {want.__name__}, got {type(value).__name__}")
        if isinstance(value, str) and len(value) > MAX_ARG_CHARS:
            raise ActionError("argument_too_large", f"{key!r} is too large")

    if action.tool == "finish":
        return Action(action.tool, args, notes)

    if action.tool == "run":
        return Action(action.tool, {"cmd": _validate_command(args["cmd"], workspace)}, notes)

    if action.tool == "write_many":
        files = args["files"]
        if not files:
            raise ActionError("bad_argument", "write_many needs at least one file")
        if len(files) > 8:
            raise ActionError("too_many_files", "write_many is limited to 8 files")
        candidates = _candidates(workspace, write=True)
        normalised = []
        path_notes = []
        for item in files:
            if not isinstance(item, dict):
                raise ActionError("bad_argument", "each file must be {path, content}")
            path, content = item.get("path"), item.get("content")
            if not isinstance(path, str) or not isinstance(content, str):
                raise ActionError("bad_argument", "each file needs a string path and content")
            path, note = _normalise_path(path, candidates)
            if note:
                path_notes.append(note)
            normalised.append({"path": path, "content": content})
        # Atomic scope check: every file first, then any write may happen.
        for item in normalised:
            _check_write(item["path"], workspace, bounded_edit=bounded_edit)
        return Action(action.tool, {"files": normalised}, notes + tuple(path_notes))

    if action.tool == "write":
        path, note = _normalise_path(args["path"], _candidates(workspace, write=True))
        _check_write(path, workspace, bounded_edit=bounded_edit)
        out = dict(args)
        out["path"] = path
        return Action(action.tool, out, notes + ((note,) if note else ()))

    if action.tool == "ast_edit":
        path, note = _normalise_path(args["path"], _candidates(workspace, write=True))
        _check_write(path, workspace, bounded_edit=False)
        op = str(args.get("op") or "").strip().lower()
        if op:
            mapped = OP_ALIASES.get(op)
            if mapped:
                args["op"] = mapped
                notes = notes + (f"op_normalised:{op}->{mapped}",)
        if not str(args.get("target") or "").strip():
            raise ActionError("missing_argument", "ast_edit needs a target symbol",
                              '{"tool":"ast_edit","args":{"path":...,"op":"replace_function_body","target":"func"}}')
        if args.get("source") is not None and not isinstance(args["source"], str):
            raise ActionError("bad_argument", "ast_edit source must be a string")
        out = dict(args)
        out["path"] = path
        return Action(action.tool, out, notes + ((note,) if note else ()))

    if action.tool in ("apply_patch", "ast_edit_batch"):
        return Action(action.tool, args, notes)

    path_arg = _PATH_ARG.get(action.tool)
    if path_arg:
        rel = args.get(path_arg) or "."
        candidates = _candidates(workspace, write=False)
        rel, note = _normalise_path(rel, candidates)
        error = workspace.read_scope_error(rel)
        if error:
            raise ActionError("out_of_scope", error,
                              "allowed paths: " + ", ".join(candidates[:4]))
        args["path"] = rel
        return Action(action.tool, args, notes + ((note,) if note else ()))
    return Action(action.tool, args, notes)


def _candidates(workspace: Any, *, write: bool) -> list:
    paths = getattr(workspace, "allow_paths" if write else "read_paths", ()) or ()
    return [str(p) for p in paths]


def _normalise_path(rel: str, candidates: Sequence[str]) -> Tuple[str, Optional[str]]:
    """Resolve a truncated/partial path to the single scope entry it can mean.

    A small lane frequently emits ``"path":"North"`` for
    ``Northstar_backend/calc.py``. Rewriting is allowed ONLY when exactly one
    in-scope path starts with what it wrote - a guess between two files is never
    made. Returns (path, note).
    """
    raw = str(rel or "").strip().replace("\\", "/").lstrip("./")
    if not raw or not candidates:
        return rel, None
    # "calc.py.py" - a doubled extension is noise, not a different file.
    parts = raw.rsplit(".", 2)
    if len(parts) == 3 and parts[1] == parts[2]:
        raw = f"{parts[0]}.{parts[1]}"
    if raw in candidates:
        return raw, None
    low = raw.lower()
    matches = [c for c in candidates if c.lower().startswith(low)]
    if len(matches) != 1:
        # A lane often emits just the basename ("calc.py") for a nested path.
        suffix = "/" + low.lstrip("/")
        matches = [c for c in candidates if c.lower().endswith(suffix)]
    if len(matches) == 1:
        return matches[0], f"path_normalised:{raw}->{matches[0]}"
    return rel, None


def _check_write(rel: str, workspace: Any, *, bounded_edit: bool) -> None:
    error = workspace.write_scope_error(rel)
    if error:
        allowed = ", ".join(list(getattr(workspace, "allow_paths", ()) or [])[:4])
        raise ActionError("out_of_scope", error,
                          f"the only writable path(s): {allowed}" if allowed
                          else "write only the task's declared path")
    if not bounded_edit:
        return
    try:
        target = workspace.resolve(rel)
    except ValueError as exc:
        raise ActionError("bad_path", str(exc)) from exc
    if target.suffix.lower() not in SOURCE_SUFFIXES:
        return
    if target.is_file():
        # An existing source file is edited in place. A whole-file write is how a
        # small lane truncates a module it cannot reproduce - observed live: an
        # 8-line module was replaced by 54 bytes of broken code.
        raise ActionError(
            "bounded_edit_required",
            f"{rel} is an existing source file; a whole-file write is refused",
            "use ast_edit (Python) or apply_patch with a small hunk")


def _validate_command(cmd: Any, workspace: Any) -> list:
    if not isinstance(cmd, list) or not cmd:
        raise ActionError("bad_command", "cmd must be a non-empty argv list",
                          '{"tool":"run","args":{"cmd":["python","-m","pytest","-q"]}}')
    if len(cmd) > 12:
        raise ActionError("bad_command", "cmd is too long")
    argv = []
    for part in cmd:
        if not isinstance(part, str) or not part.strip():
            raise ActionError("bad_command", "every argv element must be a non-empty string")
        if any(ch in FORBIDDEN_ARG_CHARS for ch in part):
            raise ActionError("control_char", f"argv element {part!r} contains a control character")
        argv.append(part)
    # The allowlist itself is enforced by Workspace.run, which is the single
    # source of truth and reports its own refusal with the permitted commands.
    return argv


def json_schemas(names: Optional[Sequence[str]] = None) -> list:
    """OpenAI/Ollama-style tool definitions built from the one schema table.

    One source of truth: a native tool call and a JSON action are validated by the
    same ``_SCHEMA``, so the two interfaces cannot drift.
    """
    _types = {str: "string", int: "integer", list: "array", dict: "object"}
    out = []
    for name in (names or CANONICAL_ACTIONS):
        if name not in _SCHEMA:
            continue
        props = {}
        required = []
        for arg, (want, req) in _SCHEMA[name].items():
            props[arg] = {"type": _types.get(want, "string")}
            if req:
                required.append(arg)
        out.append({"type": "function", "function": {
            "name": name,
            "description": f"Northstar action {name}",
            "parameters": {"type": "object", "properties": props,
                           "required": required}}})
    return out


def rejection_kind(error: ActionError) -> str:
    """Map a code to the two buckets the ledger distinguishes.

    ``model``  - the output was never a usable action (JSON, schema, unknown tool).
    ``executor`` - it was a well-formed action the task scope or policy refuses.
    """
    return "model" if error.code in {
        "empty_output", "not_json", "invalid_json", "multiple_actions", "not_object",
        "missing_tool", "unknown_tool", "bad_args", "missing_argument",
        "bad_argument", "unknown_argument", "argument_too_large",
    } else "executor"


__all__ = ["Action", "ActionError", "CANONICAL_ACTIONS", "ALIASES",
           "SOURCE_SUFFIXES",
           "parse_action", "validate_action", "rejection_kind"]
