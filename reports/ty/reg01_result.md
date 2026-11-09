# The service registry is the source of truth, and it already disagrees with the product

2026-11-08, reg-01. Owner instruction: build the service registry first, walk every
advanced-view route with Ty's Vision and the backend, record purpose, inputs, outputs, actions
and Bojo tool, then generate the tool list and the default Northstar workspaces from it — without
rebuilding advanced view as a prerequisite.

## What exists now

| file | what it is |
|---|---|
| `ty/service_registry.json` | 29 services, **79 actions**, 452 mounted routes indexed across the 32 modules `main.py` actually includes |
| `ty/bojo_tool_list.json` | every tool a service owns, generated from the registry |
| `ty/northstar_workspaces.json` | one default-view workspace per service, generated from its inputs/outputs/actions |
| `ty/registry_gaps.json` | the 13 services with **no controls**, and what is missing |

Each entry carries purpose, `inputs[]`, `outputs[]`, `actions[]` (with `file:line` or endpoint),
`bojo_tool` (`wired | declared | none`, with a reason), `has_controls`, and an `evidence` block
that says whether the route was seen **live**, from a **screenshot**, from the **audit frames**,
or from the **backend only**.

## Evidence, honestly labelled

```
backend 4 · live 4 · screenshot 21
```

The first walk found **0 live** because nothing was listening on `127.0.0.1:8101` and no Chrome
window existed — the registry said so per route instead of claiming a page. I started the UI and
Chrome on Profile 6 and re-walked: **4 routes came back live** (jobs, beta, design-studio,
product-finder), described by `understand.describe_page`. The walker's navigation degrades after a
few tabs, so 21 services rest on the committed screenshots — which are themselves vision output —
and 4 on the backend alone. That limit is recorded, not smoothed.

## Bojo tools, and the holes it exposed

21 tools are owned by a service: **14 wired, 7 declared with no handler**. 27 of the 41 entries
in `chat_tools.TOOLS` are unclaimed by any service.

Declared, no handler: `build_dieline`, `compose_listing`, `margin_report`, `plan_campaign`,
`scan_products`, `track_keywords`, `watch_competitor`.

## Default-view workspaces, generated

29 specs, each declaring `layout`, `primary_action`, `empty_state`, `data_shown` and a one-line
`why`. Layout distribution: **feed 9 · split 8 · board 6 · wizard 5 · canvas 1**. Two services may
share a shape; none is a wrapper around the advanced page, which is what the instruction forbids.

## Gaps: 13 services with no controls

`hub, ledger, thewatch, rankledger, rivalboard, account, foundation, beta, beta-support, beta-ops,
listings, keyword-tracker, competitor-monitor` — each with the reason recorded. Example:
*listings — "New Rule only toasts, History and Escalate navigate; no diff review or rule
creation."* These are the only services where advanced view gets touched, and only to fill what
the registry proves is missing.

## Two findings worth their own line

1. **`ProductFinder.jsx` makes no API call at all.** `/api/products/finder` appears only in
   comments, and adding an ASIN stages `UNKNOWN`s in local state. So product-finder records zero
   actions, and its "it works" was never true.
2. **Seven advertised tools have no handler** — the service registry and the tool surface
   disagree, and the test that keeps them honest is `test_service_registry.py`.

## Tests

```
python -m pytest Northstar_backend/test_service_registry.py -q
16 passed
python -m tools.registry.build --check
registry, tool list, workspaces and gaps agree
```

One fix was needed after merge: `apply_vision` assumed string controls and crashed on the
`{label, kind}` objects the live walker writes. It now accepts both, so live evidence can be
applied without hand editing.
