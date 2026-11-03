# UX rebuild — needs you

Owner-only actions. Everything else continues without them.

## 1. Close the Tailscale serve on port 8000 so the dev stack can start (blocks all browser work)

`scripts/dev-start.ps1` runs `scripts/check_dev_safety.py` first and it refuses:

```
REFUSING dev bypass - one or more exposure conditions detected:
 - tailscale funnel status is non-empty
 - tailscale serve config targets port 8000
```

Observed config (read-only):

```
$ tailscale serve status
https://msi.tail4b3dfd.ts.net (tailnet only)
|-- / proxy http://127.0.0.1:8000
```

The gate is right: the dev login bypass (`ENVIRONMENT=development`, demo session on loopback)
is reachable from anything on the tailnet while that proxy exists. I will not disable your
Tailscale config, and I will not touch the gate's behaviour.

**What I need from you:** either

- `tailscale serve reset` (turns off the tailnet proxy), or
- tell me the dev stack may run on a different loopback port and I will add that as a script
  option in a later unit.

Until then: the backend/e2e suites cannot run (no server), so every UI unit is built to the
point where it needs a browser, then marked `verification_pending` in `ux_queue.json`.
No unit is claimed VERIFIED without a browser run.

## 2. Studio top-up payment processor (future; interface stubbed only)

Per the work order, the billing interface is a stub in this run. When the real top-up ships it
needs an owner-configured processor (Stripe or equivalent), merchant account, and price table.
Not blocking any current unit.

## 3. Decision: does the Design Studio page keep a chat box? (2026-11-03, U14 adjudication)

Six e2e specs (`acceptance-mogra` T-auth, `asset_picker`, `chat_composer_stability`) still fail
because they open `/ui/design-studio` and wait for `data-testid="chat-input"`. That route renders the
real studio page, not the chat shell — `App.jsx` keeps `/design-studio` out of the Northstar chat
replacement, and the chat composer lives in the workbench dock (`/ui/workbench`) and in advanced
view. This was already true at the U0 baseline commit, so it is not a regression: those specs predate
the mode gate.

**What I need from you:** one of these, and I will do it in a later unit —

- **(a)** the Design Studio keeps its chat box (a studio-scoped Bojo inside the page), and I re-point
  the specs at it; or
- **(b)** the chat stays in the workbench only, and I rewrite those three specs to drive
  `/ui/workbench` instead (the `acceptance-mogra` render requests would then be asserted through the
  workbench chat, which is the surface a user actually has today).

Silence means (b) is implemented as a spec-alignment task, not a product change.

Meanwhile the two `asset_dashboard` lane-trigger failures are **not** this: at HEAD the lane is
reachable and reports `media_generation_disarmed (MEDIA_GEN_LIVE is not 1)`. It needs you to arm the
media lane (a spend decision) before that test can see `done`.

