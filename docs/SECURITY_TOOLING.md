# Security Tooling (Phase 1 — Secure Control-Layer)

Record of the pinned security tooling, where it lives, and how to run it.
No secret values appear in this document.

## 1. gitleaks — pinned & checksummed (owner-approved 2026-10-11)

| Item | Value |
|---|---|
| Version | **8.30.1** (`gitleaks version` → 8.30.1) |
| Source | `https://github.com/gitleaks/gitleaks/releases/tag/v8.30.1` |
| Asset | `gitleaks_8.30.1_windows_x64.zip` |
| Asset SHA256 | `d29144deff3a68aa93ced33dddf84b7fdc26070add4aa0f4513094c8332afc4e` |
| Checksums file | `gitleaks_8.30.1_checksums.txt` (SHA256 `061476c21adaf5441516f96f185c1a4706a83cd6329b9b38762271b3d4a52fae`) |
| Verification | Triple-checked: downloaded zip hash == checksums-file line == GitHub API asset digest; checksums file hash == API digest |
| Install path | `%LOCALAPPDATA%\gitleaks\8.30.1\gitleaks.exe` (outside the repo; nothing binary is committed) |

Usage:

```powershell
# History scan (what CI sees; skips untracked files, venvs, .env)
& "$env:LOCALAPPDATA\gitleaks\8.30.1\gitleaks.exe" git . -c .gitleaks.toml --redact --no-banner -f json -r "$env:TEMP\gl.json"

# Working-tree scan of a specific dir (NOTE: this includes local-only files
# such as .env — expect and ignore that noise; never commit the report raw)
& "$env:LOCALAPPDATA\gitleaks\8.30.1\gitleaks.exe" dir northstar -c .gitleaks.toml --redact
```

Notes:
- `.gitleaks.toml` at the repo root extends the default ruleset and allowlists
  the Phase-1 test harness paths.
- The gitleaks report can embed secret values **unless `--redact` is used —
  always pass `--redact` when writing a report.**
- CI: `.github/workflows/security.yml` runs the standard `gitleaks-action`
  (activates when the repo is hosted with Actions).
- gitleaks has **no fingerprint (hash) allowlist mechanism**; the repo's
  fingerprint-exact gate is the offline scanner below (gitleaks runs as the
  broad-spectrum advisory) — this split is deliberate and owner-visible.

## 2. Offline secret scanner — the fingerprint-exact gate

`python -m northstar.security.secret_scan` (stdlib-only; pre-commit + CI use it).

- `--tracked` (CI/local gate) · `--staged` (pre-commit) · `--root X` · `--json`
- `--allowlist PATH` / `--no-allowlist`; `--baseline PATH` / `--no-baseline`
- **Allowlist** (`.secret_scan_allowlist.json`) — reviewed-BENIGN findings;
  printed as `ALLOWED`; never fail the run.
- **Baseline** (`.secret_scan_baseline.json`) — known-ACTIVE escalations
  awaiting owner remediation; printed as `KNOWN-ACTIVE` **with reasons on
  every run** so the count stays visible; entries that stop matching are
  reported as `STALE-BASELINE` (cleanup prompt); only **NEW** findings fail.
- Both registries match by `sha256(exact matched text) + rule id` — never by
  path/substring; a changed value at the same location re-flags. A malformed
  registry is ignored with a warning (it can never suppress a finding).
- Summary line: `N new finding(s), M known-active (baseline), K allowlisted`.

## 3. uv — dependency pins (owner-approved 2026-10-11)

- uv **0.13.0** installed via `python -m pip install uv`.
- `Northstar_backend/pyproject.toml` added; **`Northstar_backend/uv.lock`
  committed** (34 packages resolved with hashes).
- Regenerate after dependency changes:

```powershell
cd Northstar_backend
uv lock        # uv.exe at C:\Python314\Scripts\uv.exe on this machine
```

- `Northstar_backend/requirements.txt` is retained for the legacy pip path
  (Dockerfile.api); switching the Docker build onto `uv.lock` is a follow-up
  item (needs the owner-visible Docker change, tracked in the Phase 1 list).

## 4. Config loader — env-only (Phase 1)

`northstar/security/env_config.py` — the control layer reads secrets ONLY from
the process environment: `get_secret(name)` / `require_secret(name)` /
`secret_presence(names)` / `redacted_summary(names)`. It never reads `.env`
files, never calls `load_dotenv`, and its summaries carry `NAME=SET|MISSING`
only — never values. A Keychain backend is an explicit future plug-in slot
(`BACKENDS`); env is the only backend today. (A test guards the module source
against ever gaining a dotenv import.)

## 5. Log redaction (Phase 1)

`Northstar_backend/logging_config.py` wraps its formatter and adds
`RedactionFilter` from `northstar.security.redaction` — messages, args,
`extra_data`, and tracebacks are redacted before leaving the process.
Coverage includes compound env names (`SCAVIO_API_KEY=…`), `sk-`/`sk_` styles,
all GitHub token prefixes (`ghp_/gho_/ghu_/ghs_/ghr_`, `github_pat_`), JWTs,
PEM blocks, auth/cookie headers, GUIDs under key names, and emails.

## 6. CI wiring

`.github/workflows/security.yml` (activates when the repo is hosted with
Actions enabled):

| Job | Blocking? | What it runs |
|---|---|---|
| `secret-scan` | **Yes** | offline scanner (`--tracked`, allowlist+baseline aware, count line printed) + `pytest tests/security -q` |
| `gitleaks` | No (advisory) | standard gitleaks-action (full history); no hash allowlist → advisory until the fingerprint-filter wrapper lands |
| `audit` | No (initial) | `pip-audit` against a frozen `uv export` of `uv.lock`; `npm audit` (root + UI); SBOM (SPDX) uploaded as an artifact |

Local equivalent: `powershell -NoProfile -File scripts/security_checks.ps1`
(scanner + tests; exit 0 = no NEW findings and all tests pass).

Action pins (full SHAs, resolved via the GitHub API on 2026-10-11):

| Action | SHA | Tag at resolution |
|---|---|---|
| `actions/checkout` | `11d5960a326750d5838078e36cf38b85af677262` | v4 |
| `actions/setup-python` | `a26af69be951a213d495a4c3e4e4022e16d87065` | v5 |
| `actions/setup-node` | `49933ea5288caeca8642d1e84afbd3f7d6820020` | v4 |
| `gitleaks/gitleaks-action` | `ff98106e4c7b2bc287b24eaf42907196329070c7` | v2 |
| `anchore/sbom-action` | `e22c389904149dbc22b58101806040fa8d37a610` | v0 |

Workflow hardening: top-level `permissions: {}` with per-job least privilege;
`persist-credentials: false` on every checkout; per-job `timeout-minutes`;
run concurrency with cancel-in-progress; `uv==0.13.0` pinned in the audit job.
