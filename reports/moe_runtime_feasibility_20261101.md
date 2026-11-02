# MoE runtime feasibility — Strata / Maya / llama.cpp on this laptop (2026-11-01)

Feasibility only. Nothing was installed, downloaded or switched. The production
runtime is untouched: Ollama 0.40.4 on `cpu`/`q4_0`, Ty on `qwen3.5:4b`.

---

## 1. RUNTIME DECISIONS

| Candidate | What it is here | Status |
|---|---|---|
| **llama.cpp (`llama-server` 0.7.0-dev, build 11889)** — already installed at `~\.config\northstar-llm\bin\llama-server.exe` | the llama.cpp-family engine with **expert-offload controls** (`--cpu-moe`, `--n-cpu-moe N`, `--override-tensor`) | **Measured** (below) |
| **Strata** | not present on disk; no local copy, source, binary or manifest | **UNKNOWN — NOT INSTALLED.** No evidence gathered and none is claimable without network research, which this prompt forbids |
| **Maya** | same | **UNKNOWN — NOT INSTALLED** |
| **Baseline: Ollama 0.40.4** | the Ty production lane | **Measured** across the whole programme |

A Strata-like runtime is *conceptually* the same class as this llama.cpp build: the
build already exposes the exact knobs (keep experts on CPU, N layers of experts on
CPU, per-tensor overrides). So the interesting question is not "which brand" but
"does expert offload fit this machine", and that is testable locally.

---

## 2. EVIDENCE

### 2.1 What is actually installed

```text
llama-server.exe   0.7.0-dev (build 11889, commit d854d98ba), Clang 20.1.8, win x86_64
  -cmoe, --cpu-moe                 keep ALL MoE weights in the CPU
  -ncmoe, --n-cpu-moe N            keep the MoE weights of the first N layers in the CPU
  -ot, --override-tensor           per-tensor buffer override
Ollama 0.40.4                      production runtime (llama.cpp-derived, no expert flags exposed)
GPU: RTX 5080 Laptop, 16,303 MiB   Host: 15.42 GB RAM total
```

### 2.2 The only local large artifact is DENSE, not MoE

`C:\Users\T2Hol\models\northstar-moe\Qwen3.8-27B-IQ4_XS_4BPW.gguf` (12.95 GB), read
with a dependency-free GGUF reader (`tmp-probe/gguf_meta.py`):

```text
architecture qwen35   blocks 65   embedding 5120   ffn 17408
context_length 262144   tensors 866   gguf v3
expert_count: ABSENT  ->  dense 27B, not a Mixture-of-Experts artifact
```

So the folder name is aspirational: **no MoE weights exist locally**, and the
expert-cache question cannot be measured on this machine without a download
(authorized = no).

### 2.3 Measured: the installed runtime on the local 27B (dense)

`llama-server -m <27B> -ngl 99 -c 4096 -fa on`, one generation of 64 tokens, then
terminated (`tmp-probe/llamacpp_27b_probe.py`, log `state/evidence/llamacpp_27b_server.log`):

| Measure | Value |
|---|---|
| Time to ready | **21.7 s** |
| Host RAM free before load | 7.31 GB |
| Host RAM free after load | **0.13 GB** |
| Host RAM free during generation | **0.11 GB** |
| Prompt processing | **17.5 tok/s** |
| Token generation | **38.34 tok/s** |
| Cleanup | process terminated, host back to **8.31 GB**, GPU **0 MiB** |
| Model/build warnings | `blk.64.*` tensors unused — the GGUF has one block more than this build consumes |

**The decisive number is not the 38 tok/s — it is 0.11 GB of free host RAM.** The
3.0 GB resident floor is missed by ~2.9 GB. This is the same wall the earlier Ollama
27B attempts hit, and it is host memory, not GPU capacity: the GPU had room, the
laptop did not.

### 2.4 Measurement limits

* One generation, `-c 4096`, no tool turns. A real Ty task adds prompt processing
  and KV growth, which only tightens the same constraint.
* No MoE artifact locally → **expert-cache behaviour NOT RUN**; all MoE performance
  numbers are therefore **UNKNOWN**, not estimated.
* Strata/Maya: **UNKNOWN** (not installed, no permitted research path in this prompt).
* This is a laptop GPU; no RTX 5090/A100 benchmark is transferable.

---

## 3. DECISION QUESTIONS

1. **Does a 30B–35B A3B/Q4 MoE become useful here?** **No, on this machine.** A 30B
   A3B at Q4 is ≈18 GB; with 15.42 GB of RAM (≈8 free) and a 16 GB GPU, the expert
   pool alone exceeds host memory. The measured dense 27B already consumed the whole
   host during load.
2. **Does it survive realistic Ty context/tool turns?** **No evidence to support it.**
   At 4k context the host was already at 0.11 GB; Ty needs 8k plus tool history.
3. **Memory floor / cleanup / STOP?** The *runtime* handled cleanup and termination
   correctly (GPU 0 MiB, host restored). The *profile* cannot hold the floor.
4. **Mature enough to carry qualification?** **No.** A `0.7.0-dev` build that warns
   about unused tensors for this exact GGUF is not a reproducible base.
5. **Safer/smarter than a 20B GPT-OSS or Qwen3.5-9B?** On measured evidence, no: the
   qualified lane (`qwen3.5:4b`, 3.1 GB VRAM, 42 tok/s, one accepted fix) runs inside
   every floor. A 20B-class model does not fit this host at all — under Ollama or
   llama.cpp.
6. **Native tool protocol without another adapter?** **Not with llama-server.** Ty's
   runner speaks Ollama's `/api/chat`; llama-server would need a new adapter (its tool
   calling exists, but the client does not speak it).
7. **Exact path if someone still wants it:** a MoE GGUF ≤ ~8 GB total with expert
   offload, `--n-cpu-moe` tuned so host stays ≥3 GB, an Ollama-compatible adapter, and
   a fresh qualification. None of that is authorized or locally possible today.

---

## 4. VERDICT

**NO-GO** for a 20B–35B MoE engineering runtime on this laptop as configured.
The blocker is **host RAM**, measured: 0.11–0.13 GB free with a 12.95 GB model,
against a 3.0 GB floor. **CONDITIONAL** only in the narrow sense that the already
installed llama.cpp build does expose the expert-offload controls a Strata-like
runtime would need — the runtime is not the obstacle, the machine is.

---

## 5. CONDITIONS to revisit

* Host RAM ≥ 32 GB (or a MoE artifact small enough that host stays ≥3 GB resident);
* a MoE GGUF present locally, with its actual expert count verified from metadata;
* a build at a release tag, not `-dev`, that does not warn about unused tensors;
* an Ollama-compatible adapter before any Ty task touches it.

---

## 6. RECOMMENDED NEXT STEP (one)

**Do not** test 20B GPT-OSS under Ollama first: it would face the same host-RAM wall
and cannot pass the floor (the measured 27B already takes the host to 0.13 GB), so it
would spend a download and a campaign to reproduce this result.

The single useful next step is a **hardware/RAM decision** by the operator: if the
goal is 20B+ local engineering, the machine needs more system RAM (≥32 GB) or a MoE
artifact under ~8 GB. Until then, keep `qwen3.5:4b` as the qualified engineering lane
and the remaining two fixes as the open work.

---

## 7. STATE

Nothing installed, downloaded or switched. The probe server was campaign-owned and
terminated; GPU 0 MiB, host 8.31 GB free. Ollama daemon untouched
(`cpu`/`q4_0`, 0 resident). No lock, STOP or worker. Regression suite unaffected.
