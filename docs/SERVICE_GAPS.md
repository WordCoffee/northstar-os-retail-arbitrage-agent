# Northstar OS — Service Gaps (production-scale operation)

**Branch:** `audit/local-readiness` (Parallel Session A)
**Purpose:** Identify exact gaps preventing production-scale operation.
**Gap-type taxonomy used throughout:**
- **MISSING CODE** — no implementation exists.
- **MISSING PROVIDER INTEGRATION** — code expects an external provider that is not wired/created locally.
- **MISSING SERVICE SPECIFICATION** — no written spec/contract for the behavior.
- **OWNER DECISION** — blocked on an explicit operator/owner choice.

---

## 1. General image generation

- **Missing service specification:** Yes — `data_rights.py` marks
  `image_generation = "planned"`; no product spec defines prompt schema, output
  format, size/aspect policies, or acceptance test.
- **Missing provider integration:** Yes — no Replicate / fal / OpenRouter
  image client found. `foundation/model_router.py` only detects *presence* of
  openrouter/fal/replicate env keys; it never calls a generation endpoint.
- **Missing code:** A thin generation-job handler could be authored, but there
  is no backend route/worker today.
- **Owner decision:** Which provider(s), cost ceiling, and whether generation
  is per-listing, per-asset-library, or both.

## 2. Reference-image / asset generation

- **Missing service specification:** Yes — Creative Studio is a working **local**
  workspace (`feature/creative-social-local`), not a concept shell; it persists
  browser-side briefs/requests/assets/variants/bundles (`ns-creative-*`), but has
  no product spec for a reference-image asset model or generation output.
- **Missing provider integration:** Yes — no image upload/storage/processing path.
- **Missing code:** No upload endpoint; no asset registry; no reference-vs-live
  diff logic.
- **Owner decision:** Where reference assets live (media storage, §7) and who
  can upload (org scope).

## 3. Short video / clip generation

- **Missing code:** Not implemented at all. No module, no route, no spec.
- **Missing service specification:** Yes — no spec for clip length, source,
  templating, or platform sizing.
- **Missing provider integration:** Yes — no video provider client.
- **Owner decision:** In/out of current scope; if in, provider + budget model.

## 4. Render / job queues

- **Partly present — durable queue infrastructure EXISTS** (verified on
  `/openapi.json`):
  - `/api/v1/foundation/jobs` and `/api/v1/foundation/jobs-durable/**`
    (`job_id`, `retry`, `cancel`, `audit`, `runs/{run_id}`, `handler-registry`,
    `queue-posture`) — `foundation/jobs_durable.py`, `jobs_handlers.py`,
    `worker`, `scheduler`.
- **What is missing:** There are **no media/render-specific job handlers** — the
  queue is generic. No handler for image/video generation, no output
  collation, no render progress/provisioning. A Docker `worker` + `scheduler`
  exist for the hosted stack only.
- **Gap type:** Missing code (handlers) + missing provider integration
  (worker invoking generation).

## 5. Exports / downloads

- **Present (CSV only):** `opportunity_export.py` (local CSV); foundation
  `admin/dashboard/export` route exists (verified).
- **Missing:** No media/asset exports, no packaged download (e.g. ZIP of
  generated assets), no signed/storage-backed download for hosted media.
- **Gap type:** Missing code; owner decision on export formats/scope.

## 6. Provider / model routing and cost limits

- **Present:** `foundation/model_router.py`, a **provider registry**
  (`/api/v1/foundation/providers`, `providers/{provider_key}`), a **credit
  ledger** (`credit_ledger`), and `plan-usage` routes. Billing/checkout and
  webhook routes exist (Stripe) but are **parked post-launch**.
- **Gap:** Routing and cost limits apply to **model selection**, not to the
  missing image/video generation providers (§1–§3). No budget ceiling exists
  for a media job because no media job exists.
- **Gap type:** Missing provider integration; owner decision on per-job
  cost budgets for media generation.

## 7. Media storage

- **Current:** Local filesystem only — `data/`, `generated_images/` (branding
  logos), no S3 / R2 / Cloudinary / GCS client found.
- **Gap:** No object-storage abstraction; no upload signing; no CDN. Blocks
  hosted media exports (§5) and reference-asset registry (§2).
- **Gap type:** Missing code + owner decision (which object store).

## 8. Moderation / safety

- **Missing code:** No moderation module. Only `test_moderate_drift` appears in
  the benchmark harness — no real moderation path.
- **Missing service specification:** Yes — no safety policy, prompt/ad
  allowlist, image-safety filter, or human-review workflow defined.
- **Gap type:** Missing code + missing service specification + owner decision
  (moderation policy + reviewer workflow).
- **Related parked item:** `keyword contracts/routes` (foundation keyword routes
  exist) — listed here only as scope context; **not touched by this session.**

---

## Non-feature gaps that block smooth production operation

| Gap | Detail | Type |
|---|---|---|
| Unpinned Python deps | `requirements.txt` (both) list no versions | Owner decision to pin |
| Unpinned Node toolchain | No `.nvmrc` (only `engines >=16` + Docker `node:20-alpine`) | Owner decision |
| Foundation migrations refuse on drift | sha256 ledger blocks `migrate` on drifted DB | Process (not a code bug) |
| Demo/seed auto-load unresolved | `010_demo_dataset.sql` — auto vs opt-in **not verified** | Owner decision |
| `run-agent.bat` broken | calls nonexistent `npm run pipeline` | Missing code (fix or delete) |
| Watch/RankLedger/RivalBoard | parked, need SP-API | Missing provider integration |
| Stripe + Postgres | parked before first PAID cohort | Owner decision / sequencing |
| n8n/webhook/email | Docker-only, not in local SQLite stack | Scope decision |
| **Automated DB backup** | Only manual SQLite copy (`backups/northstar.db.bak`); static backup + git-only rollback drill exist; **no automated hot-backup, retention, or scheduled restore verification** | Owner decision / missing code |
| **Hosted compose memory limits** | `docker-compose*.yml` specify no explicit memory limits for services | Owner decision |
| **Backend pytest fixture failure** | Full `pytest` shows **23 known pre-existing failures** confined to `test_proof_batch.py` / `test_proof_batch_run.py` because `data/scanner-search-cache.json` is missing (fixture intentionally **not** re-added) | Known pre-existing test gap |

---

## Where to go next (priority order)
1. **Owner decisions first** (cheapest, unblocks everything): product spec for
   image/video generation, media provider + object store choice, moderation
   policy, pin deps/Node, resolve `010_demo_dataset.sql`, fix/delete
   `run-agent.bat`.
2. **Foundational code, no provider needed:** media storage abstraction (§7),
   moderation policy + allowlist enforcement (§8), media export/download (§5),
   media job handlers over the existing durable queue (§4).
3. **Provider integration (requires §1 decisions + credentials):** image gen,
   reference-asset pipeline, short-video gen, and their per-job cost budgets.
4. **Hosting handoff** (see LOCAL_RUNBOOK §9 Oracle checklist) once media paths
   are not Oracle-blocked.