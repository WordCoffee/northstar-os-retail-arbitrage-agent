"""Deterministic AST editing for the coding lanes.

Text diffs are the wrong primitive for a model: they require reproducing context
line numbers and whitespace across a whole file, and on large files the failure
rate approaches 100%. This module edits the SYNTAX TREE by symbol name instead:

    replace_function_body   keep signature + decorators + docstring, new body
    replace_function        replace the whole def/class
    add_method              append a method to an existing class
    add_before / add_after  insert a block at the target's indentation
    delete                  remove a function/class node
    add_import              add a top-level import if absent
    replace_imports         replace the top-level import block
    replace_global          replace a module-level assignment

Every edit is parsed, applied to the SOURCE SPAN of the target only, re-parsed,
and only then written. Comments and formatting outside the edited span survive
byte-for-byte; comments inside a replaced node do not (ast.unparse is the
serializer for the new node). A batch is all-or-nothing: one bad edit writes
nothing.
"""
from __future__ import annotations

import ast
import io
import os
import textwrap
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from .patch_tool import PatchError, validate_path

OPS = ("replace_function_body", "replace_function", "add_method", "add_before",
       "add_after", "delete", "add_import", "replace_imports", "replace_global")


class AstEditError(ValueError):
    """The edit could not be resolved, parsed or validated."""


@dataclass
class Edit:
    op: str
    target: str = ""
    source: str = ""
    name: str = ""


def _parse_module(source: str, *, label: str = "source") -> ast.Module:
    try:
        return ast.parse(source)
    except SyntaxError as exc:
        raise AstEditError(f"{label} is not valid Python: {exc.msg} (line {exc.lineno})") from exc


def _find(node: ast.AST, target: str) -> Tuple[ast.AST, List[ast.stmt], int]:
    """Resolve a dotted target; return (node, parent body, index)."""
    parts = [p for p in str(target or "").split(".") if p]
    if not parts:
        raise AstEditError("an AST edit needs a target symbol name")
    body = getattr(node, "body", [])
    current = None
    for depth, part in enumerate(parts):
        current = None
        for child in body:
            if (isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
                    and child.name == part):
                current = child
                break
        if current is None:
            raise AstEditError(f"target {target!r} not found (missing {part!r})")
        if depth < len(parts) - 1:
            if not isinstance(current, ast.ClassDef):
                raise AstEditError(f"target {target!r}: {part!r} is not a class")
            body = current.body
    assert current is not None
    return current, body, body.index(current)


def _parse_block(source: str, *, label: str) -> List[ast.stmt]:
    text = textwrap.dedent(str(source or "")).strip("\n")
    if not text.strip():
        raise AstEditError(f"{label} is empty")
    module = _parse_module(text, label=label)
    return module.body


def _parse_one_def(source: str, *, label: str) -> ast.stmt:
    body = _parse_block(source, label=label)
    defs = [n for n in body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))]
    if len(defs) != 1:
        raise AstEditError(f"{label} must contain exactly one def/class (got {len(defs)})")
    return defs[0]


def _is_docstring(stmt: ast.stmt) -> bool:
    return isinstance(stmt, ast.Expr) and isinstance(getattr(stmt, "value", None), ast.Constant) \
        and isinstance(stmt.value.value, str)


def _replace_body(node: ast.AST, new_body: List[ast.stmt]) -> None:
    old = getattr(node, "body", [])
    doc = old[0] if old and _is_docstring(old[0]) else None
    if doc is not None and not (new_body and _is_docstring(new_body[0])):
        new_body = [doc] + list(new_body)
    node.body = list(new_body)


def _render(nodes: Sequence[ast.stmt]) -> str:
    module = ast.Module(body=list(nodes), type_ignores=[])
    ast.fix_missing_locations(module)
    return ast.unparse(module)


def _lines(source: str) -> List[str]:
    return source.splitlines(keepends=True)


def _with_newline(text: str) -> str:
    return text if text.endswith("\n") else text + "\n"


def _indent(text: str, prefix: str) -> str:
    return "\n".join((prefix + line) if line.strip() else line
                     for line in text.splitlines())


def _node_start(node: ast.AST) -> int:
    decorators = getattr(node, "decorator_list", []) or []
    return min([getattr(d, "lineno", node.lineno) for d in decorators] + [node.lineno])


def _node_end(node: ast.AST) -> int:
    return int(getattr(node, "end_lineno", node.lineno))


def _indent_at(lines: Sequence[str], lineno: int) -> str:
    raw = lines[lineno - 1] if 0 < lineno <= len(lines) else ""
    return raw[:len(raw) - len(raw.lstrip(" \t"))]


def _splice(lines: List[str], start: int, end: int, text: str) -> List[str]:
    """Replace 1-based inclusive [start, end] with rendered text."""
    block = [line + "\n" for line in text.splitlines()]
    if not block:
        block = [""]
    return lines[:start - 1] + block + lines[end:]


def _insert(lines: List[str], index: int, text: str) -> List[str]:
    block = [line + "\n" for line in text.splitlines()]
    return lines[:index] + block + lines[index:]


def _find_global(tree: ast.Module, name: str) -> Optional[ast.stmt]:
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
                isinstance(t, ast.Name) and t.id == name for t in node.targets):
            return node
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) \
                and node.target.id == name:
            return node
    return None


def _import_insert_index(tree: ast.Module) -> int:
    """0-based line index after the docstring and existing imports."""
    lines = tree.body
    index = 0
    if lines and _is_docstring(lines[0]):
        index = _node_end(lines[0])
    while index < len(lines) and isinstance(lines[index], (ast.Import, ast.ImportFrom)):
        index = _node_end(lines[index])
    return index


def _apply_edit(source: str, edit: Edit) -> str:
    op = str(edit.op or "").strip().lower()
    if op not in OPS:
        raise AstEditError(f"unknown AST op {edit.op!r}; known: {', '.join(OPS)}")
    tree = _parse_module(source)
    lines = _lines(source)

    if op == "add_import":
        stmts = _parse_block(edit.source or edit.name, label="import")
        if len(stmts) != 1 or not isinstance(stmts[0], (ast.Import, ast.ImportFrom)):
            raise AstEditError("add_import source must be one import statement")
        new = stmts[0]
        for existing in tree.body:
            if isinstance(existing, (ast.Import, ast.ImportFrom)) and ast.dump(existing) == ast.dump(new):
                return source
        at = _import_insert_index(tree)
        rendered = textwrap.dedent(str(edit.source or edit.name)).strip("\n")
        out = "".join(_insert(lines, at, rendered))
        _parse_module(out, label="edited source")
        return out

    if op == "replace_imports":
        stmts = _parse_block(edit.source, label="imports")
        imports = [s for s in stmts if isinstance(s, (ast.Import, ast.ImportFrom))]
        if not imports or len(imports) != len(stmts):
            raise AstEditError("replace_imports source may contain only import statements")
        existing = [s for s in tree.body if isinstance(s, (ast.Import, ast.ImportFrom))]
        rendered = textwrap.dedent(str(edit.source)).strip("\n")
        if existing:
            out = "".join(_splice(lines, _node_start(existing[0]),
                                  _node_end(existing[-1]), rendered))
        else:
            at = _import_insert_index(tree)
            out = "".join(_insert(lines, at, rendered))
        _parse_module(out, label="edited source")
        return out

    if op == "replace_global":
        name = str(edit.target or edit.name or "").strip()
        if not name:
            raise AstEditError("replace_global needs the assignment name")
        stmts = _parse_block(edit.source, label="global")
        if len(stmts) != 1 or not isinstance(stmts[0], (ast.Assign, ast.AnnAssign)):
            raise AstEditError("replace_global source must be one assignment")
        node = _find_global(tree, name)
        if node is None:
            raise AstEditError(f"module-level assignment {name!r} not found")
        rendered = textwrap.dedent(str(edit.source)).strip("\n")
        out = "".join(_splice(lines, _node_start(node), _node_end(node), rendered))
        _parse_module(out, label="edited source")
        return out

    node, body, index = _find(tree, edit.target)
    start, end = _node_start(node), _node_end(node)
    indent = _indent_at(lines, node.lineno)

    if op == "replace_function_body":
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            raise AstEditError("replace_function_body target must be a function/method")
        old_body = list(node.body)
        if not old_body:
            raise AstEditError("replace_function_body target has no body")
        body_indent = _indent_at(lines, old_body[0].lineno)
        new_text = textwrap.dedent(str(edit.source)).strip("\n")
        new_stmts = _parse_block(new_text, label="function body")
        old_doc = old_body[0] if _is_docstring(old_body[0]) else None
        if old_doc is not None and not _is_docstring(new_stmts[0]):
            doc_text = ast.get_source_segment(source, old_doc) or '""'
            doc_text = textwrap.dedent(" " * old_doc.col_offset + doc_text)
            new_text = doc_text + "\n" + new_text
        out = "".join(_splice(lines, _node_start(old_body[0]), _node_end(old_body[-1]),
                              _indent(new_text, body_indent)))
        _parse_module(out, label="edited source")
        return out

    if op == "replace_function":
        new = _parse_one_def(edit.source, label="replacement")
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and not isinstance(
                new, (ast.FunctionDef, ast.AsyncFunctionDef)):
            raise AstEditError("replace_function target is a function; replacement must be a def")
        if isinstance(node, ast.ClassDef) and not isinstance(new, ast.ClassDef):
            raise AstEditError("replace_function target is a class; replacement must be a class")
        rendered = textwrap.dedent(str(edit.source)).strip("\n")
        out = "".join(_splice(lines, start, end, _indent(rendered, indent)))
        _parse_module(out, label="edited source")
        return out

    if op == "add_method":
        if not isinstance(node, ast.ClassDef):
            raise AstEditError("add_method target must be a class")
        new = _parse_one_def(edit.source, label="method")
        if not isinstance(new, (ast.FunctionDef, ast.AsyncFunctionDef)):
            raise AstEditError("add_method source must be a def")
        body_indent = _indent_at(lines, node.body[0].lineno) if node.body else indent + "    "
        insert_at = _node_end(node.body[-1]) if node.body else _node_end(node)
        rendered = textwrap.dedent(str(edit.source)).strip("\n")
        rendered = _indent(rendered, body_indent)
        if insert_at > 0 and lines[insert_at - 1].strip():
            rendered = "\n" + rendered
        out = "".join(_insert(lines, insert_at, rendered))
        _parse_module(out, label="edited source")
        return out

    if op in ("add_before", "add_after"):
        stmts = _parse_block(edit.source, label=op)
        rendered = _indent(textwrap.dedent(str(edit.source)).strip("\n"), indent)
        at = start - 1 if op == "add_before" else end
        if at < len(lines) and lines[at].strip():
            rendered = rendered + "\n\n"
        out = "".join(_insert(lines, at, rendered))
        _parse_module(out, label="edited source")
        return out

    if op == "delete":
        out = "".join(lines[:start - 1] + lines[end:])
        _parse_module(out, label="edited source")
        return out

    raise AstEditError(f"unhandled AST op {op!r}")


def apply_edit(source: str, edit: Dict[str, Any] | Edit) -> str:
    """Apply one edit to source text; return validated Python with untouched
    spans preserved verbatim."""
    e = edit if isinstance(edit, Edit) else Edit(
        op=str(edit.get("op") or ""),
        target=str(edit.get("target") or ""),
        source=str(edit.get("source") or ""),
        name=str(edit.get("name") or ""))
    out = _apply_edit(source, e)
    _parse_module(out, label="edited source")
    return out if out.endswith("\n") else out + "\n"


def apply_edits(source: str, edits: Iterable[Dict[str, Any] | Edit]) -> str:
    """Apply edits sequentially in memory; any failure leaves the source intact."""
    text = source
    for edit in edits:
        text = apply_edit(text, edit)
    return text


def _read(path: Path) -> Tuple[str, str, bool]:
    raw = path.read_bytes()
    bom = raw.startswith(b"\xef\xbb\xbf")
    text = raw.decode("utf-8-sig")
    return text, ("utf-8-sig" if bom else "utf-8"), ("\r\n" in text)


def _write_atomic(path: Path, text: str, encoding: str, crlf: bool = False) -> None:
    tmp = path.with_name(f".{path.name}.asttmp-{uuid.uuid4().hex}")
    try:
        if crlf:
            text = text.replace("\r\n", "\n").replace("\n", "\r\n")
        with open(tmp, "w", encoding=encoding, newline="") as fh:
            fh.write(text)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
    finally:
        try:
            if tmp.exists():
                tmp.unlink()
        except OSError:
            pass


def apply_to_file(root: Path | str, rel_path: str, edits: Iterable[Dict[str, Any] | Edit],
                  *, dry_run: bool = False) -> Dict[str, Any]:
    """Apply a batch of AST edits to one workspace-relative Python file."""
    root = Path(root).resolve()
    try:
        path = validate_path(rel_path, root)
    except PatchError as exc:
        raise AstEditError(str(exc)) from exc
    if path.suffix.lower() != ".py":
        raise AstEditError(f"AST editing is Python-only; {rel_path!r} is not .py")
    if not path.is_file():
        raise AstEditError(f"file not found: {rel_path}")
    source, encoding, crlf = _read(path)
    rendered = apply_edits(source, edits)
    if not dry_run:
        _write_atomic(path, rendered, encoding, crlf)
    return {"ok": True, "path": str(path), "dry_run": bool(dry_run),
            "bytes_before": len(source.encode("utf-8")),
            "bytes_after": len(rendered.encode("utf-8"))}


def apply_batch(root: Path | str, batch: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    """Apply edits across files atomically: all validate first, then all write."""
    root = Path(root).resolve()
    prepared: List[Tuple[Path, str, str, bool]] = []
    seen: Dict[Path, str] = {}
    for item in batch:
        rel = str(item.get("path") or "")
        if not rel:
            raise AstEditError("every batch entry needs a path")
        try:
            path = validate_path(rel, root)
        except PatchError as exc:
            raise AstEditError(str(exc)) from exc
        if path.suffix.lower() != ".py" or not path.is_file():
            raise AstEditError(f"not an editable Python file: {rel}")
        if path not in seen:
            source, encoding, crlf = _read(path)
            seen[path] = source
            prepared.append((path, source, encoding, crlf))
        seen[path] = apply_edits(seen[path], item.get("edits") or [])
    for path, _old, _encoding, _crlf in prepared:
        _parse_module(seen[path], label=str(path))
    for path, _old, encoding, crlf in prepared:
        _write_atomic(path, seen[path], encoding, crlf)
    return {"ok": True, "files": [str(p) for p, _s, _e, _c in prepared],
            "edits": sum(len(item.get("edits") or []) for item in batch)}


__all__ = ["AstEditError", "Edit", "OPS", "apply_edit", "apply_edits",
           "apply_to_file", "apply_batch"]
