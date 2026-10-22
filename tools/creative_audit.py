"""Creative-surface audit — turns "improve the pipeline" into numbered, evidenced findings.

Every finding carries a stable code, a file, a line and the literal evidence, so a
claim can be checked instead of trusted. Nothing here guesses: each rule reports
what is in the source, and the count is whatever the source supports.

    python tools/creative_audit.py                # summary by code
    python tools/creative_audit.py --json         # full backlog
    python tools/creative_audit.py --code CRE-SILENT -v
    python tools/creative_audit.py --write docs/CREATIVE_BACKLOG.json

Rules
    CRE-NOTEST     creative module with no test file that imports it
    CRE-SILENT     except handler that neither logs, re-raises nor warns
    CRE-BARE       bare `except:` (catches KeyboardInterrupt/SystemExit)
    CRE-UNGATED    function that both calls a generation/network primitive and
                   never checks an armed/gated flag in its own body
    CRE-NOTIMEOUT  outbound call with no timeout
    CRE-HARDPATH   absolute Windows path baked into source
    CRE-MUTABLE    mutable default argument
    CRE-LONGFN     function/method >= 60 lines
    CRE-BIGFILE    module >= 800 lines
    CRE-TODO       TODO / FIXME / XXX / HACK marker
    CRE-PRINT      print() in a library module (should be logging)
    CRE-DUPFN      same function name defined in 3+ creative modules (drift risk)

Deterministic transforms (SVG/PDF/compositing/typography) are NOT flagged as
ungated: they make no provider call, so a media gate there would be cargo cult.
"""

from __future__ import annotations

import argparse
import ast
import fnmatch
import io
import json
import os
import re
import sys
import tokenize
from typing import Dict, Iterable, List

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKEND = os.path.join(REPO, "Northstar_backend")

# The creative surface: everything that produces or judges customer-facing creative.
MODULE_PATTERNS = (
    "design_studio_*.py", "studio_*.py", "mockup_*.py", "creative_*.py",
    "text_fidelity.py", "package_readiness.py", "prepress.py", "image_prep.py",
    "dieline_art.py", "listing_forge.py", "ad_pilot.py", "social_pulse.py",
    "seo_listing.py", "voicestudio*.py", "package_designs*.py", "local_*.py",
)

def _dotted(node: ast.AST) -> str:
    """Resolve `a.b.c` style attribute chains to their dotted source form."""
    parts = []
    cur = node
    while isinstance(cur, ast.Attribute):
        parts.append(cur.attr)
        cur = cur.value
    if isinstance(cur, ast.Name):
        parts.append(cur.id)
        return ".".join(reversed(parts))
    return ""


# Only real outbound calls, matched by dotted name. `x.get(...)` on a dict or a
# header is NOT a network call — an earlier draft flagged 673 of those.
NETWORK_CALLS = ("urlopen",)
NETWORK_PREFIXES = ("requests.", "httpx.", "urllib.request.")
NETWORK_METHODS = ("get", "post", "put", "patch", "request", "stream")

# System locations that are legitimately hardcoded (ICC profile search).
SYSTEM_PATH_PREFIXES = ("C:\\Windows", "C:\\Program Files", "C:\\ProgramData")

# Real generation entry points (local or remote), matched by dotted name.
GENERATION_PRIMITIVES = ("generate_image", "generate_edit", "generate_video",
                         "generate_cutout", "_run_graph", "_run_graph_guarded")

GATE_MARKERS = ("armed", "gated", "media_live_armed", "cloud_live_armed")
LOG_MARKERS = ("log.", "logger.", "logging.", "warnings.warn")
RAISE_RE = re.compile(r"\braise\b")
#: A handler is "reviewed" when the author stated WHY it is safe to swallow:
#: `except Exception:  # noqa: BLE001 - the webhook must never break the job`.
#: A bare `noqa: BLE001` with no reason does not count.
SILENT_EXEMPT_RE = re.compile(r"noqa:\s*BLE001\s*-\s*\S")

SEVERITY = {
    "CRE-NOTEST": "high",
    "CRE-SILENT": "high",
    "CRE-UNGATED": "high",
    "CRE-BARE": "medium",
    "CRE-NOTIMEOUT": "medium",
    "CRE-HARDPATH": "medium",
    "CRE-MUTABLE": "medium",
    "CRE-LONGFN": "low",
    "CRE-BIGFILE": "low",
    "CRE-TODO": "low",
    "CRE-PRINT": "low",
    "CRE-DUPFN": "low",
}


def creative_modules() -> List[str]:
    seen, out = set(), []
    for pat in MODULE_PATTERNS:
        for name in sorted(os.listdir(BACKEND)):
            if not name.endswith(".py") or name.startswith("test_"):
                continue
            if fnmatch.fnmatch(name, pat) and name not in seen:
                seen.add(name)
                out.append(name)
    return sorted(out)


def _read(name: str) -> str:
    with io.open(os.path.join(BACKEND, name), "r", encoding="utf-8", errors="replace") as fh:
        return fh.read()


def _test_sources() -> str:
    chunks = []
    for name in os.listdir(BACKEND):
        if name.startswith("test_") and name.endswith(".py"):
            try:
                chunks.append(_read(name))
            except OSError:
                continue
    return "\n".join(chunks)


def _finding(code: str, name: str, lineno: int, evidence: str, detail: str) -> Dict:
    return {
        "code": code,
        "severity": SEVERITY.get(code, "low"),
        "file": f"Northstar_backend/{name}",
        "line": lineno,
        "evidence": evidence.strip()[:160],
        "detail": detail,
    }


def _is_network_call(node: ast.Call) -> bool:
    dotted = _dotted(node.func)
    if not dotted:
        return False
    tail = dotted.split(".")[-1]
    if tail == "urlopen":
        return True
    if dotted.startswith(NETWORK_PREFIXES) and tail in NETWORK_METHODS:
        return True
    return False


def _calls_primitive(node: ast.AST) -> bool:
    for sub in ast.walk(node):
        if not isinstance(sub, ast.Call):
            continue
        dotted = _dotted(sub.func)
        if not dotted:
            continue
        tail = dotted.split(".")[-1]
        if tail in GENERATION_PRIMITIVES:
            return True
        if _is_network_call(sub):
            return True
    return False


def _main_block_ranges(tree: ast.Module):
    """Line ranges of CLI code: `if __name__ == "__main__":` and `def main()`."""
    ranges = []
    for node in ast.walk(tree):
        if isinstance(node, ast.If):
            if "__name__" in ast.dump(node.test) and "__main__" in ast.dump(node.test):
                ranges.append((node.lineno, getattr(node, "end_lineno", node.lineno) or node.lineno))
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.strip("_") in ("main", "cli"):
            ranges.append((node.lineno, getattr(node, "end_lineno", node.lineno) or node.lineno))
    return ranges


def _in_ranges(lineno: int, ranges) -> bool:
    return any(lo <= lineno <= hi for lo, hi in ranges)


def _silent(handler: ast.ExceptHandler, src: str, exposed: str = "") -> bool:
    if SILENT_EXEMPT_RE.search(exposed or ""):
        return False  # the author stated why this swallow is safe
    body = handler.body
    if len(body) == 1 and isinstance(body[0], ast.Pass):
        return True
    segment = "".join(ast.get_source_segment(src, n) or "" for n in body)
    if RAISE_RE.search(segment):
        return False
    return not any(marker in segment for marker in LOG_MARKERS)


def audit() -> List[Dict]:
    findings: List[Dict] = []
    tests = _test_sources()
    all_src = {n: _read(n) for n in creative_modules()}

    for name, src in all_src.items():
        stem = name[:-3]
        if not re.search(rf"^\s*(?:import|from)\s+{re.escape(stem)}\b", tests, re.M):
            findings.append(_finding("CRE-NOTEST", name, 0, name,
                                     "no test file imports this module"))
        lines = src.splitlines()
        if len(lines) >= 800:
            findings.append(_finding("CRE-BIGFILE", name, 1, f"{len(lines)} lines",
                                     "module large enough to hide coupling"))

        try:
            tree = ast.parse(src)
        except SyntaxError as exc:
            findings.append(_finding("CRE-BARE", name, exc.lineno or 0, str(exc),
                                     "module does not parse"))
            continue

        main_ranges = _main_block_ranges(tree)

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                span = (getattr(node, "end_lineno", node.lineno) or node.lineno) - node.lineno + 1
                if span >= 60:
                    findings.append(_finding(
                        "CRE-LONGFN", name, node.lineno,
                        f"def {node.name}(...) spans {span} lines",
                        f"function is {span} lines; split into named steps"))

                for default in list(node.args.defaults) + list(node.args.kw_defaults):
                    if isinstance(default, (ast.List, ast.Dict, ast.Set)):
                        findings.append(_finding(
                            "CRE-MUTABLE", name, node.lineno,
                            f"def {node.name}(... = {type(default).__name__})",
                            "mutable default argument shared across calls"))

                segment = ast.get_source_segment(src, node) or ""
                if _calls_primitive(node) and not node.name.startswith("_"):
                    if not any(m in segment for m in GATE_MARKERS):
                        findings.append(_finding(
                            "CRE-UNGATED", name, node.lineno, f"def {node.name}",
                            "public function reaches a generation/network primitive "
                            "with no armed check in its own body"))

            if isinstance(node, ast.Call):
                if _is_network_call(node):
                    kwargs = {k.arg for k in node.keywords}
                    if "timeout" not in kwargs:
                        findings.append(_finding(
                            "CRE-NOTIMEOUT", name, node.lineno,
                            f"{_dotted(node.func)}(...) without timeout",
                            "an unresponsive endpoint can hang the worker forever"))

            if isinstance(node, ast.ExceptHandler):
                exposed = lines[node.lineno - 1] if 1 <= node.lineno <= len(lines) else ""
                if node.type is None:
                    findings.append(_finding("CRE-BARE", name, node.lineno, exposed,
                                             "bare except swallows everything"))
                elif _silent(node, src, exposed):
                    findings.append(_finding(
                        "CRE-SILENT", name, node.lineno, exposed,
                        "failure is swallowed with no log, no re-raise, no warning, "
                        "and no stated reason"))

            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                if re.search(r"(?<![A-Za-z])[A-Za-z]:\\", node.value) and not node.value.startswith(SYSTEM_PATH_PREFIXES):
                    findings.append(_finding("CRE-HARDPATH", name, node.lineno,
                                             node.value[:120],
                                             "absolute Windows path baked into source"))
            if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                    and node.func.id == "print" and not _in_ranges(node.lineno, main_ranges)):
                findings.append(_finding("CRE-PRINT", name, node.lineno, "print(...)",
                                         "library code prints instead of logging"))

        try:
            for tok in tokenize.generate_tokens(io.StringIO(src).readline):
                if tok.type == tokenize.COMMENT and re.search(r"\b(TODO|FIXME|XXX|HACK)\b", tok.string):
                    findings.append(_finding("CRE-TODO", name, tok.start[0], tok.string,
                                             "unresolved marker in source"))
        except (tokenize.TokenError, IndentationError):
            pass

    fn_map: Dict[str, List[str]] = {}
    for name, src in all_src.items():
        try:
            tree = ast.parse(src)
        except SyntaxError:
            continue
        for node in tree.body if isinstance(tree, ast.Module) else []:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                fn_map.setdefault(node.name, []).append(name)
    for fn, mods in sorted(fn_map.items()):
        if len(mods) >= 3 and not fn.startswith("_"):
            findings.append(_finding("CRE-DUPFN", mods[0], 0,
                                     f"{fn}: {', '.join(sorted(mods))}",
                                     f"defined in {len(mods)} creative modules - drift risk"))

    order = {"high": 0, "medium": 1, "low": 2}
    findings.sort(key=lambda f: (order.get(f["severity"], 3), f["code"], f["file"], f["line"]))
    for i, f in enumerate(findings, 1):
        f["id"] = f"CRE-{i:04d}"
    return findings


def summary(findings: Iterable[Dict]) -> Dict[str, int]:
    out: Dict[str, int] = {}
    for f in findings:
        out[f["code"]] = out.get(f["code"], 0) + 1
    return dict(sorted(out.items(), key=lambda kv: -kv[1]))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Creative-surface audit")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--code", default=None)
    ap.add_argument("-v", "--verbose", action="store_true")
    ap.add_argument("--write", default=None)
    args = ap.parse_args(argv)

    all_findings = audit()
    findings = [f for f in all_findings if not args.code or f["code"] == args.code]

    if args.write:
        with io.open(os.path.join(REPO, args.write), "w", encoding="utf-8") as fh:
            json.dump({"generated_by": "tools/creative_audit.py",
                       "modules": len(creative_modules()),
                       "total": len(all_findings),
                       "findings": all_findings}, fh, indent=2)
        print(f"wrote {args.write} ({len(all_findings)} findings)")

    if args.json:
        print(json.dumps(findings, indent=2))
        return 0

    counts = summary(findings)
    print(f"creative modules: {len(creative_modules())} | findings: {len(findings)}")
    for code, n in counts.items():
        print(f"  {code:<14} {n:>4}   ({SEVERITY.get(code, 'low')})")
    if args.verbose:
        for f in findings:
            print(f"{f['id']} [{f['code']}] {f['file']}:{f['line']} :: {f['evidence']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
