# Hybrid coding/tool run — 20/20 — 2026-10-29

**Label:** capability pilot, not a prose/design quality claim. The 20 briefs were
run once through the coding tool loop (text/code) and the existing tools
(label/social/ad). Content validators gate every artifact.

**Run:** `reports/rea_probe/coding_full/20261029T071520Z/summary.json`
**Command:** `python tools/coding_full_bench.py --restart-every 2`
**Result:** **20/20 content-valid (1.00)**.

---

## 1. Per-brief result

| Brief | Route | Steps | Time |
|---|---|---|---|
| p01 fix a test | coding loop | 7 | 14.5 s |
| p02 endpoint doc | coding loop | 2 | 4.2 s |
| p03 split a module | coding loop | 2 | 8.9 s |
| p04 config flag | coding loop | 1 | 4.7 s |
| p05 repair a build | coding loop | 7 | 11.0 s |
| p06 admin audit | coding loop | 3 | 6.2 s |
| p07 safe browser run | coding loop | 4 | 7.2 s |
| p08 resume blocked run | coding loop | 2 | 4.2 s |
| p09 verify external change | coding loop | 2 | 7.3 s |
| p10 weekly digest | coding loop | 4 | 10.6 s |
| p11 pouch label | **pouch_label tool** | 1 | 5.0 s |
| p12 back panel | coding loop | 5 | 8.3 s |
| p13 social canvases | **presets.js tool** | 1 | 0.1 s |
| p14 15 s ad | **FFmpeg probe** | 1 | 0.1 s |
| p15 listing audit | coding loop | 5 | 30.5 s |
| p16 campaign plan | coding loop | 3 | 10.6 s |
| p17 re-plan | coding loop | 3 | 13.0 s |
| p18 handoff | coding loop | 11 | 15.7 s |
| p19 per-hunk diff | coding loop | 5 | 5.3 s |
| p20 three-node project | coding loop | 2 | 5.4 s |

## 2. Comparison

| Lane | Content valid |
|---|---|
| Ty-as-is (read-only coding lane) | **0 / 20** |
| Kernel text lane | 17 / 20 |
| **Kernel coding tools + tools** | **20 / 20** |

Ty end-to-end p01 (literal `run_kernel(coding_agent=True)`, no shim) is also
**complete**: `calc.py` fixed, `pytest` exit 0, valid `fix.patch`
(`reports/rea_probe/tys_kernel/20261029T070832Z/summary.json`).

## 3. What made the difference

- The coding loop has `list/read/grep/write/apply_patch/run` and a real
  observe→act→verify→repair cycle.
- `run` is allowlisted (`pytest`, `py_compile`, `npm test`, `git status/diff`);
  no shell strings.
- `apply_patch` is git-backed, rooted in the workspace, 200 KB / 60 s, no
  fallback writer.
- Acceptance is checked after a write or a run, so the loop stops when the
  artifact and tests pass instead of waiting for a `finish` the model forgets.
- p11/p13/p14 are tool nodes, not text prompts: real PNG, real preset sizes,
  real MP4.

## 4. Honest limits

- One run, not a 3-run spread. The text-lane thresholds remain the measured
  ones; this hybrid is a capability result.
- Content validators check type, required terms, tests and format — not whether
  the refactor is beautiful or the prose is good.
- p03/p04 artifacts are documents plus green tests; they do not prove a
  production-quality refactor.
- The model server still needs periodic restarts at this call volume; the run
  used 10 restarts (`--restart-every 2`).

## 5. Next

1. Repeat the hybrid twice for a spread; set hybrid thresholds only then.
2. Add semantic checks where they are cheap (e.g., p03 two modules import and
   tests pass; p04 both flag states exercised).
3. Make the coding loop Ty’s default for `coding` nodes after a Ty multi-brief
   run, not just p01.

## 6. Gates

No Amazon. No spend. No network beyond `127.0.0.1:8080`. The 27B was stopped
after the run.
