# A17 — worker lane (`opencode run --agent tys`)

**Unit:** `M2-worker-lane` — "opencode run --agent tys returns output + model provenance reliably"
**Date:** 2026-11-06 · **CLI:** opencode v2.2.5 · **Model:** `opencode-go/deepseek-v4.1-flash`
**Base commit:** `3324b71f`

## Verdict

**The CLI runs headlessly. It always did.** The lane was broken by our reader, not by the
transport. `deepseek_worker` now records `{ok, session_id, model, text, seconds, errors}` with a
non-empty `text` and a real model id, proven against the live CLI (3.5 s, exit 0).

Three defects, all measured:

| # | Defect | Evidence | Fix |
|---|---|---|---|
| 1 | Text reader looked at `event["text"]`; the payload is at `event["part"]["text"]` | live stream below; old `worker_result.json` had `"events": 48, "text": ""` | `_read_run_stream()` |
| 2 | Provenance read `session_v2.model`, which is **NULL** for `run` sessions | `select model from session_v2` → `None` for every probe session | `_session_model()` reads the assistant `session_message` row |
| 3 | Preflight gated a deepseek dispatch on llama.cpp's `/health`, a process the worker never calls | `model_lane_down` while `opencode --version` was fine | `deepseek_lane_up()` |

Also fixed: `_opencode_exe()` returned the npm `opencode.CMD` shim (CreateProcess re-parses it
through a shell); it now prefers the packaged `node_modules/@opencode/cli/bin/opencode.exe`.

## 1. The probe asked for

```
opencode run --agent tys --format json --auto      <- "reply with the single word pong" on stdin
```

Run from Python (`subprocess.run(..., input=..., capture_output=True, text=True, timeout=180)`)
with the real binary, because a bare `opencode` is not CreateProcess-resolvable here:

```
C:\Users\T2Hol\AppData\Roaming\npm\node_modules\@opencode\cli\bin\opencode.exe
```

Result — **exit 0, no timeout, 1.6 s, 0 bytes stderr, 1029 bytes stdout**:

```json
{"type":"step_start","timestamp":1794004378792,"sessionID":"ses_e4d019fd0ffe3Eg35lvKsCjIOp","part":{...}}
{"type":"text","timestamp":1794004378810,"sessionID":"ses_e4d019fd0ffe3Eg35lvKsCjIOp","part":{"id":"prt_...","sessionID":"ses_e4d019fd0ffe3Eg35lvKsCjIOp","messageID":"msg_...","type":"text","text":"pong","time":{"start":1794004378794,"end":1794004378810}}}
{"type":"step_finish","timestamp":1794004379103,"sessionID":"ses_e4d019fd0ffe3Eg35lvKsCjIOp","part":{"type":"step-finish","reason":"stop","cost":0,"tokens":{"input":11063,"output":4,"reasoning":0,"cache":{"read":0,"write":0}}}}
```

It never hung. Nothing was killed.

## 2. Candidates, in the order the unit specified

All five were run against the real CLI. `text` is read from `part.text`, `session` from the
top-level `sessionID`.

| variant | exact command (after `opencode.exe`) | stdin | exit | s | text | session |
|---|---|---|---|---|---|---|
| C1 positional | `run --agent tys --format json --auto "reply with the single word pong"` | — | 0 | 1.5 | `pong` | `ses_e4d0062defferkE05eLFHOxmkx` |
| C2 default format | `run --agent tys --format default --auto` | 31 B | 0 | 2.8 | *(plain)* `pong` on stdout, `> tys · deepseek-v4.1-flash` on stderr | *(not emitted)* |
| C3 session reuse | `run --agent tys --format json --auto -s ses_e4d019fd0ffe3Eg35lvKsCjIOp` | 31 B | 0 | 1.2 | `pong` | same session reused |
| C4 explicit model | `run --agent tys --format json --auto --model opencode-go/deepseek-v4.1-flash` | 31 B | 0 | 1.4 | `pong` | `ses_e4d004d8affeimNcIS7yQLf36g` |
| C5 long stdin | `run --agent tys --format json --auto` | 6833 B | 0 | 1.3 | `pong` | `ses_e4d004809ffe1vzufpw7bGebhc` |

C2 is the only variant that loses the session id and the JSON envelope, so the shipped invocation
keeps `--format json` with the prompt on **stdin** (a 16 KB task contract exceeds the Windows
command line; C5 proves 6.8 KB of stdin is delivered intact). `--model` is supported but not
pinned in the command: `opencode.jsonc` already pins `opencode-go/deepseek-v4.1-flash`, and the
worker passes `--model` only when `TY_WORKER_MODEL` (or the task's `model`) is set.

## 3. Live proof of the fixed worker

`tools/tys_launcher.deepseek_worker(task, result)` called directly, nothing mocked:

```
worker_exit 0 wall 3.5
{
  "ok": true,
  "worker": "opencode/run",
  "lane": "tys",
  "session_id": "ses_e4cfd7836ffeMWtKQ3yae6SoUf",
  "model": {
    "agent": "tys",
    "model_id": "deepseek-v4.1-flash",
    "provider": "opencode-go",
    "variant": null,
    "cost": 0,
    "tokens": {"input": 11181, "output": 4, "reasoning": 61, "cache": {"read": 0, "write": 0}},
    "source": "session_message"
  },
  "model_provenance_ok": true,
  "seconds": 3.5,
  "events": 3,
  "errors": [],
  "text": "pong",
  "exe": "C:\\Users\\T2Hol\\AppData\\Roaming\\npm\\node_modules\\@opencode\\cli\\bin\\opencode.exe",
  "stderr": "",
  "objective": "Reply with the single word pong and change no file."
}
```

Preflight, and a zero-cycle launcher run (proves the lane is accepted now):

```
lane_up True
exe C:\Users\T2Hol\AppData\Roaming\npm\node_modules\@opencode\cli\bin\opencode.exe
$ python tools\tys_launcher.py --worker deepseek --max-cycles 0 --max-hours 0.01
{"stopped": true, "reason": "max_cycles", "cycles": 0, "tokens_estimate": 0, "seconds": 0.1}
```

## 4. Tests

`python -m pytest Northstar_backend/test_tys_launcher.py -q` → **21 passed in 5.88s**
(15 pre-existing + 6 new), no network, no real CLI:

- `test_the_worker_records_the_text_the_transport_returned` — fake transport emits the real
  `part.text` stream; asserts `text == "pong"`, `ok`, `session_id`, `model.model_id`,
  and that the prompt went on **stdin** while `--agent/--format` went on the command.
- `test_an_empty_answer_is_a_failure_not_a_silent_pass` — exit 0 with no text → `ok: false`,
  `errors[0]` starts `empty_text`. This is the exact silent pass that hid the bug.
- `test_a_transport_error_event_is_reported` — an `{"type":"error"}` event fails the dispatch.
- `test_provenance_comes_from_the_assistant_message_row` — a temp sqlite db with
  `session_v2.model = NULL` and the model on the assistant `session_message` row resolves to
  `deepseek-v4.1-flash`, `source: session_message`.
- `test_the_packaged_exe_is_preferred_over_the_npm_shim` — resolves `opencode.exe`, not `.CMD`.
- `test_a_dead_deepseek_lane_stops_without_asking_llama_cpp` — `model_up()` false + deepseek
  worker → no `model_lane_down`.

## 5. Cost, stated plainly

Nine real dispatches this unit (5 candidates + 1 probe + 1 live worker proof + 2 development
probes). Every one reported `cost: 0` in its `step_finish` event; the session store shows
`cost ≈ 1.2e-05` USD per short turn, i.e. well under one US cent in total, on the existing
`opencode-go` subscription. No new provider, key or paid credit was touched.

## 6. What this does *not* prove

- Not a full launcher cycle. `M2-worker-lane` is about transport, text and provenance; the
  author → evaluator → acceptance → commit loop is A11 (`M1c-evaluator`) and later, and the
  queue item still has no `acceptance_commands`, so the launcher will skip it as
  `no acceptance_commands declared` (that is A15's contract writer, not this unit).
- Not a long-run soak. The 8-hour unattended run is gate item C6.
- The worker edits files with `--auto`; scope enforcement is the evaluator's job (A11/A14),
  not the transport's.
