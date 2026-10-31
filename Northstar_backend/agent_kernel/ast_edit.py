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

Every edit is parsed, applied in memory, re-parsed, and only then written. A
batch is all-or-nothing: one bad edit writes nothing. Comments and blank-line
layout inside a replaced node are not preserved (ast.unparse is the serializer);
the module docstring, imports and all untouched nodes are.
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
    parent = node
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
            parent = current
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


def _apply_one(tree: ast.Module, edit: Edit) -> ast.Module:
    op = str(edit.op or "").strip().lower()
    if op not in OPS:
        raise AstEditError(f"unknown AST op {edit.op!r}; known: {', '.join(OPS)}")

    if op == "add_import":
        stmt = _parse_block(edit.source or edit.name, label="import")
        if len(stmt) != 1 or not isinstance(stmt[0], (ast.Import, ast.ImportFrom)):
            raise AstEditError("add_import source must be one import statement")
        new = stmt[0]
        for existing in tree.body:
            if isinstance(existing, (ast.Import, ast.ImportFrom)) and ast.dump(existing) == ast.dump(new):
                return tree
        insert_at = 0
        if tree.body and _is_docstring(tree.body[0]):
            insert_at = 1
        while insert_at < len(tree.body) and isinstance(tree.body[insert_at], (ast.Import, ast.ImportFrom)):
            insert_at += 1
        tree.body.insert(insert_at, new)
        return tree

    if op == "replace_imports":
        stmts = _parse_block(edit.source, label="imports")
        imports = [s for s in stmts if isinstance(s, (ast.Import, ast.ImportFrom))]
        if not imports or len(imports) != len(stmts):
            raise AstEditError("replace_imports source may contain only import statements")
        doc = tree.body[0] if tree.body and _is_docstring(tree.body[0]) else None
        kept: List[ast.stmt] = [doc] if doc is not None else []
        kept.extend(imports)
        kept.extend(s for s in tree.body
                    if not isinstance(s, (ast.Import, ast.ImportFrom)) and s is not doc)
        tree.body = kept
        return tree

    if op == "replace_global":
        name = str(edit.target or edit.name or "").strip()
        if not name:
            raise AstEditError("replace_global needs the assignment name")
        stmts = _parse_block(edit.source, label="global")
        if len(stmts) != 1 or not isinstance(stmts[0], (ast.Assign, ast.AnnAssign)):
            raise AstEditError("replace_global source must be one assignment")
        for i, existing in enumerate(tree.body):
            if isinstance(existing, ast.Assign) and any(
                    isinstance(t, ast.Name) and t.id == name for t in existing.targets):
                tree.body[i] = stmts[0]
                return tree
            if isinstance(existing, ast.AnnAssign) and isinstance(existing.target, ast.Name) \
                    and existing.target.id == name:
                tree.body[i] = stmts[0]
                return tree
        raise AstEditError(f"module-level assignment {name!r} not found")

    node, body, index = _find(tree, edit.target)

    if op == "replace_function_body":
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            raise AstEditError("replace_function_body target must be a function/method")
        _replace_body(node, _parse_block(edit.source, label="function body"))
        return tree

    if op == "replace_function":
        new = _parse_one_def(edit.source, label="replacement")
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and not isinstance(
                new, (ast.FunctionDef, ast.AsyncFunctionDef)):
            raise AstEditError("replace_function target is a function; replacement must be a def")
        if isinstance(node, ast.ClassDef) and not isinstance(new, ast.ClassDef):
            raise AstEditError("replace_function target is a class; replacement must be a class")
        body[index] = new
        return tree

    if op == "add_method":
        if not isinstance(node, ast.ClassDef):
            raise AstEditError("add_method target must be a class")
        new = _parse_one_def(edit.source, label="method")
        if not isinstance(new, (ast.FunctionDef, ast.AsyncFunctionDef)):
            raise AstEditError("add_method source must be a def")
        node.body.append(new)
        return tree

    if op in ("add_before", "add_after"):
        stmts = _parse_block(edit.source, label=op)
        at = index if op == "add_before" else index + 1
        for offset, stmt in enumerate(stmts):
            body.insert(at + offset, stmt)
        return tree

    if op == "delete":
        body.pop(index)
        return tree

    raise AstEditError(f"unhandled AST op {op!r}")


def apply_edit(source: str, edit: Dict[str, Any] | Edit) -> str:
    """Apply one edit to source text; return validated, unparsed Python."""
    e = edit if isinstance(edit, Edit) else Edit(
        op=str(edit.get("op") or ""),
        target=str(edit.get("target") or ""),
        source=str(edit.get("source") or ""),
        name=str(edit.get("name") or ""))
    tree = _parse_module(source)
    tree = _apply_one(tree, e)
    ast.fix_missing_locations(tree)
    try:
        rendered = ast.unparse(tree)
    except Exception as exc:  # noqa: BLE001 - serializer failure is a refusal
        raise AstEditError(f"could not serialize the edited tree: {exc}") from exc
    _parse_module(rendered, label="edited source")
    return rendered + ("\n" if not rendered.endswith("\n") else "")


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
    # Every file is valid before the first write.
    for path, _old, _encoding, _crlf in prepared:
        final = seen[path]
        _parse_module(final, label=str(path))
    for path, _old, encoding, crlf in prepared:
        _write_atomic(path, seen[path], encoding, crlf)
    return {"ok": True, "files": [str(p) for p, _s, _e, _c in prepared],
            "edits": sum(len(item.get("edits") or []) for item in batch)}


__all__ = ["AstEditError", "Edit", "OPS", "apply_edit", "apply_edits",
           "apply_to_file", "apply_batch"]
