# Phase-3 adoptions — consolidated report (owner-approved, 2026-10-14)

- **Owner approval:** "install everything i selected" — Phase-3 units 1–7, executed per the standing constraints (all new services STOPPED; loopback-only; no startup entries; no app-flow wiring; no real users/credentials/data; ZAP targets local loopback only; Kratos/OpenMeter/OpenFGA = install + skeletons + docs note; enabling any of them is a separate owner approval).
- **Gates at close:** `tests/security` **240/240** · secret scan **0 new / 0 known-active / 231 allowlisted** · tree clean · one commit per unit.

## Summary

| # | Unit | Adopted | Pinned | State | Commit |
|---|---|---|---|---|---|
| 1 | pgrls | 0.56.0 (MIT verified) | uv tool (py3.12) | CLI only; no service | `a65decb` |
| 2 | grype + osv-scanner | v0.120.1 / v2.7.0 (Apache-2.0) | dual-source checksum-verified binaries | CLIs only; no service | `6e48482` |
| 3 | OWASP ZAP | zap-stable | image pulled by digest, **never started** | stopped; draft DAST script (uncommitted) | `db4c48c` |
| 4 | protego | 0.7.0 (BSD-3-Clause) | pip; wired into `RobotsGate` (gateway) | library in use | `feddcab` |
| 5 | dedupe + splink | splink 5.0.0 (MIT) | spike venv/system py | spike only, no prod wiring | `572aed5` |
| 6 | OpenMeter | image by digest | `ghcr.io/openmeterio/openmeter@sha256:875c8ab8…` | **installed, stopped** | `368d49d` |
| 7 | Kratos + OpenFGA | images by digest | `oryd/kratos@sha256:2a13bb8d…` · `openfga/openfga@sha256:9cf9a20a…` | **installed, stopped** | `db517bb` |

Per-unit full reports: `reports/phase3_unit1_pgrls_20261014.md` … `reports/phase3_unit7_kratos_openfga_20261014.md`.

## Unit recaps (evidence-first)

1. **pgrls** — dry-run vs our schema in a **throwaway Postgres** (12 forward migrations applied; rollbacks excluded by design): **132 × SEC001 across 66 tables** = the expected baseline (no RLS yet; Phase-7 item). Advisory CI job `rls-lint` added (SHA-pinned actions; baseline-commented). pgrls also ships `coverage/matrix/diff/generate` + an MCP server for the RLS rollout.
2. **grype + osv-scanner** — local runs: grype DB updated; `northstar/` clean; repo-wide scans surfaced **real npm advisories** in legacy/UI lockfiles (axios, braces, qs, uuid, react-router, proxy-addr [Critical], sprintf-js; 30 unique advisories via osv across 6 lockfiles incl. `uv.lock` — the latter noted as a pip-audit/osv record-filtering nuance, flagged for triage). Advisory CI jobs `osv-scan` + `grype-scan` added (checksum-chain pinned).
3. **ZAP** — image pinned+pulled by digest, **no container ever created** (verified: only `northstar-lightpanda` running). Loopback-only draft script at `%TEMP%\opencode\zap_baseline_draft.ps1` (full text in the unit report), **not committed to `scripts/` pending review**; scan **pending** the local stack running.
4. **protego** — now the preferred robots parser in `RobotsGate` (urllib fallback; fail-closed preserved; `parser_kind()` added). Pinned to **google/robotstxt @ 22b355ff** fixture suite: 17/28 agreements asserted, **11 Google-only divergences documented** (upstream's "GoogleOnly_SystemTest"), 1 intentional difference (empty robots → fail closed). Suite grew to 240/240.
5. **Spike** — synthetic 50-pair set (FAKE-TEST markers; seed 20261014; no real data — production data lives outside this workstream). **splink: P=1.00 / R=0.96 / F1=0.98** (1 miss = worst typo perturbation; tuning path noted). **dedupe: install-blocked** (C-extension build failures across py3.11/3.12/3.14) — source-evaluated only. No prod wiring.
6. **OpenMeter** — installed by digest, stopped; meters skeleton (`task_requests`, `llm_tokens`, `fetch_requests`, `snapshot_bytes`) mapped to the audit/snapshot model; aggregation layer only — kernel grants + ledger remain authoritative.
7. **Kratos + OpenFGA** — installed by digest, stopped; skeletons: invite-only Kratos config (MFA TOTP + passkeys; registration off; no values in file) and default-deny OpenFGA model (`user/tenant/api_key/task`); duality note (kernel grants = agent runtime; OpenFGA = customer authz). Aggregated doc: `docs/PHASE3_SERVICES.md`.

## Constraint compliance (as executed)
- **No running services added**: `docker ps` unchanged throughout (only `northstar-lightpanda`); no ports opened beyond loopback by anything adopted; no startup entries added; no app-request-flow wiring; no users/credentials/data loaded anywhere.
- **Loopback-only**: ZAP draft enforces a target allowlist (127.0.0.1/localhost/host.docker.internal); service skeletons bind 127.0.0.1 when/if enabled.
- **Pins + license records**: every adopted upstream pinned (SHAs in the unit reports); licenses verified in the Phase-2 deep-read (Apache-2.0 ×8, MIT ×3, BSD-3 ×1 — full texts hashed there).
- **Scanner gate**: every commit ran the fingerprint-exact scan (0 new throughout).

## Open items (owner decisions)
- **Enablement approvals** (separate, per directive): OpenMeter / Kratos / OpenFGA stay stopped until you say otherwise.
- **ZAP baseline scan**: run when the local stack is up; then review → decide whether the draft script graduates into `scripts/`.
- **dedupe**: re-evaluate on Linux CI (build toolchain) if desired; splink is the working path.
- **npm advisories** (grype/osv findings): triage decisions for the legacy dirs + UI lockfiles (other domains); `northstar/` itself is clean.
- **Phase-7 RLS rollout**: the pgrls baseline (132 findings over 66 tables) is the ready-made worklist.
- **pip-audit vs osv `anyio`/`idna` nuance**: flagged for triage.

## Non-claims
- No fixes were applied to any finding; no service was started; no scan of a live stack happened (ZAP pending); the spike used synthetic data only.
