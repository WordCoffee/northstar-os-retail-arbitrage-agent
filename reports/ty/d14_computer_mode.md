# D14 — computer mode scaffolding, behind flags and grants

2026-11-08. Work order §2 rule 6 and §5.1 layer 7. Built and tested; **not enabled here**.

## Scope, as code

`tools/vision/scope.py` answers one question — may Ty read or write this path? — and the
answer is no unless the resolved path is inside the project root, `reports/`, `state/`,
`research/`, `ty/` or a worktree. A `GRANT:` entry in `ty/vision_grants.json` naming a path
unlocks that path. Resolution happens **before** comparison, so `reports/../../Windows/...`
is refused.

`TY_PC_MODE=1` is built for and cannot switch itself on: PC mode needs **both** the
environment flag **and** a `pc_mode: {granted: true}` entry. Either alone leaves it off.

## What computer mode can do

`tools/vision/computer.py`:

| action | risk class | gate |
|---|---|---|
| `read_text` | observe/edit_own | scope, then the privacy redaction filter on the text |
| `write_text` | edit_own | risk policy, then scope |
| `list_dir` | observe | scope |
| `processes` | observe | names and pids only, never command lines |
| `windows` | observe | privacy blocklist applied before returning |
| `launch_app` | edit_own | risk policy |

## The dedicated low-privilege user (built, not executed)

`python -m tools.vision.computer --pc-mode-plan` prints the exact steps for the Northstar PC:
a separate local user, a read/write directory owned by that user, the launcher registered
under it, and `TY_PC_MODE=1` plus a grant. Creating a user and a grant is an owner decision
for that machine, so it is documented and not run here.

## Acceptance (scope enforcement)

```
python -m pytest Northstar_backend/test_vision_computer.py -q
16 passed in 0.25s
```

The named acceptance test is `test_a_write_outside_scope_is_refused_and_leaves_no_file`:
the write returns `refused: true`, the reason names the missing grant, and **the file does
not exist afterwards**. Also covered: `..` cannot escape; a grant unlocks exactly the path it
names; PC mode needs both switches; reads are redacted; the window list drops blocklisted
windows.

## What is deliberately not done

- No attempt to create the low-privilege user, and no `TY_PC_MODE` set.
- No elevation, no service install, no scheduled task under another account.
