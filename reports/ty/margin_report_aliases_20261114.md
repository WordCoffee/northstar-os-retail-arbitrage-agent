# margin_report — shorthand resolves instead of refusing (2026-11-14)

**Outcome: closed.** `margin_report` and `ty/service_registry.json` now carry the same
18-entry alias table, so a shorthand profitability query computes instead of being refused or
silently dropped.

## The behaviour

| input | before | after |
|---|---|---|
| `{price, cost}` | refused: `acquisition_cost is required` | renamed to `selling_price` / `acquisition_cost` |
| `{…, referral_fee: 5.25}` | `referral_fee` named as **ignored** | renamed to `referral_fee_amount` |
| `fba_fee`, `shipping`/`freight`, `prep`, `ads`/`ad_cost`, `qty`, `cogs`, `unit_cost` | ignored, then possibly refused | renamed onto the engine's own input |
| `{selling_price: 24, price: 20, …}` | — | **canonical wins**; `price` stays in `ignored_inputs` |

A rename never rescales or invents a number: `referral_fee` is an **amount**
(`referral_fee_amount`); a percentage belongs in `referral_pct`/`referral_rate`. Every rename is
reported in `aliased_inputs`, and the note says so.

**Real-engine proof:** `{price 34.99, cost 12, referral_fee 5.25, fba_fee 5.50, ads 1.0,
provenance user_supplied}` → `ok`, `contribution_profit_after_ads = 11.24`,
`readiness = COMPLETE_ESTIMATED` — no refusal.

The registry's `profitability.input_aliases` / `input_aliases_note` are pinned equal to the
handler's `INPUT_ALIASES` by a test, so the hint cannot drift from the code.

## A registry maintenance blocker found and fixed

`tools/registry/build.py` refused to run because 49 action citations had drifted, and after the
citation repair the **evidence** refs were still stale: `repair_citations` rebuilt
`evidence.backend` from action sources but kept any pre-existing ref that did not start with
`main.py`. It now keeps only refs that still resolve (plus the documented `/ui` mount), with a
test. Result: **49 citations rewritten, 0 unresolved**, the tool list regenerated
(48 wired, 5 unclaimed including `read_open_design`), and `build --check` /
`repair_citations --check` both exit 0.

## Tests

| suite | result |
|---|---|
| `test_bojo_tools_economics.py` (3 new: shorthand real engine, canonical-wins, registry parity) | **13 passed** |
| `test_bojo_tools_economics.py + test_chat_tools_handlers.py` | **25 passed** |
| `test_service_registry.py` (1 new: stale evidence refs dropped) | **23 passed** |

No Amazon, no spend, no credentials. Soak, quiet-window waiter and `state/vision/PAUSE`
untouched.
