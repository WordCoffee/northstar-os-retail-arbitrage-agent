# Parser-enabled profile for `qwen2.5-coder:7b` — BLOCKED (2026-11-01)

The authorized single runtime profile was built and tested. Ollama **stores** the
`PARSER` directive but **does not produce structured tool calls** for this artifact,
and the model strips the `<tool_call>` tags even when asked to echo them verbatim.
No screen, no real tasks, no soak.

---

## 1. MODEL DECISION

| | |
|---|---|
| Artifact | `qwen2.5-coder:7b` (`dae161e2…`, 4.7 GB) — same weights, no re-download |
| Profile | `qwen2.5-coder:7b-parser-f16` (`577c810f2253`, 4.7 GB, shares the base blobs) |
| Modelfile | `state/profiles/qwen2.5-coder-7b-parser-f16.Modelfile` |
| Runtime | campaign-scoped `ollama serve`, GPU backend, `OLLAMA_KV_CACHE_TYPE=f16`, `OLLAMA_CONTEXT_LENGTH=8192` |

```dockerfile
FROM qwen2.5-coder:7b
PARSER qwen2.5
PARAMETER temperature 0
PARAMETER num_ctx 8192
```

The stock artifact carries **no** `RENDERER`/`PARSER` line; the alias adds `PARSER`
and keeps the template and weights otherwise untouched. The operator's environment
was not modified and was restored at the end (`cpu` / `q4_0`, GPU 0 MiB).

`qwen3:8b` was **not** retried; its screen failure stands.

---

## 2. PARSER DETECTION — the directive is stored, not effective

Raw proof, same campaign serve, same request shape, `temperature 0`:

| Model | Modelfile carries | Structured `tool_calls` |
|---|---|---|
| `qwen2.5-coder:7b-parser-f16` | `PARSER qwen2.5` | **0 of 3** |
| `qwen2.5-coder:7b` (stock) | none | 0 of 3 (identical output) |
| `bojo:gpu-orig` (control) | `RENDERER qwen3.5`, `PARSER qwen3.5` | **3 of 3** |

The alias manifest is correct:

```text
$ ollama show qwen2.5-coder:7b-parser-f16 --modelfile
PARSER qwen2.5
PARAMETER num_ctx 8192
PARAMETER temperature 0
```

…but the response is byte-identical to the stock model — the call arrives as
**content**, never as `message.tool_calls`:

```json
{"name": "read_file", "arguments": {"path": "Northstar_backend/calc.py"}}
```

### Serialization test (required before trying any other parser variant)

Asked to repeat a `<tool_call>…</tool_call>` block **verbatim**, with no `tools`
array in the request (so the template's tool instructions are absent), the model
returned the block *without the tags*:

```text
content: {"name": "read_file", "arguments": {"path": "Northstar_backend/calc.py"}}
tool_calls: null
```

So the parser has nothing to parse: this artifact never emits the tag format its own
template asks for. That also means a different parser name cannot help — the failure
is upstream of parsing.

**Detection result: PARSER is not applied/effective for this artifact.** Per the
directive the campaign stops here; no screen was built on a non-working interface.

---

## 3. SCREEN / REGRESSION

* Screen: **not run** (directive: do not continue building screens when PARSER is
  not applied).
* Regression batch, same campaign: **169 passed in 5.34 s** across 12 suites.
* The three app probes still fail on HEAD, unchanged:

```text
t5_hitl_corrupt.py        FAIL (1)  unreadable records are reported
t6_diff_select_headers.py FAIL (2)  one/both hunks keep the file header
t7_artifact_jpeg.py       FAIL (2)  valid JPEG is an image; broken magic refused
```

---

## 4. RESOURCES

No resource gate was exercised, because the interface failed before any load under
the new profile. Recorded for completeness: campaign serve had **8.35 GB** host free
with 0 MiB VRAM used; the alias shares the base weights, so its footprint is the
same 4.7 GB artifact already measured (5.879 GB VRAM class when resident).

---

## 5. REAL TASKS

Not dispatched. No Ty commits. No task state was reset; the six-dispatch history and
all failed states are preserved.

---

## 6. VERDICT

**BLOCKED — the authorized parser profile does not yield structured tool calls.**

Tested and ruled out this round: `qwen2.5-coder:7b` with `PARSER qwen2.5` + f16 KV on
the GPU. Still standing: `qwen3:8b` (clean tools, cannot author a body),
`qwen2.5-coder:3b` (JSON path, 0/6), `qwen2.5vl:7b` (degenerate), `bojo` (1.9B, no
edit).

### Exact next operator action

A **new model decision** is required; nothing in the current set can be made to work
by configuration. The evidence points at a model whose Ollama manifest ships its own
`RENDERER`/`PARSER` (the qwen3.5 class does, and parsed 3/3 here) rather than a coder
artifact that needs a parser bolted on. Until then the qualification queue stays
frozen and ready.

Housekeeping: the alias remains installed (`ollama rm qwen2.5-coder:7b-parser-f16`
removes only the 1 MB alias layer; the base model is untouched).
