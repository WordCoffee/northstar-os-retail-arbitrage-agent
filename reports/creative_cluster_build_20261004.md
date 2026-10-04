# Creative-Cluster Build Session (2026-10-04)

> Branch: `feature/creative-cluster-launch` (never pushed). Worktree:
> `C:\Users\T2Hol\AppData\Local\Temp\opencode\ns-creative-social-polish-v2`.
> Base: `8ba0c9e` → `8f424ae` (batch 1) → `3e6011a` (batch 2).
> Local-only. No provider, publishing, analytics, or generated media.

## Scope owned
Creative services cluster only: Creative Studio (design), SocialPulse (social
creative/scheduling), AdPilot (ad-ops, creative-adjacent), plus the shared
creative CSS. Non-creative rooms untouched except the shared `.filter-pill`
chip class in `app.css`.

## What was inspected
- Repo/worktree state; the dirty `feature/creative-social-local` tree (164 files)
  was **not** touched or reused.
- Rooms/routes: `/creative-studio`, `/socialpulse`, `/adpilot`, `/listingforge`.
- Reports adopted: `remaining_rooms_consolidated_analysis_20260927.md` (Cluster A
  A1–A9), `cluster_a_socialpulse_creative_studio_20260927.md`,
  `cluster_ab_visual_polish_20260927.md`, `private_beta_ui_acceptance_20260927.md`,
  `parallelB_creative_social_20260930.md`.
- Status/provider docs: `docs/CREATIVE_SOCIAL_LOCAL_STATUS.md`,
  `docs/CREATIVE_MEDIA_STACK.md`.
- Harnesses: `verify-smoke.cjs`, `verify-guards.cjs`, `verify-acceptance.cjs`,
  `capture-*.cjs`.

## Implemented fixes

### Batch 1 — `8f424ae` (bugs / contradictions)
1. **Creative Studio — duplicate action removed.** `Generate Variants` called the
   same `submitRequest('image')` as `Queue Image Request`. It now records 3 draft
   variant rows for the active brief (aspect set) — a distinct, honest local action.
2. **Creative Studio — briefs are real objects.** Inline "Edit Brief"
   (name/objective/audience/brand/deliverables) persists to the local brief store.
3. **Creative Studio — Video/Shorts is a real planning surface.** Local storyboard
   beat list (numbered beats, per-beat seconds, remove, total duration). Honest:
   no clip is generated.
4. **SocialPulse — New Campaign creates a record.** Was a no-op toast; now adds a
   real local campaign (prepended + selected) with honest sample copy.
5. **AdPilot — fake count + dead control fixed.** Campaigns badge derives from the
   5 real rows (was hardcoded `8`); "Bulk Actions" was a dead button, now wired to
   an honest approval/tracking boundary toast.
6. **`.filter-pill` restored as a global styled chip.** It was only styled under
   `.room-toolbar`, so campaign/brief/preset/output chips rendered as unstyled
   native buttons with no selected state. Base + hover + active + focus-visible are
   now global (toolbar parity retained). ProductFinder has no usage → benchmark
   untouched.
7. **Mobile grids.** Creative-room card grids stack to one column at ≤480px
   (scoped via `.room-bottom-safe`), no cramped horizontal scroll at 390px.

### Batch 2 — `3e6011a` (Ad Creator + asset system)
8. **New Creative Studio "Ad Creative" tab (Ad Creator role).** Hook/offer/CTA +
   audience + placement targeting; "Build Ad Set" records one placement-aware
   variant per selected placement (Top of Search / Product Pages / Reels / Stories
   / Feed), a variant table with Approve / Request Changes, a Placement Fit
   guidance panel (labelled editorial, not measured performance), and
   Send-to-AdPilot / Send-to-SocialPulse handoff. Honestly labelled: no ad account,
   no spend authorization, no generation.
9. **Image Composer — Style direction** control (Clean studio / Lifestyle / Bold
   graphic / Editorial / Flat lay / UGC) recorded on each request.
10. **Assets — search + handoff.** Search across asset names and collections;
    "Use as reference" hands an asset to the composer (sets the selected ref-chip).

## Distinctiveness safeguards (mandatory check)

- **What informs the workflow?** Canva/Adobe Express (start-from-brief, asset
  reuse), Figma (panel/state discipline), CapCut (scene/beat sequencing), Meta ad
  tools (placement-aware variant sets), Hootsuite/Buffer (approval→schedule),
  Linear/Notion (state clarity).
- **What was intentionally NOT copied?** No template-gallery-first landing, no
  generic left-rail+top-bar editor shell, no neon AI gradients, no Canva component
  styling or naming, no section-for-section page reproduction.
- **What makes it Northstar?** Paper/pine/ochre design system + serif titles;
  every creative artifact is tied to a **work brief**, **campaign**, **placement**,
  or **approval state**; commerce/campaign intent is the organising axis.
- **How is it structurally different?** Creative Studio = brief → composer /
  ad-creative / video → queue → variants → assets → exports (studio/workshop).
  SocialPulse = calendar + workflow kanban + composer + approvals (publishing ops).
  AdPilot = performance/placement operations. Each has a distinct silhouette.
- **Is value commerce-tied?** Yes — hook/offer/CTA, placement fit, approval gates,
  export/handoff to ad-ops and social ops, not freeform design play.

## Validation
- `npm run build` → **0 errors**, 88 modules.
- `node verify-smoke.cjs` → **42 passed, 0 failed**.
- `node verify-guards.cjs` → **11 passed, 0 failed**.
- `node verify-acceptance.cjs` → **32 passed, 0 failed**.
- `capture-creative-cluster.cjs` (untracked helper) → **28 passed, 0 failed**:
  duplicate-action, brief edit, storyboard beats, New Campaign record, AdPilot
  count + Bulk Actions, global filter-pill, Ad Creative build-set + review,
  style-direction control, asset search + use-as-reference, mobile grid stack.
- `git diff --check` → clean both batches.

## Screenshots
`northstar-os-ui/screenshots/session-creative-cluster-20261004/` (untracked; not
staged): creative-studio desktop composer/briefs/video/variants/adcreative/assets,
socialpulse desktop calendar/campaigns/queue, adpilot desktop campaigns, and
creative-studio + socialpulse + adpilot mobile (390px).

## Honesty notes
- No image/video is generated; no publishing/OAuth; analytics stay `UNKNOWN`;
  provider boundaries and all sample labels preserved. New surfaces are explicit
  local planning records.

## Remaining launch gaps
- Image/video generation, publishing, analytics, asset store/download — provider
  gated (unchanged).
- SocialPulse calendar is a static September-2026 planning mock (month not dynamic).
- AdPilot remains sample-static (no local records) beyond the Creative-side ad set.
- Ad Creative renders planning records only; no rendered ad creative.

## Blocked items
- None. No auth, destructive, or tooling blocker encountered.

---

## REPORT FORMAT

**Worktree:** `C:\Users\T2Hol\AppData\Local\Temp\opencode\ns-creative-social-polish-v2`
**Branch:** `feature/creative-cluster-launch`
**Base commit:** `8ba0c9e`
**Current commit:** `3e6011a`
**Creative rooms audited:** Creative Studio, SocialPulse, AdPilot (+ ListingForge adjacent)
**Reference products consulted:** Canva, Adobe Express, Figma, CapCut, Meta ad tools, Hootsuite/Buffer, Notion/Linear (workflow patterns only)
**Distinctiveness safeguards applied:** brief/campaign/placement/approval-tied artifacts; no template-gallery landing; no clone component styling; distinct silhouettes per room; commerce-tied value
**Checklist found/adopted:** remaining_rooms_consolidated_analysis_20260927.md (A1–A9) + cluster A/B reports
**Implemented fixes:** 10 (batch 1: 7, batch 2: 3)
**Tests/builds run:** build 0 errors · smoke 42/0 · guards 11/0 · acceptance 32/0 · capture 28/0 · diff --check clean
**Visual checks:** 14 fresh PNGs at desktop + 390px (folder above)
**Remaining creative launch gaps:** provider-gated generation/publishing/analytics/asset-store; static Sep-2026 calendar; AdPilot sample-static
**Blocked items:** none
**Recommended next action:** owner decision on arming the local ComfyUI image route (docs/CREATIVE_MEDIA_STACK.md + CREATIVE_SOCIAL_LOCAL_STATUS.md §5) so Creative Studio's providers flip from static 0/4 to live readiness
