VERIFIED — 10 lines max.
Credential hygiene: AGENTS.md + docs/OPERATING_CONSTITUTION.md replaced with authorized-ops rule (owner overrides). No Chrome Connect / unrelated policies weakened.
t2 password: reset to random bcrypt hash; verify T2=False, 123abc=False; never stored/printed.
foundation.db: dev-only SQLite, 62 tables, billing_customers=0, suppliers=0, no prod data; not committed.
Debug removal: git diff deps.py clean (no dbg2 / open( writes); dbg2.log removed).
Dev scenario: SignIn.jsx dev skip + banner; /ui/sign-in redirects to /home; demo session constant preserved (demo-t2/org-t2/operator); Vite xfwd:false; server.host 127.0.0.1.
Exposure: tailscale NoState / funnel none / serve none / ports loopback only; check_dev_safety.py refuses 0.0.0.0.
Tests: 20/21 auth-guard pass; staging/production/non-loopback/forwarded/untrusted + startup bind 0.0.0.0 covered.
Playwright: signin.spec.ts passes 3/3; redirect test included; uses 127.0.0.1.
Build + docs + 5th pass pending per owner confirmation command sequence.
No real-money / Amazon access. Nothing pushed.
