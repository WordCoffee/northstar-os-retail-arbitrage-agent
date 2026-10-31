# Local model tiering, AST editing, sandboxed self-healing

- date: 2026-10-31
- commit: `30df451f` (this build), previous creative/prepress work at `4f0e431b`
- directive: local model optimization, hardware tiering, and the autonomous
  systems loop (runtime flags, dual-model routing, AST editing, sandboxed
  self-patching, HITL).

## Hardware and model reality check

The plan's topology (24 GB GPU node, 64–128 GB CPU orchestrator, separate Bojo
worker) does **not** match this machine, and the specified weights are not on
disk:

| target | this host |
|---|---|
| RTX 4090/3090 24 GB | RTX 5080 Laptop, 16 GB VRAM |
| 64–128 GB DDR5 | 15.4 GB system RAM |
| Qwen 2.5 Coder 32B | not installed |
| DeepSeek R1 32B / 671B | not installed |
| Llama 3.3 70B | not installed |
| installed local lane | Qwen3.8-27B IQ4_XS (13.9 GB), alias `northstaros-27b-coder`, 17408 ctx, q8_0 KV |
| installed Ollama | `bojo` (2.7 GB), `qwen2.5vl:7b`, `qwen3-embedding:0.6b` |

The lane policy below encodes the requested tiering but reports the actual
installed lane and an explicit fallback. It does not pretend a 32B reasoner or a
70B orchestrator exists.

## 1. Quantized KV cache and physical-thread runtime flags

`tools/runtime_flags.py` audits the launchers and the current process:

- `-fa on` (FlashAttention) — present in both PowerShell launchers and the lane
  router.
- `-ctk/-ctv q8_0` — present; `q4_0` is accepted for >32K context.
- `OLLAMA_KV_CACHE_TYPE` / `OLLAMA_FLASH_ATTENTION=1` — now exported by
  `scripts/start-northstar-llm.ps1` and `scripts/start-northstar-moe.ps1`.
- `num_thread = physical cores` — the audit reports **24 physical / 24 logical**
  on this host and sets `num_thread` to the physical count.

Measured audit (2026-10-31):

```
scripts\start-northstar-llm.ps1     flash=true  kv=q8_0  ollama_exports=true  ok
scripts\start-northstar-moe.ps1     flash=true  kv=q8_0  ollama_exports=true  ok
tools\northstar_lane_router.py      flash=true  kv=q8_0  ok
threads: physical=24 logical=24 num_thread=24 measured=true
process env now: OLLAMA_KV_CACHE_TYPE=q4_0 (running Ollama)
expected:        OLLAMA_KV_CACHE_TYPE=q8_0
```

The running Ollama server still has `q4_0`; the launchers export `q8_0`, and
`tools/runtime_flags.py --apply --kv q8_0` wrote the process-scoped record at
`config/runtime_flags.json`. The already-running server keeps its old value until
Ollama is restarted. That is an operator action, not a silent kill.

## 2. Dual-model lane policy

`Northstar_backend/lane_policy.py` (new; the existing provider/tier
`model_router.py` is untouched):

- `classify(text, has_code, path)` → `code_edit`, `reasoning`, `orchestration`.
- `route(intent, ...)` prefers `northstaros-27b-coder` /
  `northstaros-reasoner` / `northstaros-orchestrator`, checks the model file on
  disk, and returns `{lane, requested_lane, fallback, reason, installed}`.
- If the preferred lane is absent, it falls back to the installed coder and says
  so; if nothing is installed it raises `NoModelAvailable`.
- `GET /api/v1/model-router` reports the policy and installed/missing lanes;
  `POST /api/v1/model-router/route` routes one request.

On this host the reasoning and orchestrator lanes are policy targets only; every
route records `fallback: true` and `reason: <lane>_not_installed`. No second
model is claimed.

## 3. AST structural editing (replaces text diffs for Python)

`Northstar_backend/agent_kernel/ast_edit.py` (new) resolves targets by symbol:

| op | behaviour |
|---|---|
| `replace_function_body` | replaces the body; keeps signature, decorators and docstring |
| `replace_function` | replaces the whole def/class |
| `add_method` | appends a method to a class |
| `add_before` / `add_after` | inserts a block at the target's level |
| `delete` | removes a function/class node |
| `add_import` | adds a top-level import if absent |
| `replace_imports` | replaces the top-level import block, keeps the docstring and code |
| `replace_global` | replaces a module-level assignment |

Every edit is parsed, applied in memory, re-parsed, and only then written. A batch
validates every file before the first write; one bad edit leaves the tree
byte-identical. UTF-8 BOM and CRLF are preserved. The engine is exposed as
`ast_edit` / `ast_edit_batch` in `Workspace`, in the coding prompt, and in the
local model's tool-call schema. 16 tests.

## 4. Sandbox, credential isolation, self-healing, HITL

`Northstar_backend/agent_kernel/sandbox.py`:

- `scrub_env` drops credential-shaped names (`KEY`, `TOKEN`, `SECRET`,
  `PASSWORD`, `AUTH`, `SESSION`, ...) unless explicitly allowed; only a small
  allowlist (`PATH`, `SYSTEMROOT`, `HOME`, ...) plus explicit consumer tokens
  reaches a child.
- `docker` / `bubblewrap` are used when installed; `process` is the fallback.
- `require_isolated()` **refuses** the process fallback for a self-patch.
- `audit()` reports runtimes, the chosen runtime, `production_safe`, and the
  count of secret-shaped env names (names only).

`Northstar_backend/agent_kernel/self_heal.py`:

```
traceback -> ast.get_source_segment(innermost function/class)
          -> local lane returns JSON AST edits
          -> edits validated in memory
          -> patched file tested in the sandbox
          -> keep on pass, restore original bytes on fail
```

`apply=True` requires a verify command and an isolation runtime; a failed
verification restores the file byte-for-byte. `local_reasoner` routes through
`lane_policy` and fails closed when the lane is unreachable. 10 tests.

`Northstar_backend/agent_kernel/hitl.py` is the durable local approval queue
(`request` / `approve` / `deny` / `pending` / `require_approved`) with a
`publish` hook for a Matrix/AgentTeams bridge. **AgentTeams, Matrix, AgentScope
and OpenJudge are not installed**, so this is the local gate, not a Matrix room.
4 tests.

## Verification

```
python -m pytest Northstar_backend/test_ast_edit.py \
  Northstar_backend/test_lane_policy.py \
  Northstar_backend/test_model_router.py \
  Northstar_backend/test_runtime_flags.py \
  Northstar_backend/test_sandbox.py \
  Northstar_backend/test_self_heal.py \
  Northstar_backend/test_hitl.py \
  Northstar_backend/test_coding_agent.py \
  Northstar_backend/test_coding_runner.py \
  Northstar_backend/test_coding_guardrails.py \
  Northstar_backend/test_gateway.py -q
```

**135 passed.**

| suite | result |
|---|---|
| `test_ast_edit.py` | 16 |
| `test_lane_policy.py` | 10 |
| `test_model_router.py` (existing provider/tier router) | 29 |
| `test_runtime_flags.py` | 5 |
| `test_sandbox.py` | 6 |
| `test_self_heal.py` | 10 |
| `test_hitl.py` | 4 |
| `test_coding_agent.py` | 19 |
| `test_coding_runner.py` | 4 |
| `test_coding_guardrails.py` | 14 |
| `test_gateway.py` | 18 |

All edits are UTF-8 without BOM.

## Spec-vs-disk reconciliation

`shared/model-suite.json` carries the **measured** local profile (17408 context,
q8_0 KV, Qwen3.8-27B IQ4_XS, 13.9 GB) and says "nothing here is a target". The
old `test_model_router.py` still asserted the superseded 65536/q4_0 target. The
assertion was updated to the measured profile with a comment; the provider/tier
router itself was not changed.

## Not done / blockers

- **Weights**: Qwen 2.5 Coder 32B, DeepSeek R1 32B/671B, Llama 3.3 70B are not
  installed and do not fit this 16 GB / 15.4 GB host. The lane policy is ready;
  the models are not.
- **Isolation**: Docker, Bubblewrap and OpenSandbox are not installed, so
  `self_heal.apply=True` fails closed. The process fallback scrubs env but is
  not a security boundary.
- **AgentScope / AgentTeams / Matrix / OpenJudge / skills.sh**: not installed.
  HITL is the local queue with a publish hook; there is no room transport yet.
- **Galactic UI (Phase 2)**: not built in this pass.
- **Ollama restart**: the running server still has `q4_0`; the launchers export
  `q8_0`. Restart is the operator's call.
- No Amazon request, no paid provider call, no credential read.

## Next

1. Install a container runtime (Docker Desktop or Bubblewrap) so
   `require_isolated()` can pass; then enable `self_heal.apply=True` in a
   supervised run.
2. If the hardware is upgraded, install the reasoner/orchestrator weights and
   add their aliases to the lane router; the policy already names them.
3. Add the Matrix bridge (`publish` hook) and an operator room command for
   approve/deny.
4. Wire `lane_policy.route` into the chat adapter once more than one lane is
   actually resident.

## Commits

```
30df451f  AST editing, lane policy, runtime flags, sandbox, self-heal, HITL
b34bbe61  local tiering/AST/sandbox report + state fragment
cb356643  record q8_0 KV + FlashAttention process flags
```

