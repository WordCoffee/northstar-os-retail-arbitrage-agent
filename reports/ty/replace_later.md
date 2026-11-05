# Replace later

Things installed or wired for the program that are **not** production-clean, with the
production-safe replacement to find later. Every entry needs: what, license, what it is used for,
and the replacement target.

| # | Date | Tool / model | License | Used for | Lane | Replacement to find |
|---|---|---|---|---|---|---|
| 1 | 2026-11-05 | `gemma3:4b` (Ollama) | Gemma Terms of Use (proprietary EULA, not OSI) | Local vision QC: does a render match the brief (rubric JSON) | local | An Apache-2.0 or MIT VL model that returns valid JSON on this runner. Candidates to test: `qwen2.5-vl` (Apache-2.0) via a different runner/build, `InternVL2.5-4B` (MIT), `MiniCPM-V 2.6` (Apache-2.0), `moondream2` (Apache-2.0) with a stricter JSON prompt. The local lane is not resold, so this is a hygiene item, not a blocker. |
| 2 | 2026-11-05 | `llava:7b` (Ollama) | LLaVA model licence (research use; weights derived from Llama 2) | One-shot fallback for vision QC when the primary model returns unparsed output | local | Same as row 1. |

## Notes

- Neither row is a *spend*: both are local weights already on disk, no API key, no network call.
- Both are registered in `shared/provider-suite.json` as `local` only. Neither can run on the
  cloud lane, and the resolver refuses them there.
- The real defect being worked around is not the model choice: it is that the previous choice
  (`qwen2.5vl:7b`, Apache-2.0) does not answer JSON on this Ollama build. Revisit that model
  first — if a runner update fixes it, it is the production-safe answer and rows 1 and 2 go away.
