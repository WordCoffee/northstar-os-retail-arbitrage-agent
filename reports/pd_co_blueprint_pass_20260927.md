# Profitability Dashboard + Commerce Ops Blueprint Conformance Pass (2026-09-27)

## Scope
Blueprint conformance for two Operations rooms per `docs/UI_UX_BLUEPRINT_NORTHSTAROS.md` (§ Profitability Dashboard, § Commerce Ops). All 10 proposed fixes approved by operator before implementation.

## Pre-fix review evidence
- Screenshots 33/33b/33c/33d (Profitability), 34/34b/34c (Commerce Ops) — reviewed in chat; findings presented; operator approved all 10.

## ProfitabilityDashboard.jsx (fixes 1–6)
- **Tabs remapped to blueprint (P1):** `Overview / Scenarios / Fee Basis / Inventory Impact / Export` (was Set Detail / Scenario Calculator / Cash Cycle). Old `?view=` ids intentionally retired (internal-only).
- **Scenario cards (P1):** Base / Optimistic / Constrained / Worst Case above the fold on Overview + Scenarios, each `NOT CALCULATED` (clay) with dashed-ochre `assumption` pill + one-line modeled basis. Blueprint's required scenario matrix now present without implying any computed profit.
- **Primary actions (P1):** added `Create Scenario` (routes to Scenarios + restraint toast) and `Send to Commerce Ops` (handoff) beside Export Report / Refresh Data.
- **Truth pills (P2):** margin `UNKNOWN` → `pill-unknown`; `~22%` estimates → muted pills with "sample estimate — not a verified calculation" tooltips; Fee Basis `ASSUMPTION` → `pill-unverified`; Cash Cycle State → pills (Observed muted w/ tooltip, At risk warn, Assumption unverified); Restock actions → severity pills.
- **Depth + selector (P2):** sample Portfolio/Set A/B/C selector row (with "Sample selector" muted tag); Scenarios tab now carries Assumption Panel (3 explicit assumptions) + Warning Stack (UNKNOWN / REQUIRED gate / standing no-authorization note).
- **New Export tab:** contents list with per-row basis pills (NOT CALCULATED / ~observed / ASSUMPTION / observed) + "Exports carry basis labels — review before distribution" INTERNAL USE ONLY notice + Prepare Export / Send to Commerce Ops.
- Unit Economics Basis card: ASSUMPTION + ELEVATED now paired with unverified/warn pills so no favorable signal stands unlabeled.

## CommerceOps.jsx (fixes 7–10)
- **Tabs remapped to blueprint (P1):** `Workflow / Tasks / Approvals / Blockers / History` (was Queue / Workflow Detail / Documentation). `:id` routes still open Workflow detail; queue view gains **Critical Next Actions** strip (CO-04 Critical, CO-05 Required sign-off) per blueprint above-the-fold requirement.
- **Queue truth pills (P1):** Status (In Progress warn / Pending muted / Ready for Review muted / Blocked error / Awaiting Decision ochre), Blocking Condition (`Pack match UNKNOWN` → pill-unknown; Invoice expired → error; Approval needed → ochre), Priority (high warn / medium muted). Detail view same treatment. Added Age column.
- **New Approvals tab (P1):** approval checkpoints table (gates: Purchase authorization / Invoice readiness / Pack identity) + "Approvals require explicit operator sign-off — no approval step auto-completes; a green or positive signal never implies purchase authorization" INTERNAL USE ONLY notice + CO-05 validation steps.
- **New Blockers tab:** blocking-conditions table promoted from queue card, now with Age pills and Open actions.
- **New History tab:** decision notes & audit trail (sample) with kind pills.
- **Green-count fix (P2):** Documentation "4 items" `pill-forest` → `pill-muted` (success color no longer used on a bare count); Tasks statuses pillized (Complete muted with "not a verified audit state" tooltip).

## Verification
- `npm run build` clean (81 modules, 1.36s, 0 errors; 350.23 kB js)
- `node verify-smoke.cjs` — **22 passed, 0 failed** (harness updated: scenario→scenarios deep link; +3 deep links for fee/approvals/blockers)
- `node verify-guards.cjs` — **8 passed, 0 failed** (run pre-harness-update)
- Post-fix screenshots captured and individually verified: `35/35b/35c/35d/35e` (Profitability overview, scenarios, fee basis, inventory impact, export), `36/36b/36c/36d/36e` (Commerce Ops workflow, tasks, approvals, blockers, history)

## Truth-label audit of new surfaces
- Scenario cards: assumption pills, NOT CALCULATED — no computed profit shown anywhere without verified inputs.
- Approvals: explicit sign-off restraint notice; no auto-apply language.
- Blockers: aging signals urgency, "not auto-escalation" tooltip.
- Export: every row carries basis pill; no-authorization notice.
- Sample/cached provenance: "sample" tags on counts; cached language avoided where data is sample.

## Open items
- Remaining blueprint rooms: Command Center (5 local tabs + Open Priority Queue CTA), Golden Goose tab renames, SocialPulse, Creative Studio, Listing Guardian (Alerts/Diffs/History/Escalations), Keyword Tracker, Monitoring, Admin/Beta-Ops, customer/public rooms.
