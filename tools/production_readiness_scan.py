"""Scan Northstar OS for production-readiness gaps. Read-only.

"Production ready" is not a feeling, so this turns it into checks that either
find something or do not:

    dead-module          a src/lib module nothing imports (built, tested, unreachable)
    button-no-type       <button> without type= (defaults to submit inside a form)
    input-unlabelled     <input>/<select>/<textarea> with no label and no aria-label
    img-no-alt           <img> without alt=
    catch-swallowed      an empty catch block: the failure is discarded, not shown
    placeholder-copy     TODO/FIXME/coming soon/lorem in shipped source
    silent-except        `except Exception: pass` in a non-test backend module
    bare-fetch-no-catch  a fetch() in a page with no try/catch in the same function

Usage:

    python tools/production_readiness_scan.py              # human summary
    python tools/production_readiness_scan.py --json       # machine-readable
    python tools/production_readiness_scan.py --check dead-module,img-no-alt

Exit code: 0 always (a scan is not a test), 2 on usage error. The point is the
list, not a pass/fail - the loop consumes the list and each fix removes one
finding.

Nothing here edits a file.
"""
from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[1]
UI_SRC = ROOT / "northstar-os-ui" / "src"
BACKEND = ROOT / "Northstar_backend"

CHECKS = ("dead-module", "button-no-type", "input-unlabelled", "img-no-alt",
          "catch-swallowed", "placeholder-copy", "silent-except",
          "error-state-unrendered", "icon-button-unnamed")

#: `silent-except` is a triage list, not a defect list: most broad handlers are
#: deliberate resilience (poll a transient API, unload a model best-effort, kill a
#: process). Flagging 52 of them in the default report is how a scanner teaches
#: people to ignore it, so it is opt-in via --check silent-except.
DEFAULT_CHECKS = ("dead-module", "button-no-type", "input-unlabelled", "img-no-alt",
                  "catch-swallowed", "placeholder-copy",
                  "error-state-unrendered", "icon-button-unnamed")


def _ui_files() -> List[Path]:
    return sorted(p for p in UI_SRC.rglob("*")
                  if p.suffix in (".js", ".jsx") and ".test." not in p.name)


def _line_of(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


_LINE_COMMENT = re.compile(r"(?<!:)\/\/[^\n]*")
_BLOCK_COMMENT = re.compile(r"/\*.*?\*/", re.DOTALL)


def _strip_comments(text: str) -> str:
    """Blank out comments, preserving every offset and newline.

    A scanner that counts `<img>` inside a comment is a scanner that cries wolf.
    The first version tracked string literals to decide what a `//` meant, and an
    apostrophe in JSX text ("don't") flipped its state so the rest of the file
    stopped being recognised as code. This version does not guess: a `//` that
    follows a colon is a URL (http://), everything else starts a comment, and
    block comments are matched non-greedily.
    """
    def blank(match: "re.Match[str]") -> str:
        return "".join("\n" if ch == "\n" else " " for ch in match.group(0))

    return _LINE_COMMENT.sub(blank, _BLOCK_COMMENT.sub(blank, text))


def _tag_at(text: str, offset: int) -> str:
    """The whole opening tag starting at `offset`, balanced to its `>`."""
    depth = 0
    for i in range(offset, min(len(text), offset + 2000)):
        ch = text[i]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
        elif ch == ">" and depth == 0:
            return text[offset:i + 1]
    return text[offset:offset + 200]


WAIVER_RE = re.compile(
    r"readiness-scan:\s*([a-z-]+)\s+waived\s*[-\u2013]\s*(.+)", re.IGNORECASE)


def _waivers(path: Path) -> Dict[str, str]:
    """Per-file, explicit waivers: `readiness-scan: <check> waived - <reason>`.

    Some findings are structurally undecidable to a static scan: a shared input
    component has no label of its own because its consumer supplies one. Rather
    than let that sit in the report as permanent noise - which is how a real
    finding gets ignored - a file may waive a named check with a written reason.
    Waivers are visible in the report, so waiving is a reviewable act, not a
    silence.
    """
    out: Dict[str, str] = {}
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return out
    for match in WAIVER_RE.finditer(text):
        out[match.group(1).lower()] = match.group(2).strip()
    return out


def _rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT)).replace("\\", "/")
    except ValueError:          # a path outside the repo (the tests use a temp tree)
        return str(path).replace("\\", "/")


def _finding(check: str, path: Path, line: int, message: str, severity: str) -> Dict[str, Any]:
    return {"check": check, "file": _rel(path),
            "line": line, "message": message, "severity": severity}


def check_dead_modules() -> List[Dict[str, Any]]:
    """A lib module with no importer outside its own test."""
    files = _ui_files()
    text = {p: p.read_text(encoding="utf-8", errors="ignore") for p in files}
    out = []
    for path in sorted((UI_SRC / "lib").glob("*.js")):
        if ".test." in path.name:
            continue
        pattern = re.compile(r"""from\s+['"][^'"]*%s['"]""" % re.escape(path.name))
        importers = [p for p, t in text.items() if p != path and pattern.search(t)]
        if not importers:
            has_test = (path.parent / f"{path.stem}.test.js").is_file()
            out.append(_finding("dead-module", path, 1,
                                f"no module imports {path.name}"
                                f"{' (it has a test, so it looks maintained)' if has_test else ' (and it has no test)'}; "
                                "it is unreachable",
                                "medium"))
    return out


def check_buttons() -> List[Dict[str, Any]]:
    """Only buttons inside a <form>: elsewhere the default type is harmless.

    A check that flags every button in the app is noise, and noise is how a real
    defect gets ignored. Inside a form, a missing type= makes the button submit,
    which is a genuine bug: a "Cancel" or "Copy" control silently posts.
    """
    out = []
    for path in _ui_files():
        if "button-no-type" in _waivers(path):
            continue
        text = _strip_comments(path.read_text(encoding="utf-8", errors="ignore"))
        forms = []
        for opening in re.finditer(r"<form\b", text):
            closing = text.find("</form>", opening.start())
            forms.append((opening.start(), closing if closing != -1 else len(text)))
        if not forms:
            continue
        for match in re.finditer(r"<button\b", text):
            if not any(start <= match.start() <= end for start, end in forms):
                continue
            tag = _tag_at(text, match.start())
            if not re.search(r"\btype\s*=", tag):
                out.append(_finding("button-no-type", path, _line_of(text, match.start()),
                                    "button inside a <form> has no type= and will submit",
                                    "high"))
    return out


def check_inputs() -> List[Dict[str, Any]]:
    out = []
    for path in _ui_files():
        if "input-unlabelled" in _waivers(path):
            continue
        text = _strip_comments(path.read_text(encoding="utf-8", errors="ignore"))
        lines = text.splitlines()
        for match in re.finditer(r"<(input|select|textarea)\b", text):
            tag = _tag_at(text, match.start())
            if re.search(r"\baria-label", tag) or re.search(r"\baria-labelledby", tag):
                continue
            # An explicit <label htmlFor="x"> may sit anywhere, including after
            # the control; matching on the id is exact, a line window is not.
            id_match = re.search(r"""\bid\s*=\s*["']([^"']+)["']""", tag)
            if id_match and re.search(
                    r"""htmlFor\s*=\s*["'{`][^"'}]*%s""" % re.escape(id_match.group(1)), text):
                continue
            line = _line_of(text, match.start())
            window = "\n".join(lines[max(0, line - 5):line + 1])
            if "<label" in window or "htmlFor" in window:
                continue
            out.append(_finding("input-unlabelled", path, line,
                                f"<{match.group(1)}> has no label and no aria-label",
                                "medium"))
    return out


def check_images() -> List[Dict[str, Any]]:
    out = []
    for path in _ui_files():
        if "img-no-alt" in _waivers(path):
            continue
        text = _strip_comments(path.read_text(encoding="utf-8", errors="ignore"))
        for match in re.finditer(r"<img\b", text):
            tag = _tag_at(text, match.start())
            if not re.search(r"\balt\s*=", tag):
                out.append(_finding("img-no-alt", path, _line_of(text, match.start()),
                                    "<img> has no alt attribute", "medium"))
    return out


def check_swallowed_catches() -> List[Dict[str, Any]]:
    """An empty catch body: the error is dropped instead of surfaced."""
    out = []
    for path in _ui_files():
        text = path.read_text(encoding="utf-8", errors="ignore")
        for match in re.finditer(r"catch\s*(?:\([^)]*\))?\s*\{\s*\}", text):
            out.append(_finding("catch-swallowed", path, _line_of(text, match.start()),
                                "empty catch block discards the failure", "medium"))
    return out


def check_placeholder_copy() -> List[Dict[str, Any]]:
    out = []
    # TODO/FIXME/XXX are case-sensitive markers; `'todo'` is also an ordinary
    # status value ("done" vs "todo") and matched the old check twice.
    pattern = re.compile(r"\b(TODO|FIXME|XXX)\b|(?i:coming soon|lorem ipsum)")
    for path in _ui_files():
        text = path.read_text(encoding="utf-8", errors="ignore")
        for match in pattern.finditer(text):
            out.append(_finding("placeholder-copy", path, _line_of(text, match.start()),
                                f"shipped source contains {match.group(0)!r}", "low"))
    return out


def check_silent_except() -> List[Dict[str, Any]]:
    """Only the broad handlers: a typed handler is usually a deliberate skip."""
    out = []
    for path in sorted(BACKEND.glob("*.py")):
        if path.name.startswith("test_"):
            continue
        lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
        for index, line in enumerate(lines):
            if not re.match(r"\s*except\s+(Exception|BaseException)\s*:\s*$", line):
                continue
            nxt = lines[index + 1].strip() if index + 1 < len(lines) else ""
            if nxt in ("pass", "continue"):
                out.append(_finding("silent-except", path, index + 1,
                                    f"`except {line.split()[1].rstrip(':')}: {nxt}` hides the failure",
                                    "low"))
    return out


def check_error_state_unrendered() -> List[Dict[str, Any]]:
    """An error state that is set but never rendered.

    `const [error, setError] = useState('')` plus `setError(msg)` in a catch, and
    then no `{error}` anywhere in the JSX: the failure is captured and thrown away.
    The operator sees a page that simply did not change.
    """
    out = []
    for path in _ui_files():
        if "error-state-unrendered" in _waivers(path):
            continue
        text = _strip_comments(path.read_text(encoding="utf-8", errors="ignore"))
        if "</" not in text:
            continue      # no JSX: a hook/store returns state for its consumer to render
        for match in re.finditer(
                r"const\s*\[\s*(\w*[Ee]rror\w*)\s*,\s*(\w+)\s*\]\s*=\s*useState", text):
            state, setter = match.group(1), match.group(2)
            if not re.search(rf"\b{re.escape(setter)}\s*\(", text):
                continue                      # never set, so nothing is being hidden
            # Rendered means the value is read: `{error}` / `{error && ...}` /
            # `error ?` / `title={error}`. A bare mention in a prop counts.
            rendered = re.search(
                rf"\{{{re.escape(state)}\b|\b{re.escape(state)}\s*[?&]|\b{re.escape(state)}\b\s*\}}",
                text)
            if not rendered:
                out.append(_finding("error-state-unrendered", path,
                                    _line_of(text, match.start()),
                                    f"{state} is set but never rendered; the failure is invisible",
                                    "high"))
    return out


def check_icon_buttons() -> List[Dict[str, Any]]:
    """A button whose only child is an icon and which has no accessible name."""
    out = []
    for path in _ui_files():
        if "icon-button-unnamed" in _waivers(path):
            continue
        text = _strip_comments(path.read_text(encoding="utf-8", errors="ignore"))
        for match in re.finditer(r"<button\b", text):
            tag = _tag_at(text, match.start())
            if re.search(r"\baria-label|\baria-labelledby|\btitle\s*=", tag):
                continue
            close = text.find("</button>", match.start())
            if close == -1:
                continue
            body = text[match.start() + len(tag):close]
            if "<Icon" not in body and "<svg" not in body:
                continue
            # A `{expr}` child may render text (the rail renders {g.label}), so an
            # expression means "cannot tell" - and cannot tell is not a finding.
            if "{" in body:
                continue
            words = re.sub(r"<[^>]+>", " ", body)
            if words.strip():
                continue                      # there is visible text
            out.append(_finding("icon-button-unnamed", path, _line_of(text, match.start()),
                                "icon-only button has no accessible name", "medium"))
    return out


RUNNERS = {
    "dead-module": check_dead_modules,
    "button-no-type": check_buttons,
    "input-unlabelled": check_inputs,
    "img-no-alt": check_images,
    "catch-swallowed": check_swallowed_catches,
    "placeholder-copy": check_placeholder_copy,
    "silent-except": check_silent_except,
    "error-state-unrendered": check_error_state_unrendered,
    "icon-button-unnamed": check_icon_buttons,
}


def scan(selected: List[str] | None = None) -> Dict[str, Any]:
    wanted = selected or list(DEFAULT_CHECKS)
    findings: List[Dict[str, Any]] = []
    for name in wanted:
        if name not in RUNNERS:
            raise ValueError(f"unknown check {name!r}; choose from {', '.join(CHECKS)}")
        findings.extend(RUNNERS[name]())
    waivers = []
    for path in _ui_files():
        for check, reason in _waivers(path).items():
            waivers.append({"file": _rel(path), "check": check, "reason": reason})
    by_check = Counter(f["check"] for f in findings)
    by_severity = Counter(f["severity"] for f in findings)
    by_file = Counter(f["file"] for f in findings)
    return {
        "schema": "northstar.readiness_scan.v1",
        "checks": wanted,
        "total": len(findings),
        "by_check": dict(by_check),
        "by_severity": dict(by_severity),
        "hotspots": by_file.most_common(12),
        "waivers": sorted(waivers, key=lambda w: (w["file"], w["check"])),
        "findings": sorted(findings, key=lambda f: (f["severity"], f["check"], f["file"], f["line"])),
    }


def render(report: Dict[str, Any]) -> str:
    lines = [f"PRODUCTION READINESS SCAN - {report['total']} finding(s)"]
    for name in report["checks"]:
        count = report["by_check"].get(name, 0)
        lines.append(f"  {name:<20} {count}")
    if report.get("waivers"):
        lines.append("")
        lines.append(f"  WAIVED ({len(report['waivers'])}) - declared in the file, reviewable")
        for waiver in report["waivers"]:
            lines.append(f"    {waiver['file']}  [{waiver['check']}]  {waiver['reason'][:90]}")
    if report["hotspots"]:
        lines.append("")
        lines.append("  HOTSPOTS (most findings first)")
        for path, count in report["hotspots"]:
            lines.append(f"    {count:>3}  {path}")
    grouped: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for finding in report["findings"]:
        grouped[finding["check"]].append(finding)
    for name in report["checks"]:
        items = grouped.get(name) or []
        if not items:
            continue
        lines.append("")
        lines.append(f"  == {name} ({len(items)}) ==")
        for item in items[:15]:
            lines.append(f"    {item['file']}:{item['line']}  {item['message']}")
        if len(items) > 15:
            lines.append(f"    ... {len(items) - 15} more")
    return "\n".join(lines)


def main(argv: List[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--check", default="",
                    help="comma-separated subset: " + ",".join(CHECKS)
                         + " (default: " + ",".join(DEFAULT_CHECKS) + ")")
    args = ap.parse_args(argv)
    selected = [c.strip() for c in args.check.split(",") if c.strip()] or None
    try:
        report = scan(selected)
    except ValueError as exc:
        print(f"FAIL: {exc}")
        return 2
    print(json.dumps(report, indent=2) if args.json else render(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
