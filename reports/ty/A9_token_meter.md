# A9 - token meter (`M0.3b-token-meter`)

**Date:** 2026-11-06
**Rollback point:** tag `autonomy-a9-pre` (`112fef46`)
**Files:** `tools/token_meter.py` (new), `Northstar_backend/test_token_meter.py` (new),
`reports/ty/autonomy_queue.json` (acceptance command + write_paths corrected)
**Touched by another lane this cycle:** `tools/tys_launcher.py` - **not modified here**.

## Why this exists

`tools/tys_runner.py` has enforced a 3,000,000/day cap since M0.1, at 90 % - but it
counts `result["tokens"]`, which a worker supplies. Nothing measured it. Live status
before this unit:

```
$ python tools/tys_runner.py status
  "tokens_today": 2162,
  "token_cap": 3000000,
  "cap_reached": false
```

2,162 recorded against one real session that the store says spent **133,739**. The
number was off by ~60x in the safe-looking direction, which is the direction that
never stops anything. So the cap was paperwork, not a cap.

## What was built

`tools/token_meter.py`, standard library only, no network, no writes:

| function | behaviour |
|---|---|
| `estimate_text(text)` | `chars / 4`, rounded **up**. Documented as a rule of thumb (+/-25 %), not a tokeniser. |
| `estimate_session(sid, db_path=None)` | reads `%USERPROFILE%\.local\share\opencode\opencode.db` through a `mode=ro` URI. |
| `estimate_payload(payload)` | same arithmetic over a JSON result dict, keys and nesting included. |
| `estimate_file(path)` | the CLI's `--file` path. |

`estimate_session` returns `{"tokens", "source", "session_id"}`, source one of:

1. `session_v2` - `tokens_input + tokens_output + tokens_reasoning`, when the row and
   columns exist. `tokens_cache_read` is **excluded on purpose**: it re-reads a prefix
   already counted as input, and counting it twice makes the cap fire on a long
   conversation instead of on real work. It stays in the store for a stricter figure.
2. `session_message` - `SUM(LENGTH(data)) / 4` when the counters are absent or null.
3. `unavailable` - `tokens: null`.

**None of these functions raise, and none of them return 0 for "unknown".** That is
the central design decision: `0` is indistinguishable from "this cycle was free", so
a missing store, an unknown session id, a locked file and a directory-where-a-file
belongs all produce `null` plus a `reason`. The meter also never creates the store it
measures - the tests assert that the path still does not exist afterwards.

One caveat is written into the docstring rather than left to be discovered:
`estimate_session(None)` is a **lifetime** total across every session (526,983,658 on
this box), not a daily one. The launcher wiring must filter by
`time_created`/`time_updated`; feeding the lifetime number to the cap would refuse all
work forever.

## Read against the real store

```
$ python tools/token_meter.py --json --session ses_e4d0675a2ffe4yNWug2cO5BRRe
{"tokens": 133739, "source": "session_v2", "session_id": "ses_e4d0675a2ffe4yNWug2cO5BRRe"}

$ python tools/token_meter.py --json --session ses_doesnotexist
{"tokens": null, "source": "unavailable", "session_id": "ses_doesnotexist", "reason": "no_rows"}

$ python tools/token_meter.py --json --file Northstar_backend/test_token_meter.py
{"tokens": 2017, "source": "file_estimate", "path": "...", "chars": 8067}
```

Exit codes: `0` measured, `2` nothing to measure. A JSON body is printed either way,
so a caller never has to parse prose.

## Tests

`Northstar_backend/test_token_meter.py` - 17 tests, temporary sqlite stores only, no
real store, no network:

- text estimate is deterministic, is `chars/4` rounded up (8 -> 2, 9 -> 3), and 0 for
  empty/None
- **a missing store returns `null`, never `0`**, source `unavailable`, and the meter
  does not create the file it was pointed at
- a directory in place of the store does not raise
- a `session_v2` row is read correctly: `1200+300+100 = 1600`, source `session_v2`
- cache reads are not double-counted: 5,000,000 cache-read tokens add nothing to a 60
  counter total
- a row whose counters are all NULL falls back to `session_message` lengths
- a store with **no** `tokens_*` columns falls back to `session_message` (800 chars ->
  200)
- an unknown id in a real store is `unavailable`, not 0
- the store survives the read intact
- `estimate_payload` on nested dicts equals independently computed key+leaf arithmetic;
  empty shapes are 0; nesting raises the count
- CLI `--json` for text, session (exit 2 when unavailable), file, and no target

```
$ python -m pytest -q Northstar_backend/test_token_meter.py
.................                                                        [100%]
17 passed in 0.21s
```

Only this file was run. No full suite (standing rule: verification is serialised, and
this lane's deliverable is one file pair).

## Reconciliations

- **Queue acceptance command was unsatisfiable.** `M0.3b-token-meter` declared
  `python -m pytest -q test_token_meter.py`, which the launcher runs with
  `cwd=ROOT`; no such file exists at the root, so the check would have failed
  regardless of the code. Corrected to
  `python -m pytest -q Northstar_backend/test_token_meter.py` (where every other
  `tools/` test lives: `test_tys_runner.py`, `test_tys_launcher.py`), and the test
  file was added to `write_paths` so the scope matches disk. Spec-vs-disk, stated not
  silently reinterpreted.
- **No zero, no exception, no invented number.** Where the store cannot answer, the
  answer is `null` + `reason`. That is the property the tests defend hardest.

## Not done here (deliberate)

- `tools/tys_launcher.py` wiring: another lane owns that file this cycle. Until the
  launcher reports `estimate_payload(result)`, the ledger still records worker-claimed
  tokens and the cap is still soft. **A9's meter is complete; the cap only becomes real
  with the wiring follow-up.**
- No change to `tys_runner.py` (cap math, ledger schema) - unchanged and still correct
  once it is fed a real number.

**Claim, precisely:** the estimator exists, is honest about what it does not know, and
is tested. The daily cap is *not yet enforced* - that is the follow-up unit.
