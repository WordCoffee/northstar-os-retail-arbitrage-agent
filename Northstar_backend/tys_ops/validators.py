"""Structural and semantic validation suite.

Two rules drive this module:

1. **The workspace outranks the executor's self-report.** A step that says
   "done" while an asserted artifact is missing or an asserted command fails is
   a failed step, and the discrepancy is recorded rather than smoothed over.
2. **A validator says why.** Every failure carries a stable code and a sentence
   a repair loop can read, because "invalid" alone cannot be repaired.

Covered checks
--------------
``check_text``        required headings, sentence floor, character floor,
                      placeholder markers, unchanged-from-seed.
``check_json``        required keys, placeholder markers, optional headings.
``check_patch``       unified-diff shape and per-hunk line arithmetic; delegates
                      to ``agent_kernel.content.validate_patch`` when importable
                      so the CLI, the work order and the benchmark cannot drift.
``workspace_acceptance``  ``artifact_exists`` + ``command`` assertions executed
                      against a real workspace.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

PLACEHOLDER_PATTERNS = (
    (r"\bTODO\b", "placeholder_todo"),
    (r"\bTBD\b", "placeholder_tbd"),
    (r"\bFIXME\b", "placeholder_fixme"),
    (r"\bXXX\b", "placeholder_xxx"),
    (r"(?i)lorem\s+ipsum", "placeholder_lorem"),
    (r"<[A-Za-z][^>\n]{0,40}>", "placeholder_angle"),
)

_SENTENCE_RE = re.compile(r"[.!?](?:\s|$)")
_HEADING_RE = re.compile(r"^\s{0,3}#{1,6}\s+\S", re.MULTILINE)
_HUNK_RE = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")


class ValidationError_(RuntimeError):
    def __init__(self, code: str, detail: str = "", **extra: Any):
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code = code
        self.detail = detail
        self.extra = extra


def _result(ok: bool, **fields: Any) -> Dict[str, Any]:
    out = {"valid": bool(ok)}
    out.update(fields)
    return out


def find_placeholders(text: str) -> List[Dict[str, Any]]:
    found: List[Dict[str, Any]] = []
    for pattern, code in PLACEHOLDER_PATTERNS:
        for match in re.finditer(pattern, text):
            found.append({"code": code, "match": match.group(0),
                          "offset": match.start()})
    return found


def sentence_count(text: str) -> int:
    return len(_SENTENCE_RE.findall(text))


def heading_count(text: str) -> int:
    return len(_HEADING_RE.findall(text))


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip())


def check_text(text: str, *, required_headings: Optional[Iterable[str]] = None,
               min_sentences: int = 0, min_chars: int = 0,
               seed: Optional[str] = None,
               allow_placeholders: bool = False) -> Dict[str, Any]:
    problems: List[str] = []
    codes: List[str] = []

    if min_chars and len(text.strip()) < min_chars:
        problems.append(f"text is {len(text.strip())} chars, needs >= {min_chars}")
        codes.append("too_short")

    if min_sentences and sentence_count(text) < min_sentences:
        problems.append(f"found {sentence_count(text)} sentence(s), needs >= {min_sentences}")
        codes.append("sentence_floor")

    for wanted in required_headings or []:
        pattern = re.compile(r"^\s{0,3}#{1,6}\s+" + re.escape(str(wanted)) + r"\b",
                             re.IGNORECASE | re.MULTILINE)
        if not pattern.search(text):
            problems.append(f"missing required heading {wanted!r}")
            codes.append("missing_heading")

    if not allow_placeholders:
        for hit in find_placeholders(text):
            problems.append(f"placeholder marker {hit['match']!r} ({hit['code']})")
            codes.append(hit["code"])

    if seed is not None and _norm(text) == _norm(seed):
        problems.append("content is unchanged from the seed")
        codes.append("unchanged_from_seed")

    return _result(not problems, problems=problems, codes=codes,
                   sentences=sentence_count(text), chars=len(text.strip()),
                   headings=heading_count(text))


def check_json(data: Any, *, required_keys: Optional[Iterable[str]] = None,
               required_headings: Optional[Iterable[str]] = None,
               min_sentences: int = 0, allow_placeholders: bool = False) -> Dict[str, Any]:
    problems: List[str] = []
    codes: List[str] = []

    if not isinstance(data, dict):
        return _result(False, problems=["payload is not a JSON object"],
                       codes=["json_not_object"])

    for key in required_keys or []:
        if key not in data:
            problems.append(f"missing required key {key!r}")
            codes.append("missing_key")

    rendered = json.dumps(data, ensure_ascii=False)
    if not allow_placeholders:
        for hit in find_placeholders(rendered):
            # angle-bracket placeholders are common in real JSON strings only
            # when someone forgot to fill them in; report, do not guess.
            problems.append(f"placeholder marker {hit['match']!r} ({hit['code']})")
            codes.append(hit["code"])

    text = " ".join(str(v) for v in data.values() if isinstance(v, str))
    if required_headings:
        joined = "\n".join(str(value) for value in data.values()
                           if isinstance(value, str))
        for wanted in required_headings:
            if not re.search(r"^\s{0,3}#{1,6}\s+" + re.escape(str(wanted)) + r"\b",
                             joined, re.IGNORECASE | re.MULTILINE):
                problems.append(f"missing required heading {wanted!r}")
                codes.append("missing_heading")

    if min_sentences and sentence_count(text) < min_sentences:
        problems.append(f"found {sentence_count(text)} sentence(s), needs >= {min_sentences}")
        codes.append("sentence_floor")

    return _result(not problems, problems=problems, codes=codes)


# ---------------------------------------------------------------------------
# Unified diff arithmetic
# ---------------------------------------------------------------------------

def _local_patch_check(text: str) -> Dict[str, Any]:
    problems: List[str] = []
    codes: List[str] = []
    lines = text.splitlines()

    if not any(line.startswith("--- ") for line in lines):
        problems.append("missing --- file header")
        codes.append("has_minus_file")
    if not any(line.startswith("+++ ") for line in lines):
        problems.append("missing +++ file header")
        codes.append("has_plus_file")

    hunks = 0
    index = 0
    bad_hunks: List[Dict[str, Any]] = []
    while index < len(lines):
        match = _HUNK_RE.match(lines[index])
        if not match:
            index += 1
            continue
        hunks += 1
        old_want = int(match.group(2)) if match.group(2) is not None else 1
        new_want = int(match.group(4)) if match.group(4) is not None else 1
        header_line = index + 1
        index += 1
        old_seen = new_seen = 0
        while index < len(lines) and not _HUNK_RE.match(lines[index]):
            line = lines[index]
            if line.startswith("\\"):  # "\ No newline at end of file"
                index += 1
                continue
            if line.startswith("-"):
                old_seen += 1
            elif line.startswith("+"):
                new_seen += 1
            elif line.startswith(" ") or line == "":
                old_seen += 1
                new_seen += 1
            else:
                break
            index += 1
        if (old_seen, new_seen) != (old_want, new_want):
            bad_hunks.append({
                "line": header_line,
                "old": [old_seen, old_want],
                "new": [new_seen, new_want],
            })

    if not hunks:
        problems.append("missing @@ hunk header")
        codes.append("has_hunk")
    for bad in bad_hunks:
        old_seen, old_want = bad["old"]
        new_seen, new_want = bad["new"]
        problems.append(
            f"hunk at line {bad['line']} declares -{old_want}/+{new_want} lines "
            f"but its body has {old_seen} old and {new_seen} new lines")
        codes.append("hunk_arithmetic")

    return _result(not problems, problems=problems, codes=codes,
                   hunks=hunks, bad_hunks=bad_hunks, source="local")


def check_patch(path: str) -> Dict[str, Any]:
    """Validate a unified diff. Kernel validator first, local parser as fallback."""
    target = Path(path)
    if not target.is_file():
        return _result(False, problems=[f"missing {path}"], codes=["missing_file"])
    text = target.read_text(encoding="utf-8", errors="replace")
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
        from agent_kernel.content import validate_patch  # type: ignore

        kernel = validate_patch(target)
        checks = kernel.get("checks") or {}
        semantics = checks.get("semantics") or {}
        problems: List[str] = []
        codes: List[str] = []
        for key in ("has_minus_file", "has_plus_file", "has_hunk"):
            if not checks.get(key):
                problems.append(f"missing {key}")
                codes.append(key)
        for bad in semantics.get("bad_hunks") or []:
            old_seen, old_want = bad["old"]
            new_seen, new_want = bad["new"]
            problems.append(
                f"hunk at line {bad['line']} declares -{old_want}/+{new_want} lines "
                f"but its body has {old_seen} old and {new_seen} new lines")
            codes.append("hunk_arithmetic")
        return _result(bool(kernel.get("valid")) and not problems,
                       problems=problems, codes=codes,
                       hunks=semantics.get("hunks", 0),
                       bad_hunks=semantics.get("bad_hunks") or [],
                       source="agent_kernel")
    except Exception:
        return _local_patch_check(text)


# ---------------------------------------------------------------------------
# Workspace-derived acceptance
# ---------------------------------------------------------------------------

def _run_command(argv: List[str], cwd: str, timeout_s: float) -> Dict[str, Any]:
    if not argv:
        return {"exit": None, "error": "empty_argv"}
    resolved = list(argv)
    if resolved[0] in ("python", "python3", "py"):
        resolved[0] = sys.executable
    try:
        proc = subprocess.run(resolved, cwd=cwd, capture_output=True, text=True,
                              timeout=timeout_s)
        return {"exit": proc.returncode,
                "stdout": (proc.stdout or "")[-4000:],
                "stderr": (proc.stderr or "")[-4000:]}
    except subprocess.TimeoutExpired:
        return {"exit": None, "error": "timeout", "timeout_s": timeout_s}
    except OSError as exc:
        return {"exit": None, "error": f"{type(exc).__name__}: {exc}"}


def workspace_acceptance(workspace: str, spec: Optional[Dict[str, Any]],
                         self_report: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Decide a step from the workspace, and record any self-report disagreement."""
    root = os.path.abspath(workspace or ".")
    spec = spec or {}
    problems: List[str] = []
    evidence: Dict[str, Any] = {"workspace": root}

    missing: List[str] = []
    for rel in spec.get("artifact_exists") or []:
        path = os.path.abspath(os.path.join(root, rel))
        if not (path == root or path.startswith(root + os.sep)):
            problems.append(f"artifact path escapes the workspace: {rel}")
            missing.append(rel)
        elif not os.path.exists(path):
            problems.append(f"artifact missing: {rel}")
            missing.append(rel)
    evidence["artifact_exists"] = {"missing": missing,
                                   "checked": list(spec.get("artifact_exists") or [])}

    commands: List[Dict[str, Any]] = []
    for command in spec.get("command") or []:
        if isinstance(command, dict):
            argv = command.get("argv") or []
            expect = int(command.get("expect_exit", 0))
            timeout_s = float(command.get("timeout_s", 120))
        else:  # a bare list is accepted; exit 0 is the expectation
            argv, expect, timeout_s = list(command), 0, 120.0
        run = _run_command([str(a) for a in argv], root, timeout_s)
        run["expected_exit"] = expect
        run["ok"] = run.get("exit") == expect
        if not run["ok"]:
            detail = run.get("error") or f"exit {run.get('exit')} != {expect}"
            problems.append(f"command failed ({detail}): {' '.join(str(a) for a in argv)}")
        commands.append(run)
    evidence["commands"] = commands

    verdict = "pass" if not problems else "fail"
    disagreement = False
    reported = None
    if isinstance(self_report, dict):
        reported = str(self_report.get("status") or self_report.get("verdict") or "")
        reported_ok = reported.lower() in ("done", "pass", "ok", "complete", "completed")
        disagreement = reported_ok != (verdict == "pass")

    return {
        "verdict": verdict,
        "valid": verdict == "pass",
        "source": "workspace",
        "self_report_outranked": disagreement,
        "self_report": reported,
        "problems": problems,
        "evidence": evidence,
    }


# ---------------------------------------------------------------------------
# Suite
# ---------------------------------------------------------------------------

def run_suite(cases: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Run a list of cases: ``{id, kind, ...}`` where kind is text/json/patch."""
    rows: List[Dict[str, Any]] = []
    for case in cases:
        kind = str(case.get("kind") or "text")
        try:
            if kind == "text":
                result = check_text(
                    str(case.get("text") or ""),
                    required_headings=case.get("required_headings"),
                    min_sentences=int(case.get("min_sentences") or 0),
                    min_chars=int(case.get("min_chars") or 0),
                    seed=case.get("seed"),
                )
            elif kind == "json":
                result = check_json(
                    case.get("data"),
                    required_keys=case.get("required_keys"),
                    min_sentences=int(case.get("min_sentences") or 0),
                )
            elif kind == "patch":
                result = check_patch(str(case.get("path") or ""))
            elif kind == "workspace":
                result = workspace_acceptance(
                    str(case.get("workspace") or "."),
                    case.get("spec") or {}, case.get("self_report"))
            else:
                result = _result(False, problems=[f"unknown case kind {kind!r}"],
                                 codes=["unknown_kind"])
        except Exception as exc:  # a validator must never take the suite down
            result = _result(False, problems=[f"{type(exc).__name__}: {exc}"],
                             codes=["validator_crash"])
        rows.append({"id": case.get("id"), "kind": kind, **result})

    passed = sum(1 for row in rows if row["valid"])
    return {
        "total": len(rows),
        "passed": passed,
        "failed": len(rows) - passed,
        "rate": round(passed / len(rows), 4) if rows else 0.0,
        "rows": rows,
    }
