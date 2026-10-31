# Cycle 5 — Bojo keep-alive

- date: 2026-10-31
- commit: `a9adbd58`
- scope: local chat latency; no model or prompt change.

## Change

Ollama unloads an idle model after its default keep-alive. Bojo is a 1.9B CPU
model; a reload between quick turns is pure latency. The chat stream now sends an
explicit keep-alive:

- `UnifiedLLMAdapter.stream_chat(..., keep_alive=None)` writes `keep_alive` into
  the Ollama request body only when provided.
- `chat_adapter.CHAT_KEEP_ALIVE` defaults to `10m`; `CHAT_KEEP_ALIVE=0` (or any
  other Ollama duration) overrides it.
- `stream_turn` passes it on every chat turn.

The change was applied with `agent_kernel.ast_edit.replace_function` for
`stream_chat` and `stream_turn`, plus `add_before` for the constant.

## Verification

```
python -m pytest Northstar_backend/test_chat_core.py -q
# 17 passed

npm run test:ui / test:contrast / verify:galactic / build
# unchanged from Cycle 4: 73 / 11 / 34 / 0 errors
```

`test_stream_chat_passes_keep_alive_to_ollama` asserts the wire payload carries
`keep_alive: "10m"`.

## Honest notes

- `autothink/tests/test_llm_adapter.py` has 4 failures in unrelated local/cloud
  probe tests (`list_local_models`, `local_available`, `openrouter`); the changed
  `stream_chat` path is covered by `test_chat_core` and passes. Those probe tests
  were not touched by this cycle.
- A 10m keep-alive pins Bojo in memory; if ComfyUI/FLUX needs the RAM/VRAM, set
  `CHAT_KEEP_ALIVE=0` or a shorter duration.
- No model call was made to verify the reload delta; the wire contract is tested,
  not a wall-clock benchmark.
- No Amazon request, no paid provider call, no credential read.

## Next selected cycle

**Cycle 6 — local evaluation ledger for the loop.** Record each cycle's real
commands, pass/fail counts and commit into a queryable JSONL/rollup so the loop's
next task is selected from evidence, not memory. External OpenJudge/AgentScope
remain uninstalled; this is the local substitute.
