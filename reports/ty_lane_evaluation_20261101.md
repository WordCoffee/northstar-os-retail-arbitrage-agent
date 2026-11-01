# Installed-lane evaluation — interface fixed, no candidate qualifies (2026-11-01)

Continues `reports/ty_qualification_20261101.md`. The previous 6/6 campaign is
preserved unchanged. This round fixed real adapter defects, then screened the
installed lanes. **No installed lane can qualify: MODEL/INTERFACE CAPABILITY
BLOCKED.**

---

## 1. VERDICT

**BLOCKED — MODEL/INTERFACE CAPABILITY.** The harness is better than it was (native
tool calling, read discipline, decontaminated examples), but the best installed
candidate still cannot author a fix: it reads the file, then edits a symbol copied
from the prompt example instead of the one it just read.

No Ty commit exists. Qualification, soak and repair campaign were not run.

---

## 2. ADAPTER FINDINGS (the recorded malformed actions were not model-only)

The request path used `POST /api/chat` with `format: json` and a JSON-text prompt.
It never used Ollama's `tools` interface, even though the installed lanes advertise
it. Measured with a direct API probe (`tmp-probe/probe_native_tools.py`):

| Lane | Capabilities | Native tool call |
|---|---|---|
| `bojo:gpu-orig` | completion, vision, **tools**, thinking | **correct**: `read {"path":"Northstar_backend/calc.py"}` |
| `qwen2.5-coder:3b` | completion, **tools**, insert | none — returned malformed text ` ```{"name":read", ...` |
| `qwen2.5vl:7b` | completion, vision (no tools) | HTTP 400 |

So the old harness forced every lane through a text protocol that at least one lane
is worse at, and never offered the interface `bojo` uses natively. That is category
**B/C**: adapter-transformed and schema-induced, not purely model-generated.

Four harness defects found and fixed, each with regression coverage:

| Commit | Defect | Fix |
|---|---|---|
| `1da7cade` | no native tool interface | `native_tools` mode sends `tools`, converts `message.tool_calls` into the same one-JSON action; one validator judges both paths (`tool_protocol.json_schemas`) |
| `366f0a66` | task-scoped prompt told the model to answer `write_many`, which the task refuses | the nudge names `ast_edit` |
| `3b5e88ef` | a lane looped on `read` (9 times) — the compact prompt had no read pressure at all | `already_read` refusal; an edit clears the guard |
| `ea6b4dc1` | the schema example leaked `add` / `calc.py`; a lane edited `add` instead of the symbol it read | placeholders (`your_file.py`, `the_symbol_you_read`) |

---

## 3. CANDIDATES (installed only, no downloads)

| Candidate | Identity | Verdict |
|---|---|---|
| `qwen2.5-coder:3b` | 3.1B Q4_K_M, `f72c60ca…6225` | **rejected**: emits malformed text under native tools; the JSON path already failed 6/6 in the closed campaign |
| `bojo:gpu-orig` | 1.9B Q8_0 `qwen35`, `5f1256d2…a48` | **best candidate, screened out** — see §5 |
| `qwen2.5vl:7b` | 8.3B Q4_K_M, `5ced39df…1cc` | **rejected**: no `tools` capability (400) and CPU-resident weights (~5.6 GB) would leave under 1 GB free, breaking the 3 GB floor |
| `bojo:latest`, `qwen3.5:2b` | same 1.9B family | not stronger; same behaviour class as `bojo:gpu-orig` |

Selected `bojo:gpu-orig` on demonstrated tool suitability, not parameter count.

### Measured resources (operator CPU configuration, unchanged)

| Measurement | Result |
|---|---|
| Free RAM before the screen | **7.11 GB** (≥ 6.0 GB pre-load) |
| `bojo:gpu-orig` ctx 8192, cold load (earlier evidence) | 5.08 GB → **2.443 GB** min, resident 2.253 GB system → FLOOR-MET |
| `bojo:gpu-orig` warm, resident | 4.272 GB baseline → **4.215 GB** min (model already loaded) |
| Placement | **CPU** (`OLLAMA_LLM_LIBRARY=cpu`), GPU idle and unused; no setting changed |

---

## 4. SCREEN (disposable workspace, not a repository task)

`tools/screen_lane.py`: a small module with a silent-skip defect, an objective and
an independent behavioural check; the model must read, identify `summarise`, edit it
and pass the check.

| Attempt | Result | Note |
|---|---|---|
| 1 | 5 reads, no edit (37 s) | voided: the task-scoped prompt had no read pressure |
| 2 | 9 reads, no edit (29 s) | voided: same harness defect |
| 3 | read ✓ → `ast_edit` **target `add`** → 7 refused reads (40 s) | valid screen |

Valid failure, verbatim:

```text
read      ok    """Inventory limits used by the screen."""  def summarise(rows): ...
ast_edit  FAIL  target 'add' not found (missing 'add')
PROTOCOL already_read: 'src/limits.py' is in the conversation above (x7)
```

The lane read `summarise` and then tried to edit `add` — a token from the prompt
example. After that it looped on `read` until the step budget ended. Screening
budget spent.

---

## 5. QUALIFICATION / SOAK / REPAIR

* Qualification campaign: **NOT RUN** — no candidate screened; the previous 6/6
  failure history is untouched.
* The three application probes still fail on current HEAD, so the defects are
  unchanged and ready for a capable lane:

```text
t5_hitl_corrupt.py        FAIL (1)  unreadable records are reported
t6_diff_select_headers.py FAIL (2)  one/both hunks keep the file header
t7_artifact_jpeg.py       FAIL (2)  valid JPEG is an image; broken magic refused
```

* 120-minute soak: **NOT RUN** (gated on qualification).
* Repair campaign: **NOT RUN** (gated on qualification).

---

## 6. REGRESSION

```text
161 passed in 5.19s
```

Eleven suites: protocol, coding agent, kernel, loop, readiness, recovery, supervisor
crash, launcher, budget, task prompt, native adapter. New coverage this round: 7
adapter tests, the `already_read` rule, the ast_edit-before-read rule, and the
example-decontamination assertion.

---

## 7. STATE

Nothing running: no supervisor, no lock, no STOP, no worker, no resident model.
HEAD `ea6b4dc1`. Queue unchanged: three app tasks `failed` from the closed
campaign, six dispatches spent, no eligible work without an operator decision.

---

## 8. CORRECTION (2026-11-01, later) — a floor verdict was mislabelled

The resource table in §3 above contains an error that is corrected here. The
original row is preserved, not overwritten.

| Claim in §3 | Corrected fact |
|---|---|
| `bojo:gpu-orig`, cold load, 2.443 GB min → `FLOOR-MET` | **`FLOOR-MISSED`**. The floor is **3.0 GB**; 2.443 < 3.0. The label was wrong, not the number. |
| warm 4.215 GB min presented as a normal measurement | the model was **already resident** for that sample (baseline 4.272 → min 4.215, a drop of 0.057 GB). It shows headroom *with* the lane loaded; it is **not** a cold-load measurement and must not be read as one. |

Raw evidence, unedited:

```text
state/evidence/model_resident_bojo_20261101.json            3.930 -> 1.192 GB  FLOOR-MISSED
state/evidence/model_resident_bojo_cpu_restored_20261101.json 3.563 -> 1.457 GB  FLOOR-MISSED
state/evidence/model_resident_bojo_ctx8192_20261101.json    4.272 -> 4.215 GB  FLOOR-MET (warm: model already resident, -0.057 GB)
```

**Corrected conclusion:** `bojo:gpu-orig` on the CPU runtime **never** met the
3.0 GB resident floor — every cold sample left 1.19–2.44 GB. The CPU lane was not
resource-qualified at any point; it was exercised under the gate only because the
*gate* refused, and the one `GO` in this programme belongs to
`qwen2.5-coder:3b` (cold 6.99 → 5.056 GB), not to `bojo`.

Consequence: nothing in this report authorises a CPU-lane campaign, and the 8.3B
GPU evaluation starts from a corrected baseline rather than a carried-over error.

---

## 8. WHAT WOULD UNBLOCK IT

One of these, none available under this directive:

1. an installed **coder** lane in the 7B+ class that fits the CPU envelope
   (a 7B Q4 is ~4.5 GB resident, which needs ~7.5 GB pre-load at this floor), or
2. authority to run the existing 8.3B lane on the GPU (it measured 6.14 GB VRAM and
   0 GB system earlier), or
3. acceptance that the first model-authored fix must come from a lane that can hold
   a symbol across two turns.

Until then the honest capability is: **the automation detects and refuses bad model
output precisely; the installed 3B/1.9B lanes cannot yet author an accepted fix.**
