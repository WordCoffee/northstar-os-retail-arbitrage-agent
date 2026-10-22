# Golden set expansion + GPU guard — 2026-10-22

## 1. Golden set: 20 → 118

`eval/golden/domains.jsonl` adds 98 items across the eight domains (listings,
Amazon ads, Google/Bing ads, A+, Creator Connections, brand-store, reseller,
creative). The loop now loads every `*.jsonl` in `eval/golden/`.

| measure | value |
|---|---|
| total questions | **118** |
| knowledge-covered (`expects`) | 96 |
| live-only (graded by checks) | 22 |
| coverage | **96 / 96 = 100 %** |

- Items without `expects` are excluded from the coverage denominator instead of
  dragging it down — they exist to grade answers, not to demand an atom.
- **Weekly rotating hold-out:** `holdout_split()` hashes `id + ISO week`, so ~20 %
  of ids rotate in and out. The hold-out is never used to author rules.
- **One atom per slot:** `prioritise()` now de-duplicates by required atom as
  well as by question. Six questions needing one atom consume one slot, not six
  — that was wasting research capacity and leaving real gaps open.

## 2. Live baseline (real, not a fixture)

`--live --live-limit 2` → **0.65**, with both failing check names reported.

This is the first honest quality number for Bojo on the golden set. It is a
trend line, not a verdict: the sample is small and the checks are strict
(citations, exact policy terms, banned claims).

## 3. The GPU lesson, encoded

Two failures in a row looked like network errors:

```
ConnectionResetError(10054)  →  ollama http 500: cudaMalloc failed: out of memory
```

Cause: ComfyUI was still holding the card, and an interrupted Ollama load left an
**untracked `llama-server`** holding ~12 GB while `ollama ps` reported nothing.
Killing the orphan returned the card and the same request answered in 36.7 s.

Now in code:

- `gpu_state()` reads free VRAM and the models Ollama admits to having loaded.
- `can_run_live()` refuses to grade when free VRAM is low **and** nothing is
  tracked (the orphan case), with a human reason.
- `model_answer()` raises on an engine error instead of returning `""`, so an
  outage can never be graded as a zero.
- The CLI checks both before running, prints the reason, and runs the knowledge
  cycle anyway.

## 4. Feedback note field

Clicking **Wrong** now opens a one-line "What was wrong?" input. The operator's
own words are sent as the gap evidence; if left blank, the answer text is used
(as before). Enter submits.

## Gates

- **128 passed / 0 failed** (cie, chatter, chat core, tools, turn contract, plan,
  shell).
- UI build: **0 errors**.
- Live path exercised against the real model twice, including one genuine outage.

## Next

- Wire the live score into the promotion *report* (not the gate) so each cycle
  shows coverage delta and quality delta side by side.
- Tool-first grounding: factual answers must cite a tool result before they speak.
- Add a "GPU busy" state to the Improvement room so the operator sees why a
  cycle skipped live grading.
