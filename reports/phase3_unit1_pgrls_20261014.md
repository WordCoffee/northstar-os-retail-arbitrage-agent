# Phase-3 Unit 1 — pgrls (RLS lint for Phase-7 tenant isolation) — 2026-10-14

- **Standing line:** 0 new / 0 known-active / 231 allowlisted. Owner-approved Phase-3 adoption (unit 1 of 7).
- **Adopted:** `pgrls` **0.56.0** — MIT (upstream pin `68a32ab42165…` verified in Phase-2; license text sha256 `3430c5c9e1ea644f…`).
- **Install:** `uv tool install "pgrls[ephemeral]==0.56.0" --python 3.12` (managed CPython 3.12; the system Python 3.14 lacks a prebuilt `pglast` wheel — build failed there, hence the managed interpreter). Executable: `%USERPROFILE%\.local\bin\pgrls.exe`. **No service, no ports, no startup entries.**
- **Dry-run vs our schema (the ask):** `pgrls lint --migrations <forward-only copy of `Northstar_backend/migrations_foundation`>` → spins a **throwaway Postgres via Docker**, applies **12 forward migrations** (rollback files excluded — they broke the build sequence by design), then lints:
  - **132 × SEC001 ("RLS not enabled on table") across 66 tables** — the expected baseline: our migrations contain **no RLS statements yet** (Phase-7 item). Findings echo actionable table inventory (`audit_events`, `approval_requests/decisions`, `billing_*`, `entitlement_overrides`, `invites`, `identity_*`, `job_*`, …).
  - Throwaway DB is torn down by pgrls; nothing left running; no real users/credentials/data loaded (schema-only).
- **CI wiring:** advisory job `rls-lint` added to `.github/workflows/security.yml` (SHA-pinned actions only; `continue-on-error: true`; explicitly marked baseline-until-Phase-7; forward-only copy step mirrors the local run).
- **Future Phase-7 notes:** pgrls also ships `coverage`, `matrix` (role×table×command), `diff`, `generate`, and an MCP server (`pgrls mcp`) — candidates when RLS lands; all enablement stays owner-gated.
- **Non-claims:** no RLS was written; no schema changes; lint findings are the pre-existing state (no fix attempted — that is the Phase-7 rollout).
