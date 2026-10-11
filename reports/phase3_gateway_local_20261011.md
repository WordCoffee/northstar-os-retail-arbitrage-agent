# Phase 3 — Lightpanda Connect Gateway (Local Fixtures) + Owner Directive Compliance

- **Date:** 2026-10-11 · **Owner:** T2 Holdings LLC
- **Security scan state (standing line):** **0 new / 0 known-active (baseline — now EMPTY) / 231 allowlisted.** The scan is genuinely clean; the baseline holds nothing.
- **Tests:** `tests/security` **172/172** (incl. 2 integration tests against the real pinned container — ran, not skipped); `test_rate_limit_plan_resolution.py` 6/6.
- **Stop point honored:** no live compatibility run yet — **the approved-sources slot in the directive was blank.** Nothing beyond local fixtures was fetched. Send 3–5 source names (from the 12 proposed) to start the compatibility run.

## 1. Directive compliance

### 1. ROTATION RECORD — recorded, findings REMEDIATED
Recorded in `reports/security_findings_20261011.md`: rotated + old keys revoked (owner): **GitHub PAT, SCAVIO_API_KEY, BRIGHTDATA_API_KEY**. Working-tree scrub already landed (`546a236`). History still contains the old, now-dead values → **history-rewrite decision remains OPEN**. Agent cannot independently verify account-side rotation (owner-confirmed record).

### 2. SECRETS FILE — path-variable only, never touched
The designated file was **never opened, read, printed, copied, logged, diffed, or committed** by the agent (existence checked only via `git check-ignore`). The loader points at it exclusively through **`NORTHSTAR_ENV_FILE`** — no hardcoded path anywhere in code, tests, docs, or reports. `require_env_file()` **fails closed** (unset/missing) with messages containing the variable NAME only; presence checks are boolean (`NAME=SET|MISSING`); process env wins over the file. 7 new tests.

### 3. HYGIENE CHECKS
| Check | Evidence |
|---|---|
| a. `.gitignore` + scanner/pre-commit | worktree & main repo: `.gitignore:2:.env → .env`; backend: `Northstar_backend/.gitignore:1:.env`. Tracked/staged scans can never see an ignored `.env` (it cannot be tracked). **Filesystem walks now skip `.env`, `.env.*`, `*.env` entirely** (new test) — the scanner never *reads* local secret material either. |
| b. OpenCode deny rules | **30 rules added** (read+edit deny: `.env`, `.env.*` with explicit `.env.example` re-allow, `*.pem/.key/.p12/.pfx/.jks/.keystore`, keychain, `id_rsa`/`id_ed25519`, `*.ssh/*`, `~/.ssh/*`, credential files) — applied and JSONC-validated on **both** the worktree config (committed) and the main checkout config (**left uncommitted there** — that tree belongs to the parallel session; surfaced for their commit). |
| c. Loader error tests | unset variable → `EnvFileNotConfiguredError`; missing file → `EnvFileMissingError`; messages carry the variable name only; values never appear — asserted. |
| d. Cloud-sync note | documented in `docs/SECURITY_TOOLING.md` §4 (owner reviews; if moved, only `NORTHSTAR_ENV_FILE` updates). |

### 4. RATE_LIMITER — closed as a SCANNER FALSE POSITIVE
Line 84 is **`token = auth_header[7:]`** — index/slice *code*; there was never a literal or fallback, and the fail-closed `except → "foundation"` path is intact. The flag came from a scanner gap: unquoted `[`/`]` were not recognized as code. Fixed (unquoted brackets = code; **quoted** bracket values like `"Pa[s]w0rd"` still flag) + 2 tests. **The file was NOT modified.** 6 new regression tests pin the plan-resolution behavior. Baseline **cleared to empty**; frozen guard set cleared (growth still blocked; any future entry requires review).

### 5. PHASE 3 GATEWAY — BUILT (`northstar/gateway/`)
- **The only tool surface:** `fetch_page` (title + bounded content), `extract` (matching paragraphs), `markdown_dump` (full sanitized markdown).
- **Pipeline per call, exactly as specified:** policy check → isolated fetch (fresh `lightpanda fetch` process in the pinned 1.0.0 container — new context, no shared cookies, `--obey-robots`) → sanitize (scripts/styles/comments/noscript stripped; caps; truncation reported) → snapshot record (`snapshot_id`, `content_hash`, freshness `OBSERVED`, `data_class live_verified`, parser/gateway versions, `limitations`) → hash-chained audit (allow + error entries) → **untrusted-data envelope** (banner: data only, never instructions).
- **Policy-first proven:** denials (`domain_not_allowed`, `amazon_blocked`, `capability_missing`) occur BEFORE any fetch — the driver call log stays empty (tested).
- **Injection fixture:** hostile text survives only inside the envelope; scripts stripped; **exactly one fetch**; audit verified — both unit and REAL-container end-to-end.
- **Integration (local-only):** fixture pages served on host loopback, fetched through the pinned container by the gateway — ran (not skipped).

## 2. Explicitly NOT verified
- Owner-side rotations (no account access; owner-confirmed record only).
- The designated env file's contents (never read, by design — only NAMES-level checks exist).
- Live compatibility behavior on real sources (no approved list received yet).
- The main-checkout `opencode.jsonc` deny rules are modified-but-uncommitted in that tree (parallel session's commit).

## 3. Next
1. Send **3–5 approved sources** → run the first compatibility pass (local-first run already green; live fetches under the policy kernel, request caps, audit).
2. History-rewrite decision (owner).
3. Phase 4 snapshot store persistence (gateway already emits Phase-4-shaped records).
