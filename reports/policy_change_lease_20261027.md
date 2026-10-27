# Policy Change: Profile Lease Replaces Signed-Out Requirement

**Date:** 2026-10-27
**Authorized by:** Owner (standing authorization)
**Change:** Chrome Connect's isolation requirement changes from "signed-out profile" to "leased profile".

## Rationale
- Profile 7 "Northstar Research" has session cookies (Google LSID, Alibaba auth cookies)
  despite being signed out of Google account. Cookie store is not clean.
- The signed-out requirement blocks all Chrome Connect runs because no profile
  is truly clean (all 8 Chrome profiles have some cookies).
- The profile lease allows the operator to pick any profile via the native picker.
  The lease stays alive during unattended runs. Any Chrome Connect action keeps
  the lease alive (resets idle timer). Default idle timeout: 30 minutes.

## What changed
- `chrome_signed_out` is no longer a REQUIRED check for isolated runs.
- Instead, `profile_leased` (lease state ACTIVE and not expired) is REQUIRED.
- The operator picks the profile once via the picker. Chrome Connect never
  chooses a profile for the operator.
- The lease is stored locally (data/chromeconnect_lease.json), never committed.
- Cookie metadata scan still runs (if authorized) to report session cookies,
  but no longer blocks execution.

## What did NOT change
- Operator-owned allowlist (unchanged)
- Hardcoded Amazon blocklist (unchanged)
- Lessons are PROPOSED-only (unchanged)
- No credentials entered, no CAPTCHA solved (unchanged)
- Single controller rule (unchanged)
- No stealth/anti-bot (unchanged)

## Implementation
- `Northstar_backend/chromeconnect_profile_lease.py` — lease manager
- Lease state: UNLEASED → ACTIVE → EXPIRED → REVOKED
- Configurable idle timeout (default 30 min)
- Any Chrome Connect action calls `touch()` to keep lease alive
