# NORTHSTAR AUTOTHINK — MODE PLAN (the "sport mode" of Simple)
**Version:** 1.0 · **Date:** 2026-10-24 · **Status:** Planned build
**Basis:** `Northstar_AutoThink_UI_Design_Guide.md` (Spatial Canvas direction),
`05_autothink_surface.md`, `v3_s5_autothink_backend_20261018.md`,
`v3_s5_autothink_ui_20261018.md`, 00_STATE.json, operator brief 2026-10-24
("standalone view of Simple mode; same visual family but lighter, with real
movement — shooting stars, asteroid fields; like flipping a car into Sport").

---

## 1. WHAT AUTOTHINK IS (from the project's own docs)

Tier-2 premium **"build-anything"** layer. The user says what they want; the
Master Brain automates, builds, and delivers end-to-end — pulling whatever
services are needed (comparables named in the plan: Perplexity Computer,
Claude Code). General questions get full detailed answers here too — AutothinK
is the deepest surface, not a seller tool.

Already built and tested today:
- **Workbench panel** in the Simple shell: Plan · Artifacts · Runs drawer,
  honest empty/missing states (28/0 gate scenario F).
- **Plan graph** reconstructed from real turn/tool evidence as a true linear
  chain (prompt → step 0 → … → answer) — the deep-visual node-link
  constellation version is explicitly the next visual pass.
- **Run panel:** bounded run ledger, registered at turn start, honest cancel
  (finished runs refuse pretended stops).
- **Artifact browser:** name/kind/size, `present:false` honesty on missing
  assets, download support.
- **Session fork/rewind** (non-destructive copy-up-to-message with lineage).
- **Handover:** pause mid-stream, operator drives, resume hands control back.
- **Six work foci** + separate BUILD presets, server-enforced tool subsets.
- **Voice** (dictation) and VoiceStudio adapter (cloning/TTS/dub hooks).
- The standalone server UI at :8100 (913 lines) — slated for
  redirect/deprecation into this React surface (decision C2; this plan assumes
  it lands so there is ONE AutothinK).

## 2. THE AUTOTHINK THEME — "Sport mode", not dark mode

Same Simple galaxy family, visibly different behavior. The job-to-be-done is
*energy*: Simple is the cruise; AutothinK is the light-foot.

| Element | Simple Mode | AutothinK |
|---|---|---|
| Palette | deep navy void, film-gold disc, restrained | lifted/expanse blues and pale starlight — lighter background wash, same `--gold` family, no red-alert tones |
| Hero | one fixed hero body per vista | **moving field**: meteor paths, drifting asteroid belts, recurring comet passes |
| Motion budget | sparse ambient + event moments | continuous gentle motion; streaks on EVERY tool step, not just completion |
| Signature object | Gargantua (still, massive) | a **traveling starfield** — slow forward drift, duties feel like flight |
| Density | one reading column | reading column + workbench drawer flies in from the side with a star-trail transition |

**Light-speed transition (kept from the design guide, tamed):** switching into
AutothinK focus triggers one 600–800ms star-trail "warp" — then immediately
settles. It must be delightful the 50th time, so it is short, single-shot, and
skipped under reduced-motion.

**Plan graph as a true constellation:** the immersive node-link graph (already
built as ImmersivePlanGraph SVG/CSS) becomes the AutothinK default — nodes as
stars, self-drawing edges as the run unfolds, one self-drawing arc per tool
step mirroring the actual linear chain (honesty rule: no fake branches — if the
opus is linear, the constellation is a voyage line).

## 3. WHAT AUTOTHINK DOES — capability map to fill out

| Capability | State today | Plan |
|---|---|---|
| Conversational build requests | live | keep; mission-brief framing from Simple |
| Tool fleet via six foci | live, server-enforced | unchanged surface |
| Plan graph | functional chain live; immersive graph built, default here | finish deep-visual pass, make constellation the hero |
| Run panel | chat-turn rows | next refinement: per-tool run rows with timings |
| Artifact browser | live | add one-click "send to Simple session" handoff |
| Session fork/rewind | live | "slingshot" interaction from Simple plan |
| Handover (pause → operator → resume) | live | promote to first-class control in the header |
| REA capture loop | harness built, operator-gated | keep gated; surface captures as evidence in the workbench |
| Voice | dictation | shares Simple's labeling decision (C1) |
| Utility apps (BOJO-UTIL) | live | artifacts slide INTO the stream as cards |
| Memory bank integration | knowledge plane exists | opt-in "remember this" control with visible confirmation |
| Cloud tier engine | gated, unarmed | never shown as available until armed + licensed lane |

## 4. ENTRY + BRANDING
- Focus chip in Simple: switching to AutothinK = the "sport mode" moment
  (warp transition, palette lift, motion begins). Switching back = settle.
- Name styling stays **AutothinK** (capital A, capital T) everywhere.
- Telemetry chip stays: VRAM reserve warning, engine state — AutothinK is the
  most resource-hungry surface and says so honestly.
- Costs: every cloud/metered lane action presents the approval sheet; local is
  default; spend is never ambient.

## 5. BUILD ORDER
1. Fold standalone :8100 into the React surface (C2 decision; redirect +
   deprecate, keep one surface).
2. Theme variant tokens (`autothink` atmosphere preset already eased by T-2 —
   extend with motion field: meteors, asteroid belt, comet scheduler).
3. Warp transition + flying workbench drawer.
4. Immersive plan graph becomes default; per-tool run rows.
5. Acceptance: desktop + 390×844 captures of focus-switch moment (mid-warp
   AND settled), graph mid-run, artifact handoff; reduced-motion variants;
   guardrail + shell gates green; luminance gate ≥5% gutters holds here too.

## 6. FAIL-SAFE RULES INHERITED FROM SIMPLE
Reduced-motion static variant, pause-when-hidden, evidence-before-approval,
no "voice chat" wording, unknowns render unknown. If the moving field measurably
hurts reading panel stability on the capture pass, motion throttles down before
any text-weight or contrast change ships — readability outranks spectacle.
