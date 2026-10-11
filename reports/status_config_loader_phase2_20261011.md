# Status — Config Loader & Phase 2 Policy Kernel (pre-Phase-3 gate)

- **Date:** 2026-10-11 · **Owner:** T2 Holdings LLC
- **Requested:** before Phase 3, report the status of the config loader and the Phase 2 policy kernel; build them first if unbuilt. → **Both were already built and green; nothing outstanding. Status below, plus the new owner-directed conditions (baseline-growth guard, hardened workflow, worktree-per-session).**
- **Security scan state (standing line):** **0 new finding(s), 8 known-active (baseline), 231 allowlisted.** Known-active = 2 chat-archive key values (rotation done owner-side; scrub decision pending), the `ghp_` token (revocation in progress), and the `rate_limiter.py` review item — visible on every scan run by design.

## 1. Config loader — BUILT ✅

- **Module:** `northstar/security/env_config.py` (commit `66a912a`).
- **Contract:** secrets come from the process environment only — `get_secret` / `require_secret` / `secret_presence` / `redacted_summary`; never reads `.env`, never calls `load_dotenv` (guarded by an AST-based test); summaries are `NAME=SET|MISSING` only — never values. A Keychain backend is an explicit future plug-in slot (`BACKENDS`); env is the only backend today.
- **Tests:** 9 focused tests in `tests/security/test_env_config.py`.
- **Docs:** `docs/SECURITY_TOOLING.md` §4.

## 2. Phase 2 policy kernel — BUILT ✅

- **Module:** `northstar/policy/` (commit `56069fd`; delivery report `reports/phase2_policy_kernel_20261011.md`).
- **Coverage:** default-deny source allowlist; hardcoded Amazon block (unoverridable, subdomains/shorteners/lookalikes); SSRF with resolve-once-and-pin + rebinding defense + private/loopback/metadata/IPv6 blocking; robots fail-closed; per-domain rate limits + per-run request/byte/time budgets + response-size cap; capability grants (default none, TTL expiry, subdomain coverage); approval queue (no self-approval) + SIMULATED-never-snapshot guard; hash-chained tamper-evident audit with redaction.
- **Acceptance matrix:** every spec item covered with denied-AND-logged assertions (delivery report §2).
- **Tests:** 66 Phase-2 tests; full `tests/security` suite green (142 before this turn's guard, 146 after).
- **Determinism:** pure stdlib; injected resolver/clock; zero live calls (a test proves system DNS is never touched).

## 3. Conditions added this turn (owner directives) — DONE ✅

| Condition | What shipped |
|---|---|
| **Baseline can't grow** | `tests/security/test_baseline_guard.py` — frozen approval set of (rule, sha256) pairs; baseline may only SHRINK; any addition, duplicate, malformed entry, or count over the frozen set fails the suite. Approving a genuinely new escalation requires a reviewed commit that updates BOTH the baseline and the frozen set — deliberate and owner-visible. |
| **Workflow hardened** | `.github/workflows/security.yml`: every action pinned to a full commit SHA (resolved via the GitHub API on 2026-10-11; the pins live in the workflow file and are listed in `docs/SECURITY_TOOLING.md` §6), top-level `permissions: {}` with per-job least privilege, `persist-credentials: false`, per-job timeouts, run-concurrency cancel, uv pinned `==0.13.0` in CI. |
| **Worktree per session** | Branch `feature/secure-control-layer` (from `21b139d`); worktree at `C:\Users\T2Hol\Desktop\ns-worktrees\secure-control-layer`; this session moved there. The shared main checkout is left untouched for the parallel session (no more shared-index collisions). |

## 4. Lightpanda install approval — CONDITIONALITY (owner directive)

Per the owner: **the Lightpanda approval is conditional on Phase 2 being green, together with the conditions above.** Condition checklist as of this report:

- [x] Config loader built & green
- [x] Phase 2 policy kernel green (full acceptance matrix)
- [x] Baseline cannot grow (guard test shipped)
- [x] Workflow hardened (SHA-pinned actions, least privilege)
- [x] Worktree-per-session adopted

**All conditions are MET.** The Lightpanda binary download remains a **separate, explicit approval** — nothing will be fetched, installed, or run until the owner grants it in a future instruction.
