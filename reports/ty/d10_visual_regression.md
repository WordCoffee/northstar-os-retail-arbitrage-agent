# D10 — Visual regression gate

**Branch** `ty/builder-d10` (worktree `state/worktrees/builder-d10`)
**Date** 2026-11-08
**Status** Built and proven offline. No baseline has been captured yet — the dev
server was not running, so the live attempt exercised the refusal path (exit 2)
exactly as specified. That is the honest state: the gate refuses to invent a pass.

## What exists

| path | role |
|---|---|
| `ty/visual_views.json` | 31 views: every route in `ty/services.json` + `/` + `/home`; per-view viewports, readiness, freeze seed |
| `tools/visual_regression/build_registry.py` | regenerates the registry from the service catalogue; `--check` fails when stale |
| `tools/visual_regression/freeze.py` | seeded still mode: `?still=1&seed=<n>`, paused animations, `transition: none`, frozen clock, seeded `Math.random`, `window.__NS_STILL__` |
| `tools/visual_regression/capture.py` | Playwright capture, desktop Chromium 1440x900 + iPhone 12 WebKit 390x844; loopback-only, reachability-first, blank-page and still-mode assertions |
| `tools/visual_regression/diff.py` | perceptual envelope diff (PIL + numpy), per-view verdict, bbox and metrics |
| `tools/visual_regression/baseline.py` | armed baseline promotion + append-only `baselines/CHANGELOG.json` |
| `tools/visual_regression/gate.py` | CLI (`--self-test`, capture, `--update-baseline --scorecard-passed`), JSON report, exit codes 0/1/2/3 |
| `tools/visual_regression/make_fixtures.py` | deterministic fixture generator + `--check` |
| `tools/visual_regression/fixtures/` | 6 synthetic pairs (4 fail-cases required, 2 pass-cases for tolerance) |
| `tools/visual_regression/baselines/CHANGELOG.json` | empty, append-only baseline history |
| `Northstar_backend/test_visual_regression.py` | 41 offline tests, no browser |

## How the freeze works

Three independent layers, because any one of them can be defeated by a page that
animates on load:

1. **URL contract** `?still=1&seed=<n>` (preserves existing query and fragment;
   `/beta#support` becomes `/beta?still=1&seed=<n>#support`).
2. **Init script** `freeze.still_init_script(seed)`, installed with
   `page.add_init_script` so it runs before app code on every document:
   `animation-play-state: paused !important`, `transition: none !important`,
   caret/scrollbar suppression, `Date`/`Date.now`/`performance.now` frozen at
   `2026-11-08T12:00:00Z`, `Math.random` replaced by a seeded mulberry32 generator,
   `data-ns-still="1"` on `<html>`, and `window.__NS_STILL__` for verification.
3. **Screenshot options** `animations="disabled"`, `caret="hide"`, `scale="css"`.

The capture **refuses** when `window.__NS_STILL__` is absent — a page that did not
freeze is never screenshotted. The UI does not yet honour `still=1`; layers 2 and 3
carry determinism today, and the UI follow-up is written into
`tools/visual_regression/README.md`.

## Why the diff is not a raw pixel count

Raw pixel comparison fails the antialias case: every glyph edge changes at full
contrast for a half-pixel shift. Raising the threshold until that passes makes a
changed price invisible. The metric therefore compares the candidate against the
baseline's **3x3 min/max envelope** (± tolerance 12, both images blurred at 0.8):

* pass if nothing changed, or changed area ≤ 0.4 % and no 8x8 block cluster holds
  ≥ 30 changed pixels;
* fail on size mismatch, on a colour change, on a 28 px move, on a changed revenue
  figure (0.07 % of the frame — caught by the cluster rule, not the ratio rule).

Thresholds live in `diff.DiffConfig` and are recorded in every report.

## Evidence

### 1. Unit tests — `python -m pytest Northstar_backend/test_visual_regression.py -q`

```
41 passed in 0.58s
```

Covers: registry completeness against `ty/services.json` (31 views, both viewports,
unique seeds, fresh against the generator), still-mode contract (URL, script
contents, frozen epoch), all six fixture pairs, identical pass, moved/colour/text
fail, size mismatch, determinism, the self-test, baseline refusal without
`--scorecard-passed`, changelog shape and history, scorecard-file refusal,
CLI refusal for missing/unreachable/non-loopback base URLs (with the browser call
patched to raise if it is ever reached), CLI promotion with both flags, uniform
screenshot rejection, and `no_baseline` never counting as a pass.

### 2. Fixture proof — `python -m tools.visual_regression.gate --self-test`

```
pair       expected  actual  ratio      cluster  verdict
identical  pass      pass    0.0000     0        OK
antialias  pass      pass    0.0001     3        OK
noise      pass      pass    0.0000     0        OK
moved      fail      fail    0.1045     10841    OK
recolour   fail      fail    0.0203     2106     OK
text       fail      fail    0.0007     72       OK
6/6 fixture pairs classified as expected
```

Exit code 0. This is the proof that runs with no server and no browser.

### 3. Live capture attempt — `python -m tools.visual_regression.gate --base-url http://127.0.0.1:8101`

```
REFUSED: app not reachable at http://127.0.0.1:8101 (URLError: <urlopen error
[WinError 10061] No connection could be made because the target machine actively
refused it>). No capture taken; a blank page is never a pass.
exit=2
```

Port 8101 was genuinely down (`Invoke-WebRequest` reproduced the refusal before
the gate was written). No artifact, no baseline, no false pass — the exact
behaviour the brief asks for. The first real baseline therefore still needs a run
with the dev server up.

### 4. Registry and fixtures are reproducible

```
python -m tools.visual_regression.build_registry --check  -> OK: 31 views match
python -m tools.visual_regression.make_fixtures --check   -> OK: 6 fixture pairs present
```

## Baseline protocol

Baselines live at `tools/visual_regression/baselines/<view>/<viewport>.png`.
Promotion requires both `--update-baseline` and `--scorecard-passed`; the latter is
never inferred. Optional `--scorecard-file` records the full verdict and is itself
a refusal when it says `passed: false`. Each accepted promotion appends
`{ts, view, viewport, commit, scorecard, baseline_sha256,
previous_baseline_sha256, source_artifact, prior_verdict}` to
`baselines/CHANGELOG.json`. Tests prove both the refusal and the entry.

## Gaps / follow-ups

1. **No baselines exist yet.** Intentional: the server was down, and the protocol
   forbids inventing them. Next action with the server up:
   `python -m tools.visual_regression.gate --base-url http://127.0.0.1:8101
   --update-baseline --scorecard-passed` after the scorecard passes.
2. **UI does not honour `still=1`.** The init script freezes the page regardless,
   but real timestamps/metric numbers will still drift until the UI seeds them from
   `seed`. That is UI work outside D10's write scope; the contract is documented.
3. **WebKit binary.** The iPhone 12 pass needs `python -m playwright install
   webkit`. If it is absent the gate refuses with `browser_unavailable:webkit`
   rather than silently skipping mobile.
4. **Baseline set is 31 views x 2 viewports = 62 images.** Not captured here;
   first capture will be large in bytes and should land with the UI freeze work so
   the first baseline is not built on drifting data.

## Rollback

Everything is additive from `e5dccbbd` on branch `ty/builder-d10`: one new package
directory, one test module, one registry file, one report. No existing file was
modified, so rollback is `git revert <commit>` or branch deletion.
