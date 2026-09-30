# Session A — Merge Prep Report (audit/local-readiness)

**Date:** 2026-09-30
**Branch:** `audit/local-readiness` (isolated worktree, documentation-only)
**Scope:** Local-readiness documentation + merge-packaging for `audit/local-readiness`.
**Session A** produced the three readiness docs and this merge-prep report. No
implementation, test, deployment, provider, state, or config file was touched.

---

## 1. Commits on this branch (this line of merge prep)

| Commit | Subject (short) |
|---|---|
| `526037b` | local runbook, service readiness matrix, service gaps + offline boot-check (Parallel Session A) |
| `2ddda8d` | add room/scheduler/beta probe + evidence for migration/seed, persistence, backup, deployment readiness (Session A) |
| `1b85b66` | readiness matrix doc pass — reclassify Creative Studio/SocialPulse to working-locally-with-limitations; add Admin/Beta-Ops tenant/backup-restore evidence (Session A) |
| **`<new>`** | consistency corrections + merge-prep report (Session A) |

The new commit is DOCUMENTATION-ONLY. Only the four files below changed.

## 2. Files changed (this final commit)

1. `docs/SERVICE_GAPS.md`
2. `docs/LOCAL_RUNBOOK.md`
3. `docs/SERVICE_READINESS_MATRIX.md`
4. `reports/sessionA_merge_prep_20260930.md`

No other file was staged or committed. No implementation/test/deployment/
provider/state/config file is included.

## 3. What the consistency corrections changed

- **Creative Studio / SocialPulse:** reclassified consistently as *Working locally
  with limitations* everywhere (not "concept shells"); browser-persisted local
  workflow records are cited; only generation, media/object storage, moderation,
  social OAuth/publishing, analytics, and assisted copy remain
  provider-required or unimplemented.
- **Golden Goose:** added acceptance evidence `16/0` (GG) and `32/0` (full
  acceptance suite) to the readiness-matrix row. Classified *Fully working
  locally now*.
- **Backup:** clarified that only **static** SQLite backup and a **git-only**
  rollback drill exist; **no automated hot-backup, retention, or scheduled
  restore verification**.
- **Backend pytest:** documented the **23 known pre-existing failures** confined
  to `test_proof_batch.py` / `test_proof_batch_run.py` because
  `data/scanner-search-cache.json` is missing. The fixture was intentionally
  **not** re-added or fabricated.
- **Hosted compose:** noted no explicit memory limits in `docker-compose*.yml`.

## 4. Evidence sources

- **Golden Goose:** local protocol round-trips; GG acceptance `16/0`; full
  acceptance suite `32/0` (evidence commit `6302f05` backing the harness).
- **Admin / Beta-Ops:** `verify-admin.cjs` UI **34/0**; backend
  admin/tenant/audit/migration/e2e **92/0**; backup/restore drill `test_backup_restore_drill.py`
  **2/0**; evidence commit `62a2fef` (see `docs/ADMIN_SOP_AND_INTEGRITY.md`).
- **Creative Studio / SocialPulse:** browser-persisted local workflow records on
  `feature/creative-social-local` (Creative Studio `05a4ea2`, SocialPulse `a5936ce`).
- **Durable queue:** `/api/v1/foundation/jobs` + `/jobs-durable/**` present;
  no media/render handlers (see `SERVICE_GAPS.md` §4).
- **Boot verification:** offline `TestClient`; `/openapi.json` route inventory;
  local SQLite `main:app` stack. Scheduler/worker are hosted-only (Docker).

## 5. Known limits / not claimed

- **Not claimed:** live external providers, Oracle deployment, hosted scheduling,
  generated media, external publishing, or verified analytics.
- **Backend pytest:** 23 known pre-existing failures in
  `test_proof_batch.py` / `test_proof_batch_run.py`
  (`FileNotFoundError: data/scanner-search-cache.json`). These two test files are
  clean/unmodified in git and are **not** regressions from this branch. The
  missing fixture was intentionally **not** added.
- Watch / RankLedger / RivalBoard / Stripe remain parked / provider-or-spec
  dependent. Keyword Tracker is **UI/shell only** pending wiring to the existing
  foundation keyword routes.
- Dependencies/Node are **not pinned**; `run-agent.bat` is **broken/unsupported**
  (calls nonexistent `npm run pipeline`).
- Hosted compose specifies **no memory limits**.
- **Backup:** static backup + git-only rollback drill exist; no automated
  hot-backup, retention, or scheduled restore verification.

## 6. Owner decisions required before production scale

| # | Decision | Context |
|---|---|---|
| D1 | **Media scope / provider / budget / org access** | Which provider for image/video generation; per-asset vs per-listing; cost ceiling; who in the org can generate/upload. Unblocks §1–§3 of SERVICE_GAPS.md. |
| D2 | **Storage provider** | Object store (S3/R2/Cloudinary/GCS) so media exports + reference-asset registry can be built (§7). |
| D3 | **Moderation / reviewer workflow** | Safety policy, prompt/ad allowlist, image-safety filter, human-review flow (§8). |
| D4 | **Dependency pinning / `.nvmrc`** | Pin `requirements.txt` (both) + Node toolchain for reproducible builds. |
| D5 | **Automated backups** | Hot-backup, retention policy, scheduled restore verification. |
| D6 | **`run-agent.bat` disposition** | Fix the broken `npm run pipeline` call or remove/unsupport the file. |
| D7 | **Keyword Tracker wiring** | Wire the UI/shell to the existing foundation keyword routes (`/api/v1/foundation/keywords/*`). |

## 7. Merge guidance

- Merge `audit/local-readiness` **only after a final integration review of the
  full branch history** (`526037b` → `2ddda8d` → `1b85b66` → `<new>`).
- **Do not force-push, rebase, or rewrite history.**
- The branch is documentation-only; verify no merge conflicts with the readiness
  docs before merging.

---

## REPORT FORMAT
Branch: audit/local-readiness
Commit: <new> (documentation-only merge-prep commit)
Files: docs/SERVICE_GAPS.md, docs/LOCAL_RUNBOOK.md, docs/SERVICE_READINESS_MATRIX.md, reports/sessionA_merge_prep_20260930.md
Checks: git diff --check (whitespace) + isolated doc diff review — PASS
Readiness: Golden Goose fully working locally (16/0, acceptance 32/0); Admin/Beta-Ops fully working locally (UI 34/0, backend 92/0, drill 2/0, 62a2fef); Creative Studio & SocialPulse working locally with limitations; Keyword Tracker UI/shell only; Watch/RankLedger/RivalBoard/Stripe parked.
Known limits: 23 pre-existing backend pytest failures (test_proof_batch.py / test_proof_batch_run.py — missing data/scanner-search-cache.json, fixture not re-added); deps/Node not pinned; run-agent.bat broken; hosted compose no memory limits; no automated hot-backup/retention/scheduled restore.
Owner decisions: media scope/provider/budget/org access; storage provider; moderation/reviewer workflow; dependency pinning/.nvmrc; automated backups; run-agent.bat disposition; Keyword Tracker wiring.
Merge next step: merge audit/local-readiness only after final integration branch-history review; no force-push or rebase.