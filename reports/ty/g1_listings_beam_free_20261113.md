# G1 Listings — beam-free, compose → persist → read back (2026-11-13)

**Outcome: G1 Listings is met.** A listing was composed through the UI from supplied facts on
the owner-authorized `beam-free`, persisted to the tenant store, and read back in two clean
browsers — desktop Chromium and iPhone 12 WebKit. No other model id was used, no paid id was
touched, and no credential was read or printed.

## The one model change (owner-authorized)

| item | measured |
|---|---|
| id in the live Go catalog | **yes** — `GET /zen/go/v1/models` → 200, `beam-free`, "Beam Free", context 1,048,576 |
| price | **input $0 / output $0** (live catalog) |
| real completion | **HTTP 200 in 622 ms**, model echoed `beam-free`, usage `cost: 0`, response `{"ok": true, "word": "beam"}` |
| what changed | `step-5-preview-free` (withdrawn upstream) → `beam-free` as the single verified runtime default; step-5 kept for provenance, marked `retired`, `verified_usability: false` |

`POLICY_PREFERRED_MODEL`, `VERIFIED_GO_MODEL`, `RUNTIME_DEFAULT_MODEL` and the catalog's
`role`/`intended_role` now name `beam-free`. The adapter still refuses any unverified id by
name — no silent substitution exists. `GET /api/v1/reasoning/models` after restart:
`runtime_default_model=beam-free`, `verified_model=beam-free`, `usable=[beam-free]`.

**A budget defect was found and fixed, and it is not a model change:** at the adapter's
4096-token default, `beam-free` (a reasoning model — reasoning tokens count toward the
budget) returned HTTP 200 but a **truncated JSON document** (2,055 characters, parse failed).
The same prompt at 8,192 tokens returned the complete 2,919-character document. The listing
task now asks for `LISTING_MAX_TOKENS = 8192`; a test pins it. Ad-copy and spreadsheet
defaults are unchanged.

## The G1 click path, measured

`npx playwright test tests/e2e/g1_listings_persist.spec.ts --project=chromium-desktop` →
**2 passed (21.6 s)** (the phone project skips the file by design; the phone read-back runs
inside the same test).

| step | result |
|---|---|
| gate by name | `OPENCODE_GO_API_KEY configured=true`, `OPENCODE_GO_ENABLED enabled=true`, `armed=true`, `runtime_default_model=beam-free` |
| container row | created through the room's own create form when the account is empty; on a non-empty account the spec posts to the same endpoint the form posts to (the room only renders the form for an empty account) |
| facts supplied | title, 3 bullets, description, 3 keywords, brand (Mogra Organics Lion's Mane, 200 g pouch) |
| **compose** | panel reported `proposal ok`, provenance `beam-free`; **Apply to editor** replaced the copy |
| **persist** | **Save Revision** → `POST/PATCH /api/design-studio/listing-records`; the row was asserted through the API before any read-back |
| **read back — desktop** | clean Chromium context (no storage): table row by ASIN → editor Title/Bullets/Description/Keywords all equal the persisted values |
| **read back — iPhone 12** | clean **WebKit** context with the iPhone 12 descriptor: same four fields, same values |

Persisted row (the final run):

```
id      7643a5a0-7824-4c43-accd-6a26d755ecc2
asin    B0G1LOKAVJ
title   Lion's Mane Mushroom Powder, Single Ingredient, 200 g Resealable Pouch - Mogra Organics
bullets 5 (EVERYDAY USE / INGREDIENTS / TEXTURE / STORAGE / INCLUDED)
terms   lions mane powder, mushroom coffee, mogra organics
desc    363 characters
```

Two real composed listings remain in the tenant store (`B0G1LO8QE4`, `B0G1LOKAVJ`); the
draft container row left by an intermediate failed attempt was deleted. **No stub exists.**

## Tests

- `python -m unittest tests.test_reasoning_provider tests.test_reasoning_tasks
  tests.test_reasoning_routes` → **63 passed**, exit 0 (new: retired-step-5 refusal, beam-free
  default, listing token budget).
- `npx playwright test tests/e2e/g1_listings_persist.spec.ts` → desktop **2 passed**;
  `--project=chromium-mobile` → **2 skipped** (file is single-run by design).

## Honest limits

- `beam-free` is a reasoning model and returned non-JSON once at the old budget; the budget
  fix removes that observed truncation, but model-output shape is still probabilistic. The
  spec fails loudly if a proposal is not `ok`.
- No paid model was exercised. `step-5-preview` ($1.00/$2.70 per 1M) remains unselected and is
  still a spend-gated choice.
- The compose is a live provider call; it costs $0 on this model today. If the provider changes
  the price or withdraws the id, the path refuses by name and this report is superseded.
