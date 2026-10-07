# Northstar OS — Creative Services Build Plan

**Status:** proposal for owner selection · **Date:** 2026-10-06
**Scope:** the creative cluster (`Grow`: ListingForge, AdPilot, SocialPulse,
Creative Studio) plus the adjacent research rooms that feed it (Listing Guardian,
Keyword Tracker, Competitor Monitor) and the new **exact-text mockup lane**.
**Method:** static scan of `Northstar_backend/*`, `northstar-os-ui/src/**`,
`docs/{SERVICE_GAPS,SERVICE_READINESS_MATRIX,CREATIVE_MEDIA_STACK,UI_UX_BLUEPRINT_NORTHSTAROS,PRODUCTION_BLUEPRINT}.md`.

> Companion docs: `SERVICE_GAPS.md` (gap taxonomy), `SERVICE_READINESS_MATRIX.md`
> (what works locally), `CREATIVE_MEDIA_STACK.md` (providers/cost),
> `NORTHSTAR_IMAGE_TEXT_WORKFLOW.md` (the exact-text standard).

---

## 1. Where we are (evidence-based inventory)

The recurring pattern across the creative cluster is: **the backend logic already
exists, but it is not routed, not tested, and not wired to the room.** Each room
is functionally a shell with a `tone="sample"` banner.

| Creative service | Room | Backend module (exists) | Routes today | Tests | Nav status | Real readiness |
|---|---|---|---|---|---|---|
| **ListingForge** | `/listingforge` | `listing_forge.py` — title/bullets/description/backend-terms/search-terms + scoring + compliance + local-LLM w/ template fallback | **none** | **none** | Concept | `sample` |
| **SocialPulse** | `/socialpulse` | `social_pulse.py` — brand voice, captions, 30-day calendar, review-request email, influencer outreach, hashtags, scoring (Ollama + deterministic fallback) | **none** | **none** | Concept | `sample` |
| **AdPilot** | `/adpilot` | `ad_pilot.py` — bid optimizer w/ guardrails, keyword-tier classifier, negative candidates, campaign structure, budget allocator, target ACoS | **none** | **none** | Concept | `sample` |
| **Creative Studio** | `/creative-studio` | `creative/` (new) — exact-text compositor + ComfyUI Qwen lane + presets | `/api/creative/*`, `/mogra-mockup` | 58 | Concept | `partial` (mockup lane real) |
| **Listing Guardian** | `/listings` | none (needs live listing source) | none | — | Sample | `sample` |
| **Keyword Tracker** | `/keyword-tracker` | foundation `/keywords/**` (substantial) | foundation | — | Partial | `partial` |
| **Competitor Monitor** | `/competitor-monitor` | none (needs competitor source) | none | — | Sample | `sample` |

**Model map already assigns these** (`shared/service-model-map.json`):
`listingforge` T2 + media V2/V3, `socialpulse` T2 + media V1/V3, `adpilot` T2,
`creativestudio` T2 + media V2/V3. `listing_forge.addition`/`social_pulse` already
carry a local-LLM path with a deterministic template fallback — i.e. they can run
**fully offline today**.

**Readiness source of truth:** `northstar-os-ui/src/data/readiness.js` deliberately
omits the creative rooms ("owned by the creative session"). This plan is the
creative session's answer; the rooms get a truthful label per room *only once
wired* (no readiness inflation).

### What the exact-text lane already delivered
`creative/` gives a real, tested, local capability: Qwen scene lane, deterministic
exact-text compositor, brand guard, bundled brand fonts, auto label-zone
alignment, Edit-2511 panel prep, `/api/creative/*`, a standalone page, and a
Creative Studio tab. This is the reusable spine the other rooms should build on.

---

## 2. The gap pattern → the cheapest high-value move

For ListingForge / SocialPulse / AdPilot the work is the **same shape** the
mockup lane already proved:

1. **Route** the existing module as a local-first API (`/api/<service>/*`).
2. **Wire** the room to it (replace sample data with real calls + empty states).
3. **Test** (offline unit + route tests) and **assert** in the UI harnesses.
4. **Label** the room honestly with the shared truth taxonomy.

No external provider is required for steps 1–4 — the modules run offline via the
template fallback and upgrade to the local LLM (Ollama) when present.

---

## 3. Automated build plan (autonomously buildable)

> Each phase is `route → wire → test → harness → docs`, mirrors existing
> conventions, and is **additive** (no auth/schema changes unless listed as gated).

**Phase 0 — Shared creative API foundation** (no approval)
- One `creative` router pattern: `/api/<service>` with `{ok, data, basis}` envelopes,
  consistent `provider_required` / `offline` states, and the truth-state tags.
- Shared local output dir + manifest conventions (reuse `creative/_stamp`, sidecars).
- Register routers additively in `main.py` (exactly like `mount_creative`).

**Phase 1 — ListingForge lane** (highest value; pure logic; offline)
- Routes: `POST /api/listing-forge/generate` (title, 5 bullets, description,
  backend terms, search terms), `POST /api/listing-forge/score`,
  `POST /api/listing-forge/compliance`, `GET /api/listing-forge/templates`.
- Wire the Editor tab: draft canvas, generate/save revision, keyword coverage,
  score breakdown, compliance warnings; version log.
- Media prompt hand-off → exact-text lane for A+ imagery prompts.

**Phase 2 — SocialPulse lane** (offline; high demo value)
- Routes: `POST /api/social/generate` (captions/hashtags per platform),
  `POST /api/social/calendar`, `POST /api/social/review-email`,
  `POST /api/social/outreach`.
- Wire Composer + Calendar + Presets to real generation; queue/approval states
  become real local records; analytics stay `SAMPLE/UNKNOWN` until a provider exists.

**Phase 3 — AdPilot lane** (planning-only, no spend)
- Routes: `POST /api/ad-pilot/bid-recommendation`, `/classify-keywords`,
  `/negative-candidates`, `/campaign-structure`, `/budget-allocation`, `/target-acos`.
- Wire Search Terms table, bid cards **with rationale + basis + confidence**,
  planner with an explicit BASIS column. **Recommendation-only** language — the
  room must not imply autonomous spend.
- Amazon Ads API (OAuth, real spend) is **out of scope unless separately approved**.

**Phase 4 — Creative Studio deepening**
- Asset registry + variant sets + export bundles (local manifest, real records).
- Tie variants to the exact-text lane; A+ module imagery presets; comparison-chart
  and hero-image presets.
- Campaign bundle → hand-off to SocialPulse / ListingForge.

**Phase 5 — Cross-room exact-text reuse**
- Same compositor serves: A+ imagery (ListingForge), ad creatives (AdPilot),
  social images (SocialPulse), hero/banner/UI-annotation (any service).
- Add per-surface presets (A+ module sizes, IG/TikTok/Reels canvas, banner sizes).

**Phase 6 — Visual parity + polish** (see §5) and **Phase 7 — tests/harnesses**
for every wired room (add deep-links + action assertions, like the mockup lane).

---

## 4. OWNER APPROVAL GATES (need a selection to proceed)

These are the only true gates. Everything in §3 Phases 0–2 and 4–7 that touches
**no external provider, no real money, and no public exposure** can run
autonomously once selected.

| # | Gate | Options | Why it's a gate |
|---|---|---|---|
| G1 | **Service selection** | Which rooms to build this pass | Operator priority |
| G2 | **Media provider policy** | local-only vs allow cloud finals | cloud = paid keys ($0.015–0.18/img) |
| G3 | **Video generation** | in / out | real money ($0.05–0.14/s) + SynthID disclosure |
| G4 | **Media storage** | local FS only vs object store | uploads/exports at scale |
| G5 | **Moderation/safety policy** | adopt a prompt/ad allowlist + review step? | `SERVICE_GAPS §8` has none today |
| G6 | **Publishing / Ads write** | keep off (default) vs approve OAuth + spend | public posting / real ad spend |
| G7 | **Brand inputs** | supply Mogra typeface + brand-voice samples? | exact typography / voice fidelity |

---

## 5. Visual parity plan — look like the best comparable tools

Design law stays the SIGNAL system (`UI_UX_BLUEPRINT §Visual language`): warm
paper/bone, pine/forest ink, restrained ochre/clay, serif for editorial emphasis
only, **no dark-neon, no glassmorphism, no AI glow**. Beauty from proportion,
hierarchy, spacing rhythm, and room-specific composition.

Per room, the comparables and what to match (then beat):

| Room | Closest comparable | What to match (parity) | Parity gaps to close now |
|---|---|---|---|
| Creative Studio | Canva / Figma / **Flair.ai** / Photoroom | canvas + trays + variant gallery + export bundles | real thumbnails, drag-free trays, variant compare, export manifest |
| SocialPulse | Buffer / Later / Hootsuite | month calendar, queue board, platform previews, approvals | real month grid, real post previews, stage board, schedule records |
| ListingForge | Helium 10 **Scribbles** / Jungle Scout Listing Builder | editor-first, keyword coverage, score, versioning | editor canvas as the star, coverage matrix, revision diff, compliance chips |
| AdPilot | Teikametrics / Perpetua / Advigator | trading desk, search-terms table, bid cards, planner | rationale cards, BASIS column, truthful rollups, no spend implication |
| Listing Guardian | Keepa / SellerApp alerts | change feed, escalation queue | real change timeline once a source exists |
| Keyword Tracker | Helium 10 Cerebro / Magnet | coverage, trends, gaps | wire the room to the existing foundation keyword routes |
| Competitor Monitor | Keepa / Rival | watchlist + deltas | needs a data source (gated) |

Suite-level visual upgrades (apply to every creative room):
- **Real data previews** everywhere (generated images/thumbnails, not grey boxes).
- **First-class empty states** (the blueprint's #1 complaint: "must not feel empty or generic").
- **Truth pills** systemized in tables/cards/rails (already in the taxonomy).
- **Restrained motion**: ≤200 ms fades/slides only; no decorative animation.
- **Density control** and consistent spacing rhythm across rooms.

---

## 6. Beyond-parity plan — features competitors do not have

1. **Exact-text guarantee.** Every text-on-image asset is composited
   deterministically (brand guard refuses invented seals/UPCs/nutrition). No
   competitor guarantees exact packaging text — this is the differentiator.
2. **Local-first, $0 marginal generation.** Draft and often finish with the local
   Qwen/FLUX lane; cloud is optional finals only.
3. **Truth-state taxonomy as UX.** UNKNOWN / VERIFIED / ASSUMPTION / OBSERVED…
   surfaced as first-class UI, not hidden.
4. **Closed agent loop.** SourceScout → ListingForge → SocialPulse → AdPilot feed
   each other (keywords, COGS, creative) — no siloed tools.
5. **Amazon-native asset presets.** Main image, A+ modules, comparison charts,
   hero/banner, IG/TikTok/Reels canvases — sized and texted for each placement.
6. **Regenerable assets.** Every output carries a JSON sidecar (quad, curvature,
   style, copy) so any asset can be rebuilt exactly.
7. **Batch + brand consistency.** One brief → many sized variants with identical
   brand typography and packaging text.
8. **Compliance-first copy.** Rule-based compliance + Rufus-readiness scoring.
9. **Test/harness-backed rooms.** Each wired room ships with assertions (a level
   of rigor most competitor tools never expose).

---

## 7. Execution batches (what "continue" would do)

- **Batch A (autonomous, on selection):** Phase 0 + ListingForge + SocialPulse +
  AdPilot local APIs, room wiring, tests, harness assertions, docs. No provider,
  no spend. Rooms labelled truthfully afterward.
- **Batch B (autonomous):** Creative Studio deepening (assets/variants/exports) +
  Phase 5 cross-room exact-text presets.
- **Batch C (autonomous):** visual polish pass (§5) + novel DataViz/empty states.
- **Batch D (GATED):** cloud finals (G2), video (G3), storage (G4), moderation (G5),
  publishing/ads (G6) — only after a named approval.

---

## 8. Risks / honesty

- No readiness inflation: a room gets `Local` only when the visible page truly
  calls a working local route; otherwise it stays `Concept`/`Sample`/`Partial`.
- Provider-gated features ship as clearly-labelled `provider_required` surfaces,
  never as fake "complete".
- The exact-text rule is never weakened; AI text is never final packaging text.
- Local-only stays local-only; no public exposure without a separate decision.

---

## 9. Approved scope (owner decisions, 2026-10-06)

Owner directives recorded:

| # | Decision | Owner's answer | Consequence |
|---|---|---|---|
| G1 | Services | **Everything** — build out every creative service/feature; stop only to choose | Full program: ListingForge, SocialPulse, AdPilot, Creative Studio, Keyword Tracker, Guardian, Competitor Monitor |
| G2 | Media providers | **Local *and* cloud, both fully usable** | Local ComfyUI lane + fal/OpenRouter/Replicate clients, each armed independently |
| G3 | Video | **In scope (later)** | Video lane designed; built after images |
| G4 | Storage | **Add object store** | `creative/storage.py`: local backend (default) + S3-compatible backend |
| G5 | Moderation | **Adopt allowlist + review step** | `creative/moderation.py`: deterministic deny rules + `review_required` on generated creative |
| G6 | Publishing / ad spend | **Design OAuth + approval; enable write actions** | Write paths built and wired, armed only by explicit env flag + per-action approval |
| G7 | Brand voice / fonts | **Build the full upload path** (customers upload their own too) | `POST /api/social/brand-voice` → `memory_bank`; `load_brand_voice` picks it up |

**Live-action guardrail (kept explicit).** Real-money ad spend and the first
public post are the two actions the constitution still gates at the *moment of
arming*. Both paths are built and wired, default-OFF
(`NORTHSTAR_ADS_WRITE_ARMED`, `NORTHSTAR_SOCIAL_PUBLISH_ARMED`), each requiring a
fresh per-action approval. "Enable" is therefore a one-switch + one-confirmation
action when the owner says go.

### Progress

**Batch A — backend lanes: DONE (commit pending).** Built and tested:
- `creative/moderation.py` — allowlist + deny rules (word-boundary; refuses invented
  seals/nutrition/UPC) + `review_required`.
- `creative/storage.py` — local + S3-compatible backend behind one interface;
  honest `storage_status()` (no secret reads).
- `creative/providers.py` — local + cloud readiness (presence-only), arming flags,
  `write_policy()`.
- `creative/service_routes.py` — `/api/listing-forge/*`, `/api/social/*`
  (+ brand-voice upload), `/api/ad-pilot/*`, `/api/creative/capabilities`.
- Public helpers added: `listing_forge.score_listing/check_compliance`,
  `social_pulse.save_brand_voice`.
- 23 new offline tests (81 total across the creative suite); live smoke green;
  UI harnesses unchanged (smoke 43/0, mockup-lane 6/0, acceptance 33/0).

**Batch A continued — room wiring: DONE.** Each creative room now has a
**Local Lane** tab that calls its real API end-to-end:
- ListingForge → title/bullets/description/terms/score/compliance (`?view=lane`)
- SocialPulse → captions + **brand-voice upload** (`?view=lane`)
- AdPilot → bid recommendation + target ACoS, recommendation-only (`?view=lane`)
Added a fast template-only path (`use_llm=false` per request, or
`NORTHSTAR_CREATIVE_LLM=0`) so drafts are instant when the local LLM is busy.
New harness `verify-service-lanes.cjs` (3/0) drives each lane against the real
API. Fixed a real render crash (search-terms string vs array). Suite now:
pytest 81; harnesses smoke 46/0, acceptance 36/0, guards 11/0, mockup-lane 6/0,
service-lanes 3/0, invite-flow 11/0.

**Batch B — Creative Studio deepening: DONE.** Local asset registry + export
bundles over the storage layer:
- `creative/assets.py` — file-backed index (`assets.json`) over the media root:
  register / list / get / **variant sets** (grouped by product+container) / `scan`.
- `creative/bundles.py` — packages selected assets into a ZIP (manifest + files),
  stores it via the storage backend, registers it as a `bundle` asset.
- API: `/api/creative/assets` (list + sets), `/api/creative/assets/scan`,
  `/api/creative/assets/register`, `/api/creative/bundles` (create/list);
  the file route now serves correct MIME types (ZIP downloads work).
- The exact-text lane **auto-registers** every mockup it produces, so the registry
  and variant sets populate as you work.
- UI: new Creative Studio tab **Registry & Bundles** (`?view=registry`) — thumbnails,
  variant sets, multi-select → Create Bundle → download ZIP.
- Tests: +11 (92 total). Harnesses: smoke 47/0 (+1 registry deep-link), acceptance
  36/0, guards 11/0, mockup-lane 6/0, service-lanes 3/0. Live: scan indexed 33
  assets, a 3-asset bundle produced a downloadable 1.14 MB ZIP.

**Batch D — cloud / video / approvals / uploads: DONE (backend + surface).**
- `creative/cloud.py` — fal / OpenRouter / Replicate image clients, **gated**
  (key present + `MEDIA_GEN_LIVE=1`); pure request builders; cost estimates.
- `creative/video.py` — fal video spec (Wan / FLUX-3 draft / Kling 2.6 / Kling v3
  i2v / Veo 3.1-fast), per-second cost, watermark flags, gated submit.
- `creative/approvals.py` — local **write-action approval queue** for
  `social_publish` / `ads_write`: request → decide → execute, audit-logged, honest
  `write_actions_disarmed` / `not_approved` / `no_live_client` results.
- API: `/api/creative/cloud/generate` (503 until armed), `/api/creative/video/*`,
  `/api/creative/approvals*`, `/api/creative/assets/upload`.
- Tests +21 (113 total).

**Batch C — visual polish: DONE (core primitives).**
- Shared `EmptyState` + `SectionHeader` primitives; `.empty-state` and restrained
  `.fade-in` motion (respects `prefers-reduced-motion`).
- New Creative Studio tab **Cloud & Approvals** (`?view=cloud`): arming posture
  (local + cloud + write flags), video cost estimator, and the write-action
  approval queue. Harness deep-link added.

Live: video estimate `kling-2.6-pro` 15s+audio → **$2.10**; cloud generate →
**503** (gated, not armed); approval `ads_write` → approved → execute →
`write_actions_disarmed` (honest). Suite: pytest **113**; harnesses smoke **48/0**,
acceptance 36/0, guards 11/0, mockup-lane 6/0, service-lanes 3/0.

**Adjacent rooms: DONE.** Real local capability (no live data source needed):
- `creative/listing_guardian.py` — **Listing Guardian audit** of pasted listing text
  (weighted checks: title length, bullets, description, keyword coverage,
  compliance) via the ListingForge engine. `/api/listing-guardian/audit`.
- `creative/competitor_monitor.py` — **Competitor Monitor watch desk**: add
  competitors, record snapshots, exact deltas between snapshots (fields absent in
  the newest snapshot are reported as `not_reported`, not as changes).
  `/api/competitor-monitor/watchlist*`.
- UI: **Local Lane** tabs in Listing Guardian (`?view=lane`) and Competitor Monitor
  (`?view=lane`).
- Tests: +10 (123 total). Harnesses: smoke **50/0** (+2), acceptance 36/0, guards
  11/0, mockup-lane 6/0, service-lanes 3/0. Live: guardian audit `attention` 4/5;
  competitor deltas price −3.00, rank −32.

**Next:** wire Keyword Tracker to the existing foundation `/keywords` routes; then
the remaining parity polish per §5 (real previews, density, light data-viz) and a
S3/MinIO parity test for the object-store backend.
