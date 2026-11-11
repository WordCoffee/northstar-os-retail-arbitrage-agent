# Visual regression gate, first live run — and what it proved

2026-11-11. Rollback tag: none needed (read-only; nothing in the repo was changed by the gate).

## The gate ran live for the first time

```
python -m tools.visual_regression.gate --base-url http://127.0.0.1:8101/ui/ \
    --report reports/ty/visual_regression_20261111.md --out state/visual_regression/20261111
```

→ **exit 3**, 62 results, **31 views × 2 viewports (desktop + iphone12-webkit)**, every one
`no_baseline`, artefacts under `state/visual_regression/20261111/<view>/<viewport>.png`.

Exit 3 is the protocol working, not a failure: `no baseline yet for some views: re-run with
--update-baseline --scorecard-passed once the scorecard passes`. A baseline is only set from a
passing scorecard, and no service is at its bar, so the gate refuses to freeze the current state as
"correct". That is the D10 rule holding under live conditions.

## Two real hazards found

1. **The base URL must be `/ui/`.** With `http://127.0.0.1:8101/` the gate refuses immediately:
   `REFUSED: home/desktop: ready selector '#root' never appeared` (exit 2). The app is mounted under
   the `/ui/` basename, which AGENTS.md states and this run re-proved.
2. **The python Playwright install had no browsers.** The node install (which ran the 60 e2e tests)
   has them; `python -m playwright` did not, so the gate refused with "Looks like Playwright was just
   installed or updated". `python -m playwright install chromium webkit` fixed it; logged in
   `provenance.csv` (Apache-2.0, download only, no paid credit).

## Vision verification of three views (the local model, loopback)

The gate proves captures exist; it does not prove the page is the page. The local vision model
(`gemma3:4b`) was asked to describe three captured desktop views and say whether each shows a
workspace with data and controls or only a chat shell:

| view | model's reading |
|---|---|
| `beta` | "three distinct workspaces: Product Finder, Golden Goose Finder, and Portfolio & Finance, each with associated data and controls" |
| `design-studio` | "Design Studio … options and controls for creating assets … 'Social post', 'A+ module', 'Product image', 'Clip storyboard', 'Package panel' … text fields for headline, body copy" |
| `listings` | "'Listing Guardian' workspace … search bar, tables of Identity Records with ABIN, Title, Status, Score, Updated Date … Alerts, Hits, History, Escalations" |

All three pass the "not a chat shell" question. That is the ux-05 claim (`29/29 routes render`)
independently confirmed on three routes at desktop, by pixels rather than by the diff of a file.

## What this does not prove

- **Mobile.** The iphone12-webkit captures exist but were not described; "renders" on mobile is a
  capture, not yet a verified workspace.
- **Baselines.** There are none, by design. The first baseline commit must come from a passing
  scorecard, and there is none.
- **The other 28 views.** Three were described, not thirty-one.
