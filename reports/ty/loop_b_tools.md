# Loop B — Bojo tools for OfferChisel and Operations Hub

Branch `ty/loop-b`. Worktree `state/worktrees/loop-b`.
Scope written: three files, nothing else.

| file | contents |
|---|---|
| `Northstar_backend/bojo_tools_ops.py` | `offer_recommendation`, `hub_status`, `TOOLS` |
| `Northstar_backend/test_bojo_ops_tools.py` | 19 tests, no network |
| `reports/ty/loop_b_tools.md` | this report |

`ty/services.json` was already edited by the Director and was not touched.
`chat_tools.py` was not touched; the Director wires `TOOLS`.

## Contract

Both are plain functions with typed signatures returning JSON-serialisable data:

```
{"ok": true,  "tool": "<name>", "data": {...}}
{"ok": false, "tool": "<name>", "reason": "..."}
```

`hub_status` adds `data` to its refusal when per-service detail exists, so an
operator can see which sources failed rather than only that all of them did.

## Fee model (`offer_recommendation`)

Per unit the offer pays a **referral fee that is the greater of a percentage of
the sale price and a fixed per-unit minimum**, plus a flat fulfilment cost, plus
any other flat per-unit fee, plus cost of goods. Defaults are 15% with a $0.30
minimum, $0.00 fulfilment and $0.00 other — all four are overridable through
`fees={...}` and an unknown key is refused rather than ignored. The fee function
is piecewise, so both branches are solved in closed form:
`price = (cost + flat fees) / (1 - referral% - margin%)` when the percentage
binds, and `price = (cost + flat fees + referral_min) / (1 - margin%)` when the
minimum binds; the branch is chosen by the base cost at which the two meet,
`referral_min * (1 - referral% - margin%) / referral%`. The target margin must be
below `100 - referral%`, because that is the true asymptotic ceiling of this fee
model; anything higher is refused with the exact range. The competitor ceiling
(lowest price by default, or median) clamps the ask, optionally undercut by a
stated percent, and the result reports the margin **actually achieved**, never
the target. Rounding: the ask rounds up to the next whole cent, then by further
cents if needed so the half-up-rounded fee still clears the target; fees, profit
and margin are half-up to 2 dp from that rounded price. Every component and
every step is in `data["arithmetic"]`, so the seller can re-add it.

## Status aggregation (`hub_status`)

Reads the existing trust surface, `ops_status` (disk, database, lanes, models,
render lock) — no second source of truth is invented. Probes are injectable for
tests. Each service is `ok | degraded | critical | unknown` with the measured
payload as `evidence` and a `source` naming the `ops_status` function. A probe
that raises, returns a non-mapping, or reports `available: false` becomes
`unknown` for that service only. Empty lane telemetry is `unknown` — absence of
evidence is not health. `ok` is false **only** when every source was unreadable.

## Evidence

```
$ python -m pytest Northstar_backend/test_bojo_ops_tools.py -q
...................                                                      [100%]
19 passed in 0.21s
```

Neighbouring source of truth, unchanged and still green:

```
$ python -m pytest Northstar_backend/test_ops_status.py -q
................                                                         [100%]
16 passed in 1.22s
```

Randomised invariant check (500 cases, not committed): fee equals
`max(price × pct, min)`, profit re-adds from the rounded components, and the
unclamped ask meets its target margin in every case — 0 failures.

Demonstration, realistic numbers ($8.50 cost, $4.25 fulfilment, 15%/$0.30
referral, 25% target, competitors $34.99 / $32.50 / $36.00):

```
price 21.26 profit 5.32 margin 25.02 verdict sell
 - flat fees per unit = fulfilment $4.25 + other $0.00 = $4.25
 - base to recover = cost $8.50 + flat fees $4.25 = $12.75
 - percentage branch: $12.75 over (1 - 15% referral - 25% margin) = $21.25
 - round the ask up to the cent -> $21.25; add 1 cent so the rounded fee still clears the target -> $21.26
 - referral = max($21.26 x 15%, $0.30) = $3.19
 - total cost = $8.50 cost + $7.44 fees = $15.94
 - profit = $21.26 - $7.44 fees - $8.50 cost = $5.32
 - margin = $5.32 / $21.26 = 25.02% (target 25%)
```

Same inputs with competitors at $18.99 / $19.50:

```
clamped: 18.99 17.85 sell
['competitor ceiling $18.99 is below the target price $21.26; ask clamped,
  margin 17.85% vs target 25%']
```

`hub_status()` on this machine (real probes, loopback only):

```
hub: True ok {'total': 5, 'ok': 5, 'degraded': 0, 'critical': 0,
              'unknown': 0, 'readable': 5, 'unreadable': 0}
hub services: {'disk': 'ok', 'database': 'ok', 'lanes': 'ok',
               'models': 'ok', 'render_lock': 'ok'}
```

## Limits

- The fee model is flat per unit. Weight- or price-tiered marketplace fee tables
  are not modelled; a caller who needs tiers passes the resolved flat figures.
- The referral rate is a supplied number, not a live marketplace lookup — by
  design, since the tool must not call out.
- `hub_status` reports the operational substrate (the five `ops_status`
  components), not per-room business metrics; those are the scorecard's job.
