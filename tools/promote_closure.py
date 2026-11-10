"""Promote a slice with its dependency closure, gated on collection and imports in a temp worktree.

The first promotions failed for a boring reason: a *slice* is a set of paths, and code paths import
each other. Promoting `Northstar_backend-adapters` without the module it imports gave main a suite it
could not collect, twice.

So promotion now works on a **closure**: the slice's paths plus every repo module they import
transitively that main does not have yet. Before anything touches `main`, the closure is applied to a
throwaway worktree and must pass three gates:

1. **gitleaks**, exactly as the pre-commit hook runs it (`gitleaks git --pre-commit --staged
   --redact`), with findings listed as file:line and rule only — values are redacted at scan time and
   never written;
2. **collect-only**: `pytest --collect-only -q` must finish without a collection error;
3. **import**: every module in the closure imports in the worktree's interpreter.

Nothing here bypasses a hook. If gate 1 fails, the answer is an allowlist entry for a *verified*
false positive, or a rotation — not `--no-verify`.

    python tools/promote_closure.py --slice Northstar_backend-agents --dry-run
    python tools/promote_closure.py --slice Northstar_backend-agents --promote
    python tools/promote_closure.py --slice Northstar_backend-root --promote --allowlist-check
"""
from __future__ import annotations

import argparse
import ast
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, Iterable, List, Set

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "reports" / "ty" / "promotion_closure.json"


def git(*args: str, cwd: Path | None = None, check: bool = True) -> str:
    result = subprocess.run(["git", *args], cwd=str(cwd or ROOT), capture_output=True, text=True)
    if check and result.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {result.stderr.strip()[:400]}")
    return result.stdout


def changed_paths() -> List[str]:
    out = git("diff", "--name-only", "main", "staging")
    return [line.strip() for line in out.splitlines() if line.strip()]


def slice_paths(name: str) -> List[str]:
    sys.path.insert(0, str(ROOT / "tools"))
    import promote_staging as P  # noqa: PLC0415

    rows = P.build_slices(changed_paths())
    if name not in rows:
        raise SystemExit(f"no slice {name!r}; try --list")
    normalised = []
    for entry in rows[name]:
        candidate = Path(entry)
        if candidate.is_absolute():
            try:
                entry = str(candidate.resolve().relative_to(ROOT))
            except ValueError:
                continue          # outside the repo: not ours to promote
        normalised.append(str(entry).replace("\\", "/"))
    return normalised


def _module_candidates(name: str) -> Iterable[str]:
    parts = name.replace(".", "/")
    yield f"Northstar_backend/{parts}.py"
    yield f"Northstar_backend/{parts}/__init__.py"
    yield f"{parts}.py"
    yield f"tools/{parts}.py"
    yield f"tools/{parts}/__init__.py"


def imports_of(path: Path) -> Set[str]:
    """Every module this file imports, absolute or relative.

    Relative imports are the ones that broke the first closure run: `foundation/economics/__init__.py`
    does `from . import engine`, and skipping it left `foundation.economics.engine` out of the
    closure, so the import gate said `No module named 'foundation.economics.engine'`. A relative
    import is resolved against the file's own package, which is where the module actually lives.
    """
    try:
        tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
    except SyntaxError:
        return set()
    names: Set[str] = set()
    # The package the file lives in, as a dotted path (`a/b/c.py` -> `a.b`). It has to be computed
    # from the repo-relative path: using the absolute one turned a relative import into a dotted
    # name starting with `C:/Users/...`, and the closure then asked git to check out a path outside
    # the temporary worktree.
    try:
        rel = Path(path).resolve().relative_to(ROOT)
    except ValueError:
        rel = Path(str(path).replace("\\", "/"))
    package = ".".join(rel.with_suffix("").parts[:-1])
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                base = package.split(".") if package else []
                if node.level > 1:
                    base = base[: len(base) - (node.level - 1)]
                prefix = ".".join(base)
                if node.module:
                    target = f"{prefix}.{node.module}" if prefix else node.module
                    names.add(target)
                    for alias in node.names:
                        names.add(f"{target}.{alias.name}")
                else:
                    for alias in node.names:
                        names.add(f"{prefix}.{alias.name}" if prefix else alias.name)
                continue
            if node.module:
                names.add(node.module)
                for alias in node.names:
                    names.add(f"{node.module}.{alias.name}")
    return names


def closure(paths: List[str], missing: Set[str]) -> List[str]:
    """The slice plus whatever it imports that main does not have yet."""
    seen: Set[str] = set(paths)
    queue = [p for p in paths if p.endswith(".py")]
    added: Set[str] = set()
    while queue:
        rel = queue.pop()
        source = ROOT / rel
        if not source.is_file():
            continue
        for module in imports_of(source):
            for candidate in _module_candidates(module):
                if candidate in seen:
                    continue
                if candidate in missing or (ROOT / candidate).is_file():
                    if (ROOT / candidate).is_file() and candidate not in seen:
                        seen.add(candidate)
                        added.add(candidate)
                        if candidate.endswith(".py"):
                            queue.append(candidate)
                        # A package's `__init__.py` is part of the module: `tools.visual_regression`
                        # vanished without it and `from tools.visual_regression import SCHEMA_VERSION`
                        # failed to import even though `gate.py` was present.
                        parts = Path(candidate).parts[:-1]
                        for depth in range(1, len(parts) + 1):
                            init = Path(*parts[:depth]) / "__init__.py"
                            if str(init).replace("\\", "/") not in seen and (ROOT / init).is_file():
                                seen.add(str(init).replace("\\", "/"))
                                added.add(str(init).replace("\\", "/"))
                    break
    return sorted(seen - set(paths))


def main_collect_baseline() -> Dict[str, Any]:
    """Which collection errors main already has. A promotion is judged on what it *adds*."""
    cache = ROOT / "state" / "director" / "main_collect_baseline.json"
    if cache.exists():
        try:
            return json.loads(cache.read_text(encoding="utf-8"))
        except ValueError:
            pass
    worktree = Path(tempfile.mkdtemp(prefix="collect-main-"))
    try:
        subprocess.run(["git", "worktree", "add", str(worktree), "main"],
                       cwd=str(ROOT), capture_output=True, text=True, check=False)
        baseline = collect_only(worktree)
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(json.dumps(baseline, indent=2) + "\n", encoding="utf-8")
        return baseline
    finally:
        subprocess.run(["git", "worktree", "remove", "--force", str(worktree)],
                       cwd=str(ROOT), capture_output=True, text=True)


def run_gitleaks_staged(worktree: Path) -> List[Dict[str, Any]]:
    report = worktree / "gitleaks.json"
    subprocess.run(["gitleaks", "git", "--pre-commit", "--staged", "--redact",
                    "--report-format", "json", "--report-path", str(report),
                    "-c", str(ROOT / ".gitleaks.toml")],
                   cwd=str(worktree), capture_output=True, text=True, check=False)
    if not report.exists():
        return []
    data = json.loads(report.read_text(encoding="utf-8") or "[]")
    return [{"file": item.get("File"), "line": item.get("StartLine"),
             "rule": item.get("RuleID"), "description": item.get("Description")}
            for item in data]


def collect_only(worktree: Path) -> Dict[str, Any]:
    backend = worktree / "Northstar_backend"
    result = subprocess.run([sys.executable, "-m", "pytest", "--collect-only", "-q",
                             "-p", "no:cacheprovider"],
                            cwd=str(backend), capture_output=True, text=True, timeout=1800)
    errors = [line for line in result.stdout.splitlines() if line.startswith("ERROR ")]
    return {"returncode": result.returncode, "errors": errors[:20],
            "tail": (result.stdout.strip().splitlines() or [""])[-1]}


def import_check(worktree: Path, modules: List[str]) -> Dict[str, Any]:
    """Import each module from the worktree's own roots.

    The probe runs with the *worktree root* on `PYTHONPATH` as well as `Northstar_backend`, because
    a slice imports `tools.x` and `autothink.x` as well as bare backend modules. Running from
    `Northstar_backend` alone reported 95 failures for modules that import perfectly well — the
    probe was measuring its own working directory.
    """
    import os  # noqa: PLC0415

    roots = [str(worktree), str(worktree / "Northstar_backend")]
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join(roots + [env.get("PYTHONPATH", "")]).strip(os.pathsep)
    failures = []
    for rel in modules:
        if not rel.endswith(".py"):
            continue
        module = rel[len("Northstar_backend/"):] if rel.startswith("Northstar_backend/") else rel
        module = module[:-3].replace("/", ".")
        probe = subprocess.run([sys.executable, "-c", f"import {module}"],
                               cwd=str(worktree), capture_output=True, text=True, env=env)
        if probe.returncode != 0:
            failures.append({"module": module,
                             "error": (probe.stderr.strip().splitlines() or [""])[-1][:200]})
    return {"checked": len(modules), "failures": failures}


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Promote a slice with its dependency closure")
    parser.add_argument("--slice", required=True)
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--promote", action="store_true")
    parser.add_argument("--json", action="store_true")
    ns = parser.parse_args(argv)

    if ns.list:
        sys.path.insert(0, str(ROOT / "tools"))
        import promote_staging as P  # noqa: PLC0415

        rows = P.build_slices(changed_paths())
        for name in sorted(rows):
            print(f"{name:38s} {len(rows[name]):4d} paths")
        return 0

    paths = slice_paths(ns.slice)
    missing = set(changed_paths())
    extra = closure(paths, missing)
    all_paths = sorted(set(paths) | set(extra))

    # Only paths that exist in staging's tree can be checked out from it. The repo carries
    # case-only duplicates (`agent_kernel/Budget.py` next to `budget.py`); on a case-insensitive
    # filesystem `git checkout` refuses the variant that is not in the tree, so the list is filtered
    # against the tree first rather than guessed at.
    in_staging = set(git("ls-tree", "-r", "--name-only", "staging").splitlines())
    dropped = [p for p in all_paths if p not in in_staging]
    all_paths = [p for p in all_paths if p in in_staging]

    # `main` can only be checked out in one worktree at a time, so the baseline is captured first,
    # in its own throwaway worktree, before this promotion takes it.
    baseline = main_collect_baseline()

    worktree = Path(tempfile.mkdtemp(prefix=f"promo-{ns.slice}-"))
    result: Dict[str, Any] = {"slice": ns.slice, "paths": len(paths),
                              "closure_added": len(extra), "closure": extra[:80],
                              "worktree": str(worktree),
                              "base": git("rev-parse", "--short", "main").strip(),
                              "dropped_not_in_staging": dropped[:20],
                              "dropped_count": len(dropped)}
    previous_main = git("rev-parse", "main").strip()
    keep = False
    try:
        # The temp worktree is checked out ON `main`, so a passing gate commits straight onto the
        # branch. The first version committed nothing there and merged a no-op into the branch that
        # happened to be checked out (staging) — the promotion "succeeded" and changed nothing.
        subprocess.run(["git", "worktree", "add", str(worktree), "main"],
                       cwd=str(ROOT), capture_output=True, text=True, check=False)
        # Windows caps a command line at ~32k; a 586-path slice blew past it (WinError 206), so the
        # paths go in batches.
        for start in range(0, len(all_paths), 60):
            git("checkout", "staging", "--", *all_paths[start:start + 60], cwd=worktree)
        git("add", "-A", cwd=worktree)
        result["gitleaks"] = run_gitleaks_staged(worktree)
        result["collect"] = collect_only(worktree)
        result["collect_baseline"] = baseline
        # Collection names the modules and data files a slice needs but does not carry:
        # `ModuleNotFoundError: author_lane` and `FileNotFoundError: .../data/x.json`. Follow both
        # chains to the end — the point of a *dependency closure* is that it stops only when nothing
        # else is missing.
        collect_rounds: List[List[str]] = []
        for _round in range(6):
            new_errors = [error for error in result["collect"]["errors"]
                          if error not in (baseline.get("errors") or [])]
            if not new_errors:
                break
            late: List[str] = []
            for error in new_errors:
                # A collection error line often names only the file ("ERROR test_author_lane.py"),
                # with the reason on a later line, so the file's own imports are scanned too.
                if error.startswith("ERROR ") and error[6:].strip().endswith(".py"):
                    failing = error[6:].strip()
                    candidates = [f"Northstar_backend/{failing}", failing]
                    for rel in candidates:
                        if (ROOT / rel).is_file():
                            for module in imports_of(ROOT / rel):
                                for candidate in _module_candidates(module):
                                    if candidate not in all_paths and (ROOT / candidate).is_file():
                                        late.append(candidate)
                                        break
                            break
                if "No module named" in error and "'" in error:
                    module = error.split("'")[1]
                    for candidate in _module_candidates(module):
                        if candidate not in all_paths and (ROOT / candidate).is_file():
                            late.append(candidate)
                            break
                if "No such file or directory" in error and "'" in error:
                    named = error.split("'")[1].replace("\\", "/")
                    rel = named.split("Northstar_backend/")[-1]
                    for candidate in (f"Northstar_backend/{rel}", rel):
                        if candidate not in all_paths and (ROOT / candidate).is_file():
                            late.append(candidate)
                            break
            if not late:
                break
            for start in range(0, len(late), 60):
                git("checkout", "staging", "--", *late[start:start + 60], cwd=worktree)
            all_paths = sorted(set(all_paths) | set(late))
            collect_rounds.append(late)
            result["collect"] = collect_only(worktree)
        if collect_rounds:
            result["closure_added_for_collection"] = collect_rounds
        # The import gate covers the modules a *test* imports, not every file in the slice. A
        # 587-path slice is full of one-off scripts (`check_headers.py`, `seed_dev_shim.py`) that
        # read a file beside them or run work at import time; their importability says nothing about
        # whether main can run its suite, and gating on them refused correct promotions.
        test_files = [p for p in all_paths
                      if p.rsplit("/", 1)[-1].startswith("test_") and p.endswith(".py")]
        wanted: Set[str] = set()
        for rel in test_files:
            wanted |= imports_of(worktree / rel)
        introduced = []
        for module in sorted(wanted):
            for candidate in _module_candidates(module):
                if candidate in all_paths and candidate not in introduced:
                    introduced.append(candidate)
                    break
        result["imports"] = import_check(worktree, introduced)
        result["imports"]["scope"] = "modules imported by the slice's test files"
        # A static import scan cannot see `importlib.import_module("...connectors." + name)`, and the
        # runtime probe can. When it names a module that exists on staging, add it and retry once:
        # the closure becomes dynamic-aware instead of refusing a correct promotion.
        # A static import scan cannot see `importlib.import_module("...connectors." + name)`, and
        # the runtime probe can. Each round adds the modules the probe names that exist on staging;
        # the robots have to be followed to the end of the chain, so it loops until stable.
        added_rounds: List[List[str]] = []
        for _round in range(6):
            missing_modules = sorted({failure["error"].split("'")[1]
                                      for failure in result["imports"]["failures"]
                                      if "No module named" in failure["error"]
                                      and "'" in failure["error"]})
            late: List[str] = []
            for module in missing_modules:
                for candidate in _module_candidates(module):
                    if candidate not in all_paths and (ROOT / candidate).is_file():
                        late.append(candidate)
                        break
            if not late:
                break
            for start in range(0, len(late), 60):
                git("checkout", "staging", "--", *late[start:start + 60], cwd=worktree)
            all_paths = sorted(set(all_paths) | set(late))
            added_rounds.append(late)
            introduced = sorted(set(introduced) | set(late))
            result["imports"] = import_check(worktree, introduced)
        if added_rounds:
            result["closure_added_late"] = added_rounds
            result["imports"]["scope"] = ("modules imported by the slice's test files, plus every "
                                          "module the runtime probe named")
        new_errors = sorted(set(result["collect"]["errors"])
                            - set(result["collect_baseline"].get("errors") or []))
        result["collect_new_errors"] = new_errors
        ok = (not result["gitleaks"] and not new_errors
              and not result["imports"]["failures"])
        result["verdict"] = "ELIGIBLE" if ok else "REFUSED"
        if ok and ns.promote:
            commit = subprocess.run(
                ["git", "commit", "-m",
                 f"promote slice {ns.slice} with a dependency closure ({len(all_paths)} paths)"],
                cwd=str(worktree), capture_output=True, text=True)
            result["commit"] = {"returncode": commit.returncode,
                                "tail": (commit.stdout or commit.stderr).strip().splitlines()[-3:]}
            if commit.returncode != 0:
                result["verdict"] = "REFUSED-BY-HOOK"
                keep = True
            else:
                sha = git("rev-parse", "HEAD", cwd=worktree).strip()
                subprocess.run(["git", "tag", "-f", f"promote/{ns.slice}", sha],
                               cwd=str(ROOT), check=False)
                subprocess.run(["git", "tag", "-f", f"rollback/promote-{ns.slice}-{previous_main[:8]}",
                                previous_main], cwd=str(ROOT), check=False)
                result["main"] = git("rev-parse", "--short", "main").strip()
        elif ok and ns.dry_run:
            keep = False
    finally:
        if not keep:
            subprocess.run(["git", "worktree", "remove", "--force", str(worktree)],
                           cwd=str(ROOT), capture_output=True, text=True)

    REPORT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    if ns.json:
        print(json.dumps(result, indent=2))
    else:
        print(f"slice {result['slice']}: {result['paths']} paths + {result['closure_added']} "
              f"dependency paths")
        print(f"gitleaks findings: {len(result['gitleaks'])}")
        for finding in result["gitleaks"][:12]:
            print(f"   {finding['file']}:{finding['line']}  {finding['rule']}")
        print(f"collect-only: {result['collect']['tail']}")
        for error in result["collect"]["errors"][:6]:
            print("   ", error)
        print(f"import check: {result['imports']['checked']} modules, "
              f"{len(result['imports']['failures'])} failures")
        for failure in result["imports"]["failures"][:6]:
            print("   ", failure["module"], "->", failure["error"])
        print(f"VERDICT: {result['verdict']}" + (f" -> main {result.get('main')}"
                                                  if result.get("main") else ""))
    return 0 if result["verdict"] == "ELIGIBLE" else 2


if __name__ == "__main__":
    raise SystemExit(main())
