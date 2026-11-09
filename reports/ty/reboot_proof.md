# Reboot proof

One dated section per `python tools/post_reboot_check.py` run. Old sections are never rewritten.

## 2026-11-09T06:57:05+00:00 — reboot proof

boot **2026-11-03T17:48:04+00:00** via Get-CimInstance Win32_OperatingSystem LastBootUpTime; uptime 5d 13h

- task `NorthstarTyDirector`: state Ready, last run 2026-11-08T09:00:15+00:00, result 0 (success), missed runs 0
- director pid 16592: **not alive** (pid file written 2026-11-08T08:59:53+00:00)
- queue: 14 open / 35 jobs — {"merged": 9, "queued": 14, "released": 12}
- resumed after boot: yes — 2026-11-08T08:59:53+00:00 started director pid=16592
- handoff `C:\Users\T2Hol\Desktop\Northstar OS Retail Arbitrage Agent\reports\ty\handoff.md` mtime 2026-11-09T06:47:39+00:00 (continued after boot: yes)

verdict: task ran this boot yes; director alive **no**; resumed after boot yes; handoff continued yes

