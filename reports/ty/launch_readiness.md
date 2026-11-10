# Launch readiness — the core set

Bar **85.0**. Two services are at it: `hub` and `prospector`. Everything a seller actually *ships*
sits below, and the reason is the same dimension every time.

Source: `ty/scorecards.json` (29 services, weights works .23 / correct .25 / complete .12 /
usable .07 / measured .10 / seller .13 / contract .10).

## The table

| # | area | service(s) | score | measured state | what blocks production | units to close |
|---|---|---|---|---|---|---|
| 1 | **Listings** | `listingforge` 65.0, `listings` 77.0 | below bar | works 100, usable 100, measured 100, contract 100 — the machinery runs and is proved | **`seller` = 0.** The seller dimension is the reference-scored pass, and it is conditioned on **12 of 56 briefs** (21.4 % coverage). `complete` = 0 as well: no evidence that a listing *covers* a brief end to end | `sel-04` packaging families, the 12 missing upload references, and a completeness check per listing |
| 2 | **Product pictures** | `design-studio` 85.2 | **at the bar on score**, below on `correct` | seller 93.5 (the twelve stored-reference briefs), complete 66.7 | `correct` = 60 on a 3-of-5 test cap; a fifth of the catalogue is measured at all | the `packaging_mockup` + `infographic` gaps (now deterministic), plus references for 44 briefs |
| 3 | **PPC** | `adpilot` 55.0, `towncrier` 55.0 | furthest below bar | works 100, usable 100, measured 100 | **`seller` 0, `complete` 0, `contract` 0.** No ad-versus-outcome evidence exists, and the contract check never ran for this service | `reg-03-plan-campaign` (handler), then an ads plan scored against a real budget file |
| 4 | **Golden Goose** | `goldengoose` 77.0 | below bar | complete 100, measured 100, contract 100 | `seller` 0 and `correct` 60: the ranking maths is proved, the *seller outcome* is not | handler `reg-03-scan-products`, then a scored run over a real catalogue slice |
| 5 | **Research** | `prospector` 100.0 (at bar) | **at bar** | everything 100 | nothing for the service itself; the *Intel plane* (M3-intel I0–I3) is unbuilt, so research output is not yet normalised or licence-checked | M3-intel-I0…I3 (4 units, ranked below the seller-facing four) |
| 6 | **Design Studio** | `design-studio` 85.2 | see #2 | correct 60, complete 66.7 | same two dimensions; the canvas work (ux-09) is UI, not score | the deterministic layout stages now cover infographic and packaging; the remaining gap is references |

## The one pattern

`works`, `usable` and `measured` are **100 almost everywhere** — the machinery runs, is used, and is
measured. What is missing is the two dimensions that need *evidence from outside the code*:

- **`seller` = 0** wherever the reference-scored pass does not reach. It reaches 12 briefs of 56.
- **`correct` = 60** wherever the dimension is capped by a 3-of-5 test rule that no service has yet
  beaten with real artefacts.

So "launch readiness" is not a code question any more. It is a **coverage** question: more real
references, and one end-to-end proof per promise.

## Ranked by what a seller feels first

1. **Listings** — the deliverable everything downstream scores. Blocked on coverage, not code.
2. **Product pictures** — closest to the bar (85.2) and blocked on two specific situations, both now
   deterministic.
3. **PPC** — furthest below (55.0) and the only core area with `contract` at 0: nothing has checked
   that what it promises is what it does.
4. **Golden Goose** — maths proved, outcome unmeasured.
5. **Research** — at the bar; the unbuilt Intel plane is upside, not a blocker.
6. **Design Studio** — same two dimensions as #2; UI work is done.

## What this table does not claim

The scores are the scorecard's, not a judgement. A service at 86.2 with `complete` 0 is *not* ready
to launch; it is a service that runs and is measured in five of seven dimensions. The two rows that
matter for a launch decision are `seller` and `correct`, and neither is above 60 anywhere.
