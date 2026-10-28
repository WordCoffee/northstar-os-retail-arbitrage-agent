# REA Phase 3 close-out + Phase A spec — 2026-10-28

> **Update, same day:** the operator approved and the kernel was built. See
> `reports/agent_kernel_v01_20261028.md` for the implementation, tests and
> remaining live-baseline work. The Phase A text below is the historical spec
> record and is unchanged.

**Verdict:** Phase 3 items 0–1 are done and verified. `rea_regress` has a
documented entry point and passes. Phase A is on disk for operator review. **No
kernel code has been written.**

---

## 1. Item 0 — ceiling decision: 2048

The operator chose **2048**. The production constant already defaulted to 2048;
the stale 1216 assertions were the drift. They were rewritten to the measured
values, and the decision is recorded in
`reports/rea_baseline_20261028.json` (`render_fit_box.status = resolved`).

- `test_pouch_label.py` + `test_pouch_label_placement.py`: **23 passed**.
- The six old assertions are no longer red, and a ceiling test now reads
  `sg.MAX_EDGE_PX` instead of hardcoding a number that can go stale again.

## 2. Item 1 — L1 + L2 acceptance

### What changed

| File | Change |
|---|---|
| `Northstar_backend/mockup_compositor.py` | `mesh_grid(..., bow_x=(left, right))` accepts a per-side bow; a scalar still behaves exactly as before |
| `Northstar_backend/pouch_label.py` | sub-pixel edge extraction from the blurred mask's 0.5 level set; RANSAC quadratic per side; sine-fit bow per side; `geom_residual_px`; `compose()` refuses above 1.5 px; `mesh=False` preserves the homography path |
| `Northstar_backend/test_pouch_label_geometry.py` | 5 new tests (known bow, straight plate, mesh-vs-homography, refusal guard, per-side grid) |

### Measured on the Mogra reference plate

Plate: `Northstar_backend/data/studio_generated/2e4a7ab96e9941479b068792f592864d.png`
(blank kraft pouch on marble; the labelled `52afb729…` is the same scene after
composition, not a valid base).

| Metric | Value | Gate |
|---|---|---|
| Geometric residual | **0.238 px** (left 0.292, right 0.193) | < 0.5 px **PASS** |
| Fit residual | left 0.241, right 0.199 | reported |
| Bow | left −6.122 px, right −1.197 px | recorded |
| Mesh | 5 × 9, per-side | **PASS** |
| Mesh vs homography | > 16 levels, > 200 side-band pixels | **PASS** |
| OCR (`rapidocr`) | **ok**, 5 boxes incl. `ORGANICLION'S MANE`, `MUSHROOM POWDER`, `6 oz (170 g)` | **PASS** |
| Prepress (`RSWOP.icm`) | **printable** — max TAC 254.9 % (limit 300), 0 px over | **PASS** |
| Readiness (`assess_package`) | **retail_ready**, 0 blockers, 0 warnings | **PASS** |

Evidence: `reports/rea_probe/item1_mogra_composed.png`,
`reports/rea_probe/item1_acceptance.json`.
Test run: **62 passed** across the six focused suites.

## 3. `rea_regress`

`tools/rea_regress.py --quick --with-tests` → **PASS**. Added
`tools/verify-rea.ps1` as the documented entry point (`-Full`, `-WithBuild`).
The baseline JSON now records the resolved ceiling and the measured OCR,
prepress and readiness rows instead of `not_run`.

## 4. Phase A — spec on disk

| File | Contents |
|---|---|
| `research/assistant_intelligence_20261028/KERNEL_SPEC.md` | one kernel for Ty/Bojo/Autothink; state machine; plan/node/evidence/checkpoint/permission/event schemas; 12 modules; documented limits for plan mode, memory, checkpoint and permissions; our own limits; model escalation; NS-PROJ-20 |
| `research/assistant_intelligence_20261028/CLONE_LEDGER.md` | 12 rows (1/6/7/8 `spec'd`, the rest planned), declined targets, licence checks |
| `research/assistant_intelligence_20261028/SOURCES.md` | the 1,500 / 100 / 12 plan, the 12 canonical authorities, exclusions, two operator windows |
| `provenance.csv` | 4 new `SPEC` rows with source URL, access date and the documented limit |

**Honest counts:** 0 of 1,500 scored, 0 of 100 read, 0 of 12 deep. Phase A is the
plan; Phase B fills the CSV. Nothing is claimed as harvested.

### Documented limits verified from public docs (2026-10-28)

- **Checkpointing:** file-tool edits only; a file only Bash changed is untracked;
  after a file-tool edit, later Bash changes to that file *are* rewound; subagent
  edits generally not restored; symlinks/hardlinks skipped; 100 checkpoints;
  ~30-day retention; not a VCS replacement.
- **Memory:** `CLAUDE.md`/`AGENTS.md` + auto memory; auto memory loads first 200
  lines or 25 KB; `CLAUDE.md` target <200 lines; imports max 4 hops; memory is
  context, not enforcement — a `PreToolUse` hook is what blocks.
- **Plan mode:** reads + read-only shell; edits blocked until a plan is approved;
  classifier-approved commands only when auto mode exists.
- **Permissions:** deny → ask → allow, first match, specificity does not reorder;
  bare-tool deny removes the tool from context; file-edit approval lasts the
  session, Bash/WebFetch persist per repository; the harness enforces, not the
  model.

## 5. Not done

- Phase B harvest (`SOURCES_1500.csv`, `TRIAGE.md`) — not started.
- The two operator windows (Claude Code, Cowork) — not scheduled.
- Kernel code — intentionally not started; `KERNEL_SPEC.md` is the gate.
- NS-PROJ-20 baseline run — not started; thresholds stay provisional.

## 6. Gates held

No Amazon. No spend. No static bundle analysis or decompilation. No credentials
entered. No CAPTCHA. Chrome Connect remains the only browser path.

## 7. Next

1. **Operator review of `KERNEL_SPEC.md`** — the only approval this phase needs.
2. On approval: Phase B harvest, then the kernel build in the order policy →
   plan mode → checkpoint → memory.
3. Schedule the two 45-minute windows when convenient; nothing else is blocked
   on them.

**Commits:** `203ac6ba` (L2 + item 1 + baseline + verify-rea). Phase A docs are
committed separately so the spec review is a clean diff.
