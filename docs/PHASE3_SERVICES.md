# Phase-3 services — install state + enablement rules (2026-10-14)

Three service images were installed for future commercial-readiness work, per owner directive:
**installed + config skeletons + docs note only — nothing enabled; enabling any of them requires a separate owner approval.**

| Service | Purpose | Image (pinned by digest) | State |
|---|---|---|---|
| OpenMeter | per-tenant + per-task metering | `ghcr.io/openmeterio/openmeter@sha256:875c8ab832e80b9367f22d19eec6724248aa7ef7d108b5fec260161d9540eb45` | installed; **no container, no ports** |
| Ory Kratos | invite-only auth + MFA/passkeys | `oryd/kratos@sha256:2a13bb8d362c7a7ae33bd7c0f5168aee46921f15c916a06346db91c06dc76643` | installed; **no container, no ports** |
| OpenFGA | fine-grained authorization (default-deny) | `openfga/openfga@sha256:9cf9a20af32a40434cd3a788c429879439ee9ea9abf65c9c200ee17cd43f769e` | installed; **no container, no ports** |

## Skeletons (not wired to anything)
- `config/skeletons/openmeter/config.skeleton.yaml` — meter definitions mapped to the audit/snapshot model.
- `config/skeletons/kratos/kratos.skeleton.yml` — headless identity (loopback bindings; MFA + passkeys on; registration disabled — invite wiring is enable-time work; no values in the file).
- `config/skeletons/openfga/model.skeleton.fga` — tenant/user/api_key/task model; default-deny by construction.

## Enablement rules (standing until the owner says otherwise)
- Separate owner approval per service before any container is created.
- Loopback-only (`127.0.0.1`) bindings; no ports beyond loopback.
- No credentials in the repo: secrets arrive at enable-time via environment names only (never committed, never echoed).
- No wiring into the app request flow until the UI/commercial track defines it.
- Run images by digest (no tag drift); nothing added to startup entries.
- Registry notes: Kratos is pulled from Docker Hub as `oryd/kratos` (the `ory/kratos` name does not exist); OpenMeter from GHCR (`ghcr.io/openmeterio/openmeter`).
