# Non-Creative Remaining Work (canonical backlog)

**Scope:** the non-creative NorthstarOS suite (Command Center, SourceScout,
Golden Goose, Listing Guardian, Keyword Tracker, Competitor Monitor,
Profitability, Commerce Ops, Monitoring, AutothinK, Memory Bank, Shared Data
Layer, Provider Adapters, Master Brain, Beta-Ops, Admin, account/legal/support).
Creative Studio / SocialPulse / AdPilot / media generation are **out of scope**.

**Baseline:** `feature/creative-social-local`. This doc records what is now real,
what remains, and why. It supersedes the stale `SERVICE_READINESS_MATRIX.md`
(which predates this work and is currently dirty from another session).

---

## 1. New read-only API surface (local SQLite, no provider calls)

`Northstar_backend/noncreative_reads.py`, mounted at `/api/v1/noncreative/*`.
Read-only, no secrets (`password_hash` never selected), honest `[]` on failure.
Covered by `Northstar_backend/test_noncreative_reads.py` (4 tests, offline).

| Endpoint | Backs |
|---|---|
| `/commerce-ops/queue` | identity/pack resolution queue + pipeline runs |
| `/listings/health` | listings + identity-enrichment + evidence counts |
| `/competitor/observations` | products + costco source products |
| `/activity` | pipeline runs + audit + campaigns |
| `/keywords` | keyword sets + performance |
| `/sources` | refresh metadata + live pulls + pipeline runs |
| `/sessions` | memory entries + audit |
| `/accounts` | users + sessions + invites (no password material) |

## 2. Rooms with real local reads now wired (this build-out)

- **Commerce Ops** — Identity resolution queue (181 items) + recent runs.
- **Listing Guardian** — real listing/identity records + enrichment/evidence counts.
- **Competitor Monitor** — real local product/source observations.
- **Command Center** — real local activity (runs/audit/campaigns) alongside live signals.
- **Keyword Tracker** — real local keyword sets + performance.
- **Shared Data Layer** — real source refresh registry + live pulls.
- **Master Brain** — real knowledge-plane sessions (memory + audit).

Readiness badges updated: Listing Guardian SAMPLE→PARTIAL, Competitor Monitor SAMPLE→PARTIAL.

## 3. Remaining — cannot be finished without a decision or new data

### 3a. Sample bodies awaiting a dedicated backend
- **Profitability** portfolio/fee/inventory/scenarios (economics engine already real).
- **Monitoring** sample service-checks/alerts (live checks + `/health/detailed` real).
- **Beta-Ops** Cohorts / Reports rows / Eligibility checklist (dashboard/orgs/audit/support/invites real).
- **Customer Workspace** plan/usage/tasks; **Account Status** details; **Setup** profile/legal rows; **Documents** operational rows.
- **Golden Goose** real evaluate surface (`POST /foundation/golden-goose/evaluate`) — **deferred**: needs a full 10-gate input UI to avoid misrepresenting the decision policy; not built to avoid a misleading form.

### 3b. No backend / no local data (stay honest-disabled)
- **Recovery** (self-service recovery), **Reaccept** (acceptance recording), **legal acceptance recording**.

### 3c. Provider-gated (owner arming required)
- **SourceScout** live scan (`SCANNER_LIVE_ALLOWED` + paid provider).
- **AutothinK** runs (Ollama local, or armed cloud provider).

## 4. Owner-gated write activations (per `docs/WRITE_PATH_AUTHORIZATION.md`)

**Activated (7):** invite issue, invite revoke, grant/activate, plan/tier change,
suspend, resume, dashboard export CSV — all platform-admin only.
**Still disabled:** entitlement override (per-event confirmation), cancel,
archive (terminal), support triage write (no UI), invite reissue (no route),
legal acceptance recording.

## 5. Verification / hygiene gaps
- **Playwright harnesses** (`verify-*.cjs`) can't be run by the agent without an
  isolated, signed-in profile; the new panels above are **not yet harness-covered**.
  Add assertions only when the harness can be run (avoid unverifiable changes).
- **Visual QA** requires ChromeConnect with an operator-selected profile.
- **Dead-surface cleanup** deferred (`docs/DEAD_SURFACE_MANIFEST.md`).
- **Stale docs**: `SERVICE_READINESS_MATRIX.md`, `SERVICE_GAPS.md` (dirty from
  another session — coordinate before editing).

## 6. Recommended next steps (priority)
1. Run the Playwright harnesses on an isolated profile; add coverage for the new panels.
2. Approve remaining write activations you want (entitlement override / support triage).
3. Build dedicated backends where product value is high (e.g., Commerce Ops task
   workflow, Listing Guardian live feed) — otherwise those bodies remain sample.
4. Coordinate the docs-truth refresh of `SERVICE_READINESS_MATRIX.md`/`SERVICE_GAPS.md`.
