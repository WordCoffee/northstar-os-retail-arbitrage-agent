# Lessons

Append-only. Each entry is a rule with the evidence that earned it.

## L1 — A diagnosis run with inherited environment pins is not independent evidence

**Rule.** Before concluding that a capability is absent, dump the *effective environment
of the process that is actually failing* — not the registry, not the User scope, not what
a previous session found. An inherited pin makes every later measurement reproduce the
same conclusion, which looks like independent confirmation and is not.

**Evidence, 2026-11-07.** D1 concluded "Ollama cannot see this GPU" after a fresh server
with `CUDA_VISIBLE_DEVICES=0` behaved identically. That retest was worthless: the pins
`OLLAMA_LLM_LIBRARY=cpu` and `OLLAMA_NUM_GPU=0` were inherited from the parent process, so
*every* server started from that shell was told not to look. The parent was the agent
process, which had captured the pins at startup — long before they were cleared.

The trap repeated twice during the coexistence test:

1. The User-scope pins were cleared, but the new shell inherited them from its parent and
   `Start-Process` handed them to the server. Both models came back on CPU.
2. `OLLAMA_MAX_LOADED_MODELS` had the same shape: the User value was raised to 2, the
   inherited shell value was still 1, and two models evicted each other while the config
   said they could coexist.

Only clearing the variables **in the launching shell** produced the real answer
(`library=CUDA compute=12.0`, four roles at 100 % GPU).

**How to apply it.** Print the effective environment of the failing process next to every
capability verdict, and prefer a launcher that constructs the child environment explicitly
instead of inheriting one.

## L2 — A test that passes in isolation and fails in the suite is telling you about isolation

**Evidence, 2026-11-07.** Twelve to seventeen full-suite failures, each passing alone.
Root cause: `test_egress_guard.py`'s autouse teardown called `eg.uninstall()` *after*
pytest restored the monkeypatched transport, so the guard re-applied the fake `urlopen`
that `install()` had captured. Every later network test then read an empty `BytesIO`.
The baseline was red for reasons that had nothing to do with the code under test.

**How to apply it.** Treat "passes alone, fails together" as a defect with a single cause
until proven otherwise. Do not record the failures as known exceptions before finding it.

## L3 — Measure the steady state, not the instant after the event

**Evidence, 2026-11-07.** `gpu_budget.load()` sampled RAM in the same moment the model
loaded, caught the host-RAM spike, and reported a successful GPU load as a budget
refusal. The same shape appeared with embeddings: warming an embedding-only model through
`/api/generate` made it look like it never loaded at all.

**How to apply it.** A measurement that decides a verdict must say *when* it was taken
relative to the event it is judging, and it must wait for the state it is claiming to
measure. Two instruments lying in the same direction is still lying.
