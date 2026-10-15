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

## 4. Config loader — env-first, optional operator env-file (Phase 1)

`northstar/security/env_config.py` — the control layer reads secrets from the
process environment; additionally, and ONLY when the operator sets the
`NORTHSTAR_ENV_FILE` environment variable to a path, values may be read from
that file. The path is never hardcoded in code, tests, docs, or reports, and
file contents are never logged or printed. API: `get_secret(name)` /
`require_secret(name)` / `require_env_file()` / `secret_presence(names)` /
`redacted_summary(names)`. `require_env_file()` **fails closed** with a clear
error when the variable is unset or the file is missing — messages contain the
variable NAME only, never a path or a value. Presence checks are boolean
(`NAME=SET|MISSING`) and consider both sources; the module never calls
`load_dotenv` (guarded by an AST test). Process environment wins over the file.

Cloud-sync note (owner to review): the current env file lives under a user
Desktop folder that **may be synced to a cloud backup service**. The owner will
check this and move the file if needed — the loader only ever needs the
`NORTHSTAR_ENV_FILE` variable updated; nothing else changes.

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

## 7. Lightpanda (Phase 3 browser dependency) — pinned install

Owner-approved 2026-10-11 with hard pinning conditions; installed the same day.

| Item | Value |
|---|---|
| Version | **1.0.0** (numbered release, published 2026-10-02; newest numbered release) — nightly/latest rejected as moving targets |
| Install path | Docker on Windows dev (official binaries are macOS/Linux). Mac/ARM64 prod resolves the same multi-platform digest |
| Image | `lightpanda/browser`, pinned by **multi-platform digest** (never a tag): `sha256:5b84708cb3d9bef841aba4a4cd299f4de0609ac1bd7d4c6fbfcbf168d56b685e` |
| Checksum verification | Two independent sources, both agreeing: Docker Hub API (tag `1.0.0`) and `docker buildx imagetools inspect` |
| Platform manifests | linux/amd64 `sha256:16b668ba75fdf3f9b215a0550f2840a0e76b905c645d99a23751dcd40a65688a` · linux/arm64 `sha256:dddeeccaea193724896a8c7b18a6630c66de18821518179a33060b0aa189090c` |
| Release asset digests (GitHub API) | x86_64-linux `aa5a4b8e…31c3` · aarch64-linux `69791924…44f5` · macOS both · `.deb` both — recorded in `reports/lightpanda_install_20261011.md` |
| Hardening | `LIGHTPANDA_DISABLE_TELEMETRY=true`, `LIGHTPANDA_DISABLE_CORE_DUMP=true` (+ `ulimit core 0`), `--obey-robots`, `no-new-privileges`, `mem_limit 1g`, `cpus 2.0`, non-root (`User=lightpanda` from the image) |
| Network | Loopback-only publish `127.0.0.1:9222:9222`; proof: `scripts/lightpanda_loopback_test.ps1` (PASS 2026-10-11) |
| Config | `docker-compose.lightpanda.yml` (config only — the binary is never committed) |
| License posture | AGPL-3.0 — runs **unmodified** as a separate process; never forked or patched |

## Adopted dev/quality tooling - D-S2 (2026-10-14)

All pinned; installed at operator-machine scope (no repo changes beyond this record).

| Tool | Pinned version | Install location | Notes |
|---|---|---|---|
| trivy | 0.76.0 | `C:\Users\T2Hol\AppData\Local\trivy\0.76.0\trivy.exe` (sha256 VERIFIED vs release `checksums.txt`: `7b4762a5a5326cb4b83dfd2bb5d9aaf15a1ed867c75cad7dd8b38840a28e7be6`) | Container/IaC/secret/SBOM scanning. First vuln scan downloads the vulnerability DB (network). Secret scan run 2026-10-14 on `northstar/`: no findings (exit 0). Note: trivy uses entropy heuristics - low-entropy fake-shaped samples are intentionally not flagged. |
| pip-audit | 2.10.1 | uv tool (`%USERPROFILE%\.local\bin\pip-audit.exe`) | Python dependency vuln audit; audits against PyPI advisory data. |
| semgrep | 1.181.0 | uv tool (`%USERPROFILE%\.local\bin\semgrep.exe`) | Static analysis. Hygiene: run with `SEMGREP_SEND_METRICS=off` (metrics otherwise sent to Semgrep by default). |
| schemathesis | 4.31.1 | uv tool (`%USERPROFILE%\.local\bin\schemathesis.exe`) | Property-based API testing from OpenAPI (FastAPI surface). |
| promptfoo | 0.124.1 | npm global (`npm i -g promptfoo@0.124.1`) | Prompt/agent eval + red-teaming. |
| context7 (MCP) | endpoint `https://mcp.context7.com/mcp` | OpenCode global config (added 2026-10-14; backup `opencode.json.bak.20261014b`) | Remote docs MCP; verified connected (tools `resolve-library-id`, `query-docs` live). Queries go to the Context7 API - never include secrets/customer data; optional API key (context7.com/dashboard) for higher rate limits. |

- PATH note: `%USERPROFILE%\.local\bin` is not on PATH; run `uv tool update-shell` once (or use full paths). Not applied automatically.
- Wiring into `scripts/security_checks.ps1` / CI is a follow-up decision (D-S2 scope was install + verify + record).

## Docker Desktop resource caps (operator note, 2026-10-15)

Docker Desktop on this box shares resources with the local model lanes (Ollama + llama.cpp), and the engine has now been wedged twice by heavy operations (a stalled image pull on 2026-10-14 left it unresponsive to every command until an operator restart; the post-restart state came up with the engine fully stopped until Docker Desktop was launched). Recommended caps while local-model work runs:
- **Settings -> Resources -> Memory**: cap the VM (e.g. 6-8 GB). Our containers (lightpanda, postgres) are small; llama.cpp/Ollama need the headroom on this 16 GB system.
- Keep **"Start Docker Desktop when you sign in" OFF** if you want the engine stopped during GPU-heavy sessions; launch it when containers are needed.
- **Avoid pulling large images while a model is loaded** — a wedged pull can take the whole engine down (observed 2026-10-14: two probe runs stalled; engine unresponsive until restart).
- After any engine restart: `docker start northstar-lightpanda` is the only expected container action. The app stack is recreatable via its compose file; its data lives in named volumes (verified `northstarosretailarbitrageagent_postgres-data` survives container removal).