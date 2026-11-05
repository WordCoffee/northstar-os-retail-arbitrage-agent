# Ty's Vision and code — measured probe (2026-11-05)

**Question (owner):** is Tys Vision able to see code as Tys Assistant programs, so it
can help itself improve Northstar OS?

**Answer:** it can *judge* code it is shown, it cannot *read* code faithfully, and it
has no way to program. The two are separate lanes and must stay separate.

| What Tys Vision can do | Measured | Verdict |
|---|---|---|
| Answer a yes/no constraint about a code screenshot (`{pass, reasons, confidence}`) | 5/5 ground-truthed constraints, 13.0–18.2 s each | Works |
| Transcribe the same code pixels | 0.652 character similarity, invented lines | Fails |
| Read text off pixels at all (RapidOCR on the identical image) | 0.786 character similarity, drops backticks/brackets | Partial, text only |
| Open a file, edit it, run a test, write a patch | no file access, no tool calls, no write path | Cannot program |

## 1. What "Tys Vision" actually is

`Northstar_backend/agent_kernel/vision_verify.py` — one image plus one design
constraint in, one strict JSON verdict out. Default model `gemma3:4b` (2026-11-04
bake-off winner, 18/20, JSON parse 1.0), 640 px longest edge, `num_ctx` 2048,
`available: false` is a failed check and never a silent pass.

On disk it has exactly two consumers: `tools/v3_graduation.py` (Stage 2 of the
graduation gate) and `Northstar_backend/test_vision_verify.py`. It is **not wired
into Tys Assistant's loop** in any direction.

Tys Assistant programs through a different path: `CodingWorkerAdapter.run_agent`
→ `agent_kernel.coding_runner.run_coding_task` → `CodingAgent` → `coding_tools.Workspace`.
That lane reads source as **text** (`list`, `read`, `grep`, `write`, `write_many`,
`apply_patch`, `ast_edit`, `run`) against the local 27B on `127.0.0.1:8080`.

## 2. The measurement

Harness: `tools/vision_code_probe.py`. It renders 22 real lines from
`vision_verify.py` (lines 39–60, the `_parse` function) to a 1280 px screenshot,
then runs three checks.

**Verdict mode (the shipped contract).** Five constraints, ground truth fixed in
advance:

| Constraint | Expected | Got |
|---|---|---|
| the code defines a function named `_parse` | true | true |
| the code imports the subprocess module | false | false |
| the code removes a markdown code fence with a regular expression | true | true |
| the code contains a return statement that yields a dictionary | true | true |
| the code writes a file to disk | false | false |

5/5. It understands what the code *means*.

**Free-form transcription.** Asked to transcribe the image line by line, it produced
plausible, confidently wrong Python: `text = text.sub(r"\s+", "", text)`,
`if start != 0 or end != len(text)`, an invented `else:` branch. 0.652 character
similarity. This is the failure that matters — the output looked correct.

**OCR, no model.** RapidOCR on the same pixels: 0.786 similarity, backticks and
brackets lost, `if start <  or end <= start` (the `0` dropped). Better than the
vision model and still not a code reading path.

Artifacts: `state/evidence/vision_code_probe/result.json`,
`state/evidence/vision_code_probe/code.png`.

## 3. The coding lane, tested live

If the vision lane cannot program, can the lane that is supposed to? Tested
end-to-end through the real entry point, not a bench copy.

* Worker: Qwen3.8-27B IQ4_XS on llama-server `127.0.0.1:8080`, ready in **33 s**
  (`scripts/start-northstar-moe.ps1 -Lane coder`, 17408 ctx, MTP).
* Objective: write `unit_convert.py` with `to_slug()` and `KIB/MIB/GIB`.
* Acceptance: inline `python -c` assertions held **outside** the workspace, so the
  model could not weaken them. It also could not see them until it was graded.
* Result: `ok=true`, **1 step**, **1.5 s**, 181-byte artifact,
  `acceptance_recovered=false`, `protocol_errors=0`, `scope_rejections=0`.
* Independent re-check by hand, outside the loop: `bad [] ints True`, exit 0.

Artifacts: `state/evidence/tys_self_improve_probe/result.json`,
`exports/tys_self_improve_probe/unit_convert.py`.

The loop does work. It reads code as text, writes it, and is graded by a command it
cannot edit.

## 4. The boundary, stated as a rule

> Never feed vision-model output into a code edit. If a screenshot must inform a
> change, OCR it, treat the OCR text as untrusted data, and re-read the real file
> from disk before editing.

Fine print is where this model fails, and code is nothing but fine print. Two of the
twenty bake-off cases it missed were a small barcode and a square-canvas judgement;
the same limit applies to a 12 px identifier.

## 5. What this means for "help itself improve Northstar OS"

The self-improvement loop is real and cheap: a bounded objective, a workspace, an
acceptance command the agent cannot tamper with, a journal. What it is not is
vision-driven. A useful next step, if the owner wants sight in the loop, is a
screenshot→OCR→text handoff into the **coding** lane, with the OCR text marked
untrusted and the real file re-read before any edit. That is a design change to the
kernel and would breach the V3 hard freeze (rule 1: no new feature lane until Stage 1
is 100% on the full backend suite), so it is recorded here and not built.

## 6. Gates held

Local lane only. No Amazon request, no spend, no cloud inference, no credential read,
no policy or allowlist change. GPU returned to idle (13 MiB used) and the 27B worker
stopped after the test; it restarts on demand.

## 7. Files

| Path | Purpose |
|---|---|
| `tools/vision_code_probe.py` | renders source to a screenshot; measures verdict accuracy, transcription fidelity, OCR fidelity |
| `tools/tys_self_improve_probe.py` | bounded self-improvement probe with untamperable acceptance |
| `state/evidence/vision_code_probe/result.json` | this run's vision numbers |
| `state/evidence/tys_self_improve_probe/result.json` | this run's coding-loop numbers |
| `state/fragments/20261105_vision_code_probe.json` | state entry, pending operator merge |
