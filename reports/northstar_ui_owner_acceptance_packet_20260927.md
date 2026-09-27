# NorthstarOS UI — Owner Acceptance Packet (2026-09-27)

**Status:** UI architecture pass complete; presentation layer **frozen** pending owner sign-off.
**Scope:** private-beta UI only. This packet contains no application-code changes.

---

## 1. Freeze statement

The UI presentation layer is frozen for owner review. No room redesigns, no SourceScout changes (reserved for a proven regression only), no legacy-page removal/rewiring/activation, no provider activation, and no catalog/snapshot/production-data mutation are part of this packet.

---

## 2. Verification snapshot (latest)

| Check | Command | Result | Label |
|---|---|---|---|
| UI production build | `cd northstar-os-ui && npm run build` | 82 modules, 0 errors · js 429.41 kB · css 38.06 kB | **VERIFIED** |
| Smoke suite | `node verify-smoke.cjs` | 40 passed / 0 failed | **VERIFIED** |
| Role-guard suite | `node verify-guards.cjs` | 8 passed / 0 failed | **VERIFIED** |
| Running-UI acceptance harness | `node verify-acceptance.cjs` | 26 passed / 0 failed | **VERIFIED** |
| Backend package tests (plain collection) | `python -m pytest costco_non_kirkland/tests -q` | 191 passed / 0 failed | **VERIFIED** (backend; not UI) |

Evidence: `reports/private_beta_ui_acceptance_20260927.md`, `reports/post_acceptance_p2_hardening_20260927.md`, `reports/cluster_ab_visual_polish_20260927.md`, `reports/cluster_c_admin_beta_ops_20260927.md`.

---

## 3. Owner acceptance checklist

Tick each on review. Reference screenshots under `northstar-os-ui/screenshots/` (`41–54k` room evidence; `55*` desktop acceptance; `56*` mobile acceptance; `57*` post-hardening 375px).

### 3.1 Desktop & mobile
- [ ] Major service rooms render correctly at **desktop (1440×900)** — Command Center, SourceScout, Golden Goose, Listing Guardian, Keyword Tracker, ListingForge, AdPilot, SocialPulse, Creative Studio, Profitability, Commerce Ops, Monitoring, Admin, Beta-Ops.
- [ ] Rooms render correctly at **mobile (375–390px)** — no clipped grids; card grids scroll with an affordance or stack (Creative Studio, Listing Guardian, SocialPulse, Monitoring, Beta-Ops).
- [ ] No banner + table + dead-space layouts; above-the-fold content is useful.

### 3.2 Access by role
- [ ] **Customer:** lands in Customer Workspace; sees only customer routes in navigation; Entitled Services "Open" reaches internal rooms by design.
- [ ] **Operator:** internal operator rooms render; `/beta-ops` and `/admin` redirect away.
- [ ] **Platform admin:** `/beta-ops` and `/admin` load; full nav.
- [ ] **Signed-out/invitee:** Admin and Beta-Ops redirect away; no internal admin discovery via navigation.

### 3.3 Navigation & deep links
- [ ] Primary navigation (rail, top nav, mobile bottom nav, Tools sheet) works per role.
- [ ] Deep links resolve: `#/socialpulse?view=composer|queue`, `#/creative-studio?view=variants`, `#/listings?view=diffs|history`, `#/keyword-tracker?view=coverage`, `#/monitoring?view=health`, `#/beta-ops`, `#/beta-ops/eligibility`, `#/admin`, `#/product-finder`.

### 3.4 Service room identity & usability
- [ ] Each room reads as its own service (no generic dashboard with tabs).
- [ ] SocialPulse = publishing studio · Creative Studio = workshop · Listing Guardian = watchtower · Keyword Tracker = visibility lab · Monitoring = observability tower · Admin = system configuration · Beta-Ops = private-beta operating queue.
- [ ] **SourceScout is frozen as the UI benchmark** — identity, Decision Rail, Market Evidence, Economics, provenance intact.

### 3.5 Truth-state honesty
- [ ] UNKNOWN vs UNVERIFIED vs UNVERIFIED/UNKNOWN are distinct and never shown as zero.
- [ ] Cached / observed / historical / sample states are muted or labelled — never shown as success-green.
- [ ] Green is reserved for genuinely probe-backed, live-verified outcomes (Monitoring health, Provider Adapters).
- [ ] Provenance tags are present and accurate.

### 3.6 Disabled / proposed-only action clarity
- [ ] Sample-only actions are visibly disabled (e.g., Beta-Ops lifecycle confirm, eligibility verify, invite reissue/revoke, report download).
- [ ] Proposal-only content is labelled (e.g., Listing Guardian "Proposed — not enforced" escalation rules).
- [ ] Action toasts preserve manual/uncertain framing (e.g., "nothing publishes automatically").

### 3.7 Invite, lifecycle, and internal-admin flows
- [ ] Beta-Ops Invites: create form + invite detail (Expired state) render; actions disabled in sample mode.
- [ ] Beta-Ops Lifecycle: irreversible-action warning + confirm disabled in sample mode.
- [ ] Beta-Ops Organizations / Cohorts / Support / Audit / Reports / Eligibility render with semantic state pills and nav.
- [ ] Internal Admin renders System Status, Configuration, and Controls (safety gates) with internal truth labels.

### 3.8 Zero live provider calls on normal loads
- [ ] **Explicit confirmation:** no normal page load and no ordinary GET request makes a live provider call. The routed app's only calls are the foundation session bootstrap (`/api/v1/foundation/ui-mode|me|environment|preview/active`); rooms use local sample data plus navigation/toasts.

---

## 4. Area status labels

| Area | Label | Notes |
|---|---|---|
| UI build | **VERIFIED** | 82 modules, 0 errors |
| Smoke / guards / acceptance suites | **VERIFIED** | 40/40, 8/8, 26/26 |
| Desktop room rendering | **VERIFIED** | Spot-checked; SourceScout frozen |
| Mobile room rendering | **VERIFIED** | P2 grid polish applied; 375px captures |
| Role guards (running UI) | **VERIFIED** | Signed-out/customer/operator off `/beta-ops` + `/admin`; admin loads |
| Navigation & deep links | **VERIFIED** | 26-check harness |
| Sample/disabled action clarity | **VERIFIED** | Disabled controls + honesty toasts |
| Truth-state honesty | **VERIFIED** | No success-green on non-authoritative state |
| Zero live provider calls on loads | **VERIFIED** | UI-only analysis of routed code |
| SourceScout benchmark | **VERIFIED (frozen)** | Unchanged; regression-only changes permitted |
| SellerSprite retirement / fail-closed | **VERIFIED** | Adapter/CLI/sign-in/schema removed; named retirement rejects |
| SellerAmp provider status | **REPORTED** | Offline-only: disabled-by-default adapter + local CSV/JSON importer; **not** live-integrated |
| Backend package tests | **VERIFIED** | 191 passed / 0 failed (plain collection) |
| Bright Data live work | **OUT OF SCOPE** | Separate, gated, untracked; not executed |
| Legacy-page retirement | **UNKNOWN** | Inventory done; removal is a future dedicated PR |
| Live provider enrichment end-to-end | **UNKNOWN** | Not enabled; outside this packet |
| Production deployment | **UNKNOWN** | Not performed |

---

## 5. Provider & truth-state facts (as verified)

- **SellerSprite is retired and fails closed.** Removed from the adapter registry, importer, schema/detection, CLI (`import-sellersprite` gone), sign-in services, and the authorized-market-source allowlist. `provider_factory("sellersprite")` raises `ProviderRetired`; `plan_enrichment` returns `retired_provider`; retired sign-in/detection are rejected; `create-provider-manifest --provider sellersprite` is rejected by choices. A clearly-labelled retirement record remains the only reference. Evidence: `reports/sellersprite_trial_expiry_deactivation_20260927.md`.
- **SellerAmp is REPORTED / offline-only.** `SellerAmpProvider` is disabled-by-default and returns `provider_not_configured` / `requires_explicit_approval`; `SellerAmpImporter` parses local CSV/JSON exports only. There is **no live API client, credential use, browser automation, or network path**. It must **not** be described as live-integrated.
- **Bright Data live work is separate, gated, and out of scope.** An untracked `brightdata_costco_live.py` exists and fails closed without all gates (`approved`, collector id, ≤3 URLs, `max_inputs` ≤3, `spend_cap`, API token). It was not executed, modified, or committed.
- **SourceScout is frozen as the UI benchmark.** Change only to repair a proven regression.
- **No normal page load or GET request makes live provider calls.** The routed app touches only the foundation session bootstrap endpoints; provider-fetching legacy pages are unrouted.

---

## 6. Not included in acceptance

The following are explicitly **out of scope** for this packet and are not covered by owner sign-off:

- Live provider enrichment
- Production deployment
- Public signup
- Real payments
- Autonomous publishing / escalation / purchasing
- The untracked Bright Data live module
- Legacy-page retirement

---

## 7. Evidence index
- `reports/private_beta_ui_acceptance_20260927.md` — independent acceptance pass (build/smoke/guards/acceptance; provider & hygiene findings)
- `reports/post_acceptance_p2_hardening_20260927.md` — P2 hygiene (mobile grids, truth-state, test hygiene, legacy inventory)
- `reports/sellersprite_trial_expiry_deactivation_20260927.md` — provider retirement
- `reports/cluster_ab_visual_polish_20260927.md`, `reports/cluster_c_admin_beta_ops_20260927.md` — room rebuild/polish
- Harnesses: `northstar-os-ui/verify-smoke.cjs`, `verify-guards.cjs`, `verify-acceptance.cjs`, `capture-acceptance.cjs`, `capture-p2-mobile.cjs`
- Screenshots: `northstar-os-ui/screenshots/` (`41–54k`, `55*`, `56*`, `57*`)

---

## 8. Owner sign-off

- [ ] Accepted as complete for private-beta owner review.
- [ ] Accepted with notes (list below).
- [ ] Returned for changes (list below).

Notes:
______________________________________________________________________

Owner: ______________________  Date: ____________
