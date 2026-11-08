# Ty architecture

What this system is, how the pieces fit, and which invariants hold it together. Written
2026-11-08 at the end of the D0–D17 batch; the source of truth is the code named here.

## The shape

```
                     ┌──────────────────────────────────────────┐
  owner ─────────────►  Director (one cloud session)             │
                     │  reads MANDATE + TARGET_SPEC + queue      │
                     │  scores gaps, dispatches, merges, logs    │
                     └───────┬───────────────┬───────────────────┘
                             │ scoped jobs    │ merges (gates)
                  ┌──────────▼─────────┐  ┌──▼──────────────────┐
                  │ Builders (≤4)      │  │ staging branch      │
                  │ one worktree each  │  │ (main needs verifier)│
                  └──────────┬─────────┘  └─────────────────────┘
                             │
   ┌─────────────────────────┴────────────────────────────────────┐
   │ Ty's Vision: capture → privacy → tree/DOM → VLM → control     │
   │ one GPU lane, one browser, one set of risk classes            │
   └──────────────────────────────────────────────────────────────┘
```

## Roles and where each lives

| role | code | rule |
|---|---|---|
| Director | this session + `tools/director_units.py`, `director_queue.py`, `director_gaps.py` | never builds directly; owns the ranked gap list |
| Builders | `state/worktrees/<lane>`, branch `ty/<lane>` | one scope manifest each; never touch the main tree |
| Seller-Tester | `tools/seller_tester/` | scores like a seller, files gaps, escalates difficulty |
| Scouts | `tools/scout/` | GitHub/HF/PyPI/npm/arXiv, licence-verified, ranked |
| Model Scout | `tools/model_scout.py` | fixed evals per role, swap only on a clear margin |
| Verifier | separate session, `reports/ty/d15_verification.md` | never built anything; reproduces or says FAILED |
| Vision Operator | `tools/vision/` | local model only; cloud sees text, never pixels |
| Bojo | `ollama bojo:latest` | master router, measured 15/18 on the router eval |

## The queue and the gap rule

`gap = impact × (bar − score)`, ranked in `ty/scorecards.json`. A bundle must move a
dimension ≥ 5 points or close ≥ 3 gaps, otherwise it is a micro-edit and is refused
(`tools/director_gaps.py`). An empty queue while any service is below the bar calls
`replan()`; if that cannot produce work it writes a defect to `self_assessment.md` and
`needs_you.md`. Idle is a failure, by code.

Scope manifests are enforced by `tools/director_queue.py`: two concurrent jobs whose
`write_paths` overlap are refused by name, not queued silently. `main` cannot be moved
without `verifier_reproduced=True`.

## Scoring

Six weighted dimensions per service: `works` 0.28, `correct` 0.25, `complete` 0.12,
`usable` 0.12, `measured` 0.10, `seller` 0.13, bar 85 **per dimension** — an 85 average is
not a pass.

- `works`/`correct` come from test ids (`reports/ty/_idlist_*.txt`), matched by explicit
  filename patterns, never by inference. Passing tests score `correct` at **60, not 100**:
  tests prove a code path, not that the output is worth selling.
- `complete` comes from whether the Bojo tools a service declares are actually present.
- `usable` comes from the readiness scan's findings that name the service.
- `measured` comes from `tools/measured.py`: the route is **mounted** (`source:
  'app-route'` or an explicit `<Route>`), the component exists, and the app answers inside a
  latency budget. A catalogue entry is not a page.
- `seller` comes from `tools/seller_scores.py`: the mean of real Seller-Tester output scores
  for that service, requiring at least five scored outputs. A service with no scored output
  gets 0 and the reason, so **artefacts alone cannot raise a service to the bar** (the
  ceiling without seller evidence is 77).

## Ty's Vision

Deterministic before pixels, in this order:

1. **Privacy first** (`tools/vision/privacy.py`): title, process and URL are checked against
   the blocklist *before* a frame exists. Amazon is first and absolute. A refused window
   yields no pixels, no elements, no title.
2. **Structure** (`tree.py`, `browser.py`): the UIA tree and the CDP accessibility tree.
3. **Understanding** (`understand.py`): `qwen2.5vl:7b` on a clean server (f16 KV cache,
   `num_ctx` 8192), 0.47–0.75 s, downscaled to 1280 wide.
4. **Grounding** (`grounding.py`): measured 61.7 % hit rate on 40 screens with 21.7 %
   abstentions — so pixels are a fallback locator, `(0,0)` means no click, and every
   pixel-driven click is verify-after-act.
5. **Control** (`risk.py`, `act.py`, `control.py`): five risk classes; irreversible and
   blocked never execute; every action is observed again and verified, retried once, then
   reported.
6. **Browser** (`browser.py`): CDP over a Profile 6 lease, policy re-checked on every
   navigation, edits refused on external hosts.
7. **Browser without CDP** (`chrome_uia.py`): when Chrome will not expose a debugging port,
   the same job is done through UI Automation with the pixel fallback — blocklisted windows
   refused, foreground verified before every keystroke, its own tab, closed at the end.
8. **Live mode** (`live.py`): narration and questions, text only.
9. **Computer mode** (`computer.py`, `scope.py`): files, processes, windows, launches, behind
   scope and grants; `TY_PC_MODE` needs flag **and** grant.

## The GPU

One heavy lane at a time, owned by `tools/gpu_budget.py`:

- file lock (`state/gpu/lock.json`), per-role budgets, `nvidia-smi` before and after;
- residents are Bojo + embeddings; vision keeps Bojo only;
- heavy roles (27B) are **off by default** and need a stated lease;
- ComfyUI is never shared: `tools/comfy_lane.py` starts its own instance, stops it, and
  verifies the port closed. `free_comfy()` is not trusted — it acknowledges and releases
  nothing on this build.

## Loop and persistence

`scripts/ty_director.py` keeps exactly one director session alive with a model-free 5-minute
heartbeat, restarts a dead session with the resume line and a crash note, honours
`state/vision/PAUSE` and `STOP`, and stops at the token cap. It is registered as the
`NorthstarTyDirector` logon task with restart-on-failure.

## Invariants someone will break first

1. **Amazon is checked before everything.** Any new code path that touches a browser or a
   window must call `privacy.classify` first.
2. **Pixels never leave the machine.** A cloud model gets text after redaction.
3. **Irreversible means `needs_you.md`.** Not "ask later", not "try it and see".
4. **Evidence is a command and its output.** A claim without one is not a result.
5. **`main` moves only when the verifier reproduces the scorecard.**
6. **A test that would pass without the feature is not a test.** No skips as proof.
