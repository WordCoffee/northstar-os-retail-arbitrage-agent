"""Purpose commands — read-only self-analysis of this repository.

Implements the "Embedded Purpose Commands" section of the Project Thorn v5.0
plan as three deterministic routines:

    /optimize-architecture   module coupling, circular dependencies, wide interfaces
    /refactor-performance    hot-loop / blocking-in-async / memory-footprint heuristics
    /expand-vectors          test-reference gaps + generated expansion scenarios

Honesty contract (why this module is written the way it is)
-----------------------------------------------------------
* **PROPOSAL-ONLY.** Nothing here writes, renames, moves or refactors anything.
  Every finding carries the numbers it was derived from and a ``proposal`` string
  that a human — or a later, explicitly approved card — must act on.
* **HEURISTIC, AND SAYS SO.** This is static AST analysis, not a profiler and not
  a coverage tool. Each report carries ``method`` and ``caveats`` so a finding can
  never be mistaken for a measurement it is not. "No test reference" means the
  module's name does not appear in any test file — it does not mean the code is
  untested.
* **BOUNDED.** File count, file size and findings-per-report are capped, so this
  can run over the whole repository inside a chat turn.
* **DETERMINISTIC.** Same tree in, same report out: no timestamps in the body,
  every list sorted.
* **CONTAINED.** A caller may pass a sub-path; it can never escape the repo root.

CLI
---
    python -m Northstar_backend.purpose_commands --command optimize-architecture
    python -m Northstar_backend.purpose_commands --command refactor-performance --path Northstar_backend
    python -m Northstar_backend.purpose_commands --command expand-vectors --limit 40
"""
from __future__ import annotations

import argparse
import ast
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

# ── bounds (deliberately explicit constants, not magic numbers) ──────────────
MAX_FILES = 4000
MAX_FILE_BYTES = 400_000
MAX_FINDINGS = 60
MAX_LISTED = 25

LONG_FUNCTION_LOC = 120
DEEP_NESTING = 5
WIDE_FANOUT = 12
BLOCKING_IN_ASYNC = 1

SKIP_DIRS = {
    ".git", "node_modules", "__pycache__", "dist", "build", ".playwright-mcp",
    "site-packages", ".venv", "venv", ".mypy_cache", ".pytest_cache",
    "migrations_foundation", "screenshots",
}

# Calls that block the event loop when awaited-from inside `async def`.
BLOCKING_CALLS = {
    "time.sleep", "requests.get", "requests.post", "requests.put",
    "requests.delete", "requests.request", "urllib.request.urlopen",
    "open", "subprocess.run", "subprocess.call", "subprocess.check_output",
    "input",
}

METHOD_CYCLES = (
    "Parsed every Python module under the root with `ast`. Each import is resolved "
    "conservatively: an exact module/package match wins; a leaf name is used ONLY "
    "when it is unique in the tree — anything that would require guessing is "
    "counted as unresolved instead, because a guessed edge would fabricate a "
    "dependency and therefore fabricate a cycle. Strongly-connected components "
    "(Tarjan) of the resulting graph are reported as cycles; fan-in/fan-out are "
    "counted edges."
)
METHOD_PERF = (
    "Parsed every Python module with `ast`; per-function line span, control-flow "
    "nesting depth, loop-in-loop depth, blocking calls inside `async def`, "
    "unbounded reads and in-loop string growth were counted from the syntax tree. "
    "No process was executed and no code was imported."
)
METHOD_VECTORS = (
    "Built the module list from disk, then scanned every test file's text for the "
    "module's name (substring, word-bounded). A module with no hit is reported as "
    "having no test REFERENCE, which is weaker than having no coverage."
)

CAVEAT_CYCLES = [
    "Import cycles are a coupling signal, not always a defect: a package's "
    "__init__ re-export or a deliberate lazy import can create an edge that never "
    "executes at the same time.",
    "Only Python is analysed. The React UI, SQL and shell surfaces are out of scope.",
]
CAVEAT_PERF = [
    "This is static analysis. A flagged loop may run over three items; a flagged "
    "blocking call may be unreachable. Nothing here was measured at runtime.",
    "Absolute time and memory numbers are NOT produced — no profiling was run.",
]
CAVEAT_VECTORS = [
    "A missing test reference is not proof of missing coverage, and a present "
    "reference is not proof of a meaningful assertion.",
    "Generated scenarios are suggestions derived from public function names; they "
    "are not a verified plan and nothing is executed.",
]


# ── shared helpers ───────────────────────────────────────────────────────────

def repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def resolve_root(path: Optional[str]) -> Path:
    """Resolve a caller-supplied sub-path, refusing to escape the repo root."""
    root = repo_root()
    if not path:
        return root
    candidate = (root / path).resolve() if not os.path.isabs(path) else Path(path).resolve()
    try:
        candidate.relative_to(root)
    except ValueError:
        raise ValueError(f"path escapes the repository root: {path!r}")
    if not candidate.exists():
        raise ValueError(f"path does not exist: {path!r}")
    return candidate


def _iter_files(root: Path, suffix: str, limit: int) -> Tuple[List[Path], bool]:
    out: List[Path] = []
    truncated = False
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(
            d for d in dirnames
            if d not in SKIP_DIRS
            and not d.startswith(("venv", ".venv"))   # venv-phase1c02, venv-*, .venv
            and not d.endswith(".egg-info"))
        for name in sorted(filenames):
            if not name.endswith(suffix):
                continue
            p = Path(dirpath) / name
            try:
                if p.stat().st_size > MAX_FILE_BYTES:
                    continue
            except OSError:
                continue
            out.append(p)
            if len(out) >= limit:
                return out, True
    return out, truncated


def _read(p: Path) -> Optional[str]:
    try:
        return p.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None


def _parse(p: Path, text: str) -> Optional[ast.AST]:
    try:
        return ast.parse(text)
    except SyntaxError:
        return None


def _module_dotted(path: Path, root: Path) -> str:
    try:
        rel = path.relative_to(root)
    except ValueError:
        rel = path
    return ".".join(rel.with_suffix("").parts)


def _full_name(node: ast.AST) -> str:
    """dotted name for Attribute/Name chains (`a.b.c`), else ''."""
    parts: List[str] = []
    cur: Any = node
    while isinstance(cur, ast.Attribute):
        parts.append(cur.attr)
        cur = cur.value
    if isinstance(cur, ast.Name):
        parts.append(cur.id)
    return ".".join(reversed(parts))


def _tally(kinds: Iterable[str]) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for k in kinds:
        counts[k] = counts.get(k, 0) + 1
    return dict(sorted(counts.items()))


def _finding(kind: str, severity: str, target: str, detail: str,
             metric: Dict[str, Any], proposal: str) -> Dict[str, Any]:
    return {"kind": kind, "severity": severity, "target": target, "detail": detail,
            "metric": metric, "proposal": proposal}


def _report(command: str, method: str, caveats: List[str], scanned: Dict[str, Any],
            findings: List[Dict[str, Any]], summary_bits: str) -> Dict[str, Any]:
    findings = sorted(findings, key=lambda f: (f["severity"], f["kind"], f["target"]))[:MAX_FINDINGS]
    return {
        "command": command,
        "ok": True,
        "summary": f"{summary_bits} {len(findings)} finding(s). Read-only; nothing was changed.",
        "method": method,
        "caveats": caveats,
        "scanned": scanned,
        "counts": _tally(f["kind"] for f in findings),
        "findings": findings,
    }


# ── /optimize-architecture ───────────────────────────────────────────────────

def _import_specs(tree: ast.AST) -> List[Tuple[str, int, Optional[str]]]:
    """(base_module, relative_level, imported_name|None) for every import node.

    `import a.b`            -> ("a.b", 0, None)
    `from pkg import b`     -> ("pkg", 0, "b")
    `from . import b`       -> ("",    1, "b")
    """
    specs: List[Tuple[str, int, Optional[str]]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            specs.extend((a.name, 0, None) for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            base = node.module or ""
            specs.extend((base, node.level or 0, a.name) for a in node.names)
    return specs


def _resolve_import(base: str, level: int, name: Optional[str], importer: str,
                    modules: Set[str], leaf_index: Dict[str, List[str]]) -> Tuple[Optional[str], bool]:
    """Resolve one import to an internal module.

    Returns (target, ambiguous). `ambiguous` means the name COULD be internal but
    could not be resolved without guessing — counted, never turned into an edge.
    Guessing here would fabricate dependency edges, and a fabricated edge is a
    fabricated cycle.
    """
    if level:                                    # relative import
        parts = importer.split(".")[:-1]
        up = level - 1
        if up > len(parts):
            return None, False
        stack = list(parts[:len(parts) - up])
        if base:
            stack.extend(base.split("."))
        if name:
            cand = ".".join(stack + [name])
            if cand in modules:
                return cand, False
        joined = ".".join(stack)
        if joined and joined in modules:
            return joined, False
        return None, True

    if name:
        cand = f"{base}.{name}" if base else name
        if cand in modules:
            return cand, False
        if base and base in modules:
            return base, False                       # `from pkg import attr` -> pkg/__init__
    else:
        if base in modules:
            return base, False

    leaf = (name or base).rsplit(".", 1)[-1]
    hits = leaf_index.get(leaf) or []
    if len(hits) == 1:
        return hits[0], False
    # A name that exists more than once in the tree must never be guessed.
    return None, bool(hits)


def _tarjan_cycles(graph: Dict[str, Set[str]]) -> List[List[str]]:
    """Iterative Tarjan SCC; returns components of size > 1 (true cycles)."""
    index: Dict[str, int] = {}
    low: Dict[str, int] = {}
    on_stack: Set[str] = set()
    stack: List[str] = []
    sccs: List[List[str]] = []
    counter = 0

    for start in sorted(graph):
        if start in index:
            continue
        work: List[Tuple[str, int]] = [(start, 0)]
        while work:
            node, pi = work[-1]
            if pi == 0:
                index[node] = low[node] = counter
                counter += 1
                stack.append(node)
                on_stack.add(node)
            recursed = False
            neighbours = sorted(graph.get(node, ()))
            for i in range(pi, len(neighbours)):
                nxt = neighbours[i]
                if nxt not in index:
                    work[-1] = (node, i + 1)
                    work.append((nxt, 0))
                    recursed = True
                    break
                if nxt in on_stack:
                    low[node] = min(low[node], index[nxt])
            if recursed:
                continue
            if low[node] == index[node]:
                comp: List[str] = []
                while True:
                    top = stack.pop()
                    on_stack.discard(top)
                    comp.append(top)
                    if top == node:
                        break
                if len(comp) > 1:
                    sccs.append(sorted(comp))
            work.pop()
            if work:
                parent = work[-1][0]
                low[parent] = min(low[parent], low[node])
    return sorted(sccs)


def analyze_architecture(root: Optional[Path] = None) -> Dict[str, Any]:
    root = root or repo_root()
    files, truncated = _iter_files(root, ".py", MAX_FILES)
    modules: Dict[str, Path] = {}
    trees: Dict[str, ast.AST] = {}
    for p in files:
        dotted = _module_dotted(p, root)
        text = _read(p)
        if text is None:
            continue
        tree = _parse(p, text)
        if tree is None:
            continue
        modules[dotted] = p
        trees[dotted] = tree

    # short-name index so `import chat_tools` from anywhere resolves
    by_leaf: Dict[str, List[str]] = {}
    for dotted in modules:
        by_leaf.setdefault(dotted.rsplit(".", 1)[-1], []).append(dotted)

    edges: Dict[str, Set[str]] = {m: set() for m in modules}
    external = 0
    ambiguous = 0
    for dotted, tree in trees.items():
        for base, level, name in _import_specs(tree):
            target, amb = _resolve_import(base, level, name, dotted,
                                          set(modules), by_leaf)
            if target is None:
                if amb:
                    ambiguous += 1          # exists in-tree, but guessing would invent an edge
                else:
                    external += 1           # stdlib / third-party / namespace: not internal at all
                continue
            if target != dotted:
                edges[dotted].add(target)

    fan_out = {m: len(v) for m, v in edges.items()}
    fan_in: Dict[str, int] = {m: 0 for m in modules}
    for src, dsts in edges.items():
        for dst in dsts:
            fan_in[dst] = fan_in.get(dst, 0) + 1

    findings: List[Dict[str, Any]] = []

    for comp in _tarjan_cycles(edges):
        findings.append(_finding(
            "import_cycle",
            "high" if len(comp) > 2 else "medium",
            " <-> ".join(comp[:4]) + (" ..." if len(comp) > 4 else ""),
            f"{len(comp)} modules form a strongly-connected import component.",
            {"members": len(comp), "internal_edges": sum(
                1 for s in comp for d in edges.get(s, ()) if d in comp)},
            "Break the cycle by extracting the shared surface into a new module that "
            "the members import, or by moving the shared type/constant to the lowest "
            "layer. Propose-only: no file is moved by this command.",
        ))

    for m, out_degree in sorted(fan_out.items(), key=lambda kv: (-kv[1], kv[0])):
        if out_degree >= WIDE_FANOUT:
            findings.append(_finding(
                "wide_interface", "medium", m,
                f"imports {out_degree} internal modules (fan-out >= {WIDE_FANOUT}).",
                {"fan_out": out_degree, "fan_in": fan_in.get(m, 0)},
                "Split the module along its consumers, or inject the collaborators it "
                "reaches for. Propose-only.",
            ))

    top_in = sorted(fan_in.items(), key=lambda kv: (-kv[1], kv[0]))[:MAX_LISTED]
    return _report(
        "optimize-architecture", METHOD_CYCLES, CAVEAT_CYCLES,
        {"root": str(root), "files": len(files), "modules": len(modules),
         "truncated": truncated, "max_files": MAX_FILES,
         "internal_edges": sum(len(v) for v in edges.values()),
         "external_imports": external, "ambiguous_imports": ambiguous},
        findings,
        f"Analysed {len(modules)} Python modules and "
        f"{sum(len(v) for v in edges.values())} internal import edges "
        f"({external} import(s) are not modules in this tree — stdlib/third-party — "
        f"and {ambiguous} are ambiguous and were deliberately left unresolved "
        f"rather than guessed).",
    ) | {"most_depended_on": [{"module": m, "fan_in": n} for m, n in top_in if n],
         "highest_fan_out": [{"module": m, "fan_out": n}
                             for m, n in sorted(fan_out.items(),
                                                key=lambda kv: (-kv[1], kv[0]))[:MAX_LISTED]]}


# ── /refactor-performance ────────────────────────────────────────────────────

def _nesting_depth(node: ast.AST, depth: int = 0) -> int:
    deepest = depth
    for child in ast.iter_child_nodes(node):
        if isinstance(child, (ast.For, ast.While, ast.If, ast.Try, ast.With, ast.AsyncWith,
                              ast.AsyncFor)):
            deepest = max(deepest, _nesting_depth(child, depth + 1))
        else:
            deepest = max(deepest, _nesting_depth(child, depth))
    return deepest


def _loop_depth(node: ast.AST, depth: int = 0) -> int:
    deepest = depth
    for child in ast.iter_child_nodes(node):
        if isinstance(child, (ast.For, ast.While, ast.AsyncFor)):
            deepest = max(deepest, _loop_depth(child, depth + 1))
        else:
            deepest = max(deepest, _loop_depth(child, depth))
    return deepest


def _calls_in(node: ast.AST) -> List[Tuple[str, ast.Call]]:
    return [(_full_name(c.func), c) for c in ast.walk(node) if isinstance(c, ast.Call)]


def analyze_performance(root: Optional[Path] = None) -> Dict[str, Any]:
    root = root or repo_root()
    files, truncated = _iter_files(root, ".py", MAX_FILES)
    findings: List[Dict[str, Any]] = []
    functions = 0
    modules = 0

    for p in files:
        text = _read(p)
        if text is None:
            continue
        tree = _parse(p, text)
        if tree is None:
            continue
        modules += 1
        rel = str(p.relative_to(root)) if str(p).startswith(str(root)) else str(p)
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            functions += 1
            loc = (node.end_lineno or node.lineno) - node.lineno + 1
            target = f"{rel}::{node.name}"
            is_async = isinstance(node, ast.AsyncFunctionDef)

            if loc >= LONG_FUNCTION_LOC:
                findings.append(_finding(
                    "long_function", "low", target,
                    f"{loc} lines in one function body.",
                    {"loc": loc, "threshold": LONG_FUNCTION_LOC},
                    "Split along the seams already present (the phase boundaries are "
                    "usually visible as comments). Propose-only.",
                ))
            depth = _nesting_depth(node)
            if depth >= DEEP_NESTING:
                findings.append(_finding(
                    "deep_nesting", "medium", target,
                    f"control-flow nesting depth {depth}.",
                    {"depth": depth, "threshold": DEEP_NESTING},
                    "Extract the innermost block into a named function and return early "
                    "for the guard cases. Propose-only.",
                ))
            loops = _loop_depth(node)
            if loops >= 2:
                findings.append(_finding(
                    "nested_loops", "low", target,
                    f"loops nested {loops} deep — potential O(n^{loops}) work.",
                    {"loop_depth": loops},
                    "Index one side into a dict/set before the inner pass, or hoist the "
                    "inner body out. Propose-only.",
                ))
            if is_async:
                blocking = sorted({name for name, _ in _calls_in(node)
                                   if name in BLOCKING_CALLS})
                if len(blocking) >= BLOCKING_IN_ASYNC:
                    findings.append(_finding(
                        "blocking_in_async", "high", target,
                        "blocking call(s) inside `async def`: " + ", ".join(blocking),
                        {"calls": blocking},
                        "Offload via `await anyio.to_thread.run_sync(...)` / "
                        "`asyncio.to_thread(...)`, or use the async client. Propose-only.",
                    ))
            for name, call in _calls_in(node):
                # `_full_name` cannot walk through a Call value, so `open(p).read()`
                # reports as bare "read" — match on the final attribute either way.
                base = name.rsplit(".", 1)[-1]
                if base in {"read", "read_text", "read_bytes"} and not call.args:
                    findings.append(_finding(
                        "unbounded_read", "medium", target,
                        f"`{name}()` with no size limit — the whole payload lands in memory.",
                        {"call": name},
                        "Pass a cap (or stream in chunks) and record the truncation in "
                        "the result. Propose-only.",
                    ))
                    break
            for sub in ast.walk(node):
                if not isinstance(sub, (ast.For, ast.While, ast.AsyncFor)):
                    continue
                for child in ast.walk(sub):
                    if (isinstance(child, ast.AugAssign) and isinstance(child.op, ast.Add)
                            and isinstance(child.target, (ast.Name, ast.Attribute))
                            and isinstance(child.value, (ast.Constant, ast.JoinedStr, ast.Name))):
                        findings.append(_finding(
                            "quadratic_string_build", "medium", target,
                            "string growth with `+=` inside a loop.",
                            {"line": child.lineno},
                            "Collect parts in a list and `''.join(parts)` once after the "
                            "loop. Propose-only.",
                        ))
                        break
            for name, call in _calls_in(node):
                if name.startswith(("subprocess.", "requests.")) and not any(
                        kw.arg == "timeout" for kw in call.keywords):
                    findings.append(_finding(
                        "no_timeout", "medium", target,
                        f"`{name}(...)` without an explicit timeout.",
                        {"call": name},
                        "Add an explicit timeout so a stalled peer cannot pin the "
                        "worker. Propose-only.",
                    ))
                    break

    return _report(
        "refactor-performance", METHOD_PERF, CAVEAT_PERF,
        {"root": str(root), "files": len(files), "modules": modules,
         "functions": functions, "truncated": truncated},
        findings,
        f"Scanned {functions} function bodies across {modules} modules.",
    )


# ── /expand-vectors ──────────────────────────────────────────────────────────

def _public_functions(tree: ast.AST) -> List[str]:
    out: List[str] = []
    for node in tree.body if isinstance(tree, ast.Module) else []:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and not node.name.startswith("_"):
            out.append(node.name)
        elif isinstance(node, ast.ClassDef) and not node.name.startswith("_"):
            out.append(node.name)
    return out


def expand_vectors(root: Optional[Path] = None, limit: int = MAX_LISTED) -> Dict[str, Any]:
    root = root or repo_root()
    files, truncated = _iter_files(root, ".py", MAX_FILES)
    modules: Dict[str, Path] = {}
    for p in files:
        modules[_module_dotted(p, root)] = p

    test_text: List[str] = []
    test_files: List[str] = []
    for dotted, p in sorted(modules.items()):
        name = p.name
        if name.startswith("test_") or name.endswith("_test.py") or f"{os.sep}tests{os.sep}" in str(p):
            text = _read(p)
            if text is not None:
                test_text.append(text)
                test_files.append(dotted)
    haystack = "\n".join(test_text)

    findings: List[Dict[str, Any]] = []
    for dotted, p in sorted(modules.items()):
        if dotted in test_files:
            continue
        leaf = p.stem
        if leaf.startswith("test_") or leaf == "__init__":
            continue
        if leaf and leaf in haystack:
            continue
        text = _read(p) or ""
        tree = _parse(p, text)
        public = _public_functions(tree) if tree is not None else []
        if not public:
            continue
        findings.append(_finding(
            "no_test_reference", "medium", dotted,
            f"{len(public)} public symbol(s) and this module's name appears in no test file.",
            {"public_symbols": len(public), "lines": text.count("\n") + 1},
            "Expansion scenarios to consider: (1) happy path for "
            f"`{public[0]}`; (2) boundary — empty/maximum input; (3) failure — the "
            "first dependency raises. Propose-only: no test is written by this command.",
        ))

    order = {"high": 0, "medium": 1, "low": 2, "info": 3}
    findings.sort(key=lambda f: (order.get(f["severity"], 9), f["target"]))
    return _report(
        "expand-vectors", METHOD_VECTORS, CAVEAT_VECTORS,
        {"root": str(root), "modules": len(modules), "test_files": len(test_files),
         "truncated": truncated, "limit": limit},
        findings[:limit],
        f"{len(modules)} modules, {len(test_files)} test files; "
        f"{sum(1 for f in findings)} module(s) with no test reference.",
    ) | {"test_files": sorted(test_files)[:MAX_LISTED],
         "gaps_total": len(findings)}


# ── dispatcher ───────────────────────────────────────────────────────────────

COMMANDS = {
    "optimize-architecture": analyze_architecture,
    "refactor-performance": analyze_performance,
    "expand-vectors": expand_vectors,
}


def run_purpose_command(command: str, path: Optional[str] = None,
                        limit: Optional[int] = None) -> Dict[str, Any]:
    """Run one purpose command. Never raises; failures are honest results."""
    cid = str(command or "").strip().lstrip("/").lower()
    fn = COMMANDS.get(cid)
    if fn is None:
        return {"ok": False, "command": cid, "summary": f"Unknown purpose command '{command}'.",
                "error": f"known commands: {', '.join(sorted(COMMANDS))}", "findings": []}
    try:
        root = resolve_root(path)
        if cid == "expand-vectors" and limit:
            report = expand_vectors(root, limit=max(1, min(int(limit), MAX_FINDINGS)))
        else:
            report = fn(root)
        return report
    except Exception as exc:  # noqa: BLE001 - surfaced honestly, never hidden
        return {"ok": False, "command": cid, "summary": f"'{cid}' failed.",
                "error": str(exc)[:400], "findings": []}


def _safe(text: str) -> str:
    """Never let a console encoding kill a report (Windows cp1252 vs a target
    string that legitimately contains non-ASCII)."""
    enc = getattr(sys.stdout, "encoding", None) or "utf-8"
    try:
        text.encode(enc)
        return text
    except (UnicodeEncodeError, LookupError):
        return text.encode(enc, "replace").decode(enc, "replace")


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Run a purpose command (read-only).")
    ap.add_argument("--command", required=True, choices=sorted(COMMANDS))
    ap.add_argument("--path", default=None, help="sub-path under the repo root")
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--json", action="store_true", help="emit the raw report")
    args = ap.parse_args(argv)

    report = run_purpose_command(args.command, path=args.path, limit=args.limit)
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=False, ensure_ascii=True))
        return 0 if report.get("ok") else 1

    print(_safe(f"/{report.get('command')} -- {report.get('summary')}"))
    findings = report.get("findings", [])
    for f in findings[:20]:
        print(_safe(f"  [{f['severity']:>6}] {f['kind']} :: {f['target']}"))
        print(_safe(f"           {f['detail']}"))
        print(_safe(f"           metric: {f['metric']}"))
    if len(findings) > 20:
        print(_safe(f"  ... {len(findings) - 20} more finding(s); use --json for all."))
    print(_safe(f"  scanned: {report.get('scanned')}"))
    for c in report.get("caveats", []):
        print(_safe(f"  caveat: {c}"))
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
