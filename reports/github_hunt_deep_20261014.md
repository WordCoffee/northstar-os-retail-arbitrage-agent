# GitHub HUNT — Phase 2 deep-read of the 10-repo shortlist (2026-10-14)

- **Standing line:** 0 new / 0 known-active / 231 allowlisted. **Nothing installed; nothing vendored; read-only fetches at pinned SHAs.**
- **Method:** for each repo — LICENSE text fetched at the pinned SHA, sha256 computed, markers verified against the API SPDX claim; README fetched + keyword-scanned (contributor license agreement / CLA / telemetry / analytics / opt-out / trademark / posthog / sentry); root structure via API contents.
- **Evidence JSON:** `reports/github_hunt_deep_evidence_20261014.json` (full license hashes, keyword counts, README heads, structures).
- **Owner sign-off required on this file before any Phase-3 adoption.**

## Summary

| Repo | Pinned SHA | License (file) | License sha256 (16-hex) | Markers verbatim | Keywords found | GO / NO-GO |
|---|---|---|---|---|---|---|
| `scrapy/protego` | `53d6df88ea74…` | BSD-3-Clause (`LICENSE`) | `07f276b2c407d709` | PASS | none | **GO** |
| `dedupeio/dedupe` | `3f61e7910291…` | MIT (`LICENSE`) | `b56e9035c9831249` | PASS | none | **GO (spike-only; stale note)** |
| `moj-analytical-services/splink` | `12aee3fd1fac…` | MIT (`LICENSE`) | `b985d2c0fca6ff33` | PASS | none | **GO** |
| `pgrls/pgrls` | `68a32ab42165…` | MIT (`LICENSE`) | `3430c5c9e1ea644f` | PASS (MIT text, © 2026 Dmitry Maranik) | none | **GO** |
| `openmeterio/openmeter` | `35dc8cb55d45…` | Apache-2.0 (`LICENSE`) | `cfc7749b96f63bd3` | PASS | trademark ×3 (license §6 text) | **GO (design note)** |
| `ory/kratos` | `b86338da04a0…` | Apache-2.0 (`LICENSE`) | `c71d239df91726fc` | PASS | trademark ×3 (license §6 text) | **GO (design note)** |
| `openfga/openfga` | `526995eb2024…` | Apache-2.0 (`LICENSE`) | `1c46d7b2bed94d45` | PASS | trademark ×3 (license §6 text) | **GO (design note)** |
| `anchore/grype` | `3e20d69159df…` | Apache-2.0 (`LICENSE`) | `c71d239df91726fc` | PASS | trademark ×3 (license §6 text) | **GO (advisory CI)** |
| `google/osv-scanner` | `f45535354688…` | Apache-2.0 (`LICENSE`) | `cfc7749b96f63bd3` | PASS | trademark ×3 (license §6 text) | **GO (advisory CI)** |
| `zaproxy/zaproxy` | `38ffe34a1b03…` | Apache-2.0 (`LICENSE`) | `b40930bbcf80744c` | PASS | trademark ×3 (license §6 text) + Checkmarx branding in README | **GO (baseline script)** |

**Cross-cutting notes**
- **No CLA, telemetry, analytics, opt-out, posthog, or sentry strings found in any LICENSE/README of the ten.** The only `trademark` hits are the Apache-2.0 §6 text itself; ZAP additionally displays "ZAP by Checkmarx" branding/attribution (name use only — do not imply endorsement in our docs).
- License hashes: identical texts across some Apache repos (e.g., openmeter==osv-scanner, kratos==grype) = the standard Apache-2.0 body; others differ only by appended copyright attribution. All contain the canonical markers.
- **Capture gaps (ambiguous, recorded):** root structure listing fetched for 7/10; `grype`, `osv-scanner`, `zaproxy` contents calls + landmark retries failed late in the session (API/raw hiccups) — **capture at intake**. SHAs, LICENSE, README all captured for the full 10.

## Per-repo adoption notes (what Phase 3 would do per directive)

1. **pgrls — GO.** RLS static-analysis/test tooling for Phase-7 tenant isolation. Phase 3-1: pytest plugin + CI lint rules, dry-run against our schema. MIT verified (verbatim). Note: repo ships pre-commit hooks + an AGENTS.md (agent-aligned).
2. **grype — GO.** Image/FS vulnerability scanning; advisory CI alongside trivy/pip-audit. Apache-2.0 verified.
3. **osv-scanner — GO.** Dependency/SBOM vulnerability scanning (OSV database); advisory CI step. Apache-2.0 verified.
4. **zaproxy — GO.** Baseline DAST against the local stack; script NOT committed until reviewed. Apache-2.0 verified; Checkmarx branding noted.
5. **protego — GO.** robots.txt parser for the gateway (unit-tested against `google/robotstxt` fixtures per directive). BSD-3-Clause verified; no keywords.
6. **dedupe — GO (spike only).** 50-pair ASIN/UPC matching spike, no prod wiring. MIT verified; **staleness flag stands (last push 2025-07-28)** — splink is the maintained alternative for any later production interest.
7. **splink — GO (spike with dedupe).** Same 50-pair spike; leading production candidate if the spike succeeds. MIT verified.
8. **openmeter — GO (design note only).** Per-tenant+task metering mapping to the snapshot/audit model; no deploy. Apache-2.0 verified.
9. **kratos — GO (design note only).** Invite-only auth + MFA/passkeys design mapping; no deploy (UI session owns screens). Apache-2.0 verified.
10. **openfga — GO (design note only).** Capability-grant / default-deny authorization mapping; no deploy. Apache-2.0 verified.

## Constraints carried into Phase 3 (per directive)
- One commit per adoption; pin exact SHA; record license path + text hash (this file + evidence JSON); run the secret scanner over anything written into the repo; keep tests green; advisory-first for CI; DAST script uncommitted until reviewed.
- Forbidden: executing downloaded code, installing non-adopted repos, pushing, live provider calls, touching the parallel session's tree. Stop-and-ask triggers unchanged.
- **STOP — awaiting owner sign-off on this file before Phase 3.**
