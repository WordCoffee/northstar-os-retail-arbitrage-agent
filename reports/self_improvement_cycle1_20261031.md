# Autonomous self-improvement — cycle 1

- date: 2026-10-31
- commit: `b132931c`
- scope: Ty's Assistant coding loop + Bojo chat adapter, under local-only
  constraints (27B llama.cpp lane, no Docker/Bubblewrap, AST editing only).

## Analysis

| component | observation | opportunity |
|---|---|---|
| Ty's Assistant prompt (`agent_kernel/coding_agent._prompt`) | injected the last **6** tool observations at **1800 chars each** (~10.8k chars of history) on every turn | keep fewer, shorter observations; dedupe repeats; give error text the larger slice |
| Bojo chat (`chat_adapter.stream_turn`) | sent a flat **16,384** `num_predict` ceiling for every turn, including "hi" | cap short asks at 2K, long-form asks at 8K; keep the full ceiling available via env |
| AST engine (`agent_kernel/ast_edit.py`) | applied an edit by unparsing the **whole module**, which reformatted/erased comments outside the target | splice only the target's source span; preserve everything else byte-for-byte |

## Plan (incremental)

1. **Make the AST engine surgical first.** An optimization applied with a
   whole-file unparse would reformat the assistant source and make the diff
   unreviewable. Replace the whole-module `ast.unparse` with source-span splicing
   for every op; validate the result with `ast.parse`; keep BOM/CRLF.
2. **Ty: compact the prompt history.** Last 4 observations, 1200 chars each;
   failure/error/traceback observations keep 1800; drop duplicate
   `(tool, output[:400])` pairs. This keeps the evidence that matters while
   cutting prefill tokens.
3. **Bojo: adaptive output budget.** `_adaptive_num_predict(messages)`:
   2048 for short asks, 8192 for long-form or >1200-char prompts, bounded by
   `CHAT_NUM_PREDICT`; `CHAT_NUM_PREDICT_SHORT`/`_LONG` are env-overridable.

All three were applied with `agent_kernel.ast_edit.apply_to_file` (symbol-level
edits), not with a text-diff tool.

## Measured result

Ty prompt, synthetic 6-turn history (6 × 1800 chars):

| metric | before | after | change |
|---|---|---|---|
| prompt chars | 12,763 | 6,748 | **-47.1%** |
| approx tokens (4 chars/token) | 3,191 | 1,687 | **-1,504 tokens/turn** |
| observations included | 6 | 4 | -2 |
| error text allowance | 1,800 | 1,800 | unchanged |
| normal observation allowance | 1,800 | 1,200 | -33% |

At the lane's measured prompt-eval rate (~385 tok/s in the local author log),
1,504 fewer prompt tokens is roughly **3.9 s less prefill per turn**. This is an
estimate from prompt size, not a wall-clock A/B run; the report keeps the
distinction.

Bojo output ceiling:

| turn type | before | after | change |
|---|---|---|---|
| short ask | 16,384 | 2,048 | **-87.5% ceiling** |
| long-form / >1200 chars | 16,384 | 8,192 | **-50% ceiling** |

This bounds worst-case generation time and token spend; an answer that already
stops at EOS is not made slower or faster by a lower ceiling.

AST engine: 18 tests, including two new comment-preservation tests (a comment
inside an untouched function, and a module comment, survive an edit to a
different function).

## Verification

```
python -m pytest Northstar_backend/test_ast_edit.py \
  Northstar_backend/test_coding_agent.py \
  Northstar_backend/test_coding_runner.py \
  Northstar_backend/test_coding_guardrails.py \
  Northstar_backend/test_chat_core.py \
  Northstar_backend/test_chatter.py \
  Northstar_backend/test_chat_router_intent.py \
  Northstar_backend/test_agent_kernel.py \
  Northstar_backend/test_tys_kernel_integration.py \
  Northstar_backend/test_tys_routing.py \
  Northstar_backend/test_gateway.py \
  Northstar_backend/test_lane_policy.py \
  Northstar_backend/test_self_heal.py -q
```

**207 passed.**

| suite | result |
|---|---|
| `test_ast_edit.py` | 18 |
| `test_coding_agent.py` | 21 |
| `test_coding_runner.py` | 4 |
| `test_coding_guardrails.py` | 14 |
| `test_chat_core.py` | 16 |
| `test_chatter.py` | 10 |
| `test_chat_router_intent.py` | 6 |
| `test_agent_kernel.py` | 48 |
| `test_tys_kernel_integration.py` | 2 |
| `test_tys_routing.py` | 30 |
| `test_gateway.py` | 18 |
| `test_lane_policy.py` | 10 |
| `test_self_heal.py` | 10 |

## Honest caveats

- The Ty improvement is measured on a **synthetic** 6-turn history, not a live
  build; the prompt-size reduction is exact, the prefill-time estimate is not a
  benchmark.
- The Bojo change caps the worst case; Ollama already stops at EOS, so short
  answers that end early see no change.
- `chat_adapter.py` already carried local auto-recover/offline-categorization
  edits before this cycle; the commit includes them because they are part of the
  same working file. The adaptive-budget change is the new part.
- No Docker/Bubblewrap was used; the self-heal apply path remains refused by
  design. No live model call was required for these deterministic changes.
- No Amazon request, no paid provider call, no credential read.

## Next cycle candidates

1. Measure actual TTFT/tok-s on the local lane with a 6-turn vs 4-turn history
   (not a synthetic prompt), and record the delta.
2. Add `keep_alive` to the Bojo stream request (Ollama) to avoid reloading the
   1.9B model between turns; verify it does not pin VRAM needed by ComfyUI.
3. Cache-friendly prompt prefix: move the workspace tree ahead of the
   per-turn history if it is not already in the cached prefix.
4. Tool-call output budget: separate `num_predict` for read/list/run vs
   write/write_many turns.
