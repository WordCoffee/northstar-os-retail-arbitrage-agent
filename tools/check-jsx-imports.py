"""Find JSX that will crash at runtime: unimported components AND unsafe renders.

Two failure classes, both of which shipped a blank room before being caught:

1. A JSX component referenced but never imported ('createDoc is not defined').
   Vite does not fail the build for an undefined *runtime* identifier, so the
   page renders fine until you open it and then throws a ReferenceError.

2. A value rendered as a React child without an array guard. React error #31
   ("objects are not valid as a React child") and 'a.map is not a function'
   both shipped this way: an endpoint that had been returning an error began
   returning real data, and the page could not render it. The specific
   antipattern is a truthy `.length` guard — which a STRING also satisfies —
   followed by `.map(`.

This walks every page/component under northstar-os-ui/src. Zero network,
read-only, safe to run before every build.
"""

from __future__ import annotations

import io
import re
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent / "northstar-os-ui" / "src"

# <Foo, <Foo.Bar, </Foo>
JSX_TAG = re.compile(r"</?([A-Z][A-Za-z0-9_]*)")
IMPORT_NAMED = re.compile(r"import\s*\{([^}]*)\}\s*from", re.S)
IMPORT_DEFAULT = re.compile(r"import\s+([A-Za-z0-9_]+)\s*(?:,\s*\{([^}]*)\})?\s*from", re.S)
DECLARED = re.compile(r"^\s*(?:export\s+)?(?:function|const|class|let|var)\s+([A-Z][A-Za-z0-9_]*)", re.M)

# A capitalised name BOUND by destructuring, e.g. `{ as: Tag = 'section' }` in a
# parameter list or `const { row: Cell } = props`. The kit's `as`-prop pattern is
# legitimate React and the first version of this checker reported it as a crash
# (kit/Glass.jsx: <Tag>), so the scan now resolves destructured aliases too.
DESTRUCTURE_ALIAS = re.compile(
    r"(?:^|[{,\s])([A-Za-z_$][\w$]*)\s*:\s*([A-Z][A-Za-z0-9_]*)\s*(?:=[^,}]*)?(?:,|\})")
PARAM_BLOCK = re.compile(r"\(([^()]*)\)", re.S)
CONST_DESTRUCTURE = re.compile(r"(?:const|let|var)\s*\{([^{}]*)\}", re.S)

REACT_BUILTINS = {"Fragment", "Suspense", "StrictMode", "Profiler", "Memo"}

# A truthy `.length` test (a string satisfies it) combined with `.map(` on the
# same expression, without an Array.isArray guard.
UNSAFE_LENGTH_MAP = re.compile(r"&&\s*[A-Za-z_$][A-Za-z0-9_$.]*\.length\s*\)")


def strip_comments(source: str) -> str:
    """Remove comments, and only comments.

    A comment that explains *why* a page does not render a router outlet is not a reference to it
    (D-006), so comments have to go before the tag scan. But the first version of this used a regex
    that treated any ``//`` as the start of a comment, and the verifier proved the cost: in
    ``const p = "a//b"; ... <Ghost />`` the rest of the line vanished and a genuinely unimported
    component went unreported. A checker that silently misses a crash is worse than one that
    occasionally over-reports.

    So this walks the text and tracks whether it is inside a string or template literal. It is not a
    parser: it does not understand regex literals or nested templates, which is why it errs towards
    keeping text (a false positive is visible; a false negative is not).
    """
    out = []
    index = 0
    length = len(source)
    quote = ""
    while index < length:
        char = source[index]
        if quote:
            out.append(char)
            if char == "\\" and index + 1 < length:
                out.append(source[index + 1])
                index += 2
                continue
            if char == quote:
                quote = ""
            index += 1
            continue
        if char in ("'", '"', "`"):
            quote = char
            out.append(char)
            index += 1
            continue
        if char == "/" and index + 1 < length:
            nxt = source[index + 1]
            if nxt == "/":
                newline = source.find("\n", index)
                index = length if newline < 0 else newline
                continue
            if nxt == "*":
                close = source.find("*/", index + 2)
                index = length if close < 0 else close + 2
                continue
        out.append(char)
        index += 1
    return "".join(out)


def destructured_aliases(source: str) -> set[str]:
    """Capitalised names bound by destructuring, which are local bindings.

    Scans parenthesised blocks (parameter lists) and `const/let/var {…}`
    declarations. The trade-off is deliberate: an object literal passed inside a
    call, `f({ key: Ghost })`, is also counted as a binding, because the two are
    indistinguishable without a parser. That can only miss a component that is
    referenced as a *value* - which is a ReferenceError at module load, the
    loudest possible failure - while it removes a false positive that blocked a
    correct build (kit/Glass.jsx).
    """
    found: set[str] = set()
    blocks = list(PARAM_BLOCK.findall(source)) + list(CONST_DESTRUCTURE.findall(source))
    for block in blocks:
        if "{" not in block:
            continue
        for match in DESTRUCTURE_ALIAS.finditer(block):
            found.add(match.group(2))
    return found


def names_from(source: str) -> set[str]:
    found: set[str] = set()
    for match in IMPORT_NAMED.finditer(source):
        for part in match.group(1).split(","):
            part = part.strip()
            if not part:
                continue
            # `X as Y` -> the local name is Y
            if " as " in part:
                part = part.split(" as ")[-1].strip()
            found.add(part)
    for match in IMPORT_DEFAULT.finditer(source):
        if match.group(1):
            found.add(match.group(1))
        if match.lastindex and match.lastindex >= 2 and match.group(2):
            for part in match.group(2).split(","):
                part = part.strip()
                if " as " in part:
                    part = part.split(" as ")[-1].strip()
                if part:
                    found.add(part)
    for match in DECLARED.finditer(source):
        found.add(match.group(1))
    found |= destructured_aliases(source)
    return found


def unsafe_render_lines(source: str) -> list[tuple[int, str]]:
    """Line numbers where a value may be rendered without an array guard."""
    out: list[tuple[int, str]] = []
    for i, line in enumerate(source.splitlines(), 1):
        if ".map(" not in line:
            continue
        if "Array.isArray" in line:
            continue
        if UNSAFE_LENGTH_MAP.search(line):
            out.append((i, line.strip()[:120]))
    return out


def main() -> int:
    problems: list[tuple[str, str]] = []
    unsafe: list[tuple[str, int, str]] = []
    checked = 0
    for path in sorted(SRC.rglob("*.jsx")):
        try:
            source = io.open(path, encoding="utf-8").read()
        except OSError:
            continue
        checked += 1
        rel = str(path.relative_to(SRC)).replace("\\", "/")
        available = names_from(source)
        used = set(JSX_TAG.findall(strip_comments(source))) - REACT_BUILTINS
        for name in sorted(used - available):
            problems.append((rel, name))
        for line_no, text in unsafe_render_lines(source):
            unsafe.append((rel, line_no, text))

    print(f"checked {checked} .jsx files")

    failed = False
    if problems:
        failed = True
        print(f"\n{len(problems)} undefined component reference(s):")
        for file, name in problems:
            print(f"  {file}: <{name}>")
    else:
        print("no undefined JSX component references found")

    if unsafe:
        failed = True
        print(f"\n{len(unsafe)} unguarded render(s) — a truthy .length guard passes for a STRING,")
        print("so wrap the value in Array.isArray() before mapping:")
        for file, line_no, text in unsafe:
            print(f"  {file}:{line_no}: {text}")
    else:
        print("no unguarded length-then-map renders found")

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
