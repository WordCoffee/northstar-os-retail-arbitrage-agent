# U15 — suite-green work: AutothinK and the local model lane

**Verdict: DONE.** The 15 failing tests in the U15 scope are green (50 passed, 0 failed), and the
three defects behind them were real runtime defects, not test flake: the AutothinK premium server
could not be imported at all, and the coding agent's default local model could not be constructed.

## What was failing (measured, before any change)

```
python -m pytest test_autothink_auth_boundary.py test_autothink_routes.py \
                  test_autothink_transport.py test_local_model.py \
                  test_local_model_native.py test_local_model_ollama.py -q
→ 15 failed, 35 passed, 6 subtests passed
```

| Failure group | Count | Root cause |
|---|---|---|
| `test_autothink_routes.py` (9) | 9 | `ImportError: cannot import name 'build_system_prompt_with_context' from 'backend.llm_adapter'` at `autothink/backend/server.py:53` — the whole app fails to import, so every route test errors |
| `test_autothink_auth_boundary.py` (2) | 2 | same import error |
| `test_local_model.py` (4 of 5) | 4 | `NameError: name 'num_ctx' is not defined` at `agent_kernel/local_model.py:89` |

## The three defects, and what I did

**1. `build_system_prompt_with_context` was deleted, its importers were not.**
`git log -S "def build_system_prompt_with_context"` shows it added in `9d0c88be` and removed in
`7ace8f0b` (*fix: route DEFAULT_LOCAL_MODEL and model router to bojo*, 2026-10-27) — a 643-line
rewrite of `autothink/backend/llm_adapter.py` that replaced several helpers and dropped this one,
while `server.py:53` kept importing it and `server.py:208` kept calling it.
**Fixed by restoring the pre-`7ace8f0b` body verbatim** (pure and deterministic: base prompt plus an
optional list of local data sources). Because this was the import that killed the module, it also
means the AutothinK premium surface can start again — this is a functional restore, not just a green
test.

**2. `UnifiedLLMAdapter.local_available`, `.list_local_models` and `._local_fallback` were dropped in
the same rewrite.**
`server.py:168-169` calls `adapter.list_local_models()` / `adapter.local_available()`, so
`GET /api/autothink/models` answered `200 {"local_available": false, ..., "error": "'UnifiedLLMAdapter'
object has no attribute 'list_local_models'"}` — a live endpoint serving an internal AttributeError as
data. `llm_adapter.py:435` calls `self._local_fallback(...)`, which would have raised the same way on
the first empty model response.
**Fixed** by restoring `_local_fallback` verbatim and adding the two probes as one-line delegations to
the module-level functions the same rewrite made canonical (`local_available()` /
`list_local_models()`), so there is still exactly one implementation of each probe.

**3. `LlamaCppModel` referenced a parameter it never took.**
`agent_kernel/local_model.py:89` read `num_ctx` inside `__init__` while the signature had no such
argument — the line (and its comment) was copied from `OllamaChatModel` in `3669f651`. Constructing
the model raised `NameError` before any request, which is why every `test_local_model` case that
builds one failed.
**Fixed** by accepting `num_ctx: Optional[int] = None` and recording it. It is deliberately **not**
sent on the wire: llama.cpp takes the context window as a launch flag (`-c`), and the
OpenAI-compatible body has no field the server honours for it, so putting one there would pretend to
change a server-side setting. The comment now says exactly that.

## Test-side changes (and why they are not weakening)

- **The three `*_refuses_without_a_session` tests** pin `ENVIRONMENT=production` for the duration of
  the call. In a local/unset environment `foundation.authn.environment()` reports `development` and
  `main.py` opts into `app.state.dev_auto_session`, so `require_session` answers with the demo
  identity on purpose (the documented DEV-ONLY LOCALHOST EXCEPTION). The 401 boundary is a **hosted**
  property; `test_autothink_auth_boundary.py` already pins `ENVIRONMENT=test` for exactly this reason.
  The assertion (401, no session) is unchanged.
- **`test_autothink_run_non_5xx_on_empty_store`** now stubs `adapter.generate`. The file's own
  docstring says it is the *offline* route smoke and "does NOT call Ollama (that path is exercised
  manually / by the live smoke pass)". Left alone, the test attempted a real local call, took 39.8 s
  on its own, and when run with the rest of the file tripped `test_network_guard`'s
  `NetworkGuardViolation`. Routing, context build, run registry and metering all still run for real
  against an empty tenant store; only the model completion is canned.

## Verification

```
python -m pytest test_autothink_auth_boundary.py test_autothink_routes.py \
                  test_autothink_transport.py test_local_model.py \
                  test_local_model_native.py test_local_model_ollama.py -q
→ 50 passed, 6 subtests passed (4.39 s)     [was 15 failed / 35 passed]

python -m pytest test_coding_agent.py test_coding_runner.py test_local_model.py -q
→ 39 passed (1.38 s)
```

**Live check** (dev stack restarted through `scripts/dev-start.ps1`, so the fixed module is what the
running process imported):

```
GET /api/autothink/models
before: 200 {"local_available": false, ..., "error": "'UnifiedLLMAdapter' object has no attribute 'list_local_models'"}
after:  200 {"local_available": true, "cloud_available": true, "cloud_provider": "openrouter",
             "cloud_live_armed": false, "default_local_model": "bojo", "models": ["qw...", ...]}
```

The endpoint now answers with provider availability and the installed local models instead of an
internal AttributeError dressed as data. `cloud_live_armed` is still `false`, i.e. the restore did not
arm anything.

## Not touched

No model config, no lane restart, no download, no spend, no credential read, no network call, no
change to `agent_kernel/coding_agent.py` or to the AutothinK router/pricing. The restored prompt
helper is deterministic and takes its context from what the caller already passes.
