# The launcher as a persistent task (folded fix 7)

2026-11-08. WORK ORDER 3 item 7: *install the launcher as a persistent scheduled task and
prove it survives a reboot and a killed session.*

## Installed

```
TaskName         : NorthstarTyDirector
State            : Ready
Trigger          : MSFT_TaskLogonTrigger
Execute          : C:\Python314\pythonw.exe
Arguments        : scripts\ty_director.py
WorkingDirectory : C:\Users\T2Hol\Desktop\Northstar OS Retail Arbitrage Agent
RestartCount     : 3
```

`RestartInterval` 1 minute, `ExecutionTimeLimit` unlimited, `MultipleInstances` IgnoreNew,
`StartWhenAvailable` on. The exported task XML is `reports/ty/d8_launcher_task.xml`.

## Survives a killed session — proven

`reports/ty/d8_launcher_crashrestart.txt`:

```
launcher_pid=12572
child_pid=27276 started_at=2026-11-08T08:59:36+00:00
killed_child=27276 at 2026-11-08T02:59:44
restarted_child=16592 alive=True
launcher_stopped=true
```

The launcher noticed the death, applied the backoff, and started a new session that was
still alive when the check finished. `logs/ty_director.log` shows the same sequence from the
launcher's side: `started director pid=…` → `director died in 10s with no output; backing off`
→ `started director pid=…`.

## The task really launches the launcher — proven, without spawning a second director

The task was run with the PAUSE file present, so it must start and exit immediately rather
than opening a competing director session:

```
schtasks /Run /TN NorthstarTyDirector
log: 2026-11-08T09:00:15 launcher starting (heartbeat=300s cap=3000000)
log: 2026-11-08T09:00:16 stopping: PAUSE file present
LastRunTime       : 11/8/2026 3:00:15 AM
LastTaskResult    : 0
NumberOfMissedRuns: 0
```

PAUSE was removed immediately afterwards. `LastTaskResult: 0` means the registered action
resolved and ran.

## Survives a reboot — registered, not rebooted

**A real reboot was not performed.** Rebooting would end the owner's session and this one,
and the machine is the owner's working laptop. What is proven instead is the mechanism that a
reboot depends on:

- the trigger is `MSFT_TaskLogonTrigger`, which fires at every logon **including the logon
  after a boot**; it is exported in `d8_launcher_task.xml`;
- the task ran on demand with exit code 0, so the action is valid;
- `RestartCount 3` / `RestartInterval 1 min` covers the process dying after logon;
- the launcher itself is idempotent (`MultipleInstances IgnoreNew`, pid file authoritative).

Read that as: the reboot path is wired and the action is proven; the reboot itself is the one
step only the owner can do without losing their session.
