# Phase A — capability probe (before and after)

Every line below is a command that was actually run on 2026-11-05, with its real
output. A claim without output is not in this table.

Legend: **PRESENT** = the probe produced working evidence. **PARTIAL** = the
machinery exists but a path is missing or it needed a repair. **MISSING** = it
did not work at all. The "after" column is Phase B's result.

| # | Ability | Before | After | Evidence |
|---|---|---|---|---|
| A1 | Whole-system awareness | PRESENT | PRESENT | `reports/ty/_a1_snapshot.txt`: RAM 15,791 MB total / 4,648 free; disk C: 926.5 GB total, **10.6 GB free**; GPU `NVIDIA GeForce RTX 5080 Laptop, 16303 MiB, 0 used, 16003 free`; 13 Ollama models; ComfyUI down at first; listener table (11434 Ollama, 4097 opencode, 9080, …) |
| A2 | Persistent planning | MISSING | PRESENT | Queue, plan, log, grants, needs-you, replace-later written to `reports/ty/`. Resume proven by a **fresh process** reading only disk: `python -c "...json.load('reports/ty/autonomy_queue.json')..."` -> `phase A | next unfinished: init-2 - Tag autonomy-baseline + measured full test run -> tests/BASELINE.json` |
| A3 | Unattended loop | PARTIAL | PARTIAL (by design) | `tools/improvement_backlog.py --list` -> `24 items: 1 ready, 0 promoted, 7 needs-author, 7 blocked, 9 done`. `scripts/continuous_loop.py --status` -> `RUNNING: no … stop=queue_blocked / COUNTS: completed=34 failed=0 interrupted=0 remaining=0 blocked=2`. It processes every authorized task with no human; it stops at an **empty queue** and at two policy blockers (auth-adjacent scope, self-modification of its own budget). A failing test produces a PROPOSED card, not an authorized one: 15 proposals, 0 authorized. |
| A4 | Web + repo research | MISSING | PRESENT | Before: `provider_suite.py --check trafilatura --provider local` -> `NOT available on local - unknown_tool` (same for `mcp`). After: `tools/web_research.py --github "comfyui product photography" --limit 3` -> 3 repos with licences; `--hf ip-adapter` -> 5 models; `--license block/goose` -> `Apache-2.0` read from the actual LICENSE file; `--fetch https://www.amazon.com/dp/…` -> `REFUSED: amazon_refused`, exit 1. Every call is journaled to `logs/web_research.jsonl`. |
| A5 | Package vetting | PRESENT | PRESENT | `vet_package.py --name requests --ecosystem PyPI --version 2.31.0` -> `clear` + 6 advisories listed as risk, exit 0. `--endpoint http://127.0.0.1:9/v1/query` -> `REFUSED (check incomplete, never a pass): osv_unreachable`, **exit 2**. A transport failure refuses; it does not clear. |
| A6 | MCP client | MISSING | PRESENT | Ty served MCP (`tools/northstar_mcp_server.py`) and consumed none. After: `tools/mcp_client.py --arg tests/fixtures/mcp_echo_server.py --list --call add --args-file …` -> 2 tools (`add`, `echo`), `sum: 5`, exit 0. Journal: `logs/mcp_client.jsonl`. |
| A7 | Context management at 70% | PARTIAL | PRESENT | `agent_kernel/context.py` had a `Compactor` + `write_handoff` that **nothing called**, and its estimator read only `content` keys, so a 6,000-character observation history measured as **0 tokens** and the threshold could never fire. Now `CodingAgent._maybe_compact` runs every step, fires at 70% of `context_limit_tokens`, emits a marker + task anchor, writes a handoff to disk, and reports `compactions` in the result. `pytest test_agent_context_window.py test_agent_kernel.py` -> **54 passed**. |
| A8 | Local image generation | PRESENT | PRESENT | `tools/probe_image_lanes.py --probe a8 --size 1024` -> 1,357,816-byte PNG, 1024x1024, **36.3 s**, **peak VRAM 11,676 MB** (65 samples), `ram_gate ok`, brain evicted/restored (`eval_count 8`). First attempt refused honestly: `system_ram_insufficient: free 2368 MB, need 4096 MB`. |
| A9 | Vision QA | **MISSING (broken model)** | PRESENT | `qwen2.5vl:7b` returned `"The image描写"` (4 tokens) for the rubric prompt, then ` ```\n```\n``` `, then 200 tokens of `\begin{document}\textsection{…}` garbage — `unparsed` every time. Measured the alternatives on the same frame: **gemma3:4b 16.9 s valid JSON**, llava:7b 17.5 s valid JSON, moondream rambles past its JSON. After the grant: verdict `ok`, `matches_brief: true`, issue *"Label text is unreadable"* (correct), 17.3 s, model `gemma3:4b`. |
| A10 | Reference-based generation | PARTIAL | PARTIAL | Both paths render: stored (previous generation) **48.7 s**, uploaded (`renders/mogra_lions_mane/product_front.png`) **75.8 s**, both `mode: reference`, 1024x1024, reference-uploaded as `ns-ref-777.png`. But there was **no reference library** — no way to find a previous generation — and the render carries unreadable invented label text unless the text-safe/vector layer runs. Built `Northstar_backend/reference_library.py` (content-addressed store + SQLite index + embedding/keyword/perceptual retrieval), 10 tests, and live-seeded 3 references (2 product photos, 1 generated) with embeddings. Still PARTIAL because the stored path is not yet wired into the API surface. |
| A11 | UI verification | PRESENT | PRESENT | `npx playwright test tests/e2e/autonomy_probe.spec.ts --project=chromium-desktop --project=chromium-mobile` -> **2 passed**, screenshots `reports/ty/shots/probe_chromium-desktop.png` (415 KB) and `probe_chromium-mobile.png` (49 KB). Ran twice: first against a Vite-only server (backend down, `/api` proxied 502), then against the full dev stack (`/health` ok, UI 200). |
| A12 | Scorecard evals | PARTIAL | PRESENT | Existing: `image_review_scorers.py` (PickScore adherence, HPSv2 preference) calibrated on 7 real renders. Its own calibration data shows the limit: `rejected_white_bg_b` scored **23.625/0.2637**, *higher* than the accepted `listing_white_bg` **23.25/0.2559** — the scorers do not detect a rubric rejection. Built `Northstar_backend/picture_scorecard.py`: 8 dimensions, programmatic compliance/OCR/phash where possible, model axes only when enabled, `unavailable` never counted as a pass, and a bar (`min_dimension 85`, `compliance 100%`). First measured run: `state/evidence/picture_bench_*.json`. |
| A13 | Rollback | PRESENT | PRESENT | Tag `autonomy-baseline` (e61ba173); appended a line to a tracked file (sha256 changed `E01EA31D…` -> `96ADDE8E…`); `git checkout autonomy-baseline -- <file>` exit 0; `git diff --quiet autonomy-baseline -- <file>` **exit 0**. Note: the working-tree bytes come back CRLF (autocrlf), so the raw hash differs — content identity is proven by `git diff`, not by a raw byte hash. |
| A14 | Self-model | — | PRESENT | `reports/ty/self_assessment.md`. |

## What the probe changed about the plan

Three of the "known starting points" were wrong in useful ways:

1. **Research was not blocked by a missing library** — `trafilatura 2.3.1` and
   `mcp 2.1.1` were already installed. The blocker was purely the registry
   entry, so one GRANT closed both.
2. **Vision QA was not a gap, it was a broken instrument.** The model id was
   right on paper and wrong on this runner; every downstream "vision check
   passed" claim made through it was worthless. That is the single most
   important finding of Phase A.
3. **The image lane is RAM-blocked before it is model-blocked.** A render was
   refused at `free 2368 MB, need 4096 MB` while a resident brain held 2.6 GB;
   the same render succeeded once the brain was drained. Any measurement plan
   that assumes "the GPU is free" is wrong on this box.
