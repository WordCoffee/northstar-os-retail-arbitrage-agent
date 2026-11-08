# REA scan + recreation: Packify (2026-10-24)

Operator task: *"fully scan packify.ai and recreate our own version for package design"*.

## 1. REA capture status (COMPLETE)

Two live read-only captures via Chrome Connect (operator profile, no login bypassed):

| Surface | Status | pw calls | refusals | Journal |
|---|---|---|---|---|
| `www.packify.ai` (marketing) | COMPLETE | 2 | 0 | `...mvm5chit.jsonl` |
| `www.packify.ai/design-chat` (app shell) | COMPLETE | 2 | 0 | `...mvm5cqr3.jsonl` (DNS-fail on app.packify.ai noted; entry is `/design-chat`) |
| `www.packify.ai/pricing` | COMPLETE | 2 | 0 | (inline) |
| `www.packify.ai` (links) | COMPLETE | 2 | 0 | (inline) |

All captures read-only: no forms clicked, no consent accepted, no credentials entered.
Policy: packify.ai was already on the operator allowlist; no allowlist change needed.

## 2. Packify surface map (what they ship)

**Marketing / value prop:** "Redefine packaging in a conversation" — text → 3D packaging concepts.
Tagline: "Your All-in-One Platform for Creative Design, Smart Integration, and Manufacturing."
200,000+ brands/designers; 10x faster time-to-market; -90% design & sampling costs.

**Core tools (from marketing + link map):**
- AI packaging design (text → 3D packaging concept)
- Print-ready dielines ("Concept to dielines — don't just create images; create products")
- AI photoshoot (swap backgrounds instantly)
- Logo integration (integrate logos perfectly)
- Smart design edit (easily tweak designs)
- Label generator (design custom product labels)
- Nutrition facts (easy nutrition info creations)
- Packify API (integrate generation into e-commerce workflow)
- Printing (connect to verified manufacturers worldwide)
- Expert design services (20+ human designers, $299 consultation)
- Inspiration / design ideas by category (food & beverages, electronics, cosmetic, fashion & beauty, household, baby & toys, pet, supplements, luxury, others)
- Brand kit, Sessions, Workspace, Share
- Packify Wiki (docs)

**Credit model (from pricing page):**
- Free: 100 one-time credits (no refresh) — trial of all core features
- Basic: $14.9/mo (annual) — 1,000 credits/mo, personal commercial license, all tools, standard queue
- Pro: $19.9/mo (annual) — 2,500 credits/mo, personal commercial license, first-priority queue, premium image models, advanced understanding agent, early beta access
- Business: $29.9/mo (annual) — 3,500 credits/mo, company commercial license, team access, high-quality exports, API access, export editable dielines, free expert design ($299 value)
- Enterprise: $69.9/mo (annual) — 10,000 credits/mo, company license, 3 member seats, API, export dielines, free expert design, custom design services
- Yearly up to 46% off
- Credit costs: AI Design/Edit = 10 credits; AI Photoshoot = 5 credits
- AI Editor credit usage scales with images generated and AI calls per task

**Design-chat UX (captured):** sidebar (Workspace, Brand kit, Sessions, New project), credit counter (49), Share button, prompt box ("What would you like to design?"), suggested prompts ("Start a new packaging design from scratch", "Try bottle in a darker, more premium colour", "Generate the realistic sparkling lime bottle mockup now").

## 3. What we recreated (in-house, no Packify code/assets)

New module: `Northstar_backend/package_design.py` (+ `test_package_design.py`, 12 tests green).

| Packify surface | Northstar equivalent | Notes |
|---|---|---|
| Template library (box/bottle/pouch/can/label) | `TEMPLATES` dict with dimensions + material + finish | 5 starter templates; extendable |
| Text → design spec (AI packaging design) | `design_from_prompt(prompt, provider)` | Uses reasoning provider + skills plane (product-marketing + ad-creative, base-first); falls back to template-only stub offline |
| Brand consistency | skills plane injection (fact contract + claims discipline) | base skill first, 5,500-char budget |
| Claim safety | decision layer `copy_audit` on name + claims | blocked → status stays `draft` |
| Dieline spec | `dieline_spec` dict (width/height/bleed/safe zone) | geometry stays cadquery's job (cadquery 2.8.0 verified locally) |
| Credits ledger | `credits/spend_credits/grant_credits/reset_credits` | local, no money; mirrors Packify's 10/5 credit costs and 49 starter grant |
| CLI | `python package_design.py new/templates/credits` | offline, no network |

Deliberately **not** recreated (out of scope / needs operator approval):
- AI photoshoot (background swap) → maps to FLUX.2 Klein in the provider suite (paid credits, real-money gate)
- Printing (manufacturer connection) → external state change, prohibited without gate
- Expert design services → human, not code
- Packify API → would be a FastAPI endpoint; add when a customer-facing surface needs it
- 3D rendering → needs Chrome Connect carve-out (browser render) or a headless renderer

## 4. Test evidence

```
test_package_design.py   12 passed   (templates, routing, offline fallback, provider spec fill,
                                    copy audit, blocked→draft, skills injection, credits ledger,
                                    negative amounts, to_dict round trip)
```

## 5. Memory filing

Six entries filed (REA discipline): Decisions contract, loop breaker, revision gate,
setup skill, marketing capture, pricing capture, docs capture. (See memory_bank.)

## 6. Guardrail cross-check

- No Packify code, assets, or brand material imported (only structural observation) ✅
- No login bypassed; app.packify.ai was a DNS failure, captured via /design-chat instead ✅
- No paid credits spent; credits ledger is local integers only ✅
- No external state changes (no printing order, no API signup) ✅
- Chrome Connect remained the only browser path ✅
- All work on `feature/v4.1-mesh`; nothing pushed ✅

## 7. Next actions

1. Wire `package_design` into a FastAPI route + React room when the Design Studio needs it.
2. Add cadquery-based dieline SVG export (geometry is already available locally).
3. If photoshoot is wanted, route through FLUX.2 Klein (paid gate) — not Packify's.
4. Consider porting Packify's category template library (food, electronics, cosmetic, etc.) as a starter set.
