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
- `--allowlist PATH` / `--no-allowlist`
- Allowlist: **`.secret_scan_allowlist.json`** — entries match by
  `sha256(exact matched text) + rule id` (never path/substring). A changed
  value at the same location re-flags. Malformed allowlist ⇒ ignored with a
  warning (never suppresses findings).
- Exit code 0 = no active findings; 1 = active findings (allowlisted items are
  reported separately as `ALLOWED …`).

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
