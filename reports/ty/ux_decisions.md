# UX rebuild â€” decisions log

One line per decision, oldest first. Format: `date Â· unit Â· decision Â· why`.

2026-11-02 Â· U0 Â· Baseline recorded from this session's own runs (backend 5763/30 at 10:59, e2e 41/2/1 at 11:20) rather than re-running both at U0 Â· the numbers are minutes old and the only commits since are unrelated docs; U14 re-runs and compares by name.
2026-11-02 Â· U0 Â· `ns-ux-baseline` tagged at `a2d12f5e` before any unit work Â· rollback point required by the order.
2026-11-02 Â· U0 Â· Dev servers NOT started; `dev-start.ps1` was refused by the safety gate (`tailscale serve` proxies 127.0.0.1:8000 on the tailnet) Â· the gate exists to keep the dev login bypass off any shared network; disabling the owner's Tailscale config is an external-account change, so it is queued to `needs_you.md` instead of bypassed.
2026-11-02 Â· U0 Â· Units that require a browser will be built as code + unit tests and marked `verification_pending` until the tunnel is closed Â· shipping unverified UI as "done" would be a false claim.
2026-11-02 · U1 · Internal ids stay `simple`/`advanced`; only display names change · routes, CSS scope (`html[data-shell-mode="simple"]`), stored preference and `SIMPLE_KEEP_ADVANCED` all key off the id; renaming state to rename a label breaks sessions.
2026-11-02 · U1 · `normaliseMode` accepts legacy spellings (northstar, standard, default, advanced view, autothink) · old stored values must keep working, and an unknown value degrades to Northstar, never to advanced.
2026-11-02 · U1 · AGENTS.md edited by appending 647 chars, never rewritten · policy files are append-only per the order.
