# Creative pipeline — transport hardened, form-adherent (2026-11-02)

Two of the three authorised units shipped, both with measured before/after evidence.
Unit 3 was not started.

---

## VERDICT

**ADVANCING — 2 of 3 units shipped.** Transport is no longer a throughput risk; the
generator now honours the requested container form (1/4 → **4/4** measured). The
label/mockup unit (Unit 3) was **not started**: the session budget was spent on the
first two.

---

## AUDIT — where the hang actually was

`opencode run` over stdin at increasing sizes, one call each:

| prompt size | result | time |
|---|---|---|
| 1 KB | pong | 1.9 s |
| 8 KB | pong | 6.1 s |
| 16 KB | pong | 2.3 s |
| 24 KB | pong | 1.9 s |
| 32 KB | pong | 2.3 s |

**The pipe was never the problem.** The lane was sending the *whole* 22–24 KB module,
so the model answered with a whole-module replacement; the loop then retried those large
replies at 300 s each — four turns ≈ the observed 25–30 minute "hang".

**Fix.** `go_author._excerpt()` extracts only the function the objective names (AST),
with a 6 KB cap and a whole-file fallback when no symbol matches. A 24,124-byte module
now round-trips in **3.2 s** with a **767-byte** prompt (`state/evidence/
transport_synthetic.json`), and the per-call timeout (rc 124) plus a 600 s task deadline
mean a stall is deterministic, ledgered and residue-free.

---

## UNITS

### Unit 1 — `ty-go-transport-hardening` — **DONE**

| | |
|---|---|
| Steps | size matrix → root cause → AST excerpt → timeout/deadline → synthetic contract |
| Self-review caught | the first synthetic test asserted a `return 10` literal; the applied body used `min(...)`, so the check now accepts either |
| Acceptance | 24 KB module, 767 B prompt, **3.2 s**, edit applied, `under_90s: true` |
| Evidence | `state/evidence/go_transport_matrix.json`, `transport_synthetic.json` |

### Unit 2 — `ty-subject-adherence` — **DONE**

Before: the form rode only in prose; the vision check (`qwen3.5:4b`, the coherent
multimodal lane) measured **1 of 4** matches — bottle and tube both rendered as boxes,
and the box brief read as "none of these".

After: `form` is a **schema field** (`pouch|box|bottle|tube|jar`) and the clause is
stated at the **head and tail** of the brief; the vision check measures the rendered
image, not the prompt.

| requested | observed (after) | match |
|---|---|---|
| pouch | stand-up pouch | yes |
| box | rigid box | yes |
| bottle | bottle | yes |
| tube | squeeze tube | yes |

**4 of 4** (`state/evidence/form_adherence.json`). Contract tests
(`test_generate_form.py`, 4) prove the form survives `sanitize_brief_for_render` twice,
that `GenerateIn.form` is a bounded optional field, and that the suppression phrase
names **no** container — the same defect class as the botanical clause.

### Unit 3 — `ty-simple-mode-labeled` — **NOT STARTED**

Gated behind Unit 2's gate, which only flipped late in the session. No manifest, no
mockup step, no deliverable folder this run.

---

## DECISIONS (anchors)

1. **Measured the pipe before changing it** — 1–32 KB all complete, so the fix belongs
   in prompt size, not in transport. Anchor: the matrix above.
2. **Send the symbol, not the module** — a 24 KB prompt begets a 24 KB reply; a 767 B
   prompt begets an applicable one. Anchor: 3.2 s synthetic round-trip.
3. **The form must be data, not prose** — a field in `GenerateIn`, repeated head/tail.
   Anchor: 1/4 → 4/4 vision-measured matches.
4. **The gate reads the render, not the prompt** — `qwen3.5:4b` classifies the image;
   a correct prompt with a wrong render still fails.
5. **Stopped at two units** rather than starting Unit 3 without the budget to finish it.

---

## SPEND

| Item | Cost |
|---|---|
| transport matrix (5 calls) | ≈ $0.010 (usage not returned; estimate) |
| two hung unattended turns (earlier) | $0.0022 |
| probes | $0.0035 |
| **5-hour window** | **$0.0157 of $7.20 halt** |

Renders: 8 local ComfyUI runs, **$0**.

---

## REGRESSIONS

```text
test_go_author + test_generate_form + test_text_fidelity + test_author_lane
45 passed, 1 failed  (the failure is the PRE-EXISTING auth-ordering test)
```

---

## STATE

* Commits: `6f069143` (suppression phrase), `eb53fd63` (creative unit docs),
  `932ac936` (transport + form adherence).
* Backend restarted through the launcher and **armed**; engine `armed: true`.
* No lock, no STOP, no worker, no resident model; Ollama daemon untouched (`q4_0`).
* Learning store still 7 trajectories (threshold 10 not reached).

---

## NEXT DECISION (one)

Run **Unit 3 (`ty-simple-mode-labeled`)**: accepted render → label/mockup step → a
deliverable folder with the brief, the adherence verdict, template citations and a
populated manifest — or stop here.
