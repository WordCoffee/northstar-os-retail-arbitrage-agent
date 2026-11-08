# Chrome without CDP, and a scorecard that cannot be gamed by tests

2026-11-08, owner instruction batch: replace DIR-4, drive Profile 6 through UIA plus pixels,
verify three improved services, put Seller-Tester scores into the scorecard, run the full
suite, list the FAILED verifier items, keep the gap loop running.

## 1. Chrome: version, the toggle that does not exist, and the route that does

| step | result |
|---|---|
| Version | **156.0.8078.80**, running as pid 28428 on the default user-data-dir with Profile 6, no `--remote-debugging-port` |
| Relaunch with `--remote-debugging-port=9222` | handed off to the running instance; `http://127.0.0.1:9222/json/version` still refuses; no process carries the flag |
| `chrome://inspect` | no toggle exists that enables a debugging port on a running browser, and Chrome **ignores** `chrome://` URLs passed to a running instance — `start chrome://inspect` opened nothing (two windows, titles unchanged) |
| Fallback | **built**: `tools/vision/chrome_uia.py` drives Profile 6 itself through UI Automation with the pixel fallback |

The UIA route keeps every guard: a blocklisted window is never focused, the foreground is
verified immediately before any keystroke, it opens **its own tab** rather than navigating
yours, and it closes that tab. No throwaway profile, no profile copy, no killing Chrome.
10 tests (`Northstar_backend/test_chrome_uia.py`), including "Amazon window is refused
before SetActive is called" and "keys are refused when the foreground changed".

The ten-task parity suite gained a `uia` backend, so the same ten tasks can run through
either route.

## 2. What blocks it now: the desktop is locked

```
foreground: 'Windows Default Lock Screen' | LockApp.exe
```

A locked session is a different desktop: no keystroke reaches Chrome and UIA can only read
the lock window. Both the UIA backend and the dogfood harness refuse by name:

```
python -m tools.vision.parity --run --backend uia
{"backend":"uia","ran":false,
 "reason":"the desktop is locked (foreground is LockApp.exe); UIA cannot drive a browser behind the lock screen"}
```

`reports/ty/d8_parity_uia.json` is the artefact. V3 therefore stays **BLOCKED** — but now it
is blocked on a locked screen, not on a missing implementation, and the remedy is presence,
not a password.

## 3. V9 dogfood, ready and unexecuted

`tools/vision/dogfood.py` opens the three improved services (`competitor-monitor`,
`listings`, `socialpulse`) through Vision, reads what rendered, and runs a checkable seller
task on each: does the page show the service's own vocabulary **and** a number a seller could
act on. A page that renders an empty shell fails, which is the point.

```
python -m tools.vision.dogfood --services competitor-monitor,listings,socialpulse
{"pass": false, "reason": "no live Vision session: the desktop must be unlocked and Chrome attached"}
```

Five tests hold the harness honest (a real page passes, an empty shell fails, vocabulary
without a number fails, a run without a session records the refusal). The live run is queued
for the moment the desktop is unlocked.

## 4. The scorecard can no longer be raised by tests alone

Two changes in `tools/scorecards.py`:

- **a passing test is worth 60 on `correct`, not 100** — tests prove a code path, not that
  the output is worth selling;
- a sixth dimension, **`seller`** (weight 0.13), is the mean of the Seller-Tester's real
  output scores for that service, requiring at least five scored outputs.

New weights: works 0.28, correct 0.25, complete 0.12, usable 0.12, measured 0.10, seller 0.13.

Effect at once, with the real Seller-Tester pass (`30 outputs, 0 passed, mean 16.7`):

| service | before | after | why |
|---|---|---|---|
| listings | 100.0 | **77.0** | tests + route + latency, but no seller output scored |
| socialpulse | 100.0 | **77.0** | same |
| design-studio | 95.0 | **75.2** | its own 30 outputs average 16.7 |
| everything else | ≤ 95 | ≤ 77 | no seller evidence anywhere |

**No service is at the bar, and 77 is the ceiling a service can reach on artefacts alone.**
That is the honest number: the product's outputs are not good enough yet, and the scorecard
now says so instead of crediting a green test suite.

## 5. Digest

`tools/ty_digest.py` renders a **Verifier FAILED items** table from
`reports/ty/verifier_findings.json` — currently D17 (unreproducible bake-off, re-probed) and
V9 (dogfood, blocked on V3) — plus a "blocked, not failed" line for V3.

## 6. Gap loop

Four bundles were queued by the re-plan (`raise complete` for goldengoose, offerchisel,
prospector, hub). Their Bojo tools are now declared in `ty/services.json`
(`catalog_pull`, `golden_goose_scan`, `offer_recommendation`, `hub_status`) and two builders
are implementing them; `complete` moves only when the tool really exists in the backend.
