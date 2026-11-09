# Item 2 — reboot proof

2026-11-09, builder `item2-reboot`, worktree `state/worktrees/item2`, branch `ty/item2`
(from `staging` @ `f48655d3`).

Deliverables: `tools/post_reboot_check.py`, `scripts/ty_director.py` (the once-per-boot
hook), `Northstar_backend/test_post_reboot_check.py`,
`Northstar_backend/test_ty_director_launcher.py` (extended), `reports/ty/reboot_proof.md`
(the first real section), `state/director/reboot_proof.json` (gitignored runtime artefact).

---

## 1. The scheduled task's settings — verified, not trusted

Measured with `Get-ScheduledTask` / `Export-ScheduledTask` / `Get-ScheduledTaskInfo`, not
read from the install script.

```
logon_trigger              : MSFT_TaskLogonTrigger
trigger_user               : MSI\T2Hol
trigger_end                :                    (none — fires at every logon)
StartWhenAvailable         : True
RestartCount               : 3
RestartInterval            : PT1M
DisallowStartIfOnBatteries : False
StopIfGoingOnBatteries     : False
ExecutionTimeLimit         : PT0S               (unlimited)
MultipleInstances          : IgnoreNew
RunOnlyIfIdle              : False
StopOnIdleEnd              : true
LogonType                  : Interactive
LogonTypeXml               : InteractiveToken
RunLevel                   : Limited
UserId                     : T2Hol
```

| Requirement | Setting | Value | Verdict |
|---|---|---|---|
| Logon trigger, every logon incl. the one after a boot | `MSFT_TaskLogonTrigger`, `UserId MSI\T2Hol`, no `EndBoundary` | present | **pass** |
| Start when available | `StartWhenAvailable` / `<StartWhenAvailable>` | `True` / `true` | **pass** |
| Restart on failure | `RestartCount` / `RestartInterval` / `<RestartOnFailure>` | `3` / `PT1M` / Count 3, Interval PT1M | **pass** |
| Not stopped / not blocked on battery | `StopIfGoingOnBatteries`, `DisallowStartIfOnBatteries` | `False`, `False` | **pass** |
| Execution time unlimited | `ExecutionTimeLimit` | `PT0S` | **pass** |
| Never two launchers | `MultipleInstances` | `IgnoreNew` | **pass** |
| Runs in the interactive user's session | `LogonType` | `InteractiveToken` (XML) / `Interactive` (CIM) | **pass** |

**No setting was changed.** `StopOnIdleEnd: true` is the Windows default and is inert here:
Microsoft documents it as used only when `RunOnlyIfIdle` is true, and `RunOnlyIfIdle` is
`False`. Changing a live task for an inert value would be churn, so it is recorded, not
"fixed".

Action target (existence checked, not assumed): `C:\Python314\pythonw.exe` exists;
`scripts\ty_director.py` exists under the recorded working directory
`C:\Users\T2Hol\Desktop\Northstar OS Retail Arbitrage Agent`.

### Does it need an interactive session? Yes — and it has one

`InteractiveToken` is Task Scheduler's "Run only when user is logged on". The alternative
("Run whether user is logged on or not") is `S4U`/`Password`, and it would put the action in
a session with **no attached desktop**, which is where both vision lanes live:

- `tools/vision/chrome_uia.py:227` `user32.SetForegroundWindow(hwnd)`, `:66`
  `GetForegroundWindow()`, `:138`/`:369` `import uiautomation as auto` — UI Automation drives
  real windows on `WinSta0\Default`. In a non-interactive session there is no such window to
  focus, and `SetForegroundWindow` fails rather than capturing.
- `tools/vision/capture.py:106` `mss.mss()` and `:117`–`:126` `sct.grab(region)`, fallback
  `:138` `PIL.ImageGrab.grab(bbox=...)` — both read the session's display surface. A task with
  no interactive session captures a blank/black desktop, silently, which is worse than a
  failure: the director would "see" nothing and keep deciding.

So the setting is not merely permitted, it is required, and the task already carries it
(`<LogonType>InteractiveToken</LogonType>`, `UserId` = the owner's SID
`S-1-5-21-3844176191-745864684-3329959024-1001`). Switching it to S4U would break vision
without breaking the launcher, so nothing would notice.

### What has *not* been proven, and why

The task has never fired on a real logon: it was registered 2026-11-08 and the machine has
been up since boot `2026-11-03T17:48:04Z`. `Get-ScheduledTaskInfo` shows
`LastRunTime 2026-11-08T09:00:15Z`, which was the on-demand `schtasks /Run` from the D2 proof
(`reports/ty/d8_launcher.md`), `LastTaskResult 0`, `NumberOfMissedRuns 0`.

`Microsoft-Windows-TaskScheduler/Operational` is **disabled** on this box
(`Get-WinEvent -ListLog ... → IsEnabled: False`), so there is no trigger history to cite even
if it had fired. That log is the only way to see a trigger decision after the fact; the
reboot itself is the other. Neither is available to a builder that is forbidden to reboot.

---

## 2. `tools/post_reboot_check.py`

Boot time source: **`Get-CimInstance Win32_OperatingSystem` → `LastBootUpTime`**, converted to
UTC — the machine's own answer, and it describes the boot it is being asked about. The
fallback is the `time.monotonic` offset (`time.time() - time.monotonic()`, which on Windows
counts from boot); the payload records which source was used in `boot.source`, so a reader
never has to guess. One PowerShell process serves both the boot time and the task info.

Records, in `state/director/reboot_proof.json` and one appended dated section in
`reports/ty/reboot_proof.md`:

- boot instant + uptime;
- task `LastRunTime`, `LastTaskResult`, `NumberOfMissedRuns`, `State`;
- director pid from the pid-file (authoritative, as the launcher defines it) and liveness via
  `OpenProcess` — checked, never assumed;
- queue open jobs by status, read through `tools/director_queue.py` (`jobs()`), never by
  opening sqlite; no database yet ⇒ reported, and **not created**;
- the newest `started director pid=` line in `logs/ty_director.log`, plus whether any start
  happened after the boot instant;
- handoff mtime and whether it moved after the boot;
- a `verdict` block of four booleans.

`--root PATH` points the *reads* at another checkout and leaves the two artefacts with the
code. That is how this worktree cites the live log without writing into the live tree.

### Real run against this boot

```
$ python tools/post_reboot_check.py --root "C:\Users\T2Hol\Desktop\Northstar OS Retail Arbitrage Agent"
{
  "checked_at": "2026-11-09T06:57:05+00:00",
  "checked_epoch": 1794207425.386,
  "boot": {
    "source": "Get-CimInstance Win32_OperatingSystem LastBootUpTime",
    "utc": "2026-11-03T17:48:04+00:00",
    "epoch": 1793728084.5
  },
  "uptime_seconds": 479340.9,
  "task": {
    "ok": true,
    "name": "NorthstarTyDirector",
    "state": "Ready",
    "last_run_time": "2026-11-08T09:00:15+00:00",
    "last_run_epoch": 1794128415.0,
    "never_run": false,
    "last_task_result": 0,
    "missed_runs": 0
  },
  "director": {
    "pid": 16592,
    "alive": false,
    "started_at": "2026-11-08T08:59:53+00:00",
    "recorded_cmd": ["C:\\Python314\\python.exe", "-c", "import time; time.sleep(600)"],
    "pid_file": "...\\state\\director\\director.pid"
  },
  "queue": {
    "ok": true,
    "db": "...\\state\\director\\queue.sqlite",
    "total": 35,
    "open": 14,
    "by_status": {"merged": 9, "queued": 14, "released": 12},
    "open_jobs": [
      {"id": "sel-02-design-studio", "unit": "D12", "status": "queued", "owner": ""},
      ... 13 more, all "queued" (D12 sel-02…tool-watch-competitor, U ux-06…ux-09)
    ]
  },
  "resume": {
    "found": true,
    "after_boot": true,
    "pid": 16592,
    "at": "2026-11-08T08:59:53+00:00",
    "line": "2026-11-08T08:59:53+00:00 started director pid=16592",
    "newest_pid": 16592,
    "newest_at": "2026-11-08T08:59:53+00:00",
    "starts_total": 7
  },
  "handoff": {
    "path": "...\\reports\\ty\\handoff.md",
    "exists": true,
    "bytes": 11310,
    "mtime": "2026-11-09T06:47:39+00:00",
    "mtime_epoch": 1794206859.535,
    "after_boot": true
  },
  "verdict": {
    "boot_known": true,
    "task_ran_this_boot": true,
    "director_alive": false,
    "director_resumed_after_boot": true,
    "handoff_continued_after_boot": true
  }
}
```

Read it honestly: `director_alive: false`. Pid 16592 was the `time.sleep(600)` substitute from
the D2 crash/restart proof, so the "resumed after boot" evidence on **this** boot is a test
artefact, not a live director. The check reported exactly that rather than inventing a pass.
The fields a real reboot produces (a fresh `started director pid=` line after the new boot
instant) are the ones the same run already reads correctly.

---

## 3. The launcher runs it once per boot

`scripts/ty_director.py`:

- `boot_epoch()` = `time.time() - time.monotonic()` — no subprocess, so asking the question
  on every start is free.
- `reboot_check_needed()` — true when `state/director/reboot_proof.json` is missing or its
  `checked_epoch` predates this boot.
- `run_reboot_check_once()` — called from `main()` right after `launcher starting …`, i.e.
  before the first director session. It **spawns the check detached**
  (`DETACHED_PROCESS | CREATE_NO_WINDOW`, `stdin/stdout/stderr=DEVNULL`) and never waits: the
  session is never held, let alone for 2 s. One log line either way:
  `reboot check: no proof for this boot; started pid=N` or
  `reboot check skipped: <Type>: <detail>` / `… missing; skipped`.
- Whole body in `try/except Exception`; a broken check logs and returns `None`. `--once` and
  `--status` do not run it (they stay model-free and write-light).

Tests added to `Northstar_backend/test_ty_director_launcher.py`:
first start after boot runs it (`assert calls == ["ran"]` through `main()`); a second start in
the same boot does not (runner replaced with `pytest.fail`); a proof from before the boot is
stale; a runner that raises still returns 0 and logs the one line; a missing script is skipped;
`--once` never runs it.

---

## 4. Tests

```
$ python -m pytest Northstar_backend/test_post_reboot_check.py Northstar_backend/test_ty_director_launcher.py -q
................................                                 [100%]
32 passed in 2.64s
```

(17 in `test_post_reboot_check.py`: boot from CIM and from the monotonic fallback; task
last-run/result and the never-ran sentinel; newest-after-boot resume selection and a
pre-boot start being rejected; queue counting via `director_queue` and a missing database not
being created; handoff mtime; two runs appending two sections without overwriting; a probe
that raises still writing a payload; atomic JSON; dead pid; `--root` rebasing reads only.)

---

## 5. What remains for the owner

1. **One real reboot is the only missing measurement.** Everything the reboot depends on is
   now registered, checked and self-recording; the trigger has still never fired on a logon
   because there has been no logon since it was registered. After the next boot, the launcher
   runs the check by itself and the evidence lands in `reports/ty/reboot_proof.md`.
2. **Vision needs that logon to stay interactive** (see §1). Do not switch the task to "run
   whether user is logged on or not" to make it survive a locked screen — it would capture a
   black desktop silently.
3. **`Microsoft-Windows-TaskScheduler/Operational` is disabled.** Enabling it gives trigger
   history (event 100/102) after a boot; it is a machine policy change, so it is left to the
   owner rather than flipped here.
4. Nothing in this item was changed on the machine's task definition: the six settings were
   already correct, and no `Set-ScheduledTask` call was needed.
