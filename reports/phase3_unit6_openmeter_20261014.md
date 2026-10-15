# Phase-3 Unit 6 — OpenMeter (metering design) — 2026-10-14

- **Standing line:** 0 new / 0 known-active / 231 allowlisted. Owner-approved Phase-3 adoption (unit 6 of 7).
- **Adopted:** OpenMeter — **Apache-2.0** (Phase-2 verified; upstream pin `35dc8cb55d45…`).
- **Install (stays STOPPED):** image pinned + pulled by digest — `ghcr.io/openmeterio/openmeter@sha256:875c8ab832e80b9367f22d19eec6724248aa7ef7d108b5fec260161d9540eb45`. **No container created; no ports; no startup entries.** Registry note: the image lives on GHCR; `openmeterio/openmeter` does not exist on Docker Hub.
- **Skeleton + design note (NO DEPLOY, per directive):** `config/skeletons/openmeter/config.skeleton.yaml` — meters for `task_requests`, `llm_tokens`, `fetch_requests`, `snapshot_bytes`, with the mapping note: usage events mirror our per-task audit records (subject = tenant_id; grouping = task_id); the snapshot store already carries tenant linkage and the audit chain already records every task operation. OpenMeter is an aggregation layer only — **kernel grants + the billing ledger remain authoritative**.
- **Enablement:** requires a separate owner approval; loopback-only; secrets via env names at enable-time; nothing wired into the app request flow. Aggregated in `docs/PHASE3_SERVICES.md`.
- **Non-claims:** nothing deployed, nothing enabled, no data loaded, no ports.
