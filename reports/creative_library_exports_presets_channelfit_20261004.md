# Creative Cluster — Library/Exports Coherence + Presets/Channel-Fit Depth (2026-10-04)

> Branch `feature/creative-cluster-launch`. Commits `07f3010` (Creative Studio)
> and `9d70f18` (SocialPulse). Scope: creative rooms only. No provider/publishing
> changes.

## Subclusters completed

### A — Creative Studio Exports coherence (`07f3010`)
- Bundle builder **basis counts are brief-scoped** (`briefVariants`), replacing a
  global variant count that ignored lineage.
- **Bundles carry real lineage**: `briefId`, `briefName`, `variantRefs[]`,
  `assetRefs[]`, `createdAt`. The prepared-bundles list shows brief, ref counts
  and timestamp.
- **Bundle Preview** lists "Manifest contents" — the actual variant + asset refs
  for the active brief — with an explicit empty-lineage state.
- **Honest download boundary preserved** verbatim (disabled button + "no asset
  store"); the "Bundle Builder" harness marker is intact.

### B — Creative Studio Library coherence (`07f3010`)
- Each collection now shows **sample inventory** (static, labelled) alongside
  **tracked-local** count derived from real `ns-creative-assets` records.
- **"Open tracked assets"** navigates to the Assets tab with the collection as
  the search query (real filtering; previously a toast).
- Metric tiles relabelled: structure (sample) / sample inventory / real local
  records / unreviewed.

### C — SocialPulse Presets depth (`9d70f18`)
- New `PLATFORM_PRESETS` (aspect + caption guidance + recommended formats) and
  `VOICE_PRESETS` (tone + use-when); `PLATFORMS`/`VOICES` derive from them so the
  composer selects cannot drift.
- **"Active draft preset"** summary (platform · voice · campaign) with a composer
  link; **"Apply"** sets the platform and opens the composer.
- Voice chips keep active state and show a tone/use description. The **"Brand
  Voice"** harness marker is intact.

### D — SocialPulse Channel-Fit depth (`9d70f18`)
- **Campaign-tied coverage strip**: channels the active campaign targets, their
  planned-post counts, and gaps.
- Per-channel cards are **scoped to the active campaign** (draft / past-review
  split), with `targeted` and `gap` signals and a **"Compose for this channel"**
  action that opens the composer with that platform.
- Coverage strip and cards **agree on gaps** (verified by assertion) — this fixed
  a scope mismatch (global vs campaign counts) caught during the visual pass.
- Heuristic / not-measured-performance boundary preserved; no analytics.

## Truth / readiness decisions
- Generation remains **PLANNED — NOT ARMED** (unchanged; no route/engine).
- SocialPulse **still does not publish**; presets/channel-fit are operator-applied
  editorial guidance, not platform rules or enforcement.
- **No fabricated exports, downloads, analytics, or asset-store capability**;
  bundle download stays disabled.
- No readiness inflation — rooms stay PARTIAL; AdPilot unchanged (SAMPLE).

## Originality safeguards applied
Reused the existing paper/pine design system and primitives (`filter-pill`,
`field`, `pill-*`). No reference-tool layouts/naming/styling. Room roles stay
distinct: Creative Studio = brief/lineage studio, SocialPulse = publishing
workflow, AdPilot = ad-ops.

## Tests / builds
- `npm run build` → 0 errors (note: SPA bundle now >500 kB triggers Vite's chunk
  size *warning*, not an error — flagged for a future code-split).
- `verify-smoke` **42/0** · `verify-guards` **11/0** · `verify-acceptance` **32/0**.
- `capture-creative-cluster.cjs` **56/0** (adds bundle-lineage, manifest, download
  boundary, library sample/tracked + open-nav, presets depth + apply, channel-fit
  coverage + gap consistency + compose nav).
- `git diff --check` clean.

## Screenshots
`northstar-os-ui/screenshots/session-creative-cluster-20261004/` (untracked):
`creative-studio-desktop-exports-coherence.png`, `creative-studio-desktop-library.png`,
`socialpulse-desktop-presets-depth.png`, `socialpulse-desktop-channel-fit.png`
(+ prior set, desktop + 390px).

---

## REPORT FORMAT

**Worktree:** `C:\Users\T2Hol\AppData\Local\Temp\opencode\ns-creative-social-polish-v2`
**Branch:** `feature/creative-cluster-launch`
**Base commit:** `8ba0c9e`
**Current commit:** `9d70f18`
**Subclusters completed:** A CS Exports coherence, B CS Library coherence, C SocialPulse Presets depth, D SocialPulse Channel-Fit depth
**Creative rooms/services updated:** Creative Studio (Exports, Library), SocialPulse (Presets, Channel-Fit)
**Truth/readiness decisions:** generation PLANNED/NOT ARMED; SocialPulse does not publish; no fabricated exports/downloads/analytics/asset-store; download boundary preserved; rooms remain PARTIAL
**Originality safeguards applied:** existing paper/pine system + primitives reused; no reference-tool layouts/naming/styling; distinct room roles retained
**Tests/builds run:** build 0 errors · smoke 42/0 · guards 11/0 · acceptance 32/0 · capture 56/0 · diff --check clean
**Screenshots captured:** exports-coherence, library, presets-depth, channel-fit (desktop) + prior desktop/390px set
**Remaining creative launch gaps:** image/video generation provider-gated; SocialPulse publishing/analytics provider-gated; AdPilot sample-static; SPA bundle >500 kB (chunk warning); `resolve_vision(local)` reports available without probing
**Blocked items:** owner decision to arm/allow local ComfyUI execution (unchanged gate)
**Recommended next action:** next cluster — Creative Studio **Variants & History depth** (request↔variant linkage + lineage filters) and SocialPulse **Workflow/Approvals depth** (bulk review, approval audit trail); alternatively approve the readiness-only `foundation/api/creative.py` route to make Provider Readiness a live probe
