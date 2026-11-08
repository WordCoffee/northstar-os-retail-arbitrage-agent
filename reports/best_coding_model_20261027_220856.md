# Best Local Coding Model for RTX 5080 Mobile (16 GB) — 2026-10-27

## System
- GPU: NVIDIA RTX 5080 Laptop, 16,303 MiB VRAM
- Current model: `Qwen3.8-27B-GSQ-RCO-IQ3_XXS-mtp.gguf` (10.4 GB, 3.0 bpw)
- Current serving: llama.cpp CUDA b11889 (`~/.config/northstar-llm/bin/llama-server.exe`), 64K ctx, q4_0 KV, MTP
- Measured current: 13.0 GB VRAM, ~69 tok/s decode, ~70 tok/s prompt eval, no crash at 64K

## Shortlist and fit

| Model / quant | Size | 16 GB fit | Max context (q4_0 KV) | Coding strength | Verdict |
|---|---:|---|---:|---|---|
| **Swift 1.5 Qwen3.8-27B IQ3_S-mtp** | 11.29 GB | Yes (15.1 GB used) | **80K tested** | LiveCodeBench 81.71 vs base 76.76; Terminal-Bench 72.13 vs 69.21; 24.5% fewer tokens | **Best coding + high context** |
| Qwen3.8-27B base IQ3_XXS-mtp (current) | 9.73 GB | Yes (13.0 GB) | 64K tested | Strong base; LiveCodeBench 76.76 (same protocol) | Best speed/headroom |
| Qwen3.8-27B base IQ3_S-mtp | 12.1 GB | Tight | ~64–80K | Task-lossless tier (3.5 bpw) | Good, but Swift is better tuned |
| **KAT-Coder-V2.5-Dev APEX-I-MiniPlus V2.1** | 14.75 GB | Yes at 65K (15.1 GB) | 65K | Coding specialist; 93.3% resolved at 32K, 90.0% at 65K on SWE-style tasks | Best pure coding agent; less context |
| Qwen3.8-27B IQ2_XS pure | 8.4 GB | Yes | 128K tested | 2.5 bpw, noticeably weaker reasoning | Max-context fallback |
| Qwen3.8-27B VAL-APEX MiniPlus V3 | 14.16 GB | Tight | ~64K | +13.2% PPL vs IQ3_S | Good, but no 80K headroom |
| Qwen3.8-Flash-Next GSQ-RCO (177B MoE) | 68–76 GB | No (needs offload) | n/a | Stronger, but slow via RAM/SSD | Not for pure 16 GB |
| DeepSeek-V4.1-Flash (748B MoE) | 233–300 GB+ | No (needs 46–64 GB RAM) | n/a | Strongest, but slow | Not for pure 16 GB |
| GLM-5.3-Flash (320B MoE) | 93–200 GB | No | n/a | Strong coding, but huge | Not for 16 GB |
| Devstral Small 2 | ~15 GB | Yes | ~32K | Agentic coding specialist, older | Alternative, not better |

## Live test: Swift 1.5 IQ3_S-mtp at 80K
Command:
```
llama-server.exe -m Swift-1.5-Qwen3.8-27B-GSQ-RCO-IQ3_S-mtp.gguf ^
  -ngl 99 -c 81920 -fa on -ctk q4_0 -ctv q4_0 -np 1 --jinja ^
  --spec-type draft-mtp --spec-draft-n-max 4 ^
  --host 127.0.0.1 --port 8080 --temp 0.2
```
Results:
- VRAM: 15,090 / 16,303 MiB
- Prompt eval: 67.7 tok/s
- Decode: 55.1 tok/s (draft acceptance 0.60)
- Coding prompt: valid Python CSV revenue function returned in 6.4 s (468 tokens), with type hints, docstring, and error handling.

## Key evidence
- Qwen3.8-27B official: SWE-bench Pro 61.7, Terminal-Bench 2.1 73.0, LiveCodeBench v6 90.3.
- Swift 1.5 card: LiveCodeBench 81.71 vs 76.76, Terminal-Bench 72.13 vs 69.21, 58.5% fewer thinking tokens.
- ISTA-DASLab GSQ-RCO: IQ3_XXS ≈ task-lossless, IQ2_XS smallest (2.5 bpw).
- KAT-Coder APEX MiniPlus: 14.75 GB, 3.40 bpw, 65K in 15.1 GB VRAM on 16 GB cards; 90% resolved at 65K.
- llamaperf community report: Swift 1.5 IQ3_S on RTX 5060 Ti 16 GB, 81,920 ctx, 40 tok/s.
- Quesma: Q4_K_M matches BF16 on Terminal-Bench; 2-bit works but lower; 1-bit collapses.

## Recommendation
1. **Daily driver (coding + 80K context):** Swift 1.5 Qwen3.8-27B **IQ3_S-mtp** at 80K, q4_0 KV. Best measured balance on this GPU.
2. **If pure coding agent and 65K is enough:** **KAT-Coder-V2.5-Dev APEX MiniPlus V2.1** (14.75 GB) — coding-specialist, but tight VRAM.
3. **If maximum speed/headroom:** keep base **IQ3_XXS-mtp** at 64K (~69 tok/s, 13 GB).
4. **If 128K context is mandatory:** base **IQ2_XS pure** (8.4 GB), accepting lower quality.

## Disk note
C: was full during testing. Removed the incomplete Swift IQ3_XXS-mtp download and the temporary base IQ2_XS file. 9.71 GB free. Swift IQ3_S-mtp (11.29 GB) remains installed.

## Sources checked (selected)
- https://huggingface.co/Qwen/Qwen3.8-27B
- https://huggingface.co/ukisai/Swift-1.5-Qwen3.8-27b
- https://huggingface.co/ukisai/Swift-1.5-Qwen3.8-27B-GSQ-RCO-GGUF
- https://huggingface.co/ISTA-DASLab/Qwen3.8-27B-GSQ-RCO-GGUF
- https://huggingface.co/IsValorum/KAT-Coder-V2.5-Dev-APEX-I-MiniPlus-V2.1-GGUF
- https://huggingface.co/IsValorum/Qwen3.8-27B-VAL-APEX-I-MiniPlus-V3-GGUF
- https://huggingface.co/Kwaipilot/KAT-Coder-V2.5-Dev
- https://huggingface.co/unsloth/Qwen3.8-27B-GGUF
- https://huggingface.co/unsloth/DeepSeek-V4.1-Flash-1017-GGUF
- https://huggingface.co/zai-org/GLM-5.3-Flash
- https://llamaperf.com/report/4644f477-4c9c-44c4-8763-81268629782f
- https://llamaperf.com/model/kat-coder-v2-5-dev
- https://llm-bench.io/models/swift-1-5-qwen3-8-27b-gsq-rco-iq3-s-mtp
- https://llm-bench.io/models/qwen3-8-27b-gsq-rco
- https://quesma.com/blog/qwen38-27b-quantizations-benchmarked
- https://deepwakelabs.com/blog/ista-gsq-rco-vs-unsloth-qwen3-8-27b/
- https://www.reddit.com/r/LocalLLM/comments/1x14c5u/success_with_qwen38_27b_gsqrcoiq3_s_on_16gb_vram/
- https://www.reddit.com/r/LocalLLM/comments/1vr4iqj/i_benchmarked_every_qwen_38_27b_quant_that_fits/
- https://arxiv.org/pdf/2607.05471 (KAT-Coder technical report)
- https://github.com/UkisAI/Swift-Qwen3.8-27B-evals
- https://www.tomshardware.com/tech-industry/artificial-intelligence/benchmarking-qwen-3-8-27b-on-rtx-5090-and-beyond
- https://modelfit.io/models/qwen3.8-27b
- https://www.oflight.co.jp/en/columns/qwen3-8-27b-requirements-vram-local-2026
- https://kingy.ai/blog/qwen3-8-27b-best-quantization-gguf
- https://www.promptquorum.com/local-llms/best-local-llms-for-coding
- https://www.morphllm.com/best-ollama-models
- https://bestllmfor.com/guides/best-local-llm-16gb-vram
- https://localmodel.run/model/glm-5.3-flash
- https://unsloth.ai/docs/models/deepseek-v4.1-flash
- https://github.com/IST-DASLab/GSQ
