# Coding-agent pilot — 2026-10-29

**Label:** capability pilot on three briefs; not a full NS-PROJ-20 run.

**Question:** can Ty’s read-only coding lane be replaced by a bounded tool loop
that actually reads, writes, runs and repairs?

**Answer:** yes for p01, p02 and p05 — **3/3 content-valid**, with a real test run
and a real build check.

---

## 1. Result

| Brief | Agent | Content valid | Extra proof | Steps | Time |
|---|---|---|---|---|---|
| p01 fix a failing test | pass | **pass** | `calc.py` fixed (`a + b`), `pytest -q` exit 0, `fix.patch` valid | 7 | 9.2 s |
| p02 add an endpoint doc | pass | **pass** | `endpoint.md` names route, GET, response | 1 | 2.9 s |
| p05 repair a broken build | pass | **pass** | `broken.py` fixed, `py_compile` exit 0, `build.log` valid | 5 | 4.7 s |

Run: `reports/rea_probe/coding_bench/20261029T064907Z/summary.json`
Command: `python tools/coding_bench.py`

## 2. What the lane can do now

Tools, all rooted in one workspace and bounded:

| Tool | Behaviour |
|---|---|
| `list` | workspace tree, skip caches/venvs |
| `read` | text file, capped bytes |
| `grep` | regex, capped hits, text extensions only |
| `write` | create/overwrite inside the workspace, byte cap |
| `run` | **allowlist only**: `python -m pytest`, `python -m py_compile`, `pytest`, `npm test`, `git status/diff` |

No shell strings, no `shell=True`, no path escape (`..` is rejected). The loop is
`observe → act → verify → repair`: max 12 steps, max 1 repair; acceptance is
checked after a write or a run and stops the loop when it passes.

## 3. Ty adapter

`TysAssistant.run_kernel(..., coding_agent=True)` now accepts a coding tool loop
for `coding` nodes. It requires `scope.workspace` (no implicit repo-root writes)
and a reachable local 27B. The default `run()` and `run_kernel()` paths are
unchanged.

## 4. What is not proven

- Only p01/p02/p05; the other 17 briefs are not run with the tool lane.
- No patch **application** tool yet; `fix.patch` is written, not applied to a
  separate repository.
- No Ty-as-is end-to-end run with the new lane; the 0/20 Ty baseline remains the
  measured “before”.
- The model’s tool-choice reliability is 3 briefs, not 20.

## 5. Next

1. Run the tool lane on all 20 briefs; expect the binary briefs to need their
   existing tools (`pouch_label`, `presets`, FFmpeg) rather than the text agent.
2. Add `apply_patch` (git apply in the workspace) and a real sandbox repo.
3. Switch `run_kernel(coding_agent=True)` on for a Ty pilot, then compare against
   the 0/20 Ty-as-is baseline.

## 6. Gates

No Amazon. No spend. No network beyond `127.0.0.1:8080`. Workspaces are local
sandboxes; the 27B was stopped after the run.
