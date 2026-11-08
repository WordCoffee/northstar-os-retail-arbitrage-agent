# Ty Director — handoff

A fresh session continues from this file plus `ty/MANDATE.md`, `ty/TARGET_SPEC.md`
(when D4 lands) and `reports/ty/director_queue.json`.

## Resume line

> Hi, I'd like to give a work order to Ty. Resume the director program. Read
> `reports/ty/director_work_order.md`, `ty/MANDATE.md`, `reports/ty/director_queue.json`,
> and `reports/ty/handoff.md`, then continue from the first unfinished unit. No
> questions, no reports between cycles. Idle means re-plan.

## Current position

| field | value |
|---|---|
| unit | **D0 — baseline** |
| started | 2026-11-07 09:00 |
| rollback tag | `director-baseline` (at `de464cbd`) |
| model | DeepSeek V4.1 Flash on OpenCode Go (pinned, no fallback) |
| local lane | ComfyUI + qwen2.5vl, one GPU job at a time |

## What D0 has done

- `reports/ty/director_work_order.md` — the order, saved verbatim (172 lines).
- `ty/MANDATE.md` — the owner intent from §1 plus every hard line from §2, so the
  mandate cannot drift by omission.
- `reports/ty/director_queue.json`, `handoff.md`, `autonomy_log.md`, `grants.md`,
  `replace_later.md`, `self_assessment.md` — created; `state/director/` created.
- `director-baseline` tag created before any unit work.
- Measured full test run started: `scripts/run_all_tests.ps1` →
  `reports/ty/_baseline_measured_20261107.txt`. `tests/BASELINE.json` is updated from
  that run only, never by hand.

## Stopped on purpose

The previous autonomy loop (`tys_launcher` + `tys-watchdog`) is halted with a `STOP`
file so the baseline measurement is clean. D2 replaces it with the director launcher.
Its state and evidence are intact: `state/tys_runner/launcher.jsonl`,
`reports/ty/SESSION_RESUME_20261107.md`.

## Next

D1 — probe headless launch, OpenCode Go concurrency, capture libraries, UI Automation
access, GPU headroom → `reports/ty/director_probe.md`. Then D2, D3.
