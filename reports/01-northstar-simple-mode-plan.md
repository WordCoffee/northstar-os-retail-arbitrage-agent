# NORTHSTAR OS — SIMPLE MODE PLAN (customer-facing main view)
**Version:** 1.0 · **Date:** 2026-10-24 · **Status:** Planning basis for next build batch
**Basis:** `northstar-simple-mode-fix-plan.md` + `northstar-simple-mode-issue-scan.md`
(local agent), `simple_ui_rebuild_v42_20261018.md`, 00_STATE.json, operator brief
2026-10-24 ("galactic, Interstellar-grade realism that astronomers respect; a living
environment that changes; one chat window with Bojo; seller-focused but not only").

---

## 1. PRODUCT DEFINITION

Simple Mode IS the product for subscribers: **one window, one conversation, Bojo
behind it.** The user states an outcome; Bojo routes it to whichever Northstar
service or agent does the work (SourceScout, Golden Goose, ListingForge, AdPilot,
SocialPulse, Creative Studio, Guardian…). Seller outcomes are the spine, but the
surface is not seller-only: a general question gets a full, detailed answer — this
is explicitly in scope ("if they're using AutothinK… general question" is its own
surface; Simple answers generally too, at chat depth).

**Non-goals for Simple Mode:** tabs-per-service (that is Advanced), dense admin
consoles, the standalone AutothinK server UI, VR. Advanced Mode keeps the original
multi-tab layout and receives the 3D/VR Design Studio later; Simple Mode never
carries VR chrome.

---

## 2. THE CELESTIAL SYSTEM — "astronomer-respectful"

Design bar: an astronomy enthusiast should recognize the physics, not spot
mistakes. Interstellar is the reference, not the limit.

### 2.1 Anchor rules (keep from V4.2)
- Film-faithful Gargantua: near edge-on accretion disc, lensed far-side arch over
  AND under the shadow, razor photon ring, truly black shadow, Doppler ≤1.35×
  (symmetric golden disc — the film's deliberate choice), no purple, no cartoon.
- Brightest art never under the reading column; panel ≥95.5% opaque over imagery.
- 12fps-stepped grain, gentle vignette, ACES-style grade.
- Composition: hero in a gutter no panel covers; gutter luminance ≥5% measured

### 2.2 NEW — The Living Sky (daily vista rotation)
Every login day, the sky points elsewhere. Implemented as a **vista library +
deterministic daily seed** (hash of UTC date + account), so a user sees the same
vista all day, different tomorrow — never random per reload:

| # | Vista | Signature visuals |
|---|---|---|
| 1 | Gargantua approach | the film-faithful hole, disc plane low in frame |
| 2 | Ring plane transit | ice-ringed giant, thin rings crossing the frame, shepherd moon |
| 3 | Emission nebula field | warm hydrogen tones, embedded young cluster, dark dust lanes |
| 4 | Milky Way core rise | dust-laned galactic band arcing over a low horizon glow |
| 5 | Comet pass | one bright nucleus + twin tails (ion + dust), slow drift across the session |
| 6 | Binary star rise | twin suns low in frame, long shadow gradient, pale daylight wash |
| 7 | Deep field | thousands of faint stars, one distant spiral galaxy, high stillness |

Each vista is a shader-parameter set on the same engine (no new pipeline). Two
slow eases per day max (dawn drift) — the Vista System never flickers.
Accuracy notes ship IN the product: a subtle corner annotation names the vista
("Ring plane transit · vista 2 of 7") — astronomers get the nod, users get
orientation, and it doubles as the freshness signal that the environment is alive.

### 2.3 Motion budget
Ambient: star twinkle, parallax drift, one shooting star every few minutes.
Event-driven (celebration only): a comet streak crosses on job completion;
a subtle pulse ripples the inner disc while Bojo thinks (existing u_pulse).
prefers-reduced-motion → static graded frame. Tab hidden → render loop pauses.

---

## 3. THE CHAT SURFACE — "zoomed in, clean, scaling right"

Root cause of the zoom complaints: the app hard-coded pixel sizes (10.5–13.5px)
and sized the canvas/panel in viewport px, so browser zoom broke layout. Fix
class, not fix instance:

1. **All type and spacing in rem** from the root; the V4.2 scale is the floor
   (body 16.5px). Browser zoom then scales uniformly instead of "looking weird."
2. **An in-app Display Scale control** (90% / 100% / 115% / 130%) that sets a
   single `--ui-scale` variable — users who "zoom" get a designed scale with
   verified layout at each step, including screenshot acceptance at each level.
3. **Container queries, not viewport queries**, for chat internals: the column,
   cards, plan panels, artifact grid adapt to the stream width, so side panels
   opening don't squash text.
4. **Canvas is layout-aware:** the hero's gutter side flips automatically when
   rail/column geometry changes (rail collapsed, mobile, workbench open).
5. **Mobile:** 390×844 is a first-class acceptance surface; rail → drawer;
   composer docks; hero object re-anchors above the fold line instead of vanishing.

## 4. INTERACTION DESIGN — "visually and interactively different"

Familiar chat grammar (user right-of-center or left, assistant distinct,
Enter to send, streaming tokens) + Northstar signatures:

- **Mission framing:** a concrete request ("make the pouch mockup") renders a
  Plan card styled as a mission brief — manifest rows, approval as "commit",
  artifacts arriving as recovered payloads. Already built; this is the pattern
  every agentic answer follows.
- **The Event Horizon stream:** while Bojo streams, a hairline of light bends
  along the bubble edge (existing u_pulse family) — replaces a generic typing
  ellipsis; obey reduced-motion.
- **Docking:** when a tool runs, a small "dock" appears above the stream naming
  the live service (e.g., "SourceScout · Costco cache"), so users learn the
  service constellation passively.
- **Recovery pass:** completed jobs drop their artifact into the stream with the
  real name/kind/size (asset_meta shipped); opening it is a lightbox "inspection".
- **Fork/rewind (exists) becomes "slingshot":** the fork control gets orbital
  language and a visible branch marker — a signature almost no chat app has.
- **Six foci are the gearbox:** auto · create · grow · research · operate ·
  autothink chips; switching focus visibly re-aims the sky's tint/atmosphere
  (T-2 already eases this — keep the boundary that the disc stays gold).

## 5. CONTENT + HONESTY CONTRACT (unchanged, non-negotiable)
Unknown renders unknown; demo is badged; live/paid actions stay gated; voice is
labeled dictation until streaming exists; every number carries provenance.

## 6. BUILD ORDER (after B0/B1 profile-unlock)
1. Scaling class fix (rem migration, --ui-scale, container queries) + measured
   re-verification of v4.2 baselines at each scale step.
2. Vista library + daily seed + vista annotation; luminance gate in captures.
3. Interaction signatures (event horizon, docking, comet completion).
4. S1–S7 capture pass at desktop + 390×844 at TWO scale steps.
5. Ship-readiness gate from the fix plan's Phase E list.

## 7. EXPLICIT DEFERRALS
VR/3D Design Studio → Advanced tier, later. Streaming voice → named-budget
feature. Standalone :8100 AutothinK → redirect/deprecate (decision C2).
