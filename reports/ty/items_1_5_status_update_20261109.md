
---

# Update, 2026-11-09 (second pass) — what changed after the owner's follow-ups

## Item 1 — grounding: UI-TARS tried, and the honest reason it did not measure

| what | result |
|---|---|
| UI-TARS licence | **Apache-2.0**, read from the project's own `LICENSE`. |
| Downloaded | `ByteDance-Seed/UI-TARS-2B-SFT`, **9.11 GB** cached under the HF hub. |
| Stack prepared | `transformers 4.57.0` + `accelerate` installed into the **ComfyUI CUDA venv** (`torch 2.11.0+cu128`, CUDA available) — the repo interpreter is CPU-only and could not run it at all. |
| Model load | **killed during checkpoint shard loading**, no traceback: free RAM was **3.0 GB** and a 2B fp16 model needs roughly twice that before it reaches the GPU. |
| Verdict | **BLOCKED-ON-RESOURCE.** No hit rate was produced, so the **61.7 % baseline stands** and **UIA + DOM stay primary**. `tools/vision/grounding_uitars.py` is the harness; `--probe` is the smallest way to confirm a load once RAM allows. |

**OmniParser** now has a logged GRANT (`reports/ty/grants.md`, tag
`rollback/pre-grant-ultralytics-20261109`): `ultralytics` (AGPL-3.0) is allowed **dev-only, local
bench only, never served, never shipped**, for the grounding benchmark. Both `ultralytics` and
OmniParser's CC-BY-4.0 weights are in `replace_later.md` with the commercial-safe replacements to
find.

## Item 2 — stays open

**SETTINGS VERIFIED · BOOT PROOF PENDING (DIR-6).** No post-boot run exists: the task's last run
(`2026-11-08T09:00:15Z`, result 0) predates the current boot (`2026-11-03T17:48:04Z` is the boot
time, so that run is *after* the boot — but it was a launcher start, not a logon trigger after a
reboot, and the task has never fired from its trigger). It closes when
`reports/ty/reboot_proof.md` gains a section written after a reboot.

## Item 3 — corrected by measurement

**The hosted target was a live public site**, and that is now proven twice: a fresh GET of
`https://opencode.ai/` returns **200**, 194,113 bytes, `sha256 4b016d4d…3e378`, **byte-identical**
to the tracked `index.html` (`research/bakeoff/targets/hosted/_fetch.json`, force-added so it is
tracked). The independent verifier repeated the fetch and got the same hash.

**Accuracy is measured against declared ground truth, not size or speed** — and the composite is
not the accuracy ranking:

| target | accuracy leader | facts | composite leader | disagreement |
|---|---|---|---|---|
| open-source repo | **REA** | REA 10/10, craft-anything 9/10 | craft-anything | **yes** — cheaper, not more accurate |
| hosted | **tie** | 7/7 each | craft-anything | no — the win is entirely cost |
| local app | **tie** | 7/7 each | craft-anything | no — cost |

Weights: accuracy 0.40, detail 0.25, speed 0.15, tokens 0.10, reliability 0.10 — **60 % of the
composite is not accuracy**. On the one target where accuracy differed, **REA was more accurate**.
Craft Anything remains the default on cost, with that stated as the reason.

**Verifier: AGREE on all five checks** (`reports/ty/bakeoff_verification.md`, commit `9c8fb445`),
including reproducing two cells from a detached worktree and confirming the crates.io vet is
vacuous (the crate is unpublished, 404). It also caught that my first `accuracy_verdict` said "both
surfaced the same ground truth" for the OSS target, which was wrong; the verdict now says REA
10/10 vs 9/10.

## Item 4 — FLUX 3 retested with residents unloaded

| attempt | result |
|---|---|
| contended 1024 / 1536 (Bojo resident) | **ok** |
| unloaded 1024 | **failed**: `hostbuf_file_reader_read failed` in `KSampler` node 107 — the **weight-loader fault**, not cuDNN |
| unloaded 1536 | refused on budget: 13.86 free, 13.53 needed, 0.33 < 1.0 reserve |
| isolated measurement (gate relaxed) | **succeeded, 89.5 s, peak 11.93 GB** (`reports/ty/flux_vram_measure.json`) |

So the declared need was wrong, not the card: `flux3` was claiming 12.4 GB at 1024 when it peaks at
**11.93**. The table is now `(10.6, 1.3)` — the measurement plus a cushion — and the lane now waits
for VRAM to settle after an unload instead of reading the old number three seconds early.

**FLUX 3 is still not reliable**: the same configuration succeeds and fails across runs, with the
failure in the fp4 weight reader. **SDXL at 1536 is the working path and the default**, and it has
produced every composite on disk. That is the "first working path" the order asked for, and it was
reached without spending the later fixes (no CUDA-13 rebuild, no ComfyUI update, no cuDNN disable).

## Item 5 — slices

A staging-candidate freeze + full-suite run + slice promotion with per-service review packs is
being built (`ty/stageslice`). The gate logic itself is already verified: `--check` refuses today's
bundle on all three gates with the reasons and writes the review pack.
