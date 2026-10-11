"""Offline secret scanner — zero-dependency interim "gitleaks or equivalent".

Phase 1 (Secure Control-Layer) requires a secret check in pre-commit and CI.
The gitleaks binary install is pending owner approval of the download (see
``reports/audit.md`` D3); this scanner is the offline equivalent that works
today with nothing but the standard library:

- conservative credential-shape rules (AWS/GitHub/Slack/OpenAI-style tokens,
  JWTs, PEM private keys, Bearer tokens, credential-like assignments);
- placeholder values (``test-``/``fake``/``example``/``your_`` ...) are skipped;
- findings NEVER contain a full value — only rule id, path, line and a
  truncated proof fragment (first 4 chars + length);
- binary files, oversized files, ``.env.example`` files and the
  intentionally-fake ``tests/security`` fixtures are skipped.

Usage (from the repo root):

    python -m northstar.security.secret_scan --tracked
    python -m northstar.security.secret_scan --staged          # pre-commit
    python -m northstar.security.secret_scan --root northstar --root tests
    python -m northstar.security.secret_scan --json

Exit codes: 0 = clean, 1 = findings, 2 = usage error.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from dataclasses import asdict, dataclass
from northstar.security.redaction import has_sensitive_key
from pathlib import Path
from typing import Iterable, List, Optional, Sequence, Tuple

MAX_FILE_BYTES = 2_000_000

SKIP_DIR_NAMES = {
    ".git",
    "node_modules",
    "__pycache__",
    ".pytest_cache",
    ".wrangler",
    ".playwright-mcp",
    "venv",
    "venv-wsl",
    "venv-phase1c02",
    ".venv",
    "dist",
    "build",
    "Northstar_backend_audit_export",
    "site-packages",
    ".mypy_cache",
    ".ruff_cache",
}
SKIP_FILE_SUFFIXES = {".example"}
SKIP_FILE_NAMES = {".env.example"}

# Paths that contain intentionally fake fixture values (documented in the files
# themselves); the same paths are allowlisted in .gitleaks.toml.
DEFAULT_EXCLUDED_PATHS = ("tests/security",)

_TOKEN_RULES: Tuple[Tuple[str, "re.Pattern[str]", str], ...] = (
    (
        "aws-access-key-id",
        re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b"),
        "AWS access key id",
    ),
    (
        "github-token",
        re.compile(
            r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{36,}\b"
            r"|\bgithub_pat_[A-Za-z0-9_]{30,}\b"
        ),
        "GitHub token",
    ),
    (
        "openai-style-key",
        re.compile(r"\bsk[_-][A-Za-z0-9_-]{16,}\b"),
        "OpenAI-style secret key",
    ),
    ("slack-token", re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b"), "Slack token"),
    (
        "jwt",
        re.compile(r"\beyJ[A-Za-z0-9_-]{8,}(?:\.[A-Za-z0-9_-]{8,}){1,2}\b"),
        "JWT-shaped token",
    ),
    (
        "pem-private-key",
        re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
        "PEM private key block",
    ),
    (
        "authorization-header",
        re.compile(
            r"(?i)\b(?:authorization|proxy-authorization)[ \t]*[:=][ \t]*[^\r\n]+"
        ),
        "Authorization header with value",
    ),
    (
        "bearer-token",
        re.compile(r"(?i)\bbearer[ \t]+[A-Za-z0-9._~+/=-]{8,}"),
        "Bearer token",
    ),
    (
        "cookie-header",
        re.compile(r"(?i)\b(?:set-cookie|cookie)[ \t]*[:=][ \t]*[^\r\n]+"),
        "Cookie header with value",
    ),
)

_KV_PATTERN = re.compile(
    r"(?i)(?<![A-Za-z0-9])(password|passwd|pwd|secret|tokens?|api[_-]?key|"
    r"access[_-]?key|secret[_-]?key|client[_-]?secret|credentials?)\b"
    r"([\"']?[ \t]*[:=][ \t]*)"
    r"('[^']*'|\"[^\"]*\"|[^\s,;\"']{4,})"
)

# Values that are code references, not literals — never flag these.
_CODE_VALUE_PATTERN = re.compile(
    r"[+`(){}$&|<>]|process\.env|os\.environ|os\.getenv|import\.meta|"
    r"getElementById|[A-Za-z_][\w]*\.[A-Za-z_]|\b(?:await|async|include|omit)\b"
)

# Bare identifier references (constants / kebab slugs) are not literals.
_UPPER_SNAKE_PATTERN = re.compile(r"[A-Z0-9_]{4,}")
_KEBAB_PATTERN = re.compile(r"[a-z]+(?:-[a-z]+)+")

# Status/enum words are never secret values (provider presence maps, UI states).
_STATUS_WORDS = {
    "configured",
    "unconfigured",
    "missing",
    "present",
    "unset",
    "set",
    "disabled",
    "enabled",
    "armed",
    "disarmed",
    "available",
    "unavailable",
    "connected",
    "disconnected",
}

# Semver-ish values (lockfiles) are never secrets.
_SEMVER_PATTERN = re.compile(r"\^?\d+(?:\.\d+)*(?:[-+][\w.]+)?")

# Header-style rules: skip placeholder examples AND code expressions
# (docs/tests write ``Bearer <token>``; code writes ``Bearer {apiKey}``).
_HEADER_RULES = {"bearer-token", "authorization-header", "cookie-header"}

# Amazon "dib=" URL blobs are third-party checkout tokens embedded in scraped
# URLs (same class as NO_LEAK_AUDIT F2) — never Northstar credentials.
_AMAZON_DIB_PREFIX = re.compile(r"dib=")

_PLACEHOLDER_PATTERN = re.compile(
    r"(?i)(test|fake|dummy|example|placeholder|changeme|your[_-]|sample|"
    r"invalid|local|not[_-]?real|redacted|xxxx|<[^>]{2,}>|\{\{)"
)


@dataclass(frozen=True)
class Finding:
    rule: str
    description: str
    path: str
    line: int
    column: int
    proof: str  # truncated fragment — never the full value
    fingerprint: str  # sha256 of the exact matched text — the allowlist key


def _proof(match: str) -> str:
    return f"{match[:4]}…(len={len(match)})"


def _fingerprint(match: str) -> str:
    """sha256 of the exact matched text — fingerprint-exact allowlist key."""
    return hashlib.sha256(match.encode("utf-8")).hexdigest()


def _line_col(text: str, offset: int) -> Tuple[int, int]:
    line = text.count("\n", 0, offset) + 1
    last_nl = text.rfind("\n", 0, offset)
    return line, offset - last_nl


def _strip_quotes(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "'\"":
        value = value[1:-1]
    return value


def _header_context_ok(text: str, start: int) -> bool:
    """True when a header-style keyword appears in header context.

    Accepts: start of a line, or right after ``"`` ``'`` ``{`` ``[`` ``(``
    ``:`` ``,`` or a curl ``-H`` / ``--header``. Prose like
    "purchase authorization: ..." is rejected.
    """
    line_start = text.rfind("\n", 0, start) + 1
    prefix = text[line_start:start].rstrip()
    if not prefix:
        return True
    if prefix[-1] in "\"'{[(:,":
        return True
    return prefix.endswith("-H") or prefix.endswith("--header")


def scan_text(path: str, text: str) -> List[Finding]:
    """Scan a text blob; returns findings (proof fragments only, never values)."""
    findings: List[Finding] = []
    for rule_id, pattern, description in _TOKEN_RULES:
        for m in pattern.finditer(text):
            if rule_id in _HEADER_RULES:
                if _PLACEHOLDER_PATTERN.search(
                    m.group(0)
                ) or _CODE_VALUE_PATTERN.search(m.group(0)):
                    continue
                if not _header_context_ok(text, m.start()):
                    continue
            if rule_id == "jwt" and _AMAZON_DIB_PREFIX.search(
                text[max(0, m.start() - 80):m.start()]
            ):
                continue
            line, col = _line_col(text, m.start())
            findings.append(
                Finding(
                    rule_id,
                    description,
                    path,
                    line,
                    col,
                    _proof(m.group(0)),
                    _fingerprint(m.group(0)),
                )
            )
    for m in _KV_PATTERN.finditer(text):
        raw_value = m.group(3)
        value = _strip_quotes(raw_value)
        quoted = raw_value[:1] in ("'", '"')
        if len(value) < 4:
            continue
        # Unquoted values must at least look literal-ish (>=6 chars, one digit);
        # unquoted bare identifiers/expressions are almost always code.
        if not quoted and not (len(value) >= 6 and re.search(r"\d", value)):
            continue
        if _SEMVER_PATTERN.fullmatch(value):
            continue
        if value.lower() in _STATUS_WORDS:
            continue
        # Lowercase-only single words (status strings, doc placeholders, enum
        # values like "string"/"unconfigured") are never high-entropy secrets.
        if re.fullmatch(r"[a-z_]{4,24}", value):
            continue
        # Quoted prose (3+ words) is display text, never a credential value.
        if quoted and len(value.split()) >= 3:
            continue
        if (
            _PLACEHOLDER_PATTERN.search(value)
            or _CODE_VALUE_PATTERN.search(value)
            or has_sensitive_key(value)
            or _UPPER_SNAKE_PATTERN.fullmatch(value)
            or _KEBAB_PATTERN.fullmatch(value)
        ):
            continue
        line, col = _line_col(text, m.start())
        findings.append(
            Finding(
                "credential-assignment",
                "credential-like assignment",
                path,
                line,
                col,
                _proof(m.group(0)),
                _fingerprint(m.group(0)),
            )
        )
    findings.sort(key=lambda f: (f.line, f.rule))
    return findings


def _iter_files(roots: Sequence[Path]) -> Iterable[Path]:
    for root in roots:
        root = Path(root)
        if root.is_file():
            yield root
            continue
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIR_NAMES)
            for name in sorted(filenames):
                path = Path(dirpath) / name
                if (
                    path.name.lower() in SKIP_FILE_NAMES
                    or path.suffix.lower() in SKIP_FILE_SUFFIXES
                ):
                    continue
                yield path


def _read_text(path: Path) -> str:
    try:
        if path.stat().st_size > MAX_FILE_BYTES:
            return ""
        chunk = path.read_bytes()
    except OSError:
        return ""
    if b"\x00" in chunk[:8192]:
        return ""  # binary
    return chunk.decode("utf-8", errors="replace")


def _is_excluded(posix_path: str, exclude: Sequence[str]) -> bool:
    return any(item in posix_path for item in exclude)


_ALLOWLIST_FILENAME = ".secret_scan_allowlist.json"
_BASELINE_FILENAME = ".secret_scan_baseline.json"
_REGISTRY_ROOT = Path(__file__).resolve().parents[2]


def _load_registry(path: Optional[Path], default_path: Path, label: str) -> dict:
    """Load a fingerprint-exact JSON registry: ``{(rule, sha256): reason}``.

    Entries match findings by the EXACT sha256 of the matched text plus the
    rule id — never by path or substring, so a different value at the same
    location is still flagged. A malformed registry is ignored with a warning
    (it can never suppress a finding, only annotate it).
    """
    reg_path = Path(path) if path else default_path
    if not reg_path.is_file():
        return {}
    try:
        data = json.loads(reg_path.read_text(encoding="utf-8"))
        out = {}
        for entry in data.get("entries", []):
            rule = str(entry.get("rule", "")).strip()
            fp = str(entry.get("fingerprint", "")).strip().lower()
            reason = str(entry.get("reason", "")).strip()
            if rule and re.fullmatch(r"[0-9a-f]{64}", fp):
                out[(rule, fp)] = reason
        return out
    except Exception as exc:  # malformed → ignore; findings stay visible
        print(
            f"secret_scan: WARNING {label} unreadable ({exc}); ignoring it",
            file=sys.stderr,
        )
        return {}


def load_allowlist(path: Optional[Path] = None) -> dict:
    """Reviewed-benign findings: never fail the run, printed as ALLOWED."""
    return _load_registry(path, _REGISTRY_ROOT / _ALLOWLIST_FILENAME, "allowlist")


def load_baseline(path: Optional[Path] = None) -> dict:
    """Known ACTIVE findings (escalations awaiting remediation).

    They never fail the run but stay VISIBLE as ``KNOWN-ACTIVE`` with their
    reasons; a baseline entry that no longer matches is reported as
    ``STALE-BASELINE`` (cleanup prompt). NEW findings beyond the baseline
    always fail — the gate is only ever quiet about findings the owner has
    already seen.
    """
    return _load_registry(path, _REGISTRY_ROOT / _BASELINE_FILENAME, "baseline")


def scan_paths(
    roots: Sequence[Path], *, exclude: Sequence[str] = DEFAULT_EXCLUDED_PATHS
) -> List[Finding]:
    findings: List[Finding] = []
    for path in _iter_files([Path(r) for r in roots]):
        posix = path.as_posix()
        if _is_excluded(posix, exclude):
            continue
        text = _read_text(path)
        if not text:
            continue
        findings.extend(scan_text(posix, text))
    findings.sort(key=lambda f: (f.path, f.line, f.rule))
    return findings


def _git_z(args: Sequence[str]) -> List[Path]:
    try:
        out = subprocess.run(
            ["git", *args], capture_output=True, text=True, timeout=60
        )
    except (OSError, subprocess.SubprocessError):
        return []
    if out.returncode != 0:
        return []
    return [Path(p) for p in out.stdout.split("\0") if p]


def tracked_files() -> List[Path]:
    return [p for p in _git_z(["ls-files", "-z"]) if p.exists()]


def staged_files() -> List[Path]:
    return [
        p
        for p in _git_z(
            ["diff", "--cached", "--name-only", "--diff-filter=ACM", "-z"]
        )
        if p.exists()
    ]


def _scan_file_list(files: Sequence[Path]) -> List[Finding]:
    findings: List[Finding] = []
    for path in files:
        posix = path.as_posix()
        if _is_excluded(posix, DEFAULT_EXCLUDED_PATHS):
            continue
        text = _read_text(path)
        if not text:
            continue
        findings.extend(scan_text(posix, text))
    findings.sort(key=lambda f: (f.path, f.line, f.rule))
    return findings


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m northstar.security.secret_scan",
        description="Offline secret scanner (Phase 1 interim gitleaks equivalent).",
    )
    parser.add_argument(
        "--root",
        action="append",
        dest="roots",
        default=[],
        help="directory or file to scan (repeatable; default: repo root '.')",
    )
    parser.add_argument(
        "--tracked", action="store_true", help="scan git-tracked files only"
    )
    parser.add_argument(
        "--staged", action="store_true", help="scan git-staged files only (pre-commit)"
    )
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    parser.add_argument(
        "--allowlist",
        default=None,
        help=(
            "path to the fingerprint-exact allowlist JSON "
            "(default: repo-root .secret_scan_allowlist.json)"
        ),
    )
    parser.add_argument(
        "--no-allowlist",
        action="store_true",
        help="ignore the allowlist entirely (every finding is active)",
    )
    parser.add_argument(
        "--baseline",
        default=None,
        help=(
            "path to the known-active findings baseline JSON "
            "(default: repo-root .secret_scan_baseline.json)"
        ),
    )
    parser.add_argument(
        "--no-baseline",
        action="store_true",
        help="ignore the baseline entirely (every non-allowlisted finding fails)",
    )
    args = parser.parse_args(list(argv) if argv is not None else None)

    if args.tracked and args.staged:
        print(
            "secret_scan: --tracked and --staged are mutually exclusive",
            file=sys.stderr,
        )
        return 2

    if args.staged:
        findings = _scan_file_list(staged_files())
    elif args.tracked:
        findings = _scan_file_list(tracked_files())
    else:
        findings = scan_paths([Path(r) for r in (args.roots or ["."])])

    allowlist = (
        {}
        if args.no_allowlist
        else load_allowlist(Path(args.allowlist) if args.allowlist else None)
    )
    baseline = (
        {}
        if args.no_baseline
        else load_baseline(Path(args.baseline) if args.baseline else None)
    )
    new_findings = []
    known_active = []
    allowed = []
    for finding in findings:
        reason = allowlist.get((finding.rule, finding.fingerprint))
        if reason:
            allowed.append((finding, reason))
            continue
        base_reason = baseline.get((finding.rule, finding.fingerprint))
        if base_reason:
            known_active.append((finding, base_reason))
        else:
            new_findings.append(finding)

    matched_keys = {(f.rule, f.fingerprint) for f, _reason in known_active}
    stale = [
        (key, reason) for key, reason in baseline.items() if key not in matched_keys
    ]
    for (rule, fp), reason in sorted(stale):
        print(
            f"STALE-BASELINE [{rule}] fp={fp[:16]}… — {reason} "
            "(no longer present; remove the entry)",
            file=sys.stderr,
        )

    if args.json:
        print(
            json.dumps(
                {
                    "findings": [asdict(f) for f in new_findings],
                    "known_active": [
                        {"finding": asdict(f), "reason": reason}
                        for f, reason in known_active
                    ],
                    "allowlisted": [
                        {"finding": asdict(f), "reason": reason}
                        for f, reason in allowed
                    ],
                    "stale_baseline": [
                        {"rule": rule, "fingerprint": fp, "reason": reason}
                        for (rule, fp), reason in sorted(stale)
                    ],
                },
                indent=2,
            )
        )
    else:
        for f in new_findings:
            print(
                f"FINDING [{f.rule}] {f.path}:{f.line}:{f.column} "
                f"proof={f.proof} — {f.description}"
            )
        for f, reason in known_active:
            print(
                f"KNOWN-ACTIVE [{f.rule}] {f.path}:{f.line} "
                f"fp={f.fingerprint[:16]}… — {reason}"
            )
        for f, reason in allowed:
            print(
                f"ALLOWED [{f.rule}] {f.path}:{f.line} "
                f"fp={f.fingerprint[:16]}… — {reason}"
            )
        print(
            f"secret_scan: {len(new_findings)} new finding(s), "
            f"{len(known_active)} known-active (baseline), {len(allowed)} allowlisted"
        )
    return 1 if new_findings else 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
