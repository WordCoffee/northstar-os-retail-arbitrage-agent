# Phase-3 Unit 7 — Ory Kratos + OpenFGA (invite-auth + capability grants) — 2026-10-14

- **Standing line:** 0 new / 0 known-active / 231 allowlisted. Owner-approved Phase-3 adoption (unit 7 of 7).
- **Adopted:** Ory Kratos (**Apache-2.0**; upstream pin `b86338da04a0…`) and OpenFGA (**Apache-2.0**; upstream pin `526995eb2024…`).
- **Installs (stay STOPPED):**
  - Kratos: pinned + pulled by digest — `oryd/kratos@sha256:2a13bb8d362c7a7ae33bd7c0f5168aee46921f15c916a06346db91c06dc76643`. Registry note: the Docker Hub name is **`oryd/kratos`** (`ory/kratos` does not exist; GHCR requires auth).
  - OpenFGA: pinned + pulled by digest — `openfga/openfga@sha256:9cf9a20af32a40434cd3a788c429879439ee9ea9abf65c9c200ee17cd43f769e`.
  - **No containers created; no ports; no startup entries.**
- **Skeletons + design notes (NO DEPLOY, per directive):**
  - `config/skeletons/kratos/kratos.skeleton.yml` — invite-only identity: headless (public/admin on 127.0.0.1 when enabled), **MFA (TOTP) + passkeys (WebAuthn) on**, registration **disabled** (invite wiring is enable-time work), no values in the file (secrets via env names only at enable-time). Customer **API keys remain ours** (hashed at rest, shown once) — Kratos is identity, not key issuance.
  - `config/skeletons/openfga/model.skeleton.fga` — `user / tenant / api_key / task` model; **default-deny by construction** (no tuple → no access). Duality note: kernel capability grants stay the runtime enforcement for agent tasks; OpenFGA models customer-facing authorization for the hosted product.
- **Enablement:** separate owner approval per service; loopback-only; no app-flow wiring yet (UI session owns the screens). Aggregated in `docs/PHASE3_SERVICES.md`.
- **Non-claims:** nothing deployed, nothing enabled, no users/credentials/data loaded; skeletons are inert files referenced by nothing.
