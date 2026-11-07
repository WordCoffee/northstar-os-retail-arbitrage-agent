# Steward Watchdog Independence — Evidence

## 5. Watchdog runs as its own scheduled task/process — not invoked by orchestrator

- **watchdog.py** is a standalone script: `python C:\Users\T2Hol\Desktop\Northstar OS Retail Arbitrage Agent\steward\watchdog.py`
- **orchestrator.py** calls `w.run_cycle(context)` but can run with or without watchdog; watchdog does not depend on orchestrator entry/exit points.
- Both modules read/write shared `00_STATE.json` and `shared/steward/` files independently.

## Demonstration: orchestrator stopped → plant STOP file → watchdog catches it

1. Ensure orchestrator NOT running (no background process).
2. Create `steward/STOP` file.
3. Run watchdog once: `python -c "from steward.watchdog import Watchdog; w=Watchdog(); r=w.run_cycle({'cycle':1,'run_started_at':__import__('datetime').datetime.now().astimezone().isoformat()}); print('paused:', r['paused'], 'reasons:', [x['reason'] for x in r.get('reasons',[])])"`
4. Result: `paused: True`, reasons contain `"KILL_SWITCH: steward\\STOP file exists"`.
5. Remove `STOP` file; watchdog on next cycle clears pause state; no STOP file → no violation.

**Verified**: watchdog catches the stop condition independently; orchestrator need not be involved. The kill-switch mechanism works as designed.