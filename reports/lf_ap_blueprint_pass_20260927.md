# ListingForge + AdPilot Blueprint Conformance Pass (2026-09-27)

## Context
1. Operator supplied the full NorthstarOS UI/UX Blueprint (service-by-service spec). Saved verbatim (condensed formatting, content preserved) to `docs/UI_UX_BLUEPRINT_NORTHSTAROS.md` — now the authoritative room spec alongside the frozen SourceScout benchmark.
2. Prior chat review of ListingForge + AdPilot returned PASS for both with 6 approved fixes; this pass implemented all 6 plus the blueprint spec-vs-disk gaps (missing local tabs).

## Review fixes applied
### AdPilot (`northstar-os-ui/src/pages/internal/AdPilot.jsx`)
- **P1 badge contradiction fixed:** hardcoded "6 of 8 healthy" (which also contradicted 5 visible rows incl. Review/Critical) replaced by `healthRollup()` computed from the rows → muted pill "3 healthy · 1 review · 1 critical" with tooltip "Rollup computed from the sample rows below — not live campaign data".
- Status pills on Campaign Health STATUS column (Healthy → forest, Review → warn, Critical → ochre).
- Campaign Detail metric tiles gained "Basis: sample data" captions (tooltip: not verified tracking); Search Term Performance pill now "Top 5 terms · sample".
- Planner: BASIS column → truth pills (Assumption → dashed-ochre `pill-unverified` "planning only, does not authorize spend"; Observed → muted "sample window, not verified tracking"); each bid-rec card tagged with a small `assumption` pill.
- Landing dead space filled with **Budget Watch** strip (pacing meters + per-tile sample tooltips, basis pill "Basis: sample campaign data").

### ListingForge (`northstar-os-ui/src/pages/internal/ListingForge.jsx`)
- Listings table: health pills demoted from success-green to muted with "Sample health score — not a verified calculation" tooltip (Draft row keeps warn); "Updated" → provenance pills ("2h ago · sample").
- Landing dead space filled with **Studio Snapshot** strip (revisions in progress / drafts awaiting health check "REQUIRED" / publish-ready "Internal review ready" — restrained, no authorization green).

## Blueprint conformance (spec-vs-disk reconciliation)
- **AdPilot tabs 3 → 6** per blueprint (Campaigns, Campaign Detail, Search Terms, Planner, Placements, Rules):
  - *Search Terms*: term analysis with Harvest/Monitor/Add Negative/Reduce Bid suggestion pills + "no automatic changes; operator approval required" notice.
  - *Placements*: placement insights (Top of Search / Rest of Search / Product Pages) with CACHED SNAPSHOT DataNotice + per-row CACHED basis pills.
  - *Rules*: rule-management table (Draft/Armed states) + "Rules execute only after operator approval" internal notice.
- **ListingForge tabs 3 → 5** per blueprint (Listings, Editor, Templates, Assets, Revision Log):
  - *Assets*: asset tray (Attached/Draft/UNREVIEWED/Missing alt text states, truth pills) + handoff buttons to Creative Studio (blueprint handoff model).
  - *Revision Log*: version history v2.9–v3.2 with In progress / Published (sample) / Reverted states + "revert restores draft state only" notice + Restore-as-Draft affordances.

## Verification
- `npm run build` clean (81 modules, 712ms, 0 errors)
- `node verify-smoke.cjs` — **19 passed, 0 failed**
- `node verify-guards.cjs` — **8 passed, 0 failed**

## Screenshots
- Review evidence: `27/27b-listingforge`, `28/28b-adpilot`, `29-listingforge-editor`, `29b-templates`, `30-adpilot-detail`, `30b-planner` (pre-fix, reviewed in chat)
- Post-fix: `31-listingforge-blueprint.png`, `31b-assets`, `31c-revisions`, `32-adpilot-blueprint.png`, `32b-terms`, `32c-placements`, `32d-rules`, `32e-planner`

## Acceptance state
- Both rooms approved (chat review); P1 badge fix landed first as directed.
- No P0 blockers before Profitability Dashboard + Commerce Ops blueprint-conformance reviews.
- Blueprint tabs added for other rooms (CC 5-tab, GG tab renames, SocialPulse/Creative Studio/Profitability depth) remain open items for their own room passes.

## Open items (blueprint deltas noted, not yet built)
- Command Center blueprint requires local tabs (Overview/Exceptions/Activity/Exposure/Handoffs) + "Open Priority Queue" CTA + scope switch — next room pass.
- Golden Goose blueprint tab names (Queue/Review/Decisions/History) vs current (Queue/Opportunity Detail/Decision Log) — cosmetic rename candidate.
- SocialPulse, Creative Studio, Profitability, Commerce Ops depth per blueprint — future room passes in blueprint order.
