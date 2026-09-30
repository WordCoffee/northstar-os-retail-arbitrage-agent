# Northstar OS — Service Readiness Matrix

**Branch:** `audit/local-readiness` (Parallel Session A)
**Method:** Boot verification (TestClient, offline) + static code inspection.
**Classification key:**
- **Fully working locally now** — boots and functions with local/offline data.
- **Working locally with limitations** — functions but needs a provider/cache/binding that is not free-and-always-on.
- **UI/shell only** — a rendered page, no real backend data flow (explicit `tone="sample"` banners).
- **Missing product specification** — no spec/code decision.
- **Owner-decision blocked** — blocked on a named operator choice.
- **Oracle-hosting blocked only** — code is ready; only hosting/infra remains.

| Room | Route / backing code | P0 backend routes (verified via `/openapi.json`) | Readiness (local) | Notes |
|---|---|---|---|---|
| **Command Center** | `/home` → `CommandCenter.jsx` | — | **UI/shell only** | Briefing/tasks/portfolio rendered from hardcoded sample data. "New Scan" button shows *sample mode*. No live provider. |
| **Product Finder (SourceScout)** | `/product-finder` → `ProductFinder.jsx` | `/api/sourcescout`, `/matches`, `/mismatches`, `/review`, `/summary`; `/api/products/finder`, `/api/products/{asin}/canopy|offers` | **Working locally with limitations** | Reads cached scanner result; offline caches present (38 KB + 145 KB). Live scan needs `SCANNER_LIVE_ALLOWED=1` + external provider key (paid). |
| **Golden Goose** | `/golden-goose` → `GoldenGoose.jsx` | `/api/golden-goose/**` + `/api/v1/foundation/golden-goose/**` (persisted queue/review/decisions) | **Fully working locally now** | Probed: `/api/golden-goose/health` + `/entitlements` → **200**. Wires foundation API; scanner queue + review/decision round-trip persisted, org-scoped. Dry-run + mock scan. |
| **Creative Studio** | `/creative-studio` → `CreativeStudio.jsx` | none | **UI/shell only** | Concept shell; no image/video generation provider wired. 721-line UI, all sample. |
| **SocialPulse** | `/socialpulse` → `SocialPulse.jsx` | none (logic in `social_pulse.py`) | **UI/shell only** | Concept shell; backend `social_pulse.py` exists but no live publishing. Sample data. |
| **Guardian (Listing Guardian)** | `/listings` → `ListingGuardian.jsx` | none | **UI/shell only** | Sample listing-health mock; no live listing data source. |
| **Keyword Tracker** | `/keyword-tracker` → `KeywordTracker.jsx` | `/api/v1/foundation/keywords/**` DO exist | **UI/shell only** | Backend keyword routes exist and are substantial, but the UI room is a Concept shell (0 API references). |
| **Monitoring** | `/monitoring` → `Monitoring.jsx` | `/api/monitoring/error-alerts` | **Working locally with limitations** | Probed: `/api/monitoring/error-alerts` → **200**. Dashboard is mostly local/sample; delivery wiring is operator-side (see MONITORING_SETUP.md). |
| **Admin / Beta-Ops** | `/admin`, `/beta-ops` (+ ops subpages) | `/api/v1/foundation/admin/**` (dashboard, orgs, export, history, plans) | **Fully working locally now** (auth-gated) | Backed by foundation admin routes; `platform_admin` only, fail-closed 401 otherwise. Requires local-dev identity shim or real session. |
| AutothinK | `/autothink` → `AutothinK.jsx`; server :8100 | — | Working locally with limitations | Chat needs Ollama + model; else "offline" lamp. |
| Memory Bank / Shared Data / Provider Adapters / Master Brain | `/memory-bank`, `/shared-data`, `/provider-adapters`, `/master-brain` (internal) | foundation routes | Working locally with limitations | Internal read-only/management pages over foundation state. |

### Execution infrastructure (not a room, but verified)
| Area | Routes | Session A result | Readiness |
|---|---|---|---|
| **Private-beta controls** | `/api/v1/foundation/beta-status`, `/demo/status`, `/preview/active`, `/auth-posture`, `/environment`; `AlphaGateMiddleware` | **401** auth-gated (present) | Working locally (needs session/dev-shim). Code-verified: alpha is outermost + allowlist; registration blocked in alpha. |
| **Scheduler state** | `/api/v1/foundation/schedules`, `/schedules/posture` | **401** auth-gated (present) | Working locally with limitations — **hosted-only** runtime (Docker `scheduler`/`worker` services); absent from local SQLite stack. |
| **Durable render/job queue** | `/api/v1/foundation/jobs`, `/jobs-durable/**` | queue-posture **401** auth-gated | Infrastructure present; no media-render handlers (see SERVICE_GAPS.md §4). |

### Summary by classification
- **Fully working locally now:** Golden Goose, Admin/Beta-Ops.
- **Working locally with limitations:** Product Finder, Monitoring, AutothinK, internal System rooms.
- **UI/shell only:** Command Center, Creative Studio, SocialPulse, Guardian, Keyword Tracker. *(Command Center's and Keyword Tracker's backends exist but the visible rooms are shells.)*
- **Missing product specification:** Creative Studio image/video generation, SocialPulse live posting.
- **Owner-decision blocked:** media provider choice, moderation approach (see SERVICE_GAPS.md).
- **Oracle-hosting blocked only:** none purely hosting-blocked — every gap so far is code/spec/provider/decision, not hosting capacity.

> Note on "shell" vs "backed": several "shell" rooms have **real backend modules** the UI does not yet call
> (Keyword Tracker ↔ foundation keyword routes; SocialPulse ↔ `social_pulse.py`; Guardian/listings partial).
> The readiness above reflects what the **visible local page** actually does with `tone="sample"` disclaimers.