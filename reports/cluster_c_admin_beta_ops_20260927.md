# Cluster C — Admin / Beta-Ops (2026-09-27)

## Scope
Final UI cluster. Internal **Admin** and the **Beta Operations** program surfaces made practical, role-clean, truth-labeled, and operationally credible — no visual experimentation, no redesign. Admin and Beta-Ops kept distinct:
- **Admin** = system configuration, controls, and internal management.
- **Beta-Ops** = operating queue for the private-beta program.

## Admin — `src/pages/internal/Admin.jsx`
- **Fixed the pill base-class / concatenated-status defect:** status spans used `className={item.color}` (e.g. `pill-ok`) without the `pill` base and sat in a non-flex `.list-row`, so label + status ran together as plain colored text (`Catalog IndexHealthy`). Now each row is a proper flex row and every status renders as `pill <tone>`.
- **Truth labels:** added an `INTERNAL USE ONLY` DataNotice — status values are *internal/observed configuration, not a live health probe and not source-of-truth telemetry*; no control enables live calls, spend, or autonomous action. Added a muted legend ("Green is reserved for live probe-backed checks").
- **Semantic states + basis:** System Status rows show a muted basis pill (`Index build (internal)`, etc.); statuses are muted (non-authoritative). Configuration values are pills.
- **New Controls card:** explicit safety gates (Live provider calls / Automated enrichment jobs / Autonomous publishing / Purchase authorization) with `Disabled` / `Operator-only` pills and notes.
- **Distinct from Beta-Ops:** subtitle states operating queues live in Beta Operations.

## Beta Operations — control room
Added a shared `BetaOpsNav` sub-navigation (`src/pages/admin/BetaOpsNav.jsx`) across all `/beta-ops/*` pages: Overview · Organizations · Invites · Cohorts · Support · Lifecycle · Audit · Reports.

### Overview — `src/pages/admin/Overview.jsx`
- `INTERNAL USE ONLY` notice; metric tiles; **Exception Queue** card replacing the plain error banner — each exception with severity pill + **action routing** (`Review lifecycle` → `/beta-ops/lifecycle`, `Reissue invite` → invite detail).
- Recent Activity status pills (Error→error, Warn→warn, Ok→muted); Organization Readiness as semantic pills; Cohorts and Support tables with status pills and **Manage cohorts / Open support queue** actions.

### Organizations — `OrgsList.jsx`
Nav + internal notice; roster with ID/plan/members and **lifecycle status pills** (Active→muted, Suspended→warn) + per-row **Open** → org detail. `OrgDetail` gets nav, a profile with status pill, **Back to organizations**, and a **Lifecycle action** link-out.

### Invites — `InviteCreate.jsx`
Nav + internal notice; create form with **Send Invitation disabled in sample mode** (no invite issued). `InviteDetail` status corrected to **Expired** (`pill-warn`); Reissue/Revoke disabled with logged-action framing.

### Cohorts / Support / Lifecycle / Eligibility / Audit / Reports — `Cohorts.jsx`
- Cohorts: nav + notice + status pills (Complete→muted, Active→ochre).
- Support Ops: nav + notice + open/resolved metric tiles + category pills + status pills + **Open audit trail** routing.
- Reports & Exports: nav + notice (safe field set only) + **Download disabled in sample mode**.
- Audit & Notes: nav + notice + timeline with **provenance pills** (OBSERVED/HISTORICAL, muted).
- Lifecycle: nav + **`alert alert-error` base-class fix** + notice; confirm action disabled in sample mode.
- Eligibility: nav + notice (checklist does not auto-admit) + per-criterion Verified/Pending pills + Verify disabled.

## Layout / guardrails
- No banner + table + dead-space layouts introduced; operational cards carry actions.
- Truth states are explicit; **no success-green on sample/observed/internal state** (Admin status, org/cohort/ticket states, audit provenance all muted/ochre/warn).
- Role guards preserved and unchanged: `/beta-ops` and `/admin` remain platform-admin-only (client `GuardedRoutes` + role-filtered nav); customer/invitee cannot discover or reach them.
- NorthstarOS visual language and SourceScout truth-state benchmark preserved. `capture-clusterC.cjs` added for repeatable admin captures.

## Verification
- `npm run build` — **clean**, 82 modules, 0 errors (js 429.35 kB / gzip 108.63 kB; css 37.36 kB).
- `node verify-smoke.cjs` — **40 passed, 0 failed**.
- `node verify-guards.cjs` — **8 passed, 0 failed** (signed-out + customer still redirected off `/beta-ops` and `/admin`; platform_admin loads both; mobile Tools sheet role-filtering intact).
- Screenshots captured + render-verified (platform-admin stub): `53` (Admin), `54/54b–54k` (Beta-Ops overview, orgs, org detail, invites, invite detail, cohorts, support, lifecycle, eligibility, audit, reports).

## Screenshot inventory
| File | View |
|---|---|
| `53-admin-internal.png` | Internal Administration |
| `54-betaops-overview.png` | Beta-Ops Overview + Exception Queue |
| `54b-betaops-orgs.png` | Organizations roster |
| `54c-betaops-org-detail.png` | Organization detail |
| `54d-betaops-invites.png` | Create Invitation |
| `54e-betaops-invite-detail.png` | Invite detail (Expired) |
| `54f-betaops-cohorts.png` | Cohorts |
| `54g-betaops-support.png` | Support Operations |
| `54h-betaops-lifecycle.png` | Lifecycle action |
| `54i-betaops-eligibility.png` | Eligibility checklist |
| `54j-betaops-audit.png` | Audit & Notes |
| `54k-betaops-reports.png` | Reports & Exports |

## Stop point
Cluster C complete and clean. This completes the UI architecture pass — remaining work is final visual spot-checking, private-beta UX acceptance, and service/backend capability maturation, not another broad UI rebuild.
