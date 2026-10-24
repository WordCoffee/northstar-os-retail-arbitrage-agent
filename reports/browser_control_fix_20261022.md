# Browser-control fix — dead-page transport + evaluator status

**Date:** 2026-10-22
**Repo touched:** `C:\Users\T2Hol\OneDrive\Documents\Default Project` (Chrome Connect) — commit `09f02e9`
**Northstar repo:** unchanged (working tree already dirty with other work; nothing committed there)

---

## 0. Premise correction (spec vs. disk)

The brief said "Commits 65fde11 and baeb480 are in the repo." They are **not in the Northstar
repo**. `git cat-file` on every branch, worktree, stash and reflog there returns nothing. They
exist in a **second, separate repo**: `C:\Users\T2Hol\OneDrive\Documents\Default Project`, which
is where Chrome Connect actually lives and where `opencode.json` registers the `chromeconnect`
MCP server. Both commits were read there, plus `6ee51b7`, which a prior session had already
landed on top of them attempting the same two fixes.

So: the work was real, the diagnosis was real, but the repo location in the brief was wrong.
Everything below was verified against the running controller, not the brief.

## 1. What 65fde11 / baeb480 / 6ee51b7 actually contained

| Commit | Claimed | Reality |
|---|---|---|
| `65fde11` | whisker recovery of a closed page handle | detection in `call().attempt()` |
| `baeb480` | `ensureLiveTab()` + self-staleness watcher | added, but **uncallable** |
| `6ee51b7` | both bugs fixed | Fix 2 partly; Fix 1 in the read branch only |

**`call()` was dead code and `ensureLiveTab()` could never run.** Three hard defects:

1. **`rpc` is never defined** anywhere in `chromecontrol-playwright-bridge.js` (0 declarations,
   6 call sites). `ensureLiveTab()` therefore threw `ReferenceError: rpc is not defined` the
   instant it was reached.
2. **`transport()` shadows `call`** with its own local closure over `session.call`, so the
   module-level `call()` — the one with the stale detection — was never executed for any action.
3. **`state` is undefined in `transport()`**; `ensureLiveTab(state.currentUrl || null)` at the
   read recovery site was an unconditional `ReferenceError`.

That is why the dead-page error reached the caller as `data.text`: the only code that could have
caught it was unreachable, and the branch that *was* reachable crashed before it could recover.

## 2. Fixes applied (commit `09f02e9`)

**Fix 1 — detection moved into the shared transport path.**
New `callOnSession(session, tool, args, opts)` is the single path **every** action uses
(navigate, click, type, press_key, snapshot, screenshot, read). It treats `/^### Error/m` or
`/Target page, context or browser has been closed/i` as a stale page **whether or not `isError`
is set**, routes through `ensureLiveTab(session, targetUrl)`, retries the original action
**exactly once**, and on a second failure **throws** with the error string and the exact href —
never returns it as data.

`ensureLiveTab()` was rewritten to take the session and call `session.call(...)`, so it can
actually execute. It tracks the last live URL on `globalThis` and throws
`ensureLiveTab: still not on a live page (href=…)` when it cannot recover.

**Fix 2 — the evaluator cannot pass on error content.**
`pw-tool.readLivePage()` returns `status: 'UNKNOWN'`, `text: null` for error content (never
`READ`), and `agent-loop` converts a thrown read into the `page_unreadable` **FAILED** path with
the error string in `result.error` and a `failed` journal decision.

**Self-staleness watcher** already stats both `chromecontrol-playwright-bridge.js` and
`chromecontrol-mcp-server.js` (from `6ee51b7`); the server file was not touched, so it was left
as-is.

## 3. Tests

```
=== ChromeControl results: 62 passed, 3 failed ===
```

4 new offline regression tests, all green:

- `bridge: dead-page error CONTENT is recognised as an error`
- `bridge: a dead page is rebuilt once and the action retried`
- `bridge: a page still dead after one retry THROWS, never returns data`
- `pw-tool: a read that returns error text is UNKNOWN, never READ`

The 3 failures are **pre-existing and unrelated** — they assert the shipped config must be
unpinned, while the operator pinned `Profile 6` (the same change that makes the isolation gate
refuse). Exact strings:

```
profile-default: shipped config NEVER pins a profile (no silent Profile 7 re-pin):
  FAIL: config default must be unpinned: expected null, got "Profile 6"
profile-default: unpinned config + no session pick => loadEffectiveSelection stays unpinned:
  FAIL: no pin + no session pick must stay unpinned: expected null, got "Profile 6"
session-profile: save/load is session-only and loadEffectiveSelection reuses it:
  FAIL: assertEq: expected "Profile 3", got "Profile 6"
```

Not fixed by me: changing them means overriding the operator's own profile pin.

## 4. Live verification — **not (a), not (b), not (c)**

The UI typing test on `http://127.0.0.1:8101/ui/` was run through the real controller
(`chromeconnect_run`, same stdio endpoint OpenCode spawns). Result:

```json
{ "status": "COMPLETE", "steps": 1, "stop_reason": "page read",
  "trace": [{ "step": 0, "action": "navigate",
              "url": "http://127.0.0.1:8101/ui/sign-in", "page_status": "READ" }],
  "data": { "title": "NorthstarOS — Retail Arbitrage Suite",
            "text": "…Enter your credentials to access NorthstarOS. Email or Organization ID / Password / Sign In…",
            "page_status": "READ" } }
```

**Outcome: blocked at the sign-in wall.** Two independent blockers, neither caused by this fix:

1. **`/ui/` redirects to `/ui/sign-in`.** The chat composer does not exist without
   authentication. Chrome Connect must never enter credentials, so it cannot get past this —
   correct behaviour, wrong state for the test.
2. **The controller cannot type at all.** `buildPlan()` in `chromecontrol-mcp-server.js`
   (line 280) is hardcoded to `navigate` → `readLivePage` → `done`. It never emits
   `click`, `type` or `press_key`, so the "click the message box and type" half of the test is
   structurally unreachable through `chromeconnect_run`, independent of any page state.

Also surfaced, and **left unfixed deliberately**: `buildPlan`'s `{done:true}` yields
`status: COMPLETE` unconditionally (`agent-loop.js:133`), and the server's evaluator stub is
`met: !!ctx.tool_result`. A run therefore reports COMPLETE after reading *any* page, including a
login page, without performing the task. That is a real honesty defect in the status field, but
changing COMPLETE semantics is cross-cutting (sourcing runs depend on it) and was out of this
brief's scope. It is the reason the run above says COMPLETE while having typed nothing.

No ensureLiveTab error was produced and no policy refusal was returned on the second run (the
first run, with isolation left at its default, did return `isolated_profile_required`; that was
an artefact of `requireIsolated` defaulting to `true`, and was explicitly waived for a
loopback-only test — no policy file was edited).

## 5. Phase 2 (intent router) — **not started**

The brief gates Phase 2 on Phase 1 reporting **(a)**. Phase 1 reported none of (a)/(b)/(c); it
is blocked by an auth wall and a planner that cannot type. Starting `chat_router.py` now would
violate that gate, so no router code, no tests, and no `fix(router)` commit were produced.

## 6. Still open (unchanged)

- **Canvas (black)** — open.
- **Live voice** — open.
- Chrome Connect tool surface disappeared from this session when the host self-exited on the
  bridge edit; the patched server boots and lists all 6 tools when spawned fresh. A new session
  re-registers it.
