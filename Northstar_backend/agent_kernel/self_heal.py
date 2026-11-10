"""Exception interception, scope extraction and AST self-healing.

The loop this implements:

    traceback -> enclosing function/class scope (ast.get_source_segment)
              -> reasoning lane proposes AST edits (JSON)
              -> edits applied in memory and validated
              -> patched file tested in a sandbox
              -> keep on pass, restore the original bytes on fail

The model never writes a text diff. It names a symbol and supplies a body; the
AST engine resolves the target. A failed verification restores the file
byte-for-byte, so a bad self-patch cannot leave the tree half-edited.

Isolation: `apply=True` refuses to run without docker/bubblewrap unless the
caller explicitly opts into the process fallback (test-only; not a security
boundary).
"""
from __future__ import annotations

import ast
import difflib
import json
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence

from . import sandbox
from .ast_edit import AstEditError, apply_edits

MAX_SCOPE_BYTES = 40_000
_FRAME_RE = re.compile(r'File "(?P<file>[^"]+)", line (?P<line>\d+), in (?P<name>\S+)')


class SelfHealError(RuntimeError):
    """The traceback or the proposed patch could not be used safely."""


@dataclass
class Scope:
    file: Path
    line: int
    name: str
    qualname: str
    source: str
    node_type: str
    truncated: bool = False


def _resolve_frame(path_text: str, root: Path) -> Optional[Path]:
    raw = str(path_text or "").strip()
    if not raw or raw.startswith("<"):
        return None
    candidate = Path(raw)
    if not candidate.is_absolute():
        candidate = (root / candidate)
    try:
        resolved = candidate.resolve()
    except OSError:
        return None
    if resolved != root and root not in resolved.parents:
        return None
    return resolved if resolved.is_file() else None


def _qualname(node: ast.AST, parents: Sequence[str]) -> str:
    name = getattr(node, "name", "")
    return ".".join([*parents, name]) if name else ".".join(parents)


def _enclosing(tree: ast.Module, line: int) -> Optional[tuple]:
    best = None

    def walk(body: Sequence[ast.stmt], parents: List[str]) -> None:
        nonlocal best
        for node in body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                start = getattr(node, "lineno", 0)
                end = getattr(node, "end_lineno", start)
                if start <= line <= end:
                    if best is None or (end - start) < (best[1].end_lineno - best[1].lineno):
                        best = (node, node, list(parents))
                    walk(node.body, [*parents, node.name])

    walk(tree.body, [])
    if best is None:
        return None
    node, _node, parents = best
    return node, _qualname(node, parents)


def scope_from_traceback(traceback_text: str, root: Path | str) -> Scope:
    """Extract the innermost enclosing scope for the last real frame."""
    root = Path(root).resolve()
    frames = list(_FRAME_RE.finditer(str(traceback_text or "")))
    if not frames:
        raise SelfHealError("no Python frame found in the traceback")
    for frame in reversed(frames):
        path = _resolve_frame(frame.group("file"), root)
        if path is None or path.suffix.lower() != ".py":
            continue
        line = int(frame.group("line"))
        try:
            source = path.read_text(encoding="utf-8-sig")
            tree = ast.parse(source)
        except (OSError, SyntaxError) as exc:
            raise SelfHealError(f"could not read/parse {path}: {exc}") from exc
        found = _enclosing(tree, line)
        if found is None:
            raise SelfHealError(f"no enclosing function/class at {path}:{line}")
        node, qualname = found
        segment = ast.get_source_segment(source, node) or ""
        truncated = len(segment.encode("utf-8")) > MAX_SCOPE_BYTES
        return Scope(file=path, line=line, name=frame.group("name"),
                     qualname=qualname, source=segment[:MAX_SCOPE_BYTES],
                     node_type=type(node).__name__, truncated=truncated)
    raise SelfHealError("no frame inside the workspace could be resolved")


def _extract_json(text: str) -> Dict[str, Any]:
    raw = str(text or "").strip()
    raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.IGNORECASE).strip()
    start = raw.find("{")
    end = raw.rfind("}")
    if start < 0 or end <= start:
        raise SelfHealError("the reasoner did not return a JSON object")
    try:
        payload = json.loads(raw[start:end + 1])
    except json.JSONDecodeError as exc:
        raise SelfHealError(f"the reasoner JSON is invalid: {exc}") from exc
    if not isinstance(payload, dict):
        raise SelfHealError("the reasoner JSON must be an object")
    return payload


def diagnose(scope: Scope, traceback_text: str, *,
             reasoner: Callable[[Dict[str, Any]], str]) -> Dict[str, Any]:
    """Ask the reasoning lane for AST edits and validate them in memory."""
    brief = {
        "task": "repair the failing Python scope with AST edits",
        "file": str(scope.file),
        "line": scope.line,
        "qualname": scope.qualname,
        "node_type": scope.node_type,
        "scope": scope.source,
        "traceback": str(traceback_text or "")[-6000:],
        "allowed_ops": ["replace_function_body", "replace_function", "add_method",
                        "add_before", "add_after", "delete", "add_import",
                        "replace_imports", "replace_global"],
        "output": ('Return ONLY JSON: {"explanation": "...", "edits": '
                   '[{"op":"...","target":"...","source":"..."}]}'),
    }
    raw = reasoner(brief)
    payload = _extract_json(raw if isinstance(raw, str) else json.dumps(raw))
    edits = payload.get("edits")
    if not isinstance(edits, list) or not edits:
        raise SelfHealError("the reasoner returned no edits")
    source, _bom, _crlf = _read_text(scope.file)
    try:
        apply_edits(source, edits)
    except AstEditError as exc:
        raise SelfHealError(f"the proposed AST edit does not apply: {exc}") from exc
    return {"explanation": str(payload.get("explanation") or "")[:1000],
            "edits": edits, "file": str(scope.file)}


def _read_text(path: Path) -> tuple:
    raw = path.read_bytes()
    bom = raw.startswith(b"\xef\xbb\xbf")
    text = raw.decode("utf-8-sig")
    return text, bom, ("\r\n" in text)


def _write_text(path: Path, text: str, bom: bool, crlf: bool) -> None:
    if crlf:
        text = text.replace("\r\n", "\n").replace("\n", "\r\n")
    data = text.encode("utf-8")
    path.write_bytes((b"\xef\xbb\xbf" if bom else b"") + data)


def local_reasoner(brief: Dict[str, Any], *, url: Optional[str] = None,
                   timeout: float = 240.0) -> str:
    """Ask the local lane for a repair plan (JSON AST edits). Fail closed."""
    import os
    import urllib.error
    import urllib.request
    import lane_policy
    route = lane_policy.route("reasoning")
    endpoint = (url or os.environ.get("NORTHSTAR_REASONER_URL")
                or "http://127.0.0.1:8080/v1").rstrip("/")
    system = (
        "You are the Northstar repair planner. You receive one failing Python "
        "scope and its traceback. Return ONLY a JSON object with keys "
        "'explanation' and 'edits'. Each edit is one of: replace_function_body, "
        "replace_function, add_method, add_before, add_after, delete, add_import, "
        "replace_imports, replace_global. Target symbols by name. Never return a "
        "text diff, markdown or prose outside the JSON."
    )
    body = {
        "model": route["lane"],
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": json.dumps(brief, ensure_ascii=False)},
        ],
        "temperature": 0.1,
        "max_tokens": 1200,
        "reasoning_effort": "low",
        "stream": False,
    }
    req = urllib.request.Request(
        f"{endpoint}/chat/completions",
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
        raise SelfHealError(f"local reasoner unavailable: {exc}") from exc
    choices = payload.get("choices") or []
    text = (choices[0].get("message") or {}).get("content") if choices else ""
    if not str(text or "").strip():
        raise SelfHealError("local reasoner returned an empty completion")
    return str(text)


def _diff(before: str, after: str, path: Path) -> str:
    return "".join(difflib.unified_diff(
        before.splitlines(keepends=True), after.splitlines(keepends=True),
        fromfile=str(path), tofile=str(path)))[:8000]


def heal(traceback_text: str, *, root: Path | str,
         reasoner: Callable[[Dict[str, Any]], str],
         verify_cmd: Optional[Sequence[str]] = None,
         timeout: float = 120.0, apply: bool = False,
         require_isolation: bool = True,
         approval_id: Optional[str] = None) -> Dict[str, Any]:
    """Propose (and optionally verify+apply) an AST repair."""
    started = time.time()
    root = Path(root).resolve()
    scope = scope_from_traceback(traceback_text, root)
    plan = diagnose(scope, traceback_text, reasoner=reasoner)
    before, bom, crlf = _read_text(scope.file)
    after = apply_edits(before, plan["edits"])
    plan["diff"] = _diff(before, after, scope.file)
    plan["scope_ms"] = round((time.time() - started) * 1000.0, 1)
    plan["applied"] = False
    plan["verified"] = False
    if not apply:
        return plan

    runtime = "process"
    if require_isolation:
        runtime = sandbox.require_isolated()
    if not verify_cmd:
        raise SelfHealError("apply=True needs a verify_cmd (the sandboxed test command)")
    if approval_id:
        from . import hitl
        hitl.require_approved(root, approval_id)
    original = scope.file.read_bytes()
    _write_text(scope.file, after, bom, crlf)
    result: Dict[str, Any] = {"ok": False, "error": "sandbox did not run"}
    try:
        result = sandbox.run(verify_cmd, cwd=root, timeout=timeout, runtime=runtime)
    finally:
        if not result.get("ok"):
            scope.file.write_bytes(original)
    plan["verified"] = bool(result.get("ok"))
    plan["verification"] = {k: result.get(k) for k in
                            ("ok", "runtime", "isolation", "exit", "timeout",
                             "error", "output")}
    if not result.get("ok"):
        plan["restored"] = True
        return plan
    plan["applied"] = True
    return plan


__all__ = ["SelfHealError", "Scope", "scope_from_traceback", "diagnose",
           "local_reasoner", "heal"]
