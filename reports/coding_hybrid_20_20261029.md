# Hybrid coding/tool run — 3-run spread — 2026-10-29

**Label:** capability result, not a prose/design quality claim. Three post-fix
runs of all 20 briefs; content validators gate every artifact.

**Command:** `python tools/coding_full_bench.py --restart-every 2`
**Evidence:** `reports/rea_probe/coding_full/` + `spread.json`

---

## 1. Run-to-run result

| Run | Content valid | p50 | p95 |
|---|---|---|---|
| `20261029T071520Z` | **20 / 20** | 7.3 s | 15.7 s |
| `20261029T123307Z` | **19 / 20** | 7.3 s | 17.8 s |
| `20261029T123853Z` | **18 / 20** | 8.5 s | 25.6 s |
| Spread | **18–20** | 7.3–8.5 | 15.7–25.6 |
| **Threshold** | **≥ 0.90** | **≤ 10.2 s** | **≤ 30.7 s** |

Failures were p03 (stalled without writing `refactor.md`, twice) and p02 (one
server connection reset). Both are recorded, not hidden.

## 2. Per-brief route

| Route | Briefs |
|---|---|
| Coding tool loop | p01–p10, p12, p15–p20 |
| `pouch_label` tool | p11 |
| `presets.js` canvases | p13 |
| FFmpeg probe | p14 |

The coding loop has `list/read/grep/write/apply_patch/run` (allowlisted), a
12-step budget, one repair, and acceptance checked after write/run. Tools are
rooted in a workspace; `..` is rejected; `apply_patch` is git-backed, 200 KB/60 s,
no shell fallback.

## 3. Ty end-to-end

Literal `run_kernel(coding_agent=True)` (now the default when a work order names
`scope.workspace`):

| Brief | Ty status | Content valid |
|---|---|---|
| p01 | complete | **yes** |
| p02 | complete | **yes** |
| p03 | complete | **yes** |
| p04 | complete | **yes** |
| p05 | complete | **yes** |

**5/5 content-valid and 5/5 complete** across p01–p05
(`reports/rea_probe/tys_kernel_multi/20261029T134414Z/`). p01 initially exposed an
acceptance-recovery defect: the loop could write every artifact, hit its step
budget before `finish`, and the kernel would report `needs_human`. The executor
now re-checks acceptance after a loop stop and succeeds when the artifacts
already satisfy it. The defect is fixed, not hidden.

## 4. Honest limits

- Content validity is type/terms/tests/format, not prose quality or refactor
  elegance.
- p03’s flake is real: the model can stall without writing the artifact. The
  threshold allows one failure; a semantic/step-pressure fix is next.
- One model server still needs restarts at this call volume (10 per run).
- Ty p01’s `needs_human` status must be fixed before calling the Ty path clean.

## 5. Gates

No Amazon. No spend. No network beyond `127.0.0.1:8080`. Worker stopped after the
runs.
