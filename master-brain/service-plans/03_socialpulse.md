# SocialPulse — Social Media Agent — Website Plan & Architecture

> **Status:** Approved for construction (Autonomous Zone).
> **Derives from:** master plan §4.4, profile §6 (Word Coffee voice module — taglines,
> hashtags, "NOT a beverage" rule), creator outreach / review-request TOS constraints.

## 1. SERVICE IDENTITY

**Public:** SocialPulse — "Pulse your brand's voice."
**Internal agent:** Social Media Agent.
**Core promise:** post generation, scheduling copy, brand-voice content across
Facebook/Meta, TikTok, Instagram; creator/affiliate outreach; external-traffic strategy
with Amazon Attribution.

## 2. SCREENS / VIEWS (hash routes within `#/socialpulse`)

| View | Purpose |
|---|---|
| **Content Studio** | Generate captions/copy in the active brand's voice (fixture templates at first); editable and re-generatable |
| **Calendar** | Post schedule grid with copy, channel icons, and hashtag sets |
| **Creative Prompts** | Ad-creative prompts, photo prompts, video scripts — 3 channels |
| **Outreach** | Creator outreach scripts + TOS-compliant review-request emails |
| **Voices** | Brand voice module manager — load Word Coffee voice; show rule chips ("NOT a beverage") |
| **Attribution** | External-traffic strategy: maas= attribution tags, gating summary (only when Amazon PPC stable: ACoS < 30%; blended ACoS < 40%) |

## 3. COMPONENTS

1. **Voice Module Card** — brand block with exact taglines, hashtag library, forbidden
   topics (Word Coffee: never treats product as beverage).
2. **Caption Slate** — "paper" card with generated caption + hashtag chips (click to
   move to calendar slot).
3. **Channel Tiles** — Meta / TikTok / Instagram tiles with per-channel format notes.
4. **Outreach Envelope** — email/script template with macro tokens ({{brand}},
   {{product}}, {{promo}}).
5. **Attribution Strip** — external-traffic readiness lamp: PPC stable? ACoS bands
   shown; gated-LIVE lamp dark until conditions met.

## 4. DATA CONTRACT

```js
brandVoice = {
  brand: 'word_coffee', notBeverage: true,
  taglines: [...], hashtags: [...], forbidden: ['coffee beans','k-cups','beverage'],
  tone: 'bold, clear, premium, emotionally honest, practical, non-cheesy',
}
post = { brand, channel: 'meta'|'tiktok'|'instagram', copy, hashtags[], formatNote, savedSlot }
creative = { kind: 'ad'|'photo'|'video', prompt, aspect, notes }
outreach = { kind: 'creator'|'review_request', template, macros }
attribution = { maasTag, ppcStable, ppcAcos, blendedAcos, gateLamp: 'off'|'ready' }
```
- Fixtures (`demo-posts.json`) use real Word Coffee taglines ("Grab Word Coffee, not a
  cup." / "Fuel Your Focus." / "Find Your Calm in the Chaos.") labeled demo; hashtag
  sets from profile §6.1.

## 5. GATED-LIVE PATHS

- Post publishing to Meta/IG/TikTok APIs — gated off, code path stubbed (build later).
- Amazon Attribution generation/registration — gated off.
- Creator outreach sending — gated off (template-only today).

## 6. TEST CONTRACT

- Voices view: Word Coffee card enforces `notBeverage` (beverage-topic template shows
  correctness note / blocked pill).
- Content Studio: one generated caption from fixture matches exact voice tagline set.
- Calendar: slots accept caption + hashtags; persists in-memory.
- Outreach: review-request mail contains no solicitation-of-positive-review language
  (compliance assert).
- Zero `fetch` calls.

## 7. BUILD ORDER

1. Fixtures (`demo-posts.json` + voice module object).
2. Voices + Content Studio.
3. Calendar + hashtag chips.
4. Creative Prompts + Outreach.
5. Attribution strip.
6. Tests green; commit; state update.