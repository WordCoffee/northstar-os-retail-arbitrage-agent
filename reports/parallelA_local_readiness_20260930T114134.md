# Parallel Session A — Local Operation Readiness + Runbook

**Date:** 2026-09-30
**Branch:** `audit/local-readiness`
**Mode:** Audit / runbook / verification. Offline-only — no Oracle, no external
calls, no spending, no browser sign-in, no secret reading.

---

## Deliverables produced
1. `docs/LOCAL_RUNBOOK.md` — prerequisites, exact start/build commands (clean checkout),
   env var names only, DB migration/seed behavior, persistence/restart, room validation,
   backup/restore, known limitations (non-working integrations), Oracle handoff checklist.
2. `docs/SERVICE_READINESS_MATRIX.md` — per-room readiness classification
   (Command Center, Product Finder, Golden Goose, Creative Studio, SocialPulse,
   Guardian, Keyword Tracker, Monitoring, Admin/Beta-Ops, + internal rooms).
3. `docs/SERVICE_GAPS.md` — exact production gaps (image gen, reference assets,
   short video, render/job queues, exports, provider/model routing & cost,
   media storage, moderation) classified by gap type.
4. `Northstar_backend/_audit_bootcheck.py` — safe, offline boot-verification helper
   (TestClient; no server bind, no network).

---

## Tests / verification run (evidence)
| Check | Command | Result |
|---|---|---|
| Backend boot (offline) | `venv-phase1c02\Scripts\python _audit_bootcheck.py` | `/health` **200**; `/` **307**→`/ui`; `/openapi.json` **200**, **185** routes |
| Router mount | same | foundation `/api/v1/foundation/**` ✓ · golden-goose `/api/golden-goose/**` ✓ · monitoring `/api/monitoring/**` ✓ |
| Auth posture | same | unauth foundation read → **401** (fail-closed, correct) |
| UI production build | `npm --cwd northstar-os-ui run build` | **0 errors**, 88 modules, 464 KB bundle (~902 ms) |
| Env identity | `python --version` / `node --version` | Python 3.14.5; Node v24.15.0; venv `venv-phase1c02` deps OK |

> No live/external action was executed. All backend verification used FastAPI
> `TestClient` against in-process app with no server bind and no network.

---

## Readiness findings (summary)
- **Fully working locally now:** Golden Goose (persisted, org-scoped queue/review/decisions),
  Admin/Beta-Ops (platform_admin-gated, fail-closed).
- **Working locally with limitations:** Product Finder (cache-backed; live scan
  needs paid provider), Monitoring (error-telemetry route exists), AutothinK
  (needs Ollama), internal System pages.
- **UI/shell only (sample data, explicit `tone="sample"` banners):** Command Center,
  Creative Studio, SocialPulse, Guardian, Keyword Tracker.
- **Biggest production gaps:** image generation, video/clip generation, media
  storage, and moderation are **not implemented** (spec + provider + decision all
  missing). Durable render/job queue infrastructure EXISTS but has no media
  handlers. See `docs/SERVICE_GAPS.md`.

---

## Owner-only questions (batch, surfaced once)
1. **Product spec for AI media:** image + short-video generation — in scope,
   providers, output/cost budget, per-org access control?
2. **Media storage choice:** S3 / R2 / Cloudinary / GCS (none wired today)?
3. **Moderation policy & reviewer workflow:** define before enabling AI media.
4. **Pin the toolchain:** adopt pinned `requirements.txt` + `.nvmrc` for
   reproducible production builds?
5. **`010_demo_dataset.sql`:** auto-load on hosted migrate, or opt-in? (not verified auto.)
6. **`run-agent.bat`:** fix to a real invocation or delete (calls nonexistent `npm run pipeline`)?
7. **Keyword Tracker room:** backend `/api/v1/foundation/keywords/**` routes exist but
   the visible room is a Concept shell — confirm whether the shell should be wired
   next (outside this audit; keyword routes untouched).

---

## Merge steps / shared-files risk
- **Merge base:** this branch starts from the current HEAD of `build/master-plan`
  (commit `6302f05`). Only **new additive files** were created; no existing file
  edited, no deletion.
- **Files to merge (new):** `docs/LOCAL_RUNBOOK.md`, `docs/SERVICE_READINESS_MATRIX.md`,
  `docs/SERVICE_GAPS.md`, `Northstar_backend/_audit_bootcheck.py`.
- **Shared/touched files:** **none** — I did not touch `foundation/api/router.py`,
  `data_rights.py`, `golden_goose_store.py`, `GoldenGoose.jsx`,
  `verify-acceptance.cjs`, `verify-golden-goose.cjs`, keyword contracts/routes,
  deployment scripts, or Creative Studio/SocialPulse feature files.
- **Working tree caveat:** the repo carried a large set of **uncommitted changes
  from other parallel sessions** (costco/provider-research work, snapshots,
  reports, `00_STATE.json`, `northstar.db`). I did **not** stage or commit any of
  them and did **not** edit `00_STATE.json` (already dirty from another session).
  Commits below contain **only** the four audit files.
- **Merge risk:** negligible by construction (additive-only). Conflicts only if
  another session later edits the same three new doc paths or `_audit_bootcheck.py`.

## Commits
- `audit/local-readiness`: docs (3) + boot-check helper (1). Small, self-contained.

---

## Next priorities
1. Owner answers to §4 questions (esp. media spec, storage, moderation).
2. Build a thin **media job handler** over the existing durable queue (no provider needed).
3. Add a **media storage abstraction** (local-dev fake + object-store adapter).
4. Wire the **Keyword Tracker** room UI to its existing foundation keyword routes.
5. Then provider integration for image/video generation with per-job cost budgets.

---

## REPORT FORMAT
**Changes:** +4 files (3 docs + 1 offline boot-verification helper), additive only.
**Tests:** backend offline boot (health 200, 185 routes, all routers mounted, 401 fail-closed auth);
UI `npm run build` 0 errors. No live/external contacts.
**Readiness:** Fully working locally: Golden Goose, Admin/Beta-Ops. Working-with-limits:
Product Finder, Monitoring, AutothinK. UI/shell only: Command Center, Creative Studio,
SocialPulse, Guardian, Keyword Tracker.
**Owner questions:** 7 (media spec, storage, moderation, pin toolchain, demo seed,
broken run-agent.bat, Keyword Tracker wiring).
**Merge steps:** `git merge audit/local-readiness` — zero shared-file risk (additive-only).
**Next priorities:** media job handlers → storage abstraction → Keyword Tracker wiring → provider integration.