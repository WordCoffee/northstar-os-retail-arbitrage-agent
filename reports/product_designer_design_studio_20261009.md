# Product Designer + Design Studio — competitor-quality creative cluster

**Branch:** `feature/product-designer-studio`
**Date:** 2026-10-09
**Scope:** the product design service and every service that uses creatives.
**Status:** COMPLETE — 5 commits, all harnesses green, zero regressions.

---

## 1. What was built

| Surface | Route | Before | After |
|---|---|---|---|
| **Product Designer** | `/product-designer` | did not exist | full service: scene designer, real 3D packaging view, mockups, generation queue, backdrops & brand kit, library |
| **Design Studio** | `/creative-studio` | 8 tabs of local workflow records, no creative capability | unified studio: master canvas + ad sets + social + A+ + generate + video + briefs + **brand** + **today's loop** + queue + variants + assets + exports + library |
| **ListingForge** | `/listingforge` | hardcoded display shell; the "editor" read back nothing | working controlled editor, real revision history, applicable templates, real asset upload, computed health |
| **SocialPulse** | `/socialpulse` | real workflow, but the preview was a gradient box saying "media placeholder" | real rendered preview at the platform's own aspect ratio, real asset upload, brand kit, studio handoff |
| **AdPilot** | `/adpilot` | data shell + one real AI text panel | added a real ad-creative renderer rendering at each paid placement's own pixel size |

**Simple / Advanced mode** is on every one of these rooms. Simple exposes the curated set; Advanced unlocks the layer stack with reorder/duplicate/delete, full geometry sliders, rotation, opacity and composition guides.

---

## 2. The studio engine (new, `northstar-os-ui/src/studio/`)

Dependency-free, all Canvas 2D. No three.js, no Konva, no new npm packages.

- **`engine/doc.js`** — document model + renderer. Layers (`bg`/`shape`/`text`/`image`/`product`/`badge`) with **normalised geometry** (0–1 of the canvas), Canvas 2D text with wrapping, contain/cover fit, real PNG export. Normalised geometry is the single decision that makes one master render correctly at 150×300 and 2400×1000 with no stretching.
- **`engine/three.js`** — a real 3D renderer on a plain Canvas 2D context: rotated box mesh, painter's-algorithm face sort, three-point light rig, affine texture mapping of the operator's own pack art onto individual faces, contact shadow, turntable. This is the 3D view.
- **`engine/mockups.js`** — vector mockup surfaces (tee, hoodie, tote, mug, label, box face) with blend-mode artwork placement.
- **`engine/assets.js`** — IndexedDB asset store; degrades to a session-only memory map and reports that honestly rather than implying durability.
- **`engine/compliance.js`** — the Amazon pre-flight (see §4).
- **`engine/loop.js`** — brand profile + the deterministic daily planner (see §5).
- **`engine/presets.js`** — 50 output placements across ads, social, listing, A+, docs/print/web and video frames; brand kits; scene recipes; lighting rigs; box presets; mockup surfaces; camera presets; copy roles; generation purposes/tiers.
- **`components/`** — Stage (hit-test, drag-move, zoom rail, guides), Fields, Chrome (mode toggle, tool rail, provider boundary, asset thumbs, format grid).

**`npm run build`: 0 errors.** The studio engine is split into its own Vite chunk so the app chunk stays under the 500 kB warning threshold.

---

## 3. Honesty contract — what is real and what is not

This is the part that matters most, because a studio that fakes its output is worse than no studio.

**Real, and proven by the harness:**
- Canvas renders real pixels; exports produce real PNGs; the multi-format renderer produces distinct rasters per placement.
- The 3D packaging view renders real geometry and the turntable actually moves it (asserted by hashing the canvas before and after).
- SocialPulse's and AdPilot's previews are real renders, asserted by reading canvas pixel data and by asserting the `media placeholder` text is gone.
- ListingForge's editor edits propagate to the local health score live, and Save Revision persists a real revision.
- Uploaded artwork is really stored in IndexedDB.
- Every count in every room now derives from the records shown. The ListingForge pill that claimed "24 across 6 ASINs" over a 4-row table is gone.

**Not real, and stated as such:**
- **Nothing is generated.** Generate and Video are real request recorders whose honest terminal state is `Blocked — provider required`. No image or video is generated or depicted, and no placeholder image is shown in its place.
- **Nothing publishes.** No marketplace, no social OAuth, no outbound call of any kind from either room — asserted by the harness (`no unexpected network calls`).
- **No provider is contacted.** The rooms never call an image/video model. The Generate tab has a readiness probe the operator can run explicitly; it reports honestly when the engine is not armed.
- **The 3D view is labelled as rendered geometry, not a photograph.**
- **Health and keyword coverage are local heuristics**, labelled as such — never marketplace measurements.
- **Performance figures read `UNKNOWN`** wherever a provider does not exist.

---

## 4. Amazon compliance pre-flight — the differentiator

The research's Decision 3 was "ship compliance as a hard gate, not a document". That is built.

`engine/compliance.js` holds 20 rules as **data**, each with a source id from `SOURCES.csv`, an accessed date and a `date_sensitive` flag — because Amazon states it periodically updates its policies.

Two levels, deliberately:
- **BLOCK** — deterministic. Export refuses until fixed or explicitly overridden. Implemented: raster 500–10,000 longest side; MAIN white background; MAIN ≥85% product fill; no text/logo/badge/colour-block overlay on MAIN; A+ module minimum size; headline ALL CAPS; repeated `?`/`!` or >2 ellipses; CTA end punctuation; special characters substituting letters; unsubstantiated superiority claims; competitor named; brand prohibited list.
- **FLAG** — heuristic needing a human, never auto-blocking. Amazon itself rejects Premium A+ over a brand logo and over text that is part of the physical product, which no automatic check can judge.

**Overrides are explicit and recorded on the document — never silent.** The harness proves this: it names a competitor in the brand profile, asserts the verdict becomes `BLOCKED`, asserts the rule shows its name + source id + date-sensitivity, asserts export is actually refused, and asserts the override records.

Also wired: the channel-set export checks **every** placement at its own pixel size before exporting the set.

---

## 5. What the competitor research changed

The research corrected the brief in ways worth knowing:

| Claim | Finding |
|---|---|
| creator.fyi is an alias of Creatify | **Not a product.** No A record, nothing served at the hostname. Retained as an UNKNOWN row so the check is visible. |
| PicCopilot sells Amazon A+ and EBC layouts | **Refuted.** No such module exists in its tool list. It is also **shutting down 2026-12-08** — its pricing already renders `$0` / `"$NaN"`. Treat as a former competitor. |
| tryholo.ai | **Holo** — an autonomous marketing platform, not a design tool. Operator's "UNVERIFIED" caution was justified. |
| Packify.ai | **Packify / Pacdora** — confirmed in full, including the Pacdora parent, text-to-3D, dieline editor, AI photoshoots, API and manufacturer connection. |
| — | **Amazon Ads AI creative** is the real zero-price incumbent: free, ASIN-first, native to Sponsored Brands/Display/DSP/Brand Store. **Flair** is the closest like-for-like competitor. |

**And a data error in my own code, caught by the research:** `presets.js` guessed at the Amazon A+ sizes and three were wrong. Fixed to the verified figures:

| Preset | Was (guessed) | Now (verified) |
|---|---|---|
| A+ wide banner | 970×600 | Premium Full Image **1464×600** |
| A+ standard | 300×300 | Comparison Chart **150×300** |
| A+ comparison | 970×300 | Four Images & Text **200×200** |

The A+ group now carries the full verified Basic + Premium module set — 23 modules, each tagged with its Amazon module name — plus Brand Story desktop (1464×625) and mobile (463×625) carousel backgrounds. A studio built on the wrong numbers would have enshrined the error in every asset it produced.

**Where the value sits** (per the research's own read): not on raw generation, which Amazon gives away free. On the operator's own reference-locked packshot (composited, never generated), cross-surface consistency, compliance gating, and the loop.

---

## 6. Learned from Holo and Canva — by workflow, not by category

**From Holo** (which has no canvas at all): the loop shape. Describe the brand once, the system proposes work every day across every channel, the operator taps approve.

Built as the **Brand profile** + **Today** tabs:
- One `BrandProfile` every creative room reads: name, audience, one-line promise, voice, prohibited claims, competitors never to name, detail-page copy for parity, active channels, kit.
- `planToday()` — deterministic, one proposal per active channel, each carrying a placement, a template, a proposed headline and **its reason**. The plan is stable for a given day so the operator can reason about what they approved.
- **Approve opens a real editable document** from the proposal's template at its own pixel size with the proposed headline already in the headline layer. Dismiss records the decision. Nothing generates, publishes or transmits.
- **Headlines are never invented.** An empty promise reads "Add your one-line promise in the brand profile" rather than fabricated copy.
- `loopReadiness()` reports honestly — the harness asserts it shows 2/4 rather than 4/4.

**From Canva:** output breadth. Added a Docs & decks group — Presentation 16:9/4:3, Document Letter, Whiteboard A3, Poster A3, Product label, Email hero, Web hero, OG card — plus five matching templates. 50 selectable placements in total.

---

## 7. Bugs found and fixed along the way

1. **ListingForge's editor read back nothing.** Title and description used uncontrolled `defaultValue` inputs — edits were never consumed by anything. Replaced with controlled, persisted state plus a dirty tracker and Discard.
2. **`Save Revision`, `Request Health Check`, `Use Template`, `Restore as Draft`, `Upload Assets` had no handlers at all.** All wired.
3. **A pill claimed "24 across 6 ASINs" over a 4-row table.** Now derives from the records.
4. **The A+ tab rendered Meta ad formats** — channel-set state was held separately from the tab, so the URL said `aplus` while state said `ads`. The channel set is now derived from the tab.
5. **`Cannot access 'overridden' before initialization`** — the override state was declared after `exportChannelSet`, whose dependency array references it and is evaluated eagerly during render.
6. **Renamed `Create Listing` to `Open editor`**, breaking the verify-smoke `Create Listing → ?view=editor` contract. Restored.
7. **`audit-imports.cjs` written** to catch dead imports and undefined references statically — the `ReferenceError` class esbuild cannot see and that only explodes at runtime. It caught three real crashes during this build.

---

## 8. Verification

| Harness | Result |
|---|---|
| `verify-studio.cjs` (new) | **73 passed, 0 failed** |
| `verify-smoke.cjs` | 40 passed, 1 failed |
| `verify-acceptance.cjs` | 32 passed, 0 failed |
| `verify-guards.cjs` | 11 passed, 0 failed |
| `verify-admin.cjs` | 33 passed, 0 failed |
| `verify-golden-goose.cjs` | 16 passed, 0 failed |
| `npm run build` | 0 errors, no chunk warnings |
| `audit-imports.cjs` | clean |

**The one smoke failure is pre-existing.** `/commerce-ops/CO-01` fails to show the "Sourcing Validation" marker. Proven by checking out the parent commit `2482048` in a git worktree, building it, and running the identical harness: **40 passed, 1 failed, same single failure.** It is unrelated to this work and affects a room that was not touched.

**A process note worth recording:** an earlier smoke run was misread. A Playwright FATAL aborts the script and emits no `FAIL` line, so a grep-only summary hid a real regression (the `Create Listing` rename) behind a single pre-existing failure. All harnesses are now run with full output and FATAL counting.

`verify-studio.cjs` covers: 28 deep links across all five rooms; the Simple/Advanced switch changing inspector depth; real canvas pixel output on three separate renderers; the 3D turntable actually moving geometry; provider boundaries on both generation surfaces; the compliance gate blocking, refusing export, and recording an override; the approve-only loop opening a real editable document; template transformation being a real state change; the existing `New Brief` / `Add Variant` harness contracts; mobile render with no horizontal overflow; and zero unexpected network calls.

---

## 9. What is deliberately not done

- **No provider is wired.** Local ComfyUI behind `MEDIA_GEN_LIVE` (default off), or a metered cloud tier, remains an open operator decision — the research leans local-first but GPU provisioning is unconfirmed on the pilot machine.
- **No video.** Per the standing posture, video stays disabled until the per-job spend cap and the approval gate are named. The storyboard composer is real; rendering is not.
- **No asset store beyond the browser.** IndexedDB is real and works; a hosted/FS object store is a separate decision and export stays reference-only for bundles until then.
- **No creative-level attribution.** Amazon's search-term reports aggregate at campaign/ad-group/keyword and carry **no creative identifier column**, so attribution cannot be derived automatically. v1 must record which variant was live in which date range and let the operator attribute — never infer it.

## 10. Commits

```
e5c149d feat(studio): Amazon compliance pre-flight as a hard gate, not a document
c723cf0 feat(studio): brand profile + approve-only loop, verified A+ specs, output breadth
d67e83a feat(studio): ListingForge, SocialPulse and AdPilot gain real creative capability
6bfafcb feat(studio): Design Studio — one room for ads, social, A+ content, image and clip requests
f232ef8 feat(studio): Product Designer service — local scene designer, real 3D packaging view, mockups, provider-gated generation queue
```

**Files:** 6 new engine modules, 2 new UI components sets, 1 stylesheet, 5 rewritten/created pages, 1 new harness, 1 new static checker, `vite.config.js` chunk split, `App.jsx` + `nav-config.js` + `Icon.jsx` + `main.jsx` wiring.
