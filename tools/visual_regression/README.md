# Visual regression gate (D10)

Screenshots every Northstar service view at **desktop 1440x900 (Chromium)** and
**iPhone 12 WebKit 390x844**, frozen so animation cannot flake, and compares each
capture against a committed baseline with a perceptual diff.

```
python -m tools.visual_regression.gate --self-test
python -m tools.visual_regression.gate --base-url http://127.0.0.1:8101
python -m tools.visual_regression.gate --base-url http://127.0.0.1:8101 \
    --update-baseline --scorecard-passed
```

Exit codes: `0` pass · `1` regression · `2` refused (unreachable app, non-loopback
URL, bad registry, missing browser, or `--update-baseline` without
`--scorecard-passed`) · `3` captured, no baseline yet.

## What is captured

`ty/visual_views.json` is generated from `ty/services.json` (every service route)
plus `/` and `/home` — 31 views, each with both viewports, a readiness condition
(`#root` + `networkidle` + minimum text), and a per-view freeze seed.

Regenerate after a service is added:

```
python -m tools.visual_regression.build_registry          # write
python -m tools.visual_regression.build_registry --check  # CI: fail if stale
```

## Frozen still mode — `?still=1&seed=<n>`

Every capture navigates to `<route>?still=1&seed=<n>` and installs
`freeze.still_init_script(seed)` via `page.add_init_script`, which runs before
application code on every document. The init script:

* pauses every animation (`animation-play-state: paused`) and removes every
  transition (`transition: none`), hides carets and scrollbars;
* freezes `Date`, `Date.now` and `performance.now` to **2026-11-08T12:00:00Z**;
* replaces `Math.random` with a seeded mulberry32 generator;
* marks the document `data-ns-still="1"` / `data-ns-seed="<n>"` and publishes
  `window.__NS_STILL__`, which the capture asserts — a page that did not freeze is
  refused, not screenshotted.

The screenshot itself also passes `animations="disabled"` and `caret="hide"`.
That combination is what makes the gate deterministic even though the app does not
implement `still=1` yet.

**UI follow-up (not done here, outside write scope):** the app should honour
`still=1` itself — skip entrance animations, seed placeholder/metric data from
`seed`, and render a fixed "as of" timestamp. Until then, layer 2 and 3 carry
determinism, and any view that renders real timestamps or random data will drift
and should be pinned by the UI work rather than by loosening the thresholds.

## Diff

Envelope comparison, not raw pixels: for each channel, the candidate pixel passes
if it lies inside the baseline's 3x3 min/max envelope ± tolerance. Both images are
blurred at radius 0.8 first. Results:

* identical / ±0.5 px antialias drift / ±6 channel noise → pass;
* a 28 px move, a colour change, a changed price (≈0.07 % of the frame) → fail.

Verdicts also fail on `max_pixel_ratio > 0.4 %` and on any 8x8 block cluster of
≥ 30 changed pixels. Defaults live in `diff.DiffConfig`; overrides
`--max-pixel-ratio`, `--min-region-px`, `--tolerance` are recorded in the report.

## Baselines

`baselines/<view>/<viewport>.png`. Promotion is a separate armed operation:

```
--update-baseline --scorecard-passed     # both required
```

Both flags are needed; `--scorecard-passed` is never inferred. Optional
`--scorecard-file <json>` records the full scorecard verdict (`passed: false` in
that file is itself a refusal). Each accepted promotion appends a
`baselines/CHANGELOG.json` entry with timestamp, view, viewport, commit sha,
scorecard result, new sha256 and the sha256 it replaced. Tests prove the refusal
path (`test_update_without_scorecard_flag_is_refused`) and the changelog shape.

## Fixtures — the proof that runs without a server

`fixtures/<pair>/{baseline,candidate}.png`, generated deterministically by
`python -m tools.visual_regression.make_fixtures`:

| pair | expected | case |
|---|---|---|
| identical | pass | same render |
| antialias | pass | half-pixel re-render |
| noise | pass | ±6 channel jitter |
| moved | fail | card translated 28 px |
| recolour | fail | accent block pine → amber |
| text | fail | revenue figure changed |

`--self-test` classifies all six and exits non-zero on any mismatch. The unit
tests (`Northstar_backend/test_visual_regression.py`) are offline, deterministic,
run in ~0.5 s, and never launch a browser.

## Refusals are the safety property

* No server is ever started by this tool.
* `http(s)` loopback only (`127.0.0.1`, `localhost`, `::1`) — anything else is a
  Chrome Connect job, not a screenshot job.
* Reachability is probed before a browser launches; failure exits 2 with the
  reason. A blank page is never a pass: the page must expose ≥ 40 characters of
  text, the screenshot must not be a uniform colour, and `window.__NS_STILL__`
  must be present.
* A capture error is `1`/`2`, never a verdict.

Artifacts land in `artifacts/<utc>/` (git-ignored); the report is
`artifacts/<utc>/report.json`.
