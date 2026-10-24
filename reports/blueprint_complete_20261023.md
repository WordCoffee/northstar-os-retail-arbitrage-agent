# Blueprint build — completion report

**Date:** 2026-10-23 · **Repo:** `feature/v4.1-mesh` @ `10a1062c`
**Supersedes:** `reports/blueprint_build_20261023.md` (batch 1)

---

## Phase status

| Phase | Status | Evidence |
|---|---|---|
| 0 — Audit | **DONE** | `docs/audit.md` |
| 1 — Study | **PARTIAL (honest)** | 4 of 11 Tier A cloned; 2 studied deep; 1 excluded on licence; Tier B **not observed** |
| 2 — Test harness | **DONE** | 22 tasks, all runnable, `tests/agents/run_suite.py` |
| 3 — Package Designer | **DONE** | front/back/side + sheet + dieline SVG/PDF + mockup |
| 4 — Listing + PPC | **DONE** | 5/5 and 4/4 tasks at full marks |
| 5 — Creative agents | **DONE** | A+, social, video, content — all built, 18 tests |
| 6 — Router + model choice | **ROUTER DONE**, benchmark **PARTIAL** | harness built; 7B baseline run; 27B crashed (D-15) |
| 7 — Hardening | **PARTIAL** | no-egress gate + GPU queue/ledger done; observability dashboards not built |

**Suite: 138/138 deterministic (100 %), 22 of 22 tasks runnable, 0 `not_built`.**
**Tests: 133 passed, exit 0.**

---

## What exists now

### Agents (8 in the roster, 7 built)

| Agent | File | Chat tool | Tests |
|---|---|---|---|
| Package Designer | `specialists/package_designer.py` + `panels.py` | `build_package` | in `test_specialists` |
| Listing Optimizer | `specialists/listing_optimizer.py` | `optimize_listing` | in `test_specialists` |
| PPC Analyst | `specialists/ppc_agent.py` | `ppc_plan` | in `test_specialists` |
| Amazon Image & A+ | `specialists/image_aplus.py` + `image_rules.py` | `plan_aplus` | `test_creative_agents`, `test_image_rules` |
| Social & Ad Graphics | `specialists/social_graphics.py` | `plan_social` | `test_creative_agents` |
| Video & UGC | `specialists/video_ugc.py` | `plan_video` | `test_creative_agents` |
| Content Writer | `specialists/content.py` | `write_content` | `test_creative_agents` |
| Research | existing `agents/golden_goose_finder` | — | pre-existing |

**Router:** `specialists/router.py` — deterministic classification, required-input gate, quoted-span
and negation handling, injected into every chat turn as `[router] <agent> — ask for: …`.
**Queue:** `specialists/job_queue.py` — one heavy slot, interactive over batch, VRAM guard, JSONL
run ledger with credits and USD.

### Chat tools: 32 total (7 added this build)

`build_package` · `optimize_listing` · `ppc_plan` · `plan_aplus` · `plan_social` · `plan_video` ·
`write_content` — all wired into `SERVICES` and the `create`/`listing`/`ads` focus subsets.

---

## Verified study facts that changed the build

| Fact | Source | Effect |
|---|---|---|
| Bullets ≤ **500** chars (not 250) | `Amazon-Skills …/SKILL.md:160` | corrected false failures |
| Backend ≤ **250 bytes** | `Amazon-Skills …/amazon-backend-keywords/SKILL.md:3` | confirmed |
| 8-dimension rubric 15/15/15/10/10/10/15/10 | `…/SKILL.md:256-265` | rubric reported in full, 5 dimensions marked `not_measured` |
| A+ module sizes 970×600 / 970×300 / 300×300×3 / 220×220×4 / 1464×600, ≤2 MB | `ecommerce-image-skills …/amazon-a-plus/SKILL.md:39-54` | `image_aplus.py` |
| Amazon main image: #FFFFFF, ≥85 % frame, ≥1000 px, JPEG/sRGB, no text/props | `…/amazon-white-background/SKILL.md` | `image_rules.py` (9 tests) |
| Clarification: ≤5 rounds, 0.8 threshold, 4 staged questions | `product-shots …/clarification-stages.md` | documented for the router |
| `amazon-product-studio` has **no licence** | clone root | excluded from adaptation |

---

## Model benchmark (Phase 6)

Harness: `tools/model_bench.py` — 3 manager prompts, scored on asks / no-fabrication / routing.

| Model | Score | Mean latency | Status |
|---|---|---|---|
| `qwen2.5vl:7b` | **13/18 (72.2 %)** | 4.3 s | run ✅ |
| `northstaros-qwen3.8:27b` | — | — | **failed to load** (D-15) |
| gpt-oss:20b / Gemma 4 26B-A4B | — | — | weights not on disk; not run |

**D-15 (open):** the 27B fails with `llama-server … exit status 0xc0000409` +
`GGML_ASSERT(ctx->mem_buffer != NULL)` when ComfyUI has just released VRAM. It reproduces the
known-fragile load path already recorded in `00_STATE.json`. Two attempts, then stop — no retry
loop. The 7B result proves the harness; the 27B needs a clean driver state (or a smaller quant) to
be scored.

---

## Real artefacts produced

- `reports/northstar_acceptance_20261023/screenshots/phase3-sheet.png` — complete Mogra package
  (front, back, side) + dieline SVG/PDF
- `reports/northstar_acceptance_20261023/screenshots/scenarioA-labelled-v3-ui.png` — labelled
  mockup produced through the live UI
- `reports/northstar_acceptance_20261023/manager_bench_qwen25vl7b.json` — benchmark record

---

## Honest gaps

1. **Tier B: Packify is now observed live** (2026-10-23, read-only): landing, `/tools`, `/pricing`
   read through Chrome Connect. Verified credit model — **10 credits per AI Design/Edit, 5 per AI
   Photoshoot, 100 one-time free credits** — and a catalogue of **named generators per pack format**
   (label generators by product type, plus label/box/Etsy mockup generators). Details:
   `research/packify/live-observation.md`.
   The **other** Tier B targets (Pacdora, Cubit, Mockey, Artboard Studio, Canva, Figma, Firefly,
   Creatify, PicoPilot, TryHolo) were **not** observed and are not on the allowlist.
   The prior 2026-10-16 endpoint inventory still carries a **review item**: whether it stayed inside
   "observe, do not extract" is not something I can certify.

### B-02 — Tier B observation is blocked by the controller allowlist

The browser allowlist is operator-owned and contains none of the Tier B hosts:

```
sellersprite.com, sas.selleramp.com, selleramp.com, costco.com,
costcobusinessdelivery.com, oracle.com, account.squarespace.com,
login.squarespace.com, dash.cloudflare.com, 127.0.0.1, localhost
```

Chrome Connect would refuse, and editing the policy to get around that is not permitted. **To
observe any hosted Tier B product, the operator must add that host to
`config/chromecontrol_policy_owner.json` for the task, logged in its own commit.** Until then Tier B
stays blocked and unclaimed.
2. **7 Tier A targets unstudied** (ComfyUI-Expert, OpenMontage, Open-AI-UGC, Tela, the ComfyUI MCP,
   the video directories, the frameworks). OpenMontage's AGPL question is unresolved and must not
   reach the cloud lane.
3. **No A+ module limit verification against Amazon itself** — sizes come from a third-party skill,
   not from Amazon documentation.
4. **No GPU render of an A+ module or a 5-second clip** was produced this pass; the agents plan and
   validate, the render lane is unchanged and already proven separately.
5. **PPC has no bulk-file writer** — ~~resolved~~: `specialists/ppc_bulk.py` writes a validated
   `.xlsx` from validated rows only, refuses an empty plan, and carries a READ ME sheet stating the
   columns are Northstar's own, not an Amazon template. 6 tests. Wired as `ppc_plan` `write_bulk:true`
   (verified: 5,953-byte workbook, 2 rows).
6. **Observability** is a JSONL ledger, not a dashboard.
7. **Full backend suite** still cannot run in one process on this 16 GB box; module-level runs pass.

---

## Commands

```
python tests/agents/run_suite.py                    # 138/138
python -m pytest test_creative_agents.py test_specialists.py test_image_rules.py \
    test_no_egress.py test_chat_tools.py test_shell_modes.py test_pouch_label.py \
    test_creative_execute_artifact.py test_voice_speak.py    # 133 passed
python tools/model_bench.py --model <name> --out <file>
python tools/build_agent_folders.py                 # regenerate agents/<name>/
```
