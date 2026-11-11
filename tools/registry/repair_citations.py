"""Repair drifted `file:line` citations in ty/service_registry.json from the code itself.

The registry records the source location of every action. Those numbers rot as `main.py`
grows, and `tools.registry.build` refuses to write while any of them points at a line that
is no longer a route decorator — by design, because a citation that points at the wrong
line is worse than no citation.

The authority for the truth is this package's own `backend_index`, which parses the
decorators. This rewrites each action's `source`, and each service's `evidence.backend`,
from it. An action that resolves to no mounted route is reported and left alone: emptied
evidence is a regression, not a repair.

Usage:
    python -m tools.registry.repair_citations            # rewrite in place
    python -m tools.registry.repair_citations --check    # exit 1 if anything would change
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.registry import backend_index  # noqa: E402

PATH = ROOT / "ty" / "service_registry.json"
CITATION_PREFIXES = ("Northstar_backend/main.py", "Northstar_backend/design_studio_print.py")


def repair(data: dict) -> tuple[dict, list[str], list[str]]:
    """Return (registry, rewrites, unresolved). Pure: it mutates a copy the caller owns."""
    routes = backend_index.routes()
    rewrites: list[str] = []
    unresolved: list[str] = []

    for service in data.get("services") or []:
        sources: list[str] = []
        for action in service.get("actions") or []:
            route = backend_index.find(action.get("method"), action.get("endpoint"), routes)
            if route is None:
                unresolved.append(f"{service['id']}: {action.get('method')} {action.get('endpoint')}")
                continue
            if action.get("source") != route.ref:
                rewrites.append(f"{service['id']}: {action.get('endpoint')} "
                                f"{action.get('source')} -> {route.ref}")
                action["source"] = route.ref
            sources.append(route.ref)

        evidence = service.setdefault("evidence", {})
        existing = list(evidence.get("backend") or [])
        if not sources:
            continue
        kept = [c for c in existing if not c.startswith(CITATION_PREFIXES)]
        rebuilt = sorted(set(sources + kept))
        if rebuilt != existing:
            evidence["backend"] = rebuilt

    return data, rewrites, unresolved


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Repair drifted registry citations.")
    parser.add_argument("--check", action="store_true",
                        help="report what would change and exit 1, writing nothing")
    args = parser.parse_args(argv)

    original = PATH.read_text(encoding="utf-8")
    data = json.loads(original)
    data, rewrites, unresolved = repair(data)
    updated = json.dumps(data, indent=2, ensure_ascii=False) + "\n"

    for line in rewrites:
        print(line)
    for line in unresolved:
        print("UNRESOLVED", line, file=sys.stderr)

    if args.check:
        return 1 if rewrites or updated != original else 0

    if updated != original:
        PATH.write_text(updated, encoding="utf-8")
    print(f"{len(rewrites)} citation(s) rewritten, {len(unresolved)} unresolved")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
