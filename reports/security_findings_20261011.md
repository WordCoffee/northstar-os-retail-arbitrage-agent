# Phase 1 — Secret-Scan Findings & Interim Scanner Report

- **Date:** 2026-10-11 · **Owner:** T2 Holdings LLC
- **Status:** Phase 1 increment 2 (offline secret scanner + supply-chain scaffolding). **Not** Phase 1 completion — remaining items listed at the bottom.
- **Method:** read-only scans + masked triage tooling (no credential value was printed anywhere — findings show only rule/path/line and truncated proof fragments). No live fetches; no paid calls; no Amazon; no file in the repo was modified for remediation (owner decisions pending).

## 1. What was built (this increment)

| Artifact | Purpose |
|---|---|
| `northstar/security/secret_scan.py` | Offline, zero-dependency secret scanner (interim "gitleaks or equivalent"); `--tracked` / `--staged` / `--root` / `--json` |
| `tests/security/test_secret_scan.py` | 26 scanner tests (rules, precision skips, exit codes, proof truncation) |
| `.gitleaks.toml` | Pinned-config stub for the gitleaks binary (**install pending owner approval of the download**) |
| `.pre-commit-config.yaml` | Local pre-commit hook → offline scanner on staged files (gitleaks hook documented, pending pin) |
| `.github/workflows/security.yml` | CI stub: offline scan + `tests/security` + gitleaks-action job (activates when the repo is hosted with Actions) |
| `.gitignore` | Phase 1 secret-hygiene block (`*.pem/*.p12/*.pfx`, `.chromeconnect/`, `.playwright-mcp/`, `.wrangler/tmp/`) |
| (previous commit `cda7e06`) | Log redaction filter+formatter wired into `Northstar_backend/logging_config.py` |

**Evidence:** `python -m pytest tests/security -q` → **49 passed / 0 failed**. Foundation test collection unchanged (819 collected). Scanner iterations on tracked files: **214 → 51 → 32 → 10 findings** after principled precision fixes (never by hiding real findings — see §3).

**Reproduce:** `python -m pytest tests/security -q` · `python -m northstar.security.secret_scan --tracked`

## 2. Current findings (10) — classification and recommended actions

### 🔴 ESCALATION — likely real third-party credential in a committed chat export
| Field | Value |
|---|---|
| Location | `autothink-ui-chat-export.md:7852` |
| Rule | `github-token` (`ghp_…`, length 40, single occurrence in the repo) |
| Fingerprint | `sha256_16 = ef33331652fdc1f8` (no value reproduced) |
| Context | The committed text itself describes this as a *"live GitHub Personal Access Token exposed on screen"* — i.e., the token was pasted into a chat export. File committed `2026-09-11` (commit `21aed4e`), **before** the 2026-09-20 `NO_LEAK_AUDIT.md` run whose `ghp-` pattern (dash, not underscore) evidently missed it. |
| Recommended (OWNER) | 1) If this is a real GitHub token: **revoke/rotate it now**. 2) Then decide: scrub the file (working tree) **and/or** handle history (the `NO_LEAK_AUDIT.md` F2 precedent: history rewrite = owner decision). 3) Agent does NOT modify the file or history without instruction. |

### 🟡 REVIEW — confirm placeholder vs real (agent cannot verify without reading values)
| Location | Rule | Metadata (no values) | Note |
|---|---|---|---|
| `docs/API_REFERENCE.md:25` | `authorization-header`, `bearer-token` | doc example: `curl -H "…"` against `http://localhost:8000/…`; value 23 chars, no placeholder markers | Old localhost API doc. Confirm placeholder; scrub if unsure. |
| `Northstar_backend/rate_limiter.py:84` | `credential-assignment` (`token`) | legacy middleware fallback; 15-char lowercase value | Confirm it is a static demo value; if real, migrate to env read. |
| `northstar.html:312` · `word-coffee-website/northstar.html:312` | `credential-assignment` (`PASSWORD`) | legacy static-console demo gate (`lockedView`); client-side value (visible to any visitor by design) | Retire the demo gate; check for password reuse; not a server-side secret. |

### ⚪ TEST-FIXTURE allowlist candidates (owner sign-off, then allowlist file)
| Location | Rule | Why benign |
|---|---|---|
| `Northstar_backend/agents/golden_goose_finder/tests/test_export_manifest.py:73` | `bearer-token` | Input for the repo's own `ExportLeakageError` detector test |
| `Northstar_backend/test_autothink_auth_boundary.py:73` | `bearer-token` | Auth-boundary test header value |
| `Northstar_backend/foundation/tests/test_auth_jwt.py:36` | `credential-assignment` | "forged secret" rejection test |
| `Northstar_backend/foundation/tests/test_authorization_postgres.py:194` | `credential-assignment` | "forged" ledger/secret test |

*(5 findings across these 4 files.)*

## 3. Precision policy (what the scanner skips, and why)

The scanner was tuned with tests for each skip class — verified false positives in this repo were cross-line matches, code references (``os.environ.get``, ``process.env``, ``e.target.value``, ``f"Bearer {k}"``), prose ("purchase authorization: …"), placeholders (`test-`/`fake`/`your_`/`<TOKEN>`/`invalid`/`local`), uppercase constants, kebab test ids, short quoted values, and Amazon `?dib=` URL blobs (the known NO_LEAK-AUDIT F2 third-party class). Token-shape rules (GitHub/AWS/sk-/JWT/PEM) remain **strict** — they are never placeholder-skipped (except standalone Bearer examples, which are skipped only in header/placeholder/code context).

## 4. Remaining Phase 1 items (not done yet)

1. **Allowlist mechanism** (`.secret_scan_allowlist.json`, rule+path+reason, shown in output, owner-visible) + tests — needed before the 5 test-fixture candidates can be signed off and before `--staged`/CI can pass cleanly.
2. **gitleaks install** — pinned binary download **pending owner approval** (download = new fetch; `.gitleaks.toml` and pre-commit/CI hooks are already staged for it).
3. **Config loader** (env-only secret reads; keychain later) + tests.
4. **Supply chain:** pin Python deps / lockfile choice (audit D4), `pip-audit`/`npm audit` wiring, SBOM generation.
5. **Threat model** `reports/threat_model.md` (STRIDE + OWASP LLM Top 10) — draft in progress.
6. **CI activation** — workflow exists; the repo has no CI host today (audit §11); activating = owner decision.

## 5. Compliance notes (this increment)

- Zero live network calls; zero paid calls; no Amazon; no UI/old-shell edits; no policy files touched; production caches/benchmarks untouched.
- No secret value was read out, printed, logged, or committed at any point — triage was done with masked/classifying tooling (temporary helpers kept outside the repo).
- The scanner deliberately leaves the escalation and REVIEW items *flagged* — a clean exit code today would be dishonest; the findings above are the truthful state.

---

## Addendum — 2026-10-11b (owner directives executed)

**Owner approvals executed:** gitleaks pinned+checksummed install; uv + committed lockfile; Windows-dev / Mac-or-ARM-Linux-prod platform split confirmed; fingerprint-exact allowlists (mandatory); continue to threat model. Lightpanda install remains a separate approval.

### 1. gitleaks 8.30.1 — installed, verified, first scans run
- Pin/checksums + install path: `docs/SECURITY_TOOLING.md` (zip `d29144de…`, checksums file `061476c2…`; triple-verified).
- **History scan** (`gitleaks git`, 594 commits / 176 MB / 10.3 s): **72 findings** — `generic-api-key` ×69, `github-pat` ×1, `stripe-access-token` ×1, `curl-auth-header` ×1. Top: `budget-ledger.jsonl` ×30 (all `idempotency_key` field values — deterministic run ids, benign), `faire_amazon_*.json` ×24 (catalog product tokens `p_…`/`b_…`, benign), chat exports ×5, fixtures ×5, `creative_pipeline.py` ×2 (history-only, file no longer exists), docs ×2, tests ×2.
- **Working-tree scan** noise clarified: `Northstar_backend/.env` (16 hits) and untracked run artifacts are **local-only** (never committed); CI/`git` scope is the correct gate.

### 2. 🔴 SECOND ESCALATION — rotate **SCAVIO_API_KEY** and **BRIGHTDATA_API_KEY** (if live)
- `FirstNorthstarautomationchat.md` (tracked; operator chat archive) contains real-format assignments in two duplicated blocks (lines 1142–1148 and 1290–1296): `SCAVIO_API_KEY=sk_…` (sha256_16 `ca2d8a22d6f0d252`) and `BRIGHTDATA_API_KEY=…` (sha256_16 `f7f62b13a37f5afd`).
- These are exactly the class the September NO_LEAK audit missed (its pattern used `ghp-`, and earlier redaction/tooling had gaps for underscore-joined names + `sk_` keys — both fixed, see §3).
- **NOT allowlisted** — the scanner reports them as ACTIVE until the owner rotates the keys and a scrub/archive decision is made (same policy as the `ghp_` item; owner confirmed revocation in progress for the GitHub PAT).
- Recommendation: treat this archive family (`FirstNorthstarautomationchat.md`, `autothink-ui-chat-export.md`) as a single review batch: rotate possibly-live keys → decide file scrub and/or history handling.

### 3. Scanner v4 — coverage & precision upgrades
- **Multi-prefix regression tests** added (owner-requested): `ghp_/gho_/ghu_/ghs_/ghr_` + fine-grained `github_pat_…`, in **both** the scanner and the redaction module (`tests/security`, 64 tests total, all green).
- New coverage: `sk_`-style keys; underscore-joined env names (`SCAVIO_API_KEY=…`); JSON-quoted keys (`"token": "…"`); GUIDs under key names; lockfile semver; fetch options (`credentials: 'include'`); status words; lowercase-word values; quoted prose. Raw tracked findings after review-grade precision: **239**, of which **8 ACTIVE** (2 chat-export key values + `ghp_` + one review item in `rate_limiter.py`).

### 4. Fingerprint-exact allowlist — shipped
- `.secret_scan_allowlist.json`: **169 unique fingerprints / 231 occurrences**, each entry rule + sha256(exact match) + reason + reference path. Buckets: Faire catalog tokens (research data), unit-test fixtures, legacy client-side demo gate (`northstar.html` ×2), API-doc examples, captured third-party fixtures.
- Matching is by **hash + rule only** — a changed value at the same location re-flags; malformed allowlist is ignored with a warning; `--no-allowlist` available for audits.

### 5. uv adopted — lockfile committed
- uv 0.13.0; `Northstar_backend/pyproject.toml` + **`Northstar_backend/uv.lock`** (34 packages, hashes) committed. `requirements.txt` retained for the legacy Docker path until that is switched in a follow-up.

### 6. Threat model
- `reports/threat_model.md` — STRIDE across gateway/browser pool, policy kernel, snapshot store, brain kernel, MCP surface, future tenants; OWASP LLM Top 10 mapping; residual risks; review asks. **Owner review requested.**

### 7. Remaining Phase 1 items
Allowlist maintenance process (owner sign-off per new entry), config loader, SBOM + `pip-audit`/`npm audit` wiring, CI activation, dependency-license review (AGPL: Lightpanda, run unmodified; HotClip if adopted), and the still-open review items above.

