# UX rebuild — decisions log

One line per decision, oldest first. Format: `date · unit · decision · why`.

2026-11-02 · U0 · Baseline recorded from this session's own runs (backend 5763/30 at 10:59, e2e 41/2/1 at 11:20) rather than re-running both at U0 · the numbers are minutes old and the only commits since are unrelated docs; U14 re-runs and compares by name.
2026-11-02 · U0 · `ns-ux-baseline` tagged at `a2d12f5e` before any unit work · rollback point required by the order.
2026-11-02 · U0 · Dev servers NOT started; `dev-start.ps1` was refused by the safety gate (`tailscale serve` proxies 127.0.0.1:8000 on the tailnet) · the gate exists to keep the dev login bypass off any shared network; disabling the owner's Tailscale config is an external-account change, so it is queued to `needs_you.md` instead of bypassed.
2026-11-02 · U0 · Units that require a browser will be built as code + unit tests and marked `verification_pending` until the tunnel is closed · shipping unverified UI as "done" would be a false claim.
