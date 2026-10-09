"""Find JSX components that are used but never imported.

The Product Designer page shipped two crashes ('createDoc is not defined',
'MetricTiles is not defined') because a component was referenced without being
imported. Vite does not fail the build for an undefined *runtime* identifier,
so a page renders fine until you open it and then throws a ReferenceError that
blanks the room.

This walks every page/component under northstar-os-ui/src, collects the
capitalised JSX tags it renders, and reports any that is neither imported nor
declared locally. Zero network, read-only.
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

REACT_BUILTINS = {"Fragment", "Suspense", "StrictMode", "Profiler", "Memo"}


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
    return found


def main() -> int:
    problems: list[tuple[str, str]] = []
    checked = 0
    for path in sorted(SRC.rglob("*.jsx")):
        try:
            source = io.open(path, encoding="utf-8").read()
        except OSError:
            continue
        checked += 1
        available = names_from(source)
        used = set(JSX_TAG.findall(source)) - REACT_BUILTINS
        for name in sorted(used - available):
            problems.append((str(path.relative_to(SRC)).replace("\\", "/"), name))

    print(f"checked {checked} .jsx files")
    if not problems:
        print("no undefined JSX component references found")
        return 0
    print(f"\n{len(problems)} undefined component reference(s):")
    for file, name in problems:
        print(f"  {file}: <{name}>")
    return 1


if __name__ == "__main__":
    sys.exit(main())
