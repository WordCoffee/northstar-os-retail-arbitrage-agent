# Creative Cluster — Truth-Consistency, Campaign Parity, Asset Coherence (2026-10-04)

> Branch `feature/creative-cluster-launch`. Commit `f63a3c7`.
> Scope: creative rooms only. No provider/publishing/analytics changes.

## Cluster executed
Approved P0–P2: truth-consistency + SocialPulse campaign parity + AdPilot
sample-truth + asset-library coherence.

## Implemented fixes

**P0-1 — Creative Studio request-state truth.**
The queued-request terminal state was `"Blocked — provider required"`, which
contradicted the verified media truth (no route wired, engine not reachable).
Renamed to **`"Blocked — generation not armed"`** via a single `REQ_BLOCKED`
constant, applied to: the state→pill map, request creation, `blockedCount`
filter, the Production Queue metric tile, the DataTable "Queue anyway"
condition, the empty-state copy, and the queue toast. `providerState` →
`not_armed`.

**P0-2 — AdPilot sample-truth + truthful affordance.**
- Sample-derived states no longer use success-green: `Healthy` → muted,
  `Critical` → clay, `Harvest` → muted, `High Priority` → muted.
- Added a truth legend line to the room notice: *"Status and suggestion colors
  are muted because none of this is live-verified — green is reserved for
  live-verified checks."*
- Budget Watch within-range meter → new `.meter-fill-muted` (neutral) instead of
  `meter-fill-forest`.
- `"Create Campaign"` → **`"Open Planner"`** (the button only ever navigated to
  the bid/allocation planner; there is no campaign-creation flow).

**P1-3 — SocialPulse campaign parity + calendar truth.**
- **Campaign editing**: campaigns are real local records and are now editable
  (name / theme / objective / audience / state / channels) with local
  persistence — parity with Creative Studio brief editing.
- Calendar card labelled **"sample planning month · N planned records"** (static
  Sep-2026 mock, not a live calendar).

**P2-4 — Asset coherence.**
- **SocialPulse Asset Library**: added search (name/tag) and **real local
  attach-to-post / detach** linkage (`ns-social-assets.attached`), with honest
  "reference only, nothing uploads" copy.
- **Creative Studio Assets**: added a linked-variants count (variant↔brief
  lineage) and a **"Send to SocialPulse"** reference handoff.

**Harness marker (owner-approved change):** `verify-smoke.cjs` AdPilot action
selector updated to the approved `"Open Planner"` label; the navigation contract
(`/ui/adpilot?view=planner`) is unchanged.

## Originality safeguards applied
No reference-tool layouts/naming/styling introduced. New UI reuses the existing
paper/pine design system, `field`/`filter-pill` primitives, and the established
brief/campaign/placement/approval structure. AdPilot stays a performance-ops
room; Creative Studio stays the brief-driven studio; SocialPulse stays the
publishing-workflow room.

## Truth decisions
- Generation remains **PLANNED — NOT ARMED** (unchanged; no route/engine).
- AdPilot remains **SAMPLE** (static), now with muted states and an explicit
  legend.
- SocialPulse publishing remains honest: nothing publishes; campaigns/posts/
  assets are local records.
- No generation, publishing, analytics, upload, or export capability implied.

## Validation
- `npm run build` → 0 errors, 88 modules.
- `verify-smoke.cjs` **42/0** · `verify-guards.cjs` **11/0** ·
  `verify-acceptance.cjs` **32/0**.
- `capture-creative-cluster.cjs` **42/0** (adds: request-state truth, AdPilot
  sample-truth, calendar label, campaign edit persistence, asset attach, asset
  search).
- `git diff --check` clean.

## Screenshots
`northstar-os-ui/screenshots/session-creative-cluster-20261004/` (untracked):
`creative-studio-desktop-queue-truth.png`, `adpilot-desktop-sample-truth.png`,
`socialpulse-desktop-campaigns-edit.png`, `socialpulse-desktop-assets.png`
(+ prior set).

---

## REPORT FORMAT

**Worktree:** `C:\Users\T2Hol\AppData\Local\Temp\opencode\ns-creative-social-polish-v2`
**Branch:** `feature/creative-cluster-launch`
**Base commit:** `8ba0c9e`
**Current commit:** `f63a3c7`
**Blueprint/readiness artifacts adopted:** `remaining_rooms_consolidated_analysis_20260927.md` (Cluster A A1–A9), `cluster_a_socialpulse_creative_studio_20260927.md`, `cluster_ab_visual_polish_20260927.md`, `private_beta_ui_acceptance_20260927.md`, `parallelB_creative_social_20260930.md`, `creative_cluster_build_20261004.md`, `creative_media_readiness_20261004.md`, `docs/CREATIVE_SOCIAL_LOCAL_STATUS.md`, `docs/CREATIVE_MEDIA_STACK.md`, `docs/LOCAL_IMAGE_GEN_SETUP.md`
**Cluster executed:** P0–P2 — truth-consistency + campaign parity + AdPilot sample-truth + asset coherence
**Creative rooms/services audited:** Creative Studio, SocialPulse, AdPilot (+ ListingForge adjacent)
**Implemented fixes:** request-state rename; AdPilot muted sample states + legend + neutral meter + `Open Planner`; SocialPulse campaign editing + calendar sample label; SocialPulse asset search + attach/detach; Creative Studio asset linked-variants + Send-to-SocialPulse; harness marker update (approved)
**Generation/publishing truth decisions:** generation stays PLANNED/NOT ARMED; AdPilot stays SAMPLE with muted truth colors; SocialPulse never publishes; nothing uploads/renders
**Originality safeguards applied:** no reference-tool layouts/naming/styling; existing design system + brief/campaign/placement/approval structure reused; rooms keep distinct roles
**Tests/builds run:** build 0 errors · smoke 42/0 · guards 11/0 · acceptance 32/0 · capture 42/0 · diff --check clean
**Browser verification status:** repo harnesses + captured PNGs (no manual browser driving; Chrome Connect not used)
**Remaining creative launch gaps:** image/video generation provider-gated; SocialPulse publishing/analytics provider-gated; AdPilot sample-static; SocialPulse calendar static sample month; `resolve_vision(local)` reports available without probing
**Blocked items:** owner decision to arm/allow local ComfyUI execution (unchanged gate)
**Recommended next action:** next cluster — Creative Studio Library/Exports coherence (real bundle contents tied to variants + honest download boundary) and SocialPulse presets/channel-fit depth; alternatively approve the readiness-only `foundation/api/creative.py` route to make Provider Readiness a live probe
