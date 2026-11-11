"""Machine-readable proof that this repository is production-shaped.

One command, one verdict per claim, and a non-zero exit when any claim fails::

    python Northstar_backend/production_assert.py            # human table
    python Northstar_backend/production_assert.py --json     # machine-readable
    python Northstar_backend/production_assert.py --only ui  # one area
    python Northstar_backend/production_assert.py --strict   # advisories fail too

The checklist these checks implement is ``docs/PRODUCTION_READINESS.md``; every
row there cites a check id from this file, and the ``docs.checklist_commands``
check refuses a document that drifts from the code (a row without a command, or
a check id that no longer exists).

Checks are read-only with two deliberate exceptions, both inside a temporary
directory that is removed afterwards:

- ``backup.restore_drill`` writes a snapshot of the SQLite stores to a temp
  directory, verifies it and restores it. The live stores are opened read-only
  (``VACUUM INTO`` reads a consistent snapshot).
- ``health.endpoints_answer`` starts the app in a **subprocess** with FastAPI's
  in-process TestClient. No port is bound and no network egress happens.

Nothing here contacts a provider, reads a credential value, spends money or
touches a browser.

Exit codes: 0 = production-shaped, 1 = at least one failure, 2 = usage error.
"""
from __future__ import annotations

import argparse
import ast
import json
import os
import re
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Tuple

SCHEMA = "northstar.production_assert.v1"
BACKEND_DIR = Path(__file__).resolve().parent
REPO_ROOT = BACKEND_DIR.parent
DOC_PATH = "docs/PRODUCTION_READINESS.md"

CREDENTIAL_NAME_RE = re.compile(
    r"(?:^|_)(?:API_?KEY|KEY|TOKEN|SECRET|PASSWORD|PASSWD|CREDENTIAL|AUTH)(?:_|$)"
)

# Env reads the app performs: a call with an optional default, or an index read.
_ENV_READ_RE = re.compile(
    r"""(?:os\.getenv|os\.environ\.get|environ\.get)\(\s*["']([A-Z][A-Z0-9_]{2,})["'](\s*,\s*[^)]*)?"""
    r"""|os\.environ\[\s*["']([A-Z][A-Z0-9_]{2,})["']\s*\]"""
)

# ---------------------------------------------------------------------------
# Registered gaps
#
# A registered gap is a key the app really reads (the check re-verifies that)
# but that `.env.example` does not yet document. Registering a gap is not a
# waiver: it is a published backlog item. The check fails if a gap stops being
# read (stale register) or if a new undocumented key appears, and
# `docs.checklist_commands` fails unless every gap is named in the checklist.
# `.env.example` is outside this lane's write manifest, which is why the gaps
# are reported rather than fixed here.
# ---------------------------------------------------------------------------

REGISTERED_SECRET_GAPS: Dict[str, str] = {
    "CANOPY_API_KEY": (
        "secondary supplier adapter (canopy_client); optional, no default value"
    ),
    "EASYPARSER_API_KEY": (
        "secondary offer adapter (easyparser_client); optional, no default value"
    ),
    "RAPIDAPI_KEY": (
        "legacy RapidAPI client (rapidapi_client); optional, no default value"
    ),
    "VOICESTUDIO_API_KEY": (
        "voice adapter (voicestudio_adapter); optional, no default value"
    ),
}

# Findings the scanner reports on **shipping** code that are pattern matches on
# code shape, not values. Each entry names the file, the rule and why, and the
# check fails if the finding disappears (a stale register).
REGISTERED_SECRET_FALSE_POSITIVES: Dict[Tuple[str, str], str] = {
    ("Northstar_backend/operator_rea_capture.py", "authorization-header"): (
        "matches the `authorization:` parameter annotation in auth_valid() / "
        "run_capture(); no header value exists in the file"
    ),
}

# Directories whose contents ship to a customer-facing process. A finding here
# is a production finding; a finding in tests/, research vendor code or a report
# is a fixture/documentation matter and is reported, not failed.
PRODUCTION_ROOTS = ("Northstar_backend", "northstar", "shared", "autothink")

# The scan reads source and configuration, not evidence. These prefixes hold
# generated artefacts, committed databases/media and third-party vendored trees;
# `python -m northstar.security.secret_scan --tracked` remains the whole-tree
# command, and the repo-wide backlog is listed in docs/PRODUCTION_READINESS.md.
SECRET_SCAN_SKIP_PREFIXES = (
    "research/", "reports/", "state/", "backups/", "logs/", "renders/",
    "generated_images/", "screenshots/", "exports/", "data/",
    "Northstar_backend/data/", ".pytest_cache/", "node_modules/",
    "Northstar_backend_audit_export/",
)

# Source and config suffixes. A media or database file cannot carry a literal
# credential that a text rule would find, and reading 44 MB of it is waste.
SECRET_SCAN_SUFFIXES = {
    ".py", ".js", ".jsx", ".ts", ".tsx", ".json", ".jsonl", ".yml", ".yaml",
    ".toml", ".ini", ".cfg", ".conf", ".md", ".txt", ".csv", ".sh", ".ps1",
    ".sql", ".html", ".css", ".rs", ".go", ".java", ".rb", ".env", ".example",
}
SECRET_SCAN_MAX_BYTES = 2_000_000

REGISTERED_HOSTED_KEY_GAPS: Dict[str, str] = {
    "DB_URL": (
        "Postgres DSN read by auth/auth_deps/data_layer; root .env.example "
        "documents FOUNDATION_DB_URL instead"
    ),
    "NORTHSTAR_JWT_ALGORITHMS": (
        "JWT algorithm allowlist read by foundation/authn; defaults to HS256"
    ),
    "NORTHSTAR_OWNER_SELF_APPROVAL": (
        "owner self-approval guard read by foundation/approvals; defaults off"
    ),
}

# The only files allowed to set HTML from a string, with the reason. Anything
# else fails `ui.no_untrusted_innerhtml`. The rule is deliberately narrow: the
# injected value must be a bare variable that the same file derives (never a
# prop, a template, a call result or a request string), so "trusted" is a
# property of the code that is checked, not a judgement about the server.
INNERHTML_ALLOWLIST: Dict[str, str] = {
    "northstar-os-ui/src/components/Icon.jsx": (
        "static, module-local SVG path table (const paths); no prop, request or "
        "stored value reaches __html"
    ),
    "northstar-os-ui/src/pages/internal/design-studio/Dielines.jsx": (
        "renders the SVG produced by the local print engine (d.svg) from numeric "
        "dieline geometry; the same string is what Download SVG hands out"
    ),
}

# `dangerouslySetInnerHTML={{ __html: <expr> }}` only. A mention in prose or a
# comment is not a use (Markdown.jsx documents that it never inserts HTML).
_INNERHTML_USE_RE = re.compile(
    r"dangerouslySetInnerHTML\s*=\s*\{\{\s*__html\s*:\s*([^{}]*?)\s*\}\s*\}"
)
# An injected value this check accepts: one identifier, nothing else.
_BARE_IDENT_RE = re.compile(r"^[A-Za-z_$][A-Za-z0-9_$]*$")

UI_SOURCE_SUFFIXES = {".js", ".jsx", ".ts", ".tsx"}


# ---------------------------------------------------------------------------
# Result helpers
# ---------------------------------------------------------------------------

def _result(check_id: str, title: str, status: str, detail: str,
            evidence: Optional[Dict[str, Any]] = None,
            advisories: Optional[Sequence[str]] = None) -> Dict[str, Any]:
    return {
        "id": check_id,
        "title": title,
        "status": status,          # pass | fail | skip
        "detail": detail,
        "command": f"python Northstar_backend/production_assert.py --only {check_id}",
        "evidence": evidence or {},
        "advisories": list(advisories or []),
    }


def _pass(check_id: str, title: str, detail: str, **kwargs) -> Dict[str, Any]:
    return _result(check_id, title, "pass", detail, **kwargs)


def _fail(check_id: str, title: str, detail: str, **kwargs) -> Dict[str, Any]:
    return _result(check_id, title, "fail", detail, **kwargs)


def _skip(check_id: str, title: str, detail: str, **kwargs) -> Dict[str, Any]:
    return _result(check_id, title, "skip", detail, **kwargs)


def _run(cmd: Sequence[str], *, cwd: Path, timeout: int = 300) -> Dict[str, Any]:
    try:
        proc = subprocess.run(
            list(cmd), cwd=str(cwd), capture_output=True, text=True,
            timeout=timeout, encoding="utf-8", errors="replace",
        )
        return {
            "argv": list(cmd),
            "exit_code": proc.returncode,
            "stdout": proc.stdout,
            "stderr": proc.stderr,
        }
    except FileNotFoundError as exc:
        return {"argv": list(cmd), "exit_code": 127, "stdout": "", "stderr": str(exc)}
    except subprocess.TimeoutExpired as exc:
        return {
            "argv": list(cmd), "exit_code": 124,
            "stdout": (exc.stdout or ""), "stderr": f"timed out after {timeout}s",
        }


def _tail(text: str, lines: int = 12) -> str:
    rows = [row for row in (text or "").strip().splitlines() if row.strip()]
    return "\n".join(rows[-lines:])


# ---------------------------------------------------------------------------
# 1. UI production build
# ---------------------------------------------------------------------------

# Vite emits `<name>-<hash>.<ext>`; the hash is what makes a stale bundle
# impossible to serve from a cache.
_HASHED_ASSET_RE = re.compile(r"-[A-Za-z0-9_-]{8,}\.[A-Za-z0-9]+$")


def _asset_is_hashed(name: str) -> bool:
    return bool(_HASHED_ASSET_RE.search(name))


def _check_ui_dist(ctx: Dict[str, Any]) -> Dict[str, Any]:
    cid, title = "ui.dist_production_shaped", "UI production build is production-shaped"
    dist = ctx["root"] / "northstar-os-ui" / "dist"
    if not (dist / "index.html").is_file():
        return _fail(cid, title, f"no production build at {dist} (run: npm run build)")

    assets_dir = dist / "assets"
    if not assets_dir.is_dir():
        return _fail(cid, title, f"no assets directory at {assets_dir}")

    assets = sorted(p.name for p in assets_dir.iterdir() if p.is_file())
    if not assets:
        return _fail(cid, title, "assets directory is empty")

    unhashed = [name for name in assets if not _asset_is_hashed(name)]
    sourcemaps = sorted(str(p.relative_to(dist)) for p in dist.rglob("*.map"))

    html = (dist / "index.html").read_text(encoding="utf-8", errors="replace")
    refs = re.findall(r'(?:src|href)="([^"]+)"', html)
    asset_refs = [ref for ref in refs if "/assets/" in ref]
    unhashed_refs = [
        ref for ref in asset_refs
        if not _asset_is_hashed(ref.rsplit("/", 1)[-1])
    ]

    problems: List[str] = []
    if unhashed:
        problems.append(f"{len(unhashed)} unhashed asset(s): {unhashed[:5]}")
    if sourcemaps:
        problems.append(f"{len(sourcemaps)} source map(s) served: {sourcemaps[:3]}")
    if not asset_refs:
        problems.append("index.html references no hashed asset under /assets/")
    if unhashed_refs:
        problems.append(f"index.html references unhashed assets: {unhashed_refs[:3]}")

    evidence = {
        "dist": str(dist),
        "asset_count": len(assets),
        "total_bytes": sum((assets_dir / name).stat().st_size for name in assets),
        "sample": assets[:3],
        "sourcemaps": len(sourcemaps),
    }
    if problems:
        return _fail(cid, title, "; ".join(problems), evidence=evidence)
    return _pass(cid, title,
                 f"{len(assets)} hashed assets, no source maps, index references hashed assets",
                 evidence=evidence)


def _check_ui_bundle_clean(ctx: Dict[str, Any]) -> Dict[str, Any]:
    cid, title = ("ui.served_bundle_clean",
                  "served bundle carries no dev-only shim or test hook")
    script = ctx["root"] / "tools" / "check-prod-bundle.cjs"
    if not script.is_file():
        return _fail(cid, title, f"bundle guard missing: {script}")
    run = _run(["node", str(script)], cwd=ctx["root"], timeout=180)
    if run["exit_code"] == 127:
        return _fail(cid, title, "node is not available, so the bundle cannot be scanned")
    summary = _tail(run["stdout"], lines=3)
    if run["exit_code"] != 0:
        return _fail(cid, title, f"bundle guard exited {run['exit_code']}: {summary}",
                     evidence={"tail": _tail(run["stdout"], 12),
                               "exit_code": run["exit_code"]})
    return _pass(cid, title, summary or "bundle guard passed",
                 evidence={"exit_code": 0, "tail": summary})


def _check_ui_innerhtml(ctx: Dict[str, Any]) -> Dict[str, Any]:
    cid, title = "ui.no_untrusted_innerhtml", "no untrusted dangerouslySetInnerHTML"
    root = ctx["root"]
    src = root / "northstar-os-ui" / "src"
    if not src.is_dir():
        return _fail(cid, title, f"UI source missing: {src}")

    uses: List[Dict[str, Any]] = []
    for path in src.rglob("*"):
        if not path.is_file() or path.suffix not in UI_SOURCE_SUFFIXES:
            continue
        rel = str(path.relative_to(root)).replace("\\", "/")
        text = path.read_text(encoding="utf-8", errors="replace")
        for match in _INNERHTML_USE_RE.finditer(text):
            uses.append({
                "file": rel,
                "expression": match.group(1),
                "line": text[: match.start()].count("\n") + 1,
            })

    evidence = {
        "uses": uses,
        "allowlisted": sorted(INNERHTML_ALLOWLIST),
    }
    problems: List[str] = []
    for use in uses:
        rel = use["file"]
        if rel not in INNERHTML_ALLOWLIST:
            problems.append(f"{rel}:{use['line']} injects HTML but is not allowlisted")
            continue
        if not _BARE_IDENT_RE.match(use["expression"]):
            problems.append(
                f"{rel}:{use['line']} injects an expression ({use['expression']!r}); "
                "only a variable derived in the same file is allowed"
            )
            continue
        identifier = use["expression"]
        text = (root / rel).read_text(encoding="utf-8", errors="replace")
        setter = "set" + identifier[:1].upper() + identifier[1:]
        derived = any(marker in text for marker in (
            f"const {identifier} =", f"let {identifier} =", f"{setter}(",
        ))
        if not derived:
            problems.append(
                f"{rel}:{use['line']} injects {identifier!r} but the file never "
                "derives it (no const/let/state setter for that name)"
            )

    # Every allowlist entry must still be a real use, or the list has rotted.
    used_files = {use["file"] for use in uses}
    for rel, reason in INNERHTML_ALLOWLIST.items():
        if rel not in used_files:
            problems.append(f"allowlist entry no longer injects HTML: {rel} ({reason})")

    # Icon.jsx carries one extra structural promise: the injected value is a
    # lookup into a static table.
    icon = "northstar-os-ui/src/components/Icon.jsx"
    if icon in used_files:
        icon_text = (root / icon).read_text(encoding="utf-8", errors="replace")
        if "const paths = {" not in icon_text or "paths[name]" not in icon_text:
            problems.append(f"{icon}: the static SVG path table is gone")

    if problems:
        return _fail(cid, title, "; ".join(problems), evidence=evidence)
    if not uses:
        return _fail(cid, title,
                     "no dangerouslySetInnerHTML found at all; the check is vacuous",
                     evidence=evidence)
    return _pass(cid, title,
                 f"{len(uses)} use(s), every value a file-local variable, "
                 f"all allowlisted",
                 evidence=evidence)


# ---------------------------------------------------------------------------
# 2. Config and secrets
# ---------------------------------------------------------------------------

def _backend_modules(root: Path) -> Dict[str, Path]:
    index: Dict[str, Path] = {}
    backend = root / "Northstar_backend"
    skip = ("venv", "__pycache__", "site-packages", "node_modules")
    for path in backend.rglob("*.py"):
        if any(part in skip for part in path.parts):
            continue
        index[".".join(path.relative_to(backend).with_suffix("").parts)] = path
    northstar = root / "northstar"
    if northstar.is_dir():
        for path in northstar.rglob("*.py"):
            if any(part in skip for part in path.parts):
                continue
            index["northstar." + ".".join(
                path.relative_to(northstar).with_suffix("").parts)] = path
    return index


def _production_graph(root: Path, entry: str = "main") -> List[str]:
    """Modules transitively imported by the API entrypoint (best effort)."""
    index = _backend_modules(root)
    seen: List[str] = []
    stack = [entry]
    while stack:
        name = stack.pop()
        if name in seen or name not in index:
            continue
        seen.append(name)
        try:
            tree = ast.parse(index[name].read_text(encoding="utf-8", errors="replace"))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    stack.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                base = node.module or ""
                if node.level:
                    package = name.split(".")[:-1]
                    up = node.level - 1
                    base = ".".join(
                        package[: len(package) - up] + ([base] if base else []))
                if base:
                    stack.append(base)
                for alias in node.names:
                    stack.append(f"{base}.{alias.name}" if base else alias.name)
    return seen


def _env_reads(root: Path, modules: Iterable[str], *,
               top_level_only: bool) -> Dict[str, Dict[str, Any]]:
    index = _backend_modules(root)
    reads: Dict[str, Dict[str, Any]] = {}
    for name in modules:
        path = index.get(name)
        if path is None:
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        try:
            tree = ast.parse(text)
        except SyntaxError:
            continue
        if top_level_only:
            # Only statements that execute at import time. The line ranges are
            # sliced out of the source once: `ast.get_source_segment` per node
            # is quadratic and made this check take minutes on a 300-module graph.
            lines = text.splitlines()
            segments = [
                "\n".join(lines[max(node.lineno - 1, 0): (node.end_lineno or node.lineno)])
                for node in tree.body
                if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            ]
            searchable = "\n".join(segments)
        else:
            searchable = text
        for match in _ENV_READ_RE.finditer(searchable):
            key = match.group(1) or match.group(3)
            entry = reads.setdefault(key, {"has_default": False, "modules": set()})
            entry["has_default"] = entry["has_default"] or bool(match.group(2))
            entry["modules"].add(name)
    for entry in reads.values():
        entry["modules"] = sorted(entry["modules"])
    return reads


def _env_example_names(root: Path) -> set:
    """Every NAME mentioned in .env.example, commented or assigned."""
    text = (root / ".env.example").read_text(encoding="utf-8", errors="replace")
    return set(re.findall(r"^\s*#?\s*([A-Z][A-Z0-9_]*)\s*=", text, re.M))


def _check_secrets_repo(ctx: Dict[str, Any]) -> Dict[str, Any]:
    cid, title = "secrets.repo_clean", "no secret value in the shipped code"
    root = ctx["root"]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    try:
        from northstar.security import secret_scan
    except Exception as exc:  # noqa: BLE001
        return _fail(cid, title, f"the secret scanner could not be imported: {exc}")

    allowlist = secret_scan.load_allowlist()
    baseline = secret_scan.load_baseline()

    def _classify(rel: str) -> str:
        posix = rel.replace("\\", "/")
        name = posix.rsplit("/", 1)[-1]
        if name.startswith("test_") or "/tests/" in posix or "/fixtures/" in posix:
            return "test_fixture"
        if posix.startswith("research/") or "/vendor/" in posix:
            return "vendored_research"
        if posix.startswith(("reports/", "state/", "docs/")):
            return "report_or_doc"
        if posix.startswith(("tools/", "scripts/", "deploy/")):
            return "tooling"
        if posix.startswith(PRODUCTION_ROOTS):
            return "shipped_code"
        return "other"

    shipped: List[Dict[str, Any]] = []
    counts: Dict[str, int] = {}
    checked = 0
    skipped = 0
    for path in secret_scan.tracked_files():
        candidate = path if path.is_absolute() else (root / path)
        try:
            rel = str(candidate.relative_to(root)).replace("\\", "/")
        except ValueError:
            rel = str(path).replace("\\", "/")
        if rel.startswith(SECRET_SCAN_SKIP_PREFIXES):
            skipped += 1
            continue
        if candidate.suffix.lower() not in SECRET_SCAN_SUFFIXES:
            skipped += 1
            continue
        try:
            if candidate.stat().st_size > SECRET_SCAN_MAX_BYTES:
                skipped += 1
                continue
            text = candidate.read_text(encoding="utf-8", errors="replace")
        except OSError:
            skipped += 1
            continue
        checked += 1
        for finding in secret_scan.scan_text(rel, text):
            key = (finding.rule, finding.fingerprint)
            if key in allowlist or key in baseline:
                continue
            kind = _classify(rel)
            counts[kind] = counts.get(kind, 0) + 1
            if kind == "shipped_code":
                registered = (rel, finding.rule) in REGISTERED_SECRET_FALSE_POSITIVES
                shipped.append({
                    "path": rel, "rule": finding.rule, "line": finding.line,
                    "registered_false_positive": registered,
                })

    active = [row for row in shipped if not row["registered_false_positive"]]
    registered_seen = {(row["path"], row["rule"]) for row in shipped}
    stale = sorted(set(REGISTERED_SECRET_FALSE_POSITIVES) - registered_seen)

    evidence = {
        "files_scanned": checked,
        "files_skipped": skipped,
        "findings_by_class": counts,
        "shipped_findings": shipped,
        "registered_false_positives": sorted(
            f"{path}: {rule}" for path, rule in REGISTERED_SECRET_FALSE_POSITIVES
        ),
    }
    problems: List[str] = []
    if active:
        problems.append(
            f"{len(active)} unregistered finding(s) in shipped code: "
            + ", ".join(f"{row['path']}:{row['line']} [{row['rule']}]"
                        for row in active[:5])
        )
    if stale:
        problems.append("registered false positives no longer reported: "
                        + ", ".join(f"{path} [{rule}]" for path, rule in stale))
    if problems:
        return _fail(cid, title, "; ".join(problems), evidence=evidence)

    other = sum(v for k, v in counts.items() if k != "shipped_code")
    advisories = []
    if other:
        advisories.append(
            f"{other} finding(s) outside shipped code "
            f"({', '.join(f'{k}={v}' for k, v in sorted(counts.items()) if k != 'shipped_code')}); "
            "fixtures and docs, not baselined in .secret_scan_baseline.json"
        )
    advisories.append(
        f"{skipped} tracked file(s) were not scanned (evidence, media, committed "
        "databases, vendored research); the whole-tree command is "
        "`python -m northstar.security.secret_scan --tracked`"
    )
    return _pass(cid, title,
                 f"{len(shipped)} finding(s) in {checked} source/config files, all "
                 "registered false positives; no secret value in shipped code",
                 evidence=evidence, advisories=advisories)


def _check_env_secrets(ctx: Dict[str, Any]) -> Dict[str, Any]:
    cid, title = ("config.env_example_covers_secrets",
                  "every import-time secret the API reads is documented")
    root = ctx["root"]
    graph = _production_graph(root)
    reads = _env_reads(root, graph, top_level_only=True)
    documented = _env_example_names(root)
    required = sorted(
        name for name in reads
        if CREDENTIAL_NAME_RE.search(name) and name not in documented
    )
    unregistered = [name for name in required if name not in REGISTERED_SECRET_GAPS]
    stale = [name for name in REGISTERED_SECRET_GAPS if name not in reads]

    # Full sweep is advisory: it is the honest size of the remaining
    # documentation work, not a claim this check makes.
    all_reads = _env_reads(root, graph, top_level_only=False)
    all_missing = sorted(name for name in all_reads if name not in documented)

    evidence = {
        "graph_modules": len(graph),
        "import_time_keys": len(reads),
        "documented_keys": len(documented),
        "undocumented_secret_keys": required,
        "registered_gaps": sorted(REGISTERED_SECRET_GAPS),
        "all_read_keys": len(all_reads),
        "all_undocumented_keys": len(all_missing),
    }
    problems: List[str] = []
    if unregistered:
        problems.append(
            "secret-shaped keys read at import time and absent from .env.example: "
            + ", ".join(unregistered)
        )
    if stale:
        problems.append("registered gaps no longer read by the app: " + ", ".join(stale))
    if problems:
        return _fail(cid, title, "; ".join(problems), evidence=evidence)

    advisories = [
        f"{name} is read at import time but not in .env.example "
        f"({REGISTERED_SECRET_GAPS[name]})"
        for name in sorted(REGISTERED_SECRET_GAPS)
    ]
    advisories.append(
        f"{len(all_missing)} of {len(all_reads)} read keys are absent from "
        ".env.example over the whole import graph (optional knobs with code defaults)"
    )
    return _pass(cid, title,
                 f"{len(reads)} import-time keys checked, "
                 f"{len(REGISTERED_SECRET_GAPS)} registered gap(s)",
                 evidence=evidence, advisories=advisories)


def _check_env_hosted(ctx: Dict[str, Any]) -> Dict[str, Any]:
    cid, title = ("config.env_example_covers_hosted",
                  "every hosted deploy key is documented")
    root = ctx["root"]
    hosted_file = root / "deploy" / "hosted.env.example"
    if not hosted_file.is_file():
        return _fail(cid, title, f"missing {hosted_file}")
    hosted_names = re.findall(
        r"^\s*([A-Z][A-Z0-9_]*)\s*=",
        hosted_file.read_text(encoding="utf-8", errors="replace"), re.M,
    )
    documented = _env_example_names(root)
    compose_text = "".join(
        path.read_text(encoding="utf-8", errors="replace")
        for path in sorted(root.glob("docker-compose*.yml"))
    )
    compose_vars = set(re.findall(r"\$\{([A-Z][A-Z0-9_]*)", compose_text))

    undocumented = [
        name for name in hosted_names
        if name not in documented and name not in compose_vars
    ]
    unregistered = [name for name in undocumented
                    if name not in REGISTERED_HOSTED_KEY_GAPS]
    stale = [name for name in REGISTERED_HOSTED_KEY_GAPS if name not in hosted_names]

    evidence = {
        "hosted_keys": len(hosted_names),
        "documented_in_env_example": len([n for n in hosted_names if n in documented]),
        "used_by_compose": len([n for n in hosted_names if n in compose_vars]),
        "undocumented": undocumented,
        "registered_gaps": sorted(REGISTERED_HOSTED_KEY_GAPS),
    }
    problems: List[str] = []
    if unregistered:
        problems.append("hosted keys with no documentation: " + ", ".join(unregistered))
    if stale:
        problems.append("registered gaps no longer in the hosted example: "
                        + ", ".join(stale))
    if problems:
        return _fail(cid, title, "; ".join(problems), evidence=evidence)

    advisories = [
        f"{name} is required by the hosted example but absent from .env.example "
        f"({REGISTERED_HOSTED_KEY_GAPS[name]})"
        for name in sorted(REGISTERED_HOSTED_KEY_GAPS)
    ]
    return _pass(cid, title,
                 f"{len(hosted_names)} hosted keys, "
                 f"{len(REGISTERED_HOSTED_KEY_GAPS)} registered gap(s)",
                 evidence=evidence, advisories=advisories)


def _check_dev_bypass(ctx: Dict[str, Any]) -> Dict[str, Any]:
    cid, title = ("config.dev_bypass_guarded",
                  "dev-only identity bypass is unreachable outside development")
    root = ctx["root"]
    backend = root / "Northstar_backend"
    if str(backend) not in sys.path:
        sys.path.insert(0, str(backend))

    authn_source = (backend / "foundation" / "authn.py").read_text(
        encoding="utf-8", errors="replace")
    # The gate must be exactly `return environment() == "development"`: read
    # from the AST, so a docstring or a comment cannot make a looser gate pass.
    gate_is_env_only = False
    try:
        authn_tree = ast.parse(authn_source)
    except SyntaxError:
        authn_tree = None
    if authn_tree is not None:
        for node in authn_tree.body:
            if not (isinstance(node, ast.FunctionDef) and node.name == "dev_shim_enabled"):
                continue
            body = [
                stmt for stmt in node.body
                if not (isinstance(stmt, ast.Expr)
                        and isinstance(stmt.value, ast.Constant)
                        and isinstance(stmt.value.value, str))
            ]
            if len(body) == 1 and isinstance(body[0], ast.Return):
                expr = body[0].value
                gate_is_env_only = (
                    isinstance(expr, ast.Compare)
                    and isinstance(expr.left, ast.Call)
                    and getattr(expr.left.func, "id", None) == "environment"
                    and len(expr.comparators) == 1
                    and isinstance(expr.comparators[0], ast.Constant)
                    and expr.comparators[0].value == "development"
                )

    from starlette.requests import Request  # local import: no app import needed

    def shim(headers: Dict[str, str]):
        from auth_deps import _dev_shim_identity

        raw = [(k.lower().encode(), v.encode()) for k, v in headers.items()]
        scope = {
            "type": "http", "method": "GET", "path": "/", "headers": raw,
            "client": ("127.0.0.1", 5555), "scheme": "http",
            "server": ("testserver", 80), "query_string": b"", "root_path": "",
        }
        return _dev_shim_identity(Request(scope))

    original = os.environ.get("ENVIRONMENT")
    results: Dict[str, Any] = {}
    try:
        os.environ["ENVIRONMENT"] = "production"
        results["production_with_header"] = shim({"X-User-Id": "demo-t2"})
        results["production_with_header_and_role"] = shim(
            {"X-User-Id": "demo-t2", "X-Role": "platform_admin"})
        os.environ["ENVIRONMENT"] = "staging"
        results["staging_with_header"] = shim({"X-User-Id": "demo-t2"})
        os.environ["ENVIRONMENT"] = "development"
        results["development_with_header"] = shim({"X-User-Id": "demo-t2"})
        results["development_without_header"] = shim({})
    finally:
        if original is None:
            os.environ.pop("ENVIRONMENT", None)
        else:
            os.environ["ENVIRONMENT"] = original

    evidence = {
        "gate_reads_environment_only": gate_is_env_only,
        "production_refused": results["production_with_header"] is None
        and results["production_with_header_and_role"] is None,
        "staging_refused": results["staging_with_header"] is None,
        "development_allowed": isinstance(results["development_with_header"], dict),
        "development_needs_explicit_header":
            results["development_without_header"] is None,
    }
    problems: List[str] = []
    if not gate_is_env_only:
        problems.append(
            "dev_shim_enabled() is not a pure ENVIRONMENT == development gate")
    if not evidence["production_refused"]:
        problems.append("the shim answered with ENVIRONMENT=production")
    if not evidence["staging_refused"]:
        problems.append("the shim answered with ENVIRONMENT=staging")
    if not evidence["development_allowed"]:
        problems.append(
            "the shim refused a loopback development request (the gate is now inert)")
    if not evidence["development_needs_explicit_header"]:
        problems.append(
            "the shim answered development without an explicit X-User-Id")
    if problems:
        return _fail(cid, title, "; ".join(problems), evidence=evidence)
    return _pass(cid, title,
                 "production/staging refuse the shim; development needs "
                 "loopback + an explicit header",
                 evidence=evidence)


# ---------------------------------------------------------------------------
# 3. Redaction
# ---------------------------------------------------------------------------

def _check_redaction(ctx: Dict[str, Any]) -> Dict[str, Any]:
    cid, title = "redaction.enforced", "logs and error paths never emit credentials"
    root = ctx["root"]
    backend = root / "Northstar_backend"
    if str(backend) not in sys.path:
        sys.path.insert(0, str(backend))
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    import io
    import logging

    try:
        import logging_config
        from northstar.security import redaction
    except Exception as exc:  # noqa: BLE001
        return _fail(cid, title, f"redaction module could not be imported: {exc}")

    fake_key = "sk-live-0123456789abcdefghij"
    fake_bearer = "Bearer abcdef0123456789abcdef"
    fake_jwt = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJkZW1vIn0.c2lnbmF0dXJlLXZhbHVl"

    captured = io.StringIO()
    original_stdout = sys.stdout
    sys.stdout = captured
    try:
        logging_config.setup_logging(level="INFO")
        logger = logging_config.get_logger("production-assert")
        logger.info("provider key=%s and header Authorization: %s", fake_key, fake_bearer)
        logger.info("session token %s", fake_jwt)
        try:
            raise RuntimeError(f"failed with key={fake_key}")
        except RuntimeError:
            logger.exception("provider call failed")
    finally:
        sys.stdout = original_stdout
        logging.getLogger().handlers.clear()
        logging.getLogger().setLevel(logging.WARNING)

    output = captured.getvalue()
    leaks = [value for value in (fake_key, "abcdef0123456789abcdef", fake_jwt)
             if value in output]
    filter_ok = False
    formatter_ok = False
    try:
        logging_config.setup_logging(level="INFO")
        handler = logging.getLogger().handlers[0]
        filter_ok = any(isinstance(f, redaction.RedactionFilter) for f in handler.filters)
        formatter_ok = isinstance(handler.formatter, redaction.RedactingFormatter)
    finally:
        logging.getLogger().handlers.clear()

    evidence = {
        "module": "northstar/security/redaction.py",
        "wired_by": "Northstar_backend/logging_config.py:setup_logging",
        "sample_bytes": len(output),
        "leaked_values": len(leaks),
        "filter_attached": bool(filter_ok),
        "formatter_wrapped": bool(formatter_ok),
    }
    problems: List[str] = []
    if leaks:
        problems.append(f"{len(leaks)} credential value(s) survived into the log output")
    if "[REDACTED]" not in output:
        problems.append("no [REDACTED] marker in the captured output "
                        "(redaction did not run)")
    if not filter_ok:
        problems.append("the logging handler has no RedactionFilter")
    if not formatter_ok:
        problems.append("the logging formatter is not a RedactingFormatter")
    if problems:
        return _fail(cid, title, "; ".join(problems), evidence=evidence)
    return _pass(cid, title,
                 "keys, bearer headers and JWTs are redacted in the message "
                 "and in the traceback",
                 evidence=evidence)


# ---------------------------------------------------------------------------
# 4. Health and readiness
# ---------------------------------------------------------------------------

_HEALTH_PROBE = r"""
import json, sys
sys.path.insert(0, "Northstar_backend")
from fastapi.testclient import TestClient
import main
client = TestClient(main.app)
out = {}
for path in ("/health", "/health/detailed", "/readyz", "/health/readyz"):
    response = client.get(path)
    try:
        body = response.json()
    except Exception:
        body = {}
    out[path] = {
        "status_code": response.status_code,
        "status": (body or {}).get("status"),
        "keys": sorted((body or {}).keys()),
    }
print("PROBE_JSON " + json.dumps(out))
"""


def _check_health(ctx: Dict[str, Any]) -> Dict[str, Any]:
    cid, title = "health.endpoints_answer", "health and readiness endpoints answer"
    root = ctx["root"]
    run = _run([sys.executable, "-c", _HEALTH_PROBE], cwd=root, timeout=300)
    marker = [line for line in run["stdout"].splitlines()
              if line.startswith("PROBE_JSON ")]
    if not marker:
        return _fail(cid, title,
                     f"the app could not serve the probes (exit {run['exit_code']}): "
                     f"{_tail(run['stderr'], 6)}")
    payload = json.loads(marker[-1][len("PROBE_JSON "):])

    problems: List[str] = []
    for path in ("/health", "/health/detailed", "/readyz", "/health/readyz"):
        row = payload.get(path, {})
        if row.get("status_code") != 200:
            problems.append(f"{path} -> {row.get('status_code')}")
        elif not row.get("status"):
            problems.append(f"{path} has no status field")
    if payload.get("/readyz", {}).get("status") != "ready":
        problems.append(f"/readyz status is {payload.get('/readyz', {}).get('status')!r}")
    if "checks" not in payload.get("/readyz", {}).get("keys", []):
        problems.append("/readyz does not report per-check results")

    evidence = {"probes": payload, "command": "python -c <TestClient probe>"}
    if problems:
        return _fail(cid, title, "; ".join(problems), evidence=evidence)
    return _pass(cid, title,
                 "liveness, detailed and readiness probes all answer 200 with JSON",
                 evidence=evidence)


# ---------------------------------------------------------------------------
# 5. Backup and restore
# ---------------------------------------------------------------------------

def _check_backup(ctx: Dict[str, Any]) -> Dict[str, Any]:
    cid, title = "backup.restore_drill", "SQLite stores back up and restore verifiably"
    root = ctx["root"]
    backend = root / "Northstar_backend"
    if str(backend) not in sys.path:
        sys.path.insert(0, str(backend))

    import sqlite_backup

    inventory = sqlite_backup.describe_stores(root=root)
    present = [row for row in inventory if row["exists"]]
    if not present:
        return _fail(cid, title, f"no SQLite stores present under {root}; nothing to drill")

    with tempfile.TemporaryDirectory(prefix="ns_prod_assert_backup_") as tmp:
        dest = Path(tmp) / "backups"
        backups = sqlite_backup.backup_all(dest, root=root)
        backed_up = [row for row in backups if row["status"] == "backed_up"]
        if not backed_up:
            return _fail(cid, title, "no store could be backed up")

        verified = [sqlite_backup.verify_backup(Path(row["manifest_path"]))
                    for row in backed_up]

        # Restore drill: the smallest critical store plus the store that carries
        # a sqlite-vec virtual table, into the temp directory only.
        drill_ids = [row["store"] for row in backed_up
                     if row["store"] in ("foundation", "tys_memory")]
        drill_ids = drill_ids or [row["store"] for row in backed_up[:1]]
        restores = []
        for store_id in drill_ids:
            manifest = next(Path(row["manifest_path"]) for row in backed_up
                            if row["store"] == store_id)
            target = Path(tmp) / f"restored_{store_id}.db"
            result = sqlite_backup.restore_backup(manifest, target)
            info = sqlite_backup.inspect_database(target)
            if not info["integrity_ok"]:
                return _fail(cid, title,
                             f"restored {store_id} failed integrity_check")
            restores.append({
                "store": store_id,
                "bytes": target.stat().st_size,
                "row_total": result["row_total"],
                "tables": result["tables"],
                "integrity_ok": info["integrity_ok"],
            })

        evidence = {
            "stores_present": [row["id"] for row in present],
            "stores_backed_up": [
                {"store": row["store"], "bytes": row["bytes"],
                 "row_total": row["row_total"]}
                for row in backed_up
            ],
            "verified": len(verified),
            "restores": restores,
            "skipped": [row for row in backups if row["status"] == "skipped"],
        }
        if len(verified) != len(backed_up):
            return _fail(cid, title, "not every backup verified", evidence=evidence)
        if not restores:
            return _fail(cid, title, "no restore drill ran", evidence=evidence)

    total_rows = sum(row["row_total"] for row in backed_up)
    return _pass(cid, title,
                 f"{len(backed_up)} store(s) backed up and verified, "
                 f"{len(restores)} restored and integrity-checked "
                 f"({total_rows} rows)",
                 evidence=evidence)


# ---------------------------------------------------------------------------
# 6. Rate limits
# ---------------------------------------------------------------------------

def _check_rate_limits(ctx: Dict[str, Any]) -> Dict[str, Any]:
    cid, title = "rate_limits.enforced", "rate limits are configured and enforced"
    root = ctx["root"]
    backend = root / "Northstar_backend"
    if str(backend) not in sys.path:
        sys.path.insert(0, str(backend))

    original = {k: os.environ.get(k)
                for k in ("NORTHSTAR_DISABLE_RATE_LIMIT", "ENVIRONMENT")}
    os.environ.pop("NORTHSTAR_DISABLE_RATE_LIMIT", None)
    os.environ.pop("ENVIRONMENT", None)
    try:
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from rate_limiter import RateLimitMiddleware

        limits = dict(RateLimitMiddleware.PLAN_LIMITS)
        anonymous_limit = min(limits.values())

        app = FastAPI()
        app.add_middleware(RateLimitMiddleware, window_seconds=60)

        @app.get("/probe")
        def probe():  # pragma: no cover - exercised over HTTP below
            return {"ok": True}

        client = TestClient(app)
        codes = [client.get("/probe").status_code
                 for _ in range(anonymous_limit + 1)]
        allowed = codes.count(200)
        throttled = codes.count(429)
        last = client.get("/probe")
        headers_present = ("X-RateLimit-Limit" in last.headers
                           and "Retry-After" in last.headers)
    finally:
        for key, value in original.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    posture_refused = False
    try:
        from rate_limiter import assert_prod_posture, prod_posture_ok

        saved = {k: os.environ.get(k)
                 for k in ("NORTHSTAR_DISABLE_RATE_LIMIT", "ENVIRONMENT")}
        os.environ["NORTHSTAR_DISABLE_RATE_LIMIT"] = "1"
        os.environ["ENVIRONMENT"] = "production"
        try:
            posture_refused = prod_posture_ok() is False
            try:
                assert_prod_posture()
                posture_refused = False
            except RuntimeError:
                pass
        finally:
            for key, value in saved.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value
    except Exception:
        posture_refused = False

    main_source = (backend / "main.py").read_text(encoding="utf-8", errors="replace")
    middleware_mounted = "app.add_middleware(RateLimitMiddleware" in main_source

    evidence = {
        "plan_limits": limits,
        "anonymous_limit": anonymous_limit,
        "requests_allowed": allowed,
        "requests_throttled": throttled,
        "headers_on_429": headers_present,
        "prod_posture_refused": posture_refused,
        "middleware_mounted_in_main": middleware_mounted,
    }
    problems: List[str] = []
    if not limits:
        problems.append("no plan limits configured")
    if allowed != anonymous_limit:
        problems.append(f"expected {anonymous_limit} allowed requests, saw {allowed}")
    if throttled != 1:
        problems.append(f"expected exactly one throttled request, saw {throttled}")
    if not headers_present:
        problems.append("429 response is missing X-RateLimit-Limit / Retry-After")
    if not posture_refused:
        problems.append("the limiter opt-out is not refused in production")
    if not middleware_mounted:
        problems.append("main.py does not mount RateLimitMiddleware")
    if problems:
        return _fail(cid, title, "; ".join(problems), evidence=evidence)
    return _pass(cid, title,
                 f"anonymous bucket {anonymous_limit}/min enforced with headers; "
                 "production opt-out refused",
                 evidence=evidence)


# ---------------------------------------------------------------------------
# 7. The checklist itself
# ---------------------------------------------------------------------------

CHECK_IDS: Tuple[str, ...] = (
    "ui.dist_production_shaped",
    "ui.served_bundle_clean",
    "ui.no_untrusted_innerhtml",
    "secrets.repo_clean",
    "config.env_example_covers_secrets",
    "config.env_example_covers_hosted",
    "config.dev_bypass_guarded",
    "redaction.enforced",
    "health.endpoints_answer",
    "backup.restore_drill",
    "rate_limits.enforced",
    "docs.checklist_commands",
)

_CHECK_COMMAND_RE = re.compile(
    r"`(python|npm|node|deploy/[^\s`]+|\S+\.(?:ps1|sh))[^`]*`"
)


def _doc_rows(text: str) -> List[Tuple[int, List[str]]]:
    """Table rows of the checklist: (line number, cells)."""
    rows: List[Tuple[int, List[str]]] = []
    for number, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        if not stripped.startswith("|") or stripped.startswith("|---"):
            continue
        cells = [cell.strip() for cell in stripped.strip("|").split("|")]
        if not cells or set(cells[0]) <= set("-: "):
            continue
        rows.append((number, cells))
    return rows


def _check_docs(ctx: Dict[str, Any]) -> Dict[str, Any]:
    cid, title = "docs.checklist_commands", "checklist rows carry real commands"
    root = ctx["root"]
    path = root / DOC_PATH
    if not path.is_file():
        return _fail(cid, title, f"missing {DOC_PATH}")
    text = path.read_text(encoding="utf-8", errors="replace")

    referenced = set(re.findall(
        r"`((?:ui|secrets|config|redaction|health|backup|rate_limits|docs)\.[a-z_]+)`",
        text,
    ))
    unknown = sorted(referenced - set(CHECK_IDS))
    undocumented = sorted(set(CHECK_IDS) - referenced)

    rows = _doc_rows(text)
    # Skip the header row of each table (its first cell is the column name).
    data_rows = [
        (number, cells) for number, cells in rows
        if cells[0].lower() not in ("area", "check", "id", "row", "key", "name",
                                    "item", "requirement")
    ]
    rows_without_command = [
        number for number, cells in data_rows
        if not any(_CHECK_COMMAND_RE.search(cell) for cell in cells)
    ]

    gaps = sorted(REGISTERED_SECRET_GAPS) + sorted(REGISTERED_HOSTED_KEY_GAPS)
    gaps_not_documented = [name for name in gaps if name not in text]

    evidence = {
        "doc": DOC_PATH,
        "data_rows": len(data_rows),
        "check_ids_referenced": len(referenced & set(CHECK_IDS)),
        "unknown_ids": unknown,
        "checks_not_documented": undocumented,
        "rows_without_command": rows_without_command,
        "registered_gaps_not_documented": gaps_not_documented,
    }
    problems: List[str] = []
    if unknown:
        problems.append("doc cites ids that do not exist: " + ", ".join(unknown))
    if undocumented:
        problems.append("checks missing from the doc: " + ", ".join(undocumented))
    if not data_rows:
        problems.append("the doc has no checklist table")
    if rows_without_command:
        problems.append(
            f"{len(rows_without_command)} row(s) carry no verifiable command "
            f"(lines {rows_without_command[:6]})")
    if gaps_not_documented:
        problems.append("registered config gaps not named in the doc: "
                        + ", ".join(gaps_not_documented))
    if problems:
        return _fail(cid, title, "; ".join(problems), evidence=evidence)
    return _pass(cid, title,
                 f"{len(data_rows)} rows, each with a command; "
                 f"all {len(CHECK_IDS)} checks documented",
                 evidence=evidence)


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

CHECKS: Tuple[Tuple[str, Callable[[Dict[str, Any]], Dict[str, Any]]], ...] = (
    ("ui.dist_production_shaped", _check_ui_dist),
    ("ui.served_bundle_clean", _check_ui_bundle_clean),
    ("ui.no_untrusted_innerhtml", _check_ui_innerhtml),
    ("secrets.repo_clean", _check_secrets_repo),
    ("config.env_example_covers_secrets", _check_env_secrets),
    ("config.env_example_covers_hosted", _check_env_hosted),
    ("config.dev_bypass_guarded", _check_dev_bypass),
    ("redaction.enforced", _check_redaction),
    ("health.endpoints_answer", _check_health),
    ("backup.restore_drill", _check_backup),
    ("rate_limits.enforced", _check_rate_limits),
    ("docs.checklist_commands", _check_docs),
)


def run(only: Optional[Sequence[str]] = None, root: Optional[Path] = None,
        strict: bool = False) -> Dict[str, Any]:
    ctx = {"root": Path(root) if root else REPO_ROOT}
    selected = [
        (check_id, fn) for check_id, fn in CHECKS
        if not only or any(token in check_id for token in only)
    ]
    if not selected:
        return {
            "schema": SCHEMA,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "root": str(ctx["root"]),
            "ok": False,
            "error": f"no check matches {list(only or [])}",
            "checks": [],
            "summary": {"pass": 0, "fail": 0, "skip": 0, "advisory": 0},
        }

    results: List[Dict[str, Any]] = []
    for check_id, fn in selected:
        try:
            results.append(fn(ctx))
        except Exception as exc:  # noqa: BLE001 - a crashing check is a failure
            results.append(_fail(check_id, check_id,
                                 f"check raised: {type(exc).__name__}: {exc}"))

    advisories = sum(len(row.get("advisories", [])) for row in results)
    summary = {
        "pass": sum(1 for row in results if row["status"] == "pass"),
        "fail": sum(1 for row in results if row["status"] == "fail"),
        "skip": sum(1 for row in results if row["status"] == "skip"),
        "advisory": advisories,
    }
    ok = summary["fail"] == 0 and (advisories == 0 or not strict)
    return {
        "schema": SCHEMA,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "root": str(ctx["root"]),
        "strict": bool(strict),
        "ok": ok,
        "summary": summary,
        "checks": results,
    }


def _print_human(report: Dict[str, Any]) -> None:
    for row in report["checks"]:
        mark = {"pass": "PASS", "fail": "FAIL", "skip": "SKIP"}[row["status"]]
        print(f"{mark}  {row['id']:<34} {row['title']}")
        print(f"      {row['detail']}")
        for advisory in row.get("advisories", []):
            print(f"      GAP  {advisory}")
        print(f"      run: {row['command']}")
    summary = report["summary"]
    verdict = "PRODUCTION-SHAPED" if report["ok"] else "NOT PRODUCTION-SHAPED"
    print(
        f"\n{verdict}: {summary['pass']} passed, {summary['fail']} failed, "
        f"{summary['skip']} skipped, {summary['advisory']} advisories"
    )
    if report.get("strict") and summary["advisory"] and not summary["fail"]:
        print("--strict: advisories are treated as failures")


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="production_assert",
        description="Assert that the repository is production-shaped.",
    )
    parser.add_argument("--json", action="store_true", help="machine-readable report")
    parser.add_argument("--only", action="append", default=None,
                        help="run checks whose id contains this token (repeatable)")
    parser.add_argument("--strict", action="store_true",
                        help="fail on advisories as well as failures")
    parser.add_argument("--root", default=None, help="repo root (default: this repo)")
    parser.add_argument("--list", action="store_true", help="list the check ids")
    args = parser.parse_args(argv)

    if args.list:
        for check_id in CHECK_IDS:
            print(check_id)
        return 0

    report = run(only=args.only,
                 root=Path(args.root) if args.root else None,
                 strict=args.strict)
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        _print_human(report)
    return 0 if report["ok"] else 1


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
