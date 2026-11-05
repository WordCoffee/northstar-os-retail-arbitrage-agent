# Handoff — Ty autonomy program

**Updated:** 2026-11-05T21:35Z · **Phase:** C (loop, cycle 1 complete) · **Branch:** feature/chrome-connect-3.0

## Resume in one line

Read `reports/ty/autonomy_queue.json` and continue from the first `pending` item,
highest `priority` first. The queue is the source of truth; this file is the map.

## Where things stand

| Thing | State |
|---|---|
| Phase A probe | Done. `reports/ty/capability_probe.md` has PRESENT/PARTIAL/MISSING with commands and outputs. |
| Phase B repairs | Done for A4 (research), A6 (MCP client), A7 (context compaction), A9 (vision model). A10 and A3 stay PARTIAL for stated reasons. |
| Phase C plan | `reports/ty/production_plan.md` — 14 workstreams ranked by impact x gap. |
| Cycle 1 shipped | Product Pictures instrument + first measured lift: main-image compliance 0% -> 100% on 3 measured cases. |
| Full suite | Green at HEAD before the new tests: 6196 backend / 511 GG / 1122 UI / 307 shell / 31 functions. A post-change measured run is the gate for updating `tests/BASELINE.json`. |

## Commits this session

```
4e69f0f1 GRANT: replace the local vision QC model with gemma3:4b (llava:7b fallback)
a8d3c27e feat(product-pictures): stored-reference library, 60-case fixed bench, scorecard
b19582e0 feat(agent): compact at a measured 70% + write a handoff; feat(eval): picture scorecard
f029dd2b GRANT: register the MCP client and the research lane
```

Tags: `autonomy-baseline` (e61ba173), `autonomy-grant-01-pre`, `autonomy-grant-02-pre`,
`autonomy-cycle-01-pre`.

## Creative + UX are now the front of the queue (owner directive 2026-11-05 22:1x)

The owner said to start creative features and the UI/UX immediately, and to keep
deep-researching against Packify, Perplexity Computer, Claude Code, Jungle Scout,
Helium 10, tryholo and Canva until told to stop. So the ranking changed:

- **UX is measured now, not "16/16 units done"**: `tests/e2e/ux_scorecard.spec.ts`
  walks three journeys (first run, creative, research) on desktop Chromium and
  iPhone 12 WebKit, runs axe on every page, and writes
  `state/evidence/ux_scorecard_<project>_<journey>.json`.
  Measured: **20/20 page-measurements render, 0 critical a11y, 0 console errors,
  2 serious patterns left.** Fixed already: the app name was the `<h1>` on every
  route (now each page announces its own title) and muted ink failed AA
  (2.93:1 -> 4.77:1). Left: `tabIndex` on two scroll regions, the documents page's
  own contrast, and `/ui` + `/ui/home` still having "Bojo" as their first heading.
- **Creative identity is the top experiment** (`reports/ty/research_20261105.md`).
  E1 (Qwen-Image-Edit-2511) is BLOCKED: the weights are not on disk and 12 GB is
  needed against 9.5 GB free. The registry now says `weights_missing` instead of
  lying. E2 (deterministic composite) landed as
  `Northstar_backend/product_composite.py` with 7 CPU tests; its render step is
  the next GPU job.

## Do this next, in order

0. **UX** (`UX-a11y-1`): add `tabIndex={0}` to `main` and `.stage-canvas-pane`,
   fix the documents page's own heading/subtitle contrast, and give `/ui` +
   `/ui/home` a real page h1 (the Bojo dock becomes h2). Re-run
   `npx playwright test tests/e2e/ux_scorecard.spec.ts` on both projects.
1. **Creative** (`R-E2`): generate a scene canvas, BiRefNet the real photo,
   `product_composite.place_product`, then score the 12-case dev set. This is the
   run that should move `product_fidelity` off 0 for reference mode — the
   competitor gap that matters most (tryholo-class identity).
1. **W1-c2** — fix product fidelity: compare the product region, not the whole
   frame. Right now a correct lifestyle render scores 0 against a front
   packshot, which makes the dimension meaningless outside one scenario.
2. **W1-c2 (second half)** — run the 12-case dev set with `--models` so
   instruction fidelity and photographic quality stop being `unmeasured`. Those
   two are the difference between "it rendered" and "it is a good picture".
3. **W2-c1** — build the listing scorecard (rank 1 by impact x gap) and measure
   the current ListingForge output against 40 held-out listings.
4. **W0-c1** — the author/evaluator. Every workstream stalls when the queue
   drains, and the supervisor is idle right now (`remaining=0`).

## Traps that cost time already

- `dev-start.ps1` ends in `while ($true)`; run it **backgrounded**, never with a
  timeout, or the `finally` block kills the servers it just started.
- ComfyUI + a resident brain cannot coexist: `llama-server` held 2.6 GB and the
  render gate refused at 2368 MB. Drain the brain, verify `/api/ps` empty,
  render, restore, health-check.
- Playwright's `webServer` starts Vite but not the backend; `/api` proxies 502
  and the shell still renders. Start the dev stack for a real UI check.
- Windows `git checkout` restores CRLF, so a raw sha256 comparison "fails" on an
  identical file. Use `git diff --quiet`.
- PowerShell mangles JSON in `--args`; `mcp_client.py` has `--args-file` for
  that reason.

## Open decisions waiting on the owner

`reports/ty/needs_you.md` — five items, none blocking: listing style reference
set, real top-up processor, Amazon ad-video spec, nutrition/UPC finals, and the
product-pictures design call.
