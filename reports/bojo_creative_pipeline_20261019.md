# Bojo + creative pricing/planning — build report

**Date:** 2026-10-19 · **Branch:** `feature/v4.1-mesh` · **Snapshot:** `snapshot/pre-bojo`
**Requested:** hyper-focus on the creative pipeline and the listing / ad / product-
design / package-and-label services; a Bojo chat surface with live voice, text,
upload, thinking settings, image/video switch, a plan → credits → cancel/edit/
draft/final confirmation flow with tier economics (60–70% margin); 20 galactic
view improvements; a rollback file.

---

## 1. Scope — what is built and verified, and what is not

I refuse to describe this as "complete" when two thirds of the UI request is still
open. The honest split:

| Requested | State |
|---|---|
| Job-scaled credit pricing with tier economics | **BUILT + 75 tests** |
| Quick/detailed plan, quote, cancel / edit / draft / final | **BUILT + 24 tests** |
| Plan card in the chat with live credits and four actions | **BUILT** (build 0 errors; V3 gate green) |
| Customer-facing assistant named **Bojo** | **BUILT** |
| Rollback file + snapshot/restore tooling | **BUILT + snapshot taken** |
| Voice **message** (record → local whisper transcript) | Already existed; unchanged |
| **Live two-way voice conversation** | **NOT BUILT** — needs a streaming STT/TTS loop |
| File upload in the composer | **NOT BUILT** — needs a real upload route wired |
| Image/video switch driving the turn | **NOT BUILT** — needs a `media` field on the turn contract |
| Thinking level / style settings | **NOT BUILT** — needs a turn-level control + prompt plumbing |
| 20 galactic view improvements | **SPEC'D (below), not implemented** |

The four NOT-BUILT UI items each need a turn-contract change (the SSE endpoint
accepts `content` + `think` only), and the voice loop needs a duplex transport.
Shipping dead buttons would have been worse than saying so.

---

## 2. The economics (measured, not asserted)

Single source of truth: `shared/usage-caps.json` — 1 credit = **$0.0078**, model
costs image_v1 $0.015 / image_v2 $0.03 / image_v3 $0.08 / Wan-15s $0.75, and the
repository's existing 60–80% margin band (`cost_model.py`).

`creative_pricing.py` prices each job so real cost sits at **68% margin**, and
because a plan's monthly allotment is worth exactly its price in credits, a member
who drains the entire allowance on one job class still leaves the tier at ≥60%.

| Job | Quality | Credits | Real cost | Margin |
|---|---|---|---|---|
| Ultra-realistic person holding product | draft / final | **9 / 17** | $0.021 / $0.040 | 70% |
| Studio product shot | draft / final | 9 / 17 | $0.021 / $0.040 | 70% |
| Listing image | draft / final | 10 / 17 | $0.023 / $0.042 | 68–71% |
| Ad creative set | draft / final | 17 / 31 | $0.040 / $0.076 | 69–70% |
| Print-ready label | draft / final | 15 / 32 | $0.035 / $0.078 | 69–70% |
| **Package design (print-ready)** | draft / final | **34 / 71** | $0.084 / $0.176 | **68%** |
| Short video (15s) | draft / final | 306 / 609 | $0.762 / $1.518 | 68% |
| Long video (60s) | draft / final | 1209 / 1813 | $3.016 / $4.524 | 68% |

The operator's headline requirement holds: **a portrait costs 17 credits, a package
design costs 71** — 4.2× more, tracking the real work.

Tier access is explicit data (`TIER_ACCESS`): the entry tier gets **draft for every
image class plus final for cheap stills** (555 portraits or 147 package drafts a
month), `ad` final unlocks at scout, label/package final at mover, video at
autothink. A test asserts every tier can afford **≥20 jobs/month** at its level, so
the cheap tier is a real experience rather than a teaser.

---

## 3. The flow Bojo runs

```
operator: "design a 6 oz stand-up pouch for mushroom powder"
   → creative_plan builds a plan (quick | detailed) with REAL registered steps
   → quotes draft 34 cr / final 71 cr, lists what it still needs (brand assets,
     mandatory label copy), and renders a card with four actions
   → operator: draft (34 cr) | final (71 cr) | edit | cancel
   → creative_plan(action, plan_id) validates tier access and returns the ledger
     RESERVE INSTRUCTION  (idempotency key = plan_id:quality)
```

The tool **never generates and never charges** — it quotes and validates; the
charge belongs to `credit_ledger.reserve/commit` and execution to the creative
tools. Plans live in a bounded per-process registry (200 max, oldest dropped) so a
button press in the next turn can find its plan; a restart forgets them (cheap to
rebuild) rather than persisting a decision surface.

---

## 4. 20 ways to improve the galactic view (spec'd)

Scenery only: none of these may raise luminance behind the reading column (the
panel is 95.5% opaque for that reason), and the disc stays film-gold.

1. **Star colour temperature** — sample a blackbody ramp per star instead of one tint.
2. **Diffraction spikes** on the 8 brightest stars only (anamorphic cross, 4 px).
3. **Real parallax** — three depth layers drifting at 1× / 0.6× / 0.3×.
4. **Shooting star** — one every 40–90 s, 0.4 s streak, never in the reading column.
5. **Dust lanes** with occlusion (multiply, not add) in front of the Milky Way band.
6. **Nebula filaments** — ridged fbm instead of soft blobs.
7. **Aurora ribbon** near the horizon, 2% luminance, focus-tinted.
8. **Planet limb** with a thin atmosphere gradient and a terminator (mode-gated).
9. **Ring shadow** on the planet from its own ring.
10. **Photon-ring shimmer** — ±0.5% radius breathing tied to `u_pulse`.
11. **Gravitational star smear** already present; extend it to a second layer.
12. **Chromatic bloom** — a 1-px warm fringe on the hottest disc edge.
13. **Dithering** (blue-noise) to kill banding in the dark gradient.
14. **Filmic tone curve** with a shoulder — already ACES-ish; add a toe for blacks.
15. **Vignette shaped to the panel** (elliptical, not radial) so gutters are darker.
16. **Grain at 12 fps** (already) with a second coarser layer at 3 fps.
17. **Focal breathing** — 0.5% scale over 40 s, not a sine.
18. **Event-horizon shimmer** — a faint refractive offset inside the shadow edge.
19. **Focus-mode comet colour** — the tint shifts the comet tail, not the disc.
20. **Idle dim** — after 60 s of no input, luminance drops 15% (still readable).

Each is a shader/CSS change with a screenshot baseline; items 1–5 are the highest
visual return. **None are implemented yet** beyond what V4.2/T-2 already shipped
(film-faithful disc, lensing, photon ring, star smear, eased focus tints).

---

## 5. Rollback (requested)

`ROLLBACK.md` + `tools/rollback.ps1`: `snapshot` (tag + DB copies + bundle hash +
manifest), `list`, `restore` (backs up the current DBs, creates
`rollback/<name>` at the snapshot commit — **your branch is never moved** — restores
the DBs, rebuilds the bundle).

Taken now: **`snapshot/pre-bojo` @ `85b813e`**, both databases copied, bundle
`index-Bln06uzv.js` recorded.

---

## 6. Verification

| Gate | Result |
|---|---|
| `test_creative_pricing.py` | **75 passed, 17 skipped** (skips = "not on this tier") |
| `test_creative_plan.py` | **24 passed** (includes the real chat-tool round trip) |
| chat + shell + tools regression | **145 passed / 17 skipped** |
| `npm run build` | **0 errors** |
| V3 shell gate | **28/0** (see run log) |
| rollback snapshot + list | worked; tag created |

## 7. Next, in order

1. **Turn contract v2**: add `media`, `thinking`, `style`, `attachments` to the turn
   body and thread them to the tools (unblocks the switches honestly).
2. **Live voice loop**: duplex transport (SSE in, chunked STT out), barge-in, and a
   visible "listening / thinking / speaking" state.
3. **Uploads**: reuse the design-studio asset route; store provenance.
4. **Galactic items 1–5**, screenshot-verified.
5. **Wire `creative_confirm` → reserve → generate → commit** so a paid job actually
   runs end to end (reserve now, commit on success, release on failure).
