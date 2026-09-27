# Cluster B Blueprint Conformance — Listing Guardian + Keyword Tracker + Monitoring (2026-09-27)

## Scope
Watchtower/monitoring rooms rebuilt to blueprint (`docs/UI_UX_BLUEPRINT_NORTHSTAROS.md` lines 167–179) under cluster-level autonomy. Cluster B completed cleanly — no regressions. Cluster C remains gated.

## Listing Guardian — `internal/ListingGuardian.jsx`
Rebuilt from alert-table into a watchtower.
- **Tabs (blueprint):** `Alerts, Diffs, History, Escalations` (was Alerts/Tracked Entities/Guardian Rules).
- **Above-the-fold (Alerts):** 3 metric tiles with basis captions + **Policy & Suppression Warnings** panel (policy/suppression, severity pills, escalate) + Alert Feed with **severity pills** (High→error, Medium→warn, Low→muted), **status pills** (Resolved→muted, no green), and per-row Escalate.
- **Diffs (new):** detected-changes list + **before/after side-by-side viewer** with severity + escalate/mark-reviewed.
- **History (new):** change timeline with OBSERVED/CACHED/HISTORICAL provenance tags (muted).
- **Escalations (new):** escalation queue (→ ListingForge / Commerce Ops, "Open in room") + Escalation Rules (moved from old Rules tab, "Proposed — not enforced").
- **Truth:** SAMPLE notice; "escalation is manual — no rule takes automated action"; no auto-fix language.

## Keyword Tracker — `internal/KeywordTracker.jsx`
Rebuilt from rankings-table into a search-visibility lab.
- **Tabs (blueprint):** `Sets, Trends, Coverage, Alerts` (was Rankings/Tracked Terms/Reports).
- **Above-the-fold (Sets):** keyword **set selector** + rank-trend summary tiles (terms / improving / declining) + **Coverage Status** block (covered/partial/gap bars) + **Flagged Movement** list + sets table.
- **Trends:** rank-trend table with inline **sparklines** + position + movement pills (up→muted, down→ochre).
- **Coverage:** per-ASIN covered/partial/gap table (gaps → ochre when high).
- **Alerts:** flagged movement alerts with severity pills.
- **Truth:** CACHED SNAPSHOT notice retained; movement labeled "indication, not verified"; arrows → movement pills; removed green on counts.

## Monitoring — `internal/Monitoring.jsx`
Repositioned as an **observability watchtower**; duplication removed.
- **De-duplication:** removed the duplicated per-source freshness matrix; replaced with a high-level **Staleness Summary** + explicit **"Investigate in the right room"** deep-links to **Shared Data Layer** and **Provider Adapters**. Subtitle/notice state that source-level detail lives in those rooms.
- **Tabs:** `Alerts, Health, Sync & Staleness`.
- **Alerts:** severity pills + **Detail Source** column (Shared Data Layer / Provider Adapters / Commerce Ops).
- **Health:** service checks with **basis pills**; green only for genuinely healthy internal checks + system-health metrics with basis captions.
- **Sync & Staleness:** summary tiles + staleness table where `Cached/Observed/Stale/Unavailable` are **muted/ochre/error — no longer success-green**.
- **Truth:** INTERNAL notice "not source-of-truth".

## Distinct room shapes (no clone risk)
- Guardian = listing watchtower (alerts + policy/suppression + **diff viewer** + escalations).
- Keyword = visibility lab (set selector + **sparkline trends** + coverage bars + movement alerts).
- Monitoring = system observability (service checks + alert stream + staleness summary with link-outs).
- Each landing has a different above-the-fold composition (no repeated banner+table+dead-space).

## Verification
- `npm run build` clean (81 modules, 0.77s, 0 errors; 402.27 kB js)
- `node verify-smoke.cjs` — **40 passed, 0 failed** (+ Guardian diffs/history/escalations, Keyword trends/coverage/alerts, Monitoring health/sync; Guardian "New Rule" action now targets Escalations; old Keyword terms / Guardian rules deep links retired)
- `node verify-guards.cjs` — **8 passed, 0 failed**
- Screenshots captured + render-verified: `50/50b–50d` (Guardian alerts, diffs, history, escalations), `51/51b–51d` (Keyword sets, trends, coverage, alerts), `52/52b–52c` (Monitoring alerts, health, sync)

## Reference correction (operator directive)
Per operator instruction, **SellerSprite is no longer a reference product**. Blueprint header updated to reference **SellerAmp (SAS, https://sas.selleramp.com/)** as the sole competitor reference.

## Decision required (flagged, not actioned)
`Northstar_backend/costco_non_kirkland/` still implements a **SellerSprite** import provider (`import-sellersprite`, `SellerSpriteImporter`, `--provider sellersprite`) alongside SellerAmp. Removing SellerSprite support touches data-import pipelines + tests across the package — a cross-cutting decision. Not modified in this cluster; awaiting operator direction (retire SellerSprite provider vs leave backend as-is).

## Stop point
Cluster B complete and clean. **Cluster C (Admin / Beta-Ops) held for its own gate.**
