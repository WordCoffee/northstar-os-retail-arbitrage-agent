# "Exited with code 1" after the last commit — what it actually was

Last commit at the time of writing: `0141fbf6`. Every entry below is a command whose wrapper
reported exit **1** after that commit. None of them is a failed unit, and the evidence is the
object each one was supposed to create.

## 1. `git commit` — reported 1, committed successfully

The hook runs gitleaks, which writes its progress to **stderr**. PowerShell surfaces any native
command's stderr as an error record and sets `$LASTEXITCODE` from the process, so the wrapper prints
`Exited with code 1` even when git returned 0. Evidence that the commits are real:

```
git log --oneline -6
0141fbf6 handoff: persistence proven, Bojo reads the design, quiet window armed
d414b8ff G1 Design Studio persistence, Bojo reads the open design, and the quiet window is armed
cc81f118 G1 Design Studio: measured, and the persistence gap named rather than papered over
9d9dad5c keep state/ ignored: the heartbeat is a runtime file, not a tracked artifact
f3142bad private bundle, titles out of every artifact, and one recorded Chrome window
b238a076 digest, handoff and queue: soak running, guard in place, research G1 closed
```

Each of those commits printed *"no leaks found"* from the hook before the code-1 wrapper line.

## 2. `pytest` — genuinely non-zero while a test was red, then green

Two runs after the last commit were red and are not hidden:

- `test_read_open_design_scope.py` — 6 failed. Cause: the tool had no org scope yet (that is the
  change being made) and three older tests still called `read_open_design()` without an account.
- `test_bojo_read_open_design.py` — 1 failed. Cause: a stale assertion expecting the old refusal
  text ("nothing open to read") after the message changed to name the organisation.

Both were fixed in the same pass; the suites now read:

```
python -m pytest Northstar_backend/test_read_open_design_scope.py \
                  Northstar_backend/test_bojo_read_open_design.py -q
10 passed
```

## 3. `dev-start.ps1` — exit 255, not 1, and by design

The background supervisor exits `255` when the harness stops it (its `finally` then stops the pids
it started). That is the supervisor contract, not a crash; the stack was restarted afterwards and
`/health` returned 200.

## 4. `tools/vision/v3_gate.py` — exit 3 on purpose

`--status` exits **3** while `state/vision/PAUSE` exists, so a scheduler can tell "refused" from
"failed". Nothing in the launch work depends on it.

## What was not found

No background job, service or test died with code 1 in a way that lost work: the worktree was clean
after each commit (`git status --porcelain` empty), the UI build returned `✓ built`, and the soak and
quiet-window processes are alive (pids 22344 and 22852). The one real, unfixed non-zero is the
**render lane** refusing for lack of free RAM, which is recorded where it belongs and is not an
exit code.
