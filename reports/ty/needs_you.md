# UX rebuild — needs you

Owner-only actions. Everything else continues without them.

## 1. ~~Close the Tailscale serve on port 8000 so the dev stack can start~~ — RESOLVED 2026-11-03

`tailscale serve status` returned **No serve config**; `scripts/dev-start.ps1`'s safety gate passes,
the backend is on 127.0.0.1:8000 and the UI on 127.0.0.1:8101. No action needed.

## 2. Studio top-up payment processor (future; interface stubbed only)

Per the work order, the billing interface is a stub in this run. When the real top-up ships it
needs an owner-configured processor (Stripe or equivalent), merchant account, and price table.
Not blocking any current unit.

## 3. Decision: does the Design Studio page keep a chat box? (2026-11-03, U14 adjudication)

Six e2e specs (`acceptance-mogra` T-auth, `asset_picker`, `chat_composer_stability`) still fail
because they open `/ui/design-studio` and wait for `data-testid="chat-input"`. That route renders the
real studio page, not the chat shell — `App.jsx` keeps `/design-studio` out of the Northstar chat
replacement, and the chat composer lives in the workbench dock (`/ui/workbench`) and in advanced
view. This was already true at the U0 baseline commit, so it is not a regression: those specs predate
the mode gate.

**What I need from you:** one of these, and I will do it in a later unit —

- **(a)** the Design Studio keeps its chat box (a studio-scoped Bojo inside the page), and I re-point
  the specs at it; or
- **(b)** the chat stays in the workbench only, and I rewrite those three specs to drive
  `/ui/workbench` instead (the `acceptance-mogra` render requests would then be asserted through the
  workbench chat, which is the surface a user actually has today).

Silence means (b) is implemented as a spec-alignment task, not a product change.

Meanwhile the two `asset_dashboard` lane-trigger failures are **not** this: at HEAD the lane was
reachable and reported `media_generation_disarmed (MEDIA_GEN_LIVE is not 1)`. **Resolved 2026-11-03** —
you asked for FLUX 3 to be armed, the lane is now armed and both tests pass without the spec changing.
See `docs/FLUX3_LANE.md`. Nothing is left on you for that one.

## 4. Item 0 candidates are ready for your eye (not a blocker)

`renders/mogra_lions_mane/product_front.png` and `product_back.png` (1024×1536) are the first
service-produced product pictures: FLUX 3 plate, designed panel in perspective, OCR gate passed.
What only you can judge is whether the *design* is right — the cream label on kraft, the lion's-mane
mark, the composition. The loop will not pick a style silently. Say what to change and it becomes
the next design task; silence leaves the current artwork as the declared design.

## 5. Amazon ad-video spec (standing gate — operator document, not a request to browse)

The two Amazon video presets are `verified: false` on purpose because reading Amazon's own specs is
a standing gate. To flip them, upload or hand over the current ad-video spec as a document; the code
will then record `verified: true` with the checked date. No Amazon request is made by the loop.

## 6. Nutrition values and UPC (before print, not before a picture)

The Supplement Facts values (2 g serving, 85 servings, 2,000 mg), the UPC and the best-by format are
the values you stated; the panel carries `DRAFT · VERIFY BEFORE PRINT` for that reason. A product
picture does not need them final; a print order does.



## 7. A 15 s video render is a time commitment, not a blocker (2026-11-03)

The video ad lane is proven end to end on a **3 s** clip (4 min wall clock on this box). A 15 s
TikTok plans as 5 scenes / 8 sampler clips and takes roughly 20 minutes of local GPU/CPU time.
POST /api/design-studio/video-ad/plan shows the cost first; POST /render with confirm: true
starts it. Say the word if you want the 15 s master rendered; the loop will not spend 20 minutes of
render time on a guess.
