# Creative Studio + SocialPulse — Local Service Status

> Branch: `feature/creative-social-local` · Scope: local service-specific room
> completion for **Creative Studio** (`/creative-studio`) and **SocialPulse**
> (`/socialpulse`) in `northstar-os-ui`. No backend router, data-rights, Golden
> Goose, Product Finder, keyword, private-beta, or deployment files were touched.
> Last updated: 2026-09-30.

This document separates **what is genuinely functional locally** from
**demo/UI-only surfaces** and **what requires an external provider**. It is the
source of truth for the honesty boundary these two rooms enforce.

---

## 1. Working local capabilities (real, persisted in the browser)

Both rooms use an isolated `localStorage`-backed room store (`ns-creative-*`,
`ns-social-*`). These are genuine operator records the room creates and keeps —
not provider output, and not reset on reload.

### Creative Studio
- **Work briefs** — create, list, select, and open briefs; each carries objective,
  audience, brand, formats, deliverable count, and state.
- **Image request composer** — prompt/work-brief input, brand/context, output
  format, aspect, resolution, staging tier, and reference-asset attachment.
  Queueing produces a **real local request record**.
- **Production queue** — real record list with honest states. Because no provider
  is connected, requests land in the terminal state **“Blocked — provider
  required”** and can be moved to `Queued` / `Error` to exercise those paths.
  No request ever reaches a fake “Complete”.
- **Variants & history** — add variant records with real review state
  transitions (`Draft` ↔ `Changes Requested` ↔ `Approved`) and a merged local
  history log of requests + variants.
- **Reference assets** — local asset metadata with type/collection/state and
  brief-attachment state (`Attached to …` / `Not attached`).
- **Export bundles** — bundle builder produces a **local manifest record**
  (references only) and real handoff navigation to SocialPulse / ListingForge.
- Empty, blocked, and restricted states are explicit throughout.

### SocialPulse
- **Campaigns** — create/list/select campaigns (objective, audience, channels,
  state) with a per-campaign post count.
- **Content records** — genuine workflow transitions
  `Draft → In Review → Approved → Publish-ready → Scheduled`, in Board and List
  views. Every transition is a local state change with an explanatory note.
- **Composer** — operator-authored hook/caption with local save (creates a real
  `Draft` record), platform + voice presets, and a live platform preview.
- **Channel Fit** — per-channel format/aspect/strength guidance, explicitly
  labeled **heuristics, not measured performance**.
- **Asset Library** — metadata + attachment state to posts; upload is honestly
  declared unavailable.
- **Presets** — platform presets and brand-voice/format presets that apply to
  the active draft.
- **Approvals** — derived from `In Review` records; approve/request-changes are
  real local transitions.
- **Analytics** — local workflow counts (real) alongside `UNKNOWN` provider
  metrics.

**Holds in both rooms:** nothing is generated, published, uploaded, downloaded,
listed, or transmitted. Approval/state changes are internal review states only,
never purchase, budget, or publishing authorization.

---

## 2. Demo-only / UI-only capabilities

- **Seeded sample records.** First load seeds demonstrations records (3 briefs,
  6 assets, 5 variants; 3 campaigns, 6 posts, 6 assets). After the operator adds
  their own, the seeds remain as examples — they are labeled sample and are not
  fabricated *provider* data.
- **Creative collections library** counts (24/38/17/8) are static **sample
  inventory**, not a real asset index.
- **SocialPulse calendar grid** is a September-2026 planning mock; only posts
  with a manual reminder string appear on it.
- **“Copilot” suggestions**, **Generate Variants**, **Schedule**, **New
  Campaign**, **New Brief**, **Upload Asset**, and **Download Bundle** are
  UI-only affordances: they toast an honest boundary or create a local record,
  but perform no external action.
- **AI/assisted copy** does not run in these rooms. Suggestions are static
  prompt ideas; the composer copy is operator-authored.

---

## 3. External provider / model requirements

### Images (Creative Studio)
No image provider is wired to this UI. The repo does contain a **real local
image CLI** — `tools/generate_images.py` — supporting:
- `local` → **ComfyUI** at `COMFYUI_URL` (default `http://127.0.0.1:8188`),
  models per `docs/LOCAL_IMAGE_GEN_SETUP.md` (FLUX.2 klein / FLUX.1 dev / etc.);
- `pollinations` (keyless), `cloudflare` (Workers AI), `huggingface`.

`Northstar_backend/model_router.resolve_vision()` resolves local generation to
`comfyui` and gates **all** media generation behind `MEDIA_GEN_LIVE=1`;
`Northstar_backend/foundation/data_rights.py` still lists `image_generation` as
“(planned)”. Cloud/final tiers per `docs/CREATIVE_MEDIA_STACK.md` (fal: FLUX.2
pro, Kling, Wan, Veo; OpenRouter: GPT Image 2).

The room's **Provider Readiness** checklist states these requirements explicitly
and shows **0/4 ready** until they are satisfied — it does not claim they exist.

### Video (Creative Studio)
**No video pipeline exists in the repo.** The video/shorts surface is a planning
shell only; rendering requires a connected provider (e.g. fal: Kling / Wan /
Veo) plus `MEDIA_GEN_LIVE=1`.

### Social copy (SocialPulse)
A real brand-aware generator exists — `Northstar_backend/social_pulse.py`
(local Ollama at `OLLAMA_HOST` with a deterministic template fallback) — but it is
**not exposed through the API and not wired to the UI**. The composer states this
boundary instead of presenting generated copy.

### Social publishing / analytics (SocialPulse)
**No social OAuth, publishing, or analytics provider exists.** Reach,
engagement, follower, and “top platform” surfaces read `UNKNOWN`.

**Wiring gap (why nothing reaches the backend):** the only HTTP client these
rooms could use is the foundation router, which exposes **no** creative/social
route, and the room/navigation harnesses stub `fetch` to foundation routes only.
Bridging requires a new backend router module *plus* an API client method — out
of this branch's scope (router is do-not-touch).

---

## 4. Unanswered product decisions

1. **Provider strategy for images** — wire the existing local ComfyUI CLI as the
   first real backend, or go straight to a metered cloud tier (fal/OpenRouter)?
   Local-first matches the “Local = first deployment environment” principle but
   needs GPU/model provisioning confirmed on the pilot machine.
2. **Where generation runs** — a new dedicated creative router (mirroring
   `foundation/api`) vs. extending the foundation router. Affects org/approval
   scoping and the harness stubs.
3. **Async model** — generation is long-running; should it use the existing
   `jobs-durable` queue (real, already exposed) or a new media-specific queue?
4. **Asset storage** — bundles currently hold references only. Is there an asset
   store (local FS / object store) for real media before download is enabled?
5. **Approval semantics** — should SocialPulse approval tie into the existing
   approvals/permissions model, or remain a room-local review state?
6. **Video budget** — per-second video cost is real money; confirm the caps and
   the approval gate before any video backend is armed.

---

## 4b. Owner-leaning defaults (NOT implemented — recorded as notes only)

> Status: **directives for a later merge/integration decision, not implemented
> facts.** Nothing below is wired, and none of it changes the honesty boundary
> described above. Recorded 2026-09-30.

1. **Images — prefer local ComfyUI as the first backend.**
2. **Router — prefer extending the existing foundation router** before adding a
   new dedicated creative router.
3. **Queues — prefer reusing `jobs-durable` for render queues** if no hard
   mismatch appears.
4. **Assets — an asset store remains a later required layer** before full
   creative export/upload maturity.
5. **Approvals — SocialPulse approvals should ultimately align** with broader
   platform approval concepts.
6. **Video — remains disabled** pending explicit provider + spend-cap approval.

**Hold posture:** branch `feature/creative-social-local` is held as-is pending
(a) main-session shared integration work, (b) the audit-session readiness matrix,
and (c) a later merge/cherry-pick decision. No provider wiring, publishing,
analytics, or video spend paths are to be implemented under this branch.

---

## 5. Recommended next backend integration order

1. **Expose the local image CLI as a real backend route** (new module, e.g.
   `foundation/api/creative.py`, registered alongside the foundation router) with
   `MEDIA_GEN_LIVE` defaulting **off**, returning `provider_required` when the
   engine is unreachable. Flip the room's Provider Readiness from static to live.
2. **Wire `model_router.resolve_vision` into that route** so tiers (draft/final)
   and cost estimates are authoritative; keep `MEDIA_GEN_LIVE=0` until a named
   operator approves the first render.
3. **Back image requests with `jobs-durable`** so queue/progress/error states are
   real server-side jobs rather than local records.
4. **Expose `social_pulse.py`** (caption/hashtag/calendar/email/outreach) behind
   the same router; keep the template fallback as the honest offline path.
5. **Add an asset store + download** once media exists; enable the currently
   disabled bundle download and asset upload.
6. **Analytics integration last** — only after a social analytics provider is
   selected; until then the `UNKNOWN` surfaces stay.

---

## 6. Verification (this branch)

- `npm run build` → **0 errors** (Vite, 88 modules).
- `verify-smoke.cjs` → **42 passed, 0 failed** (all room deep-links + wired
  actions, including Creative Studio `Add Variant` / `Bundle Builder` and
  SocialPulse `Platform Preview` / `Brand Voice` / `Drafts`).
- `verify-acceptance.cjs` → **32 passed, 0 failed** (role guards, deep-links,
  primary actions, Creative Studio “New Brief” toast, SocialPulse
  “Draft Post” → composer, SocialPulse send-to-approvals honesty toast).

Both harnesses run against the local preview server with stubbed foundation
`fetch`; no external accounts or providers are contacted.

---

## 7. Creative-cluster update (2026-10-04, branch `feature/creative-cluster-launch`)

Additions on top of the above; honesty boundary unchanged (nothing publishes,
nothing renders, no analytics):

- **Creative Studio — Ad Creative tab (Ad Creator role).** Hook / offer / CTA +
  audience + placement targeting (Top of Search, Product Pages, Reels / Shorts,
  Stories, Social Feed). “Build Ad Set” records one placement-aware variant per
  selected placement; variants move through local Draft → Changes Requested →
  Approved; Placement Fit is labelled **editorial guidance, not measured
  performance**; handoff to AdPilot / SocialPulse is reference-only. No ad is
  generated, no account is connected, nothing authorizes spend.
- **Creative Studio — image composer** gains a **Style direction** control
  recorded on each local request; **Generate Variants** now records 3 draft
  variant rows for the active brief instead of duplicating “Queue Image Request”.
- **Creative Studio — Video / Shorts** gains a local **storyboard beat list**
  (numbered beats, per-beat seconds, total duration); no clip is generated.
- **Creative Studio — Briefs** are editable (name/objective/audience/brand/
  deliverables) as real local records.
- **Creative Studio — Assets** gains search (name/collection) and a
  **Use as reference** handoff into the composer.
- **SocialPulse — New Campaign** creates a real local campaign record.
- **AdPilot** Campaigns badge derives from the real row count; “Bulk Actions” is
  wired to an honest approval/tracking boundary (was dead).
- **Shared CSS** — `.filter-pill` is a global styled chip (base/hover/active/
  focus); creative-room card grids stack to one column at ≤480px.

These remain **local records only**. The provider-dependent capabilities in §3
(image/video generation, publishing, analytics, asset store) are unchanged and
still gated on the decisions in §4/§5.

---

## 8. Media-generation truth verification (2026-10-04)

Verified against the repo and the running environment:

- A local image **CLI** exists (`tools/generate_images.py --backend local` →
  ComfyUI at `COMFYUI_URL`), and `shared/model-suite.json` maps V1/V2/V3
  generation to `comfyui:flux2-klein-4b`. **However, no HTTP route exposes it to
  the app, no local engine is reachable, and `MEDIA_GEN_LIVE` is off.** Image and
  video generation are therefore labelled **PLANNED — NOT ARMED**, not merely
  "provider required".
- Creative Studio now shows an explicit 4-state generation legend (**local
  available · provider-gated · demo-only · planned/not-armed**) and a **static**
  Provider Readiness checklist (5 items, including "generation route exposed to
  the app"), explicitly labelled *not live-probed*.
- **Not viable yet in this environment.** Arming requires the owner to install
  ComfyUI + weights, add a media route, and set `MEDIA_GEN_LIVE=1`. The doc's §5
  recommended route (`foundation/api/creative.py`, `MEDIA_GEN_LIVE` default off,
  `provider_required` when unreachable) remains the minimal safe next step.

---

## 9. Autonomous creative build pass (2026-10-04)

Eight clusters were executed on branch `feature/creative-cluster-launch`
(`be6e815` → `1ca70ef`), all local and truth-preserving:

- **Creative Studio:** Variants & History lineage (request↔variant, filters,
  history filters); Production Queue Brief column + "Add variant"; Ad Creative
  placement/state filters + Brief column + review trail; **local handoff log**
  (reference-only) with an Exports "Handoff log"; Video/Shorts Caption/overlay +
  Export intent recorded on the clip request.
- **SocialPulse:** per-post **workflow audit history**, board "Last:" line,
  Approvals **multi-select bulk review** + "Recent decisions" trail; room-level
  "Generate Variants" now records variant draft posts; Workflow List "Last
  transition"; Asset Library "Creative references received" (read-only);
  Analytics "Local workflow by channel" breakdown.
- **AdPilot:** read-only "Creative handoffs received" panel (closes the
  creative→ad-ops handoff loop).
- **Mobile:** 22 creative tabs verified at 390px with zero horizontal overflow.

**Truth posture unchanged:** generation PLANNED/NOT ARMED; SocialPulse does not
publish; no analytics provider; all new state is local workflow/reference
records. Rooms remain PARTIAL/SAMPLE — no readiness inflation. See
`reports/creative_autonomous_pass_20261004.md`.

---

## 10. Generation readiness route (2026-10-04)

Creative Studio's Provider Readiness is now backed by a **read-only**,
provider-neutral route: `GET /api/v1/foundation/creative/readiness`
(`foundation/api/creative.py`; mounted additively in `foundation/app.py` and
`main.py`). It returns only safe status metadata — generation state
(`local_available` / `provider_gated` / `planned_not_armed` / `unavailable` /
`probe_failed`), `armed`/`media_live` booleans, the configured backend id, local
engine `reachable|unreachable|unknown`, a cloud-key **presence** boolean, reason,
and `checked_at`. It returns no secrets, tokens, env values, URLs, or provider
configuration, and performs no generation/upload/publish/transfer.

The only probe is a bounded (0.3 s) **localhost** reachability check of the
operator's own engine (default ComfyUI at `COMFYUI_URL`). It never installs,
starts, loads a model, arms `MEDIA_GEN_LIVE`, or contacts a provider.

**Readiness does not equal activation.** `MEDIA_GEN_LIVE` remains false, no
render/generation route exists, no provider is called, and no credits are
consumed. The UI shows the live contract when reachable and otherwise falls back
to the static checklist with an explicit "route not reachable" note. See
`reports/creative_generation_readiness_20261004.md`.
