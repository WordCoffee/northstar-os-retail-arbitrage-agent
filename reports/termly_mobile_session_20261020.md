# Termly mobile bridge — live session + install notes

**Date:** 2026-10-20 · **Machine:** MSI (Windows) · **OpenCode:** 2.0.32

## What is live right now

```
termly start --ai opencode        (run from the Northstar project root)
```

| Field | Value |
|---|---|
| Session ID | `a2a950cc-704a-4235-873f-8fb4f79c20e5` |
| PID | 4196 → `conhost` → `cmd.exe /c opencode` |
| AI Tool | OpenCode 2.0.32 |
| Project | Northstar OS Retail Arbitrage Agent |
| Mobile | 🟢 Connected |
| E2EE fingerprint | `5B:10:A4:14:5D:E1:D2:04:AC:33:2D:58` |

The phone paired with pairing code `BAC-2NV`. Verify that the Termly app shows
the **same fingerprint** above — that is the AES-256-GCM / DH-2048 proof that
nobody is between your phone and this machine.

## Install state

- Project: `@termly-dev/cli@1.9.5` as a **devDependency** (run with `npx termly`).
- Machine: `npm install -g @termly-dev/cli` → `termly` on PATH
  (`C:\Users\T2Hol\AppData\Roaming\npm\termly.ps1`), version 1.9.5.
- Both point at the production relay `wss://api.termly.dev`. No account, no
  subscription — the vendor states it is free and zero-knowledge.

## How to use it

```bash
cd "C:\Users\T2Hol\Desktop\Northstar OS Retail Arbitrage Agent"
termly start --ai opencode        # prints a QR + a 6-char code, waits 5 min
```

Scan the QR (or type the code) in the Termly app. One device per session.

```bash
termly status          # sessions + connection state + fingerprint
termly list            # compact list
termly stop <id>       # stop one
termly stop --all
termly cleanup         # drop dead registry entries
termly config          # environment / server
```

**Phone *and* tablet at the same time:** one mobile device per session, so run a
second `termly start` in a *different* directory (or a different project) and
pair the tablet to that one.

## Caveats that matter

1. **Two agents on one repo.** The termly session and this chat are two separate
   OpenCode instances pointed at the same directory. Concurrent edits will
   collide. Pick one active agent at a time, or point the phone session at a
   different folder.
2. **The session dies with PID 4196.** It was launched from an agent shell. For
   durable use, run `termly start --ai opencode` in your own terminal window.
3. **This machine holds live credentials.** `Northstar OS Retail Arbitrage
   Agent\.env` and `Northstar_backend\.env` contain real provider keys. The
   mirrored terminal is a real shell — anything typed from the phone can read or
   write them. The relay is zero-knowledge, but the *session* is live on this box.
4. **Stale registry entries** `e612a76b` and `cffd15cc` remain in
   `~/.termly/sessions.json` marked stopped (the first was a pre-existing session
   whose pairing window had expired; the second was superseded). `termly cleanup`
   reports them as clean because the processes are gone.
5. **Stale docs.** The npm package README still says "Mobile app (iOS/Android) —
   coming soon". The live site lists App Store and Google Play builds; the app is
   real and the pairing worked. README text in the package is out of date.

## Evidence

| Check | Result |
|---|---|
| `termly tools list` | OpenCode v2.0.32 ✓ installed (18 others detected as absent) |
| `termly status` | session `a2a950cc` Running, Mobile 🟢 Connected |
| `termly list` | `a2a950cc  OpenCode  🟢 (Mobile connected)` + fingerprint |
| Process tree | 4196 → conhost → `cmd.exe /c opencode` |
| `termly --version` (global) | 1.9.5 |
| `Get-Command termly` | on PATH |
