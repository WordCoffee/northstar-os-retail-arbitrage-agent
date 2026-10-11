# Archive Scrub — Option A Executed (owner-approved)

- **Date:** 2026-10-11 · **Owner:** T2 Holdings LLC
- **Security scan state (standing line):** **0 new finding(s), 1 known-active (baseline: `rate_limiter.py` review), 231 allowlisted** — was 8 known-active before this scrub. Scanner exit code **0**; tests **146/146**.
- **Owner context acknowledged:** rotation is deferred ("skipping rotation until everything is complete"). The scrub was executed anyway on the owner's explicit Option A instruction.

## 1. What was executed (fingerprint-keyed, byte-preserving, fail-closed)

| File | Action | Count |
|---|---|---|
| `FirstNorthstarautomationchat.md` | `SCAVIO_API_KEY` values → `[REDACTED]` (fp `ca2d8a22d6f0d252`) | 2 |
| | `BRIGHTDATA_API_KEY` values → `[REDACTED]` (fp `f7f62b13a37f5afd`) | 2 |
| | README-style PLACEHOLDER left untouched (see §3) | 1 left |
| `autothink-ui-chat-export.md` | `ghp_…` token → `[REDACTED]` | 1 |

Diffs are minimal: `git diff --numstat` = **4/4** and **1/1** lines (no line-ending or wholesale changes).

## 2. Process evidence (the fail-closed design earned its keep)

1. First scrub attempt **aborted with NO writes**: 5 `KEY=value` matches found vs the 4 inventoried in the review — the review's line-anchored inventory had missed one mid-line occurrence.
2. A masked probe located it (inside a JSON `"content"` dump at line 2528).
3. The extra occurrence turned out to be a **README-style placeholder** (`…your…key…`, 28 chars, no digits) — **not credential material**. The scanner's placeholder-skip had correctly never flagged it (no scanner gap).
4. v2 scrub: fingerprint-keyed (redacts ONLY the two reviewed real values), dry-run verified, then executed. Any unexpected value aborts with no writes.

## 3. Honest notes

- **The redacted key values remain VALID until rotation** (deferred by the owner). This scrub removes them from the working tree of the repo — it does not rotate anything and it does not touch **git history** (history decision remains open, per the F2 precedent).
- The placeholder occurrence (`fp 87055694a7eef7e0`) stays by design — it is not a credential.
- Post-scrub, the 4 remediated baseline fingerprints produced the designed `STALE-BASELINE` prompts; the baseline was then pruned **5 entries → 1** and the frozen guard set pruned to match. The growth guard still enforces: baseline ⊆ frozen set, shrink-only, no duplicates, well-formed entries.

## 4. Verification / evidence

- `git diff --numstat` → `4 4 FirstNorthstarautomationchat.md` · `1 1 autothink-ui-chat-export.md`
- Scanner before → after: `8 known-active` → `1 known-active`; stale prompts consumed; final summary: `0 new, 1 known-active (baseline), 231 allowlisted`; **exit 0** (measured directly, no pipeline artifacts).
- `python -m pytest tests/security -q` → **146 passed** (guard green with the pruned sets).

## 5. Follow-ups

- **Rotation** (owner, deferred): when it happens, no scanner action is needed — the values are already gone from the working tree; only the history question remains.
- **History rewrite decision** (owner, open) — unchanged by this scrub.
- **Remaining known-active:** the `rate_limiter.py` review item — confirm whether the legacy fallback is a real static value; if so it migrates to an env read (close-out = baseline → 0).
