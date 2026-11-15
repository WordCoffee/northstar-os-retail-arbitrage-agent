# Final green state — 2026-11-15

Owner-authorized close-out. Paired with `security_history_purge_20261115.md`.

## Live stack

| component | state |
|---|---|
| backend `127.0.0.1:8000` | `{"status":"ok","service":"northstar-backend"}` |
| UI `127.0.0.1:8101` | HTTP 200 |
| ComfyUI `127.0.0.1:8188` | **0.43.0**, listening |
| FLUX gateway `127.0.0.1:8190` | `status ok`, model **flux-3-image-klein**, all three weights present, 16 steps |

**Media lane: ARMED.** `NORTHSTAR_NO_MEDIA=0`; ComfyUI and the gateway are running. A real render
through `/api/design-studio/generate` was attempted and **refused by the lane's own budget guard**:

```
502 {"detail":{"code":"generation_failed",
     "message":"system_ram_insufficient: free 3858 MB, need 4096 MB (after stop-list freed 0 MB)"}}
```

Free RAM on this box is 3.4–3.9 GB with Chrome, Teams and the agent harness resident, against a
hard 4,096 MB render floor. The guard was **not** bypassed. Closing applications to free ~300–700 MB
(or adding RAM) is the one action that turns the armed lane into a rendered asset.

## Vision pause and parity

`state/vision/PAUSE` was **removed** on the owner's word. The parity suite was executed twice:

`python -m tools.vision.parity --run --twice --backends uia,chromeconnect`
→ both runs **not_run**, exit 1, with the exact reasons:

| backend | refusal |
|---|---|
| `uia` | **the desktop is locked** (foreground `LockApp.exe`); UIA cannot drive a browser behind the lock screen |
| `chromeconnect` | no Chrome Connect runner CLI configured (`CHROMECONNECT_CLI`) |

Report: `reports/ty/d8_parity_run1.json` and `d8_parity_run2.json` (the suite's own outputs; the
`--out` flag did not create a third file). The pause is lifted, but the desktop is locked; unlock
and sign in (never a password from Ty) and run the same command to exercise the vision loop.

## Security

- 18 historical findings → **0** on the rewritten mirror **and 0 on the working repo** (1,824
  commits, 553 MB).
- Remote rewritten: `main` **`98875d7f`**, `staging` **`d9e778c1`**; all branches/tags pushed.
- 5 files purged from history, one synthetic token replaced, 406 MB audio removed for GitHub's
  limit. Backups: `northstar-pre-purge-20261114-234441.bundle` (SHA256 `00B28480…BB7F`) and the
  four dirty worktrees archived before removal.

## Verification results

| check | result |
|---|---|
| `python Northstar_backend/production_assert.py --json` | **12 pass / 0 fail / 0 skip / 10 advisory**, exit 0 |
| `pytest test_service_registry test_tool_offering test_ty_toolkit test_chat_tools_handlers test_ad_copy_scorer` | **69 passed** |
| `repair_citations --check` / `build --check` | exit **0** / exit **0** |
| Playwright: research, listings, golden-goose, PPC primary action (desktop + iPhone 12 WebKit) | **8 passed, 2 skipped (43.3 s)** — the 2 skips are the listings spec's phone duplicate by design |
| gitleaks (mirror + working repo) | **0 findings** each |
| parity | refused by name (desktop locked; no CDP runner) |

## Owner decisions recorded

`ty/product_decisions.json`: Listings G2 accepted as an **honest zero** (watchtower scope); PPC
target ad type **Sponsored Products** (owner-confirmed in `ad_copy.py` + briefs; 9 tests pass);
reference media defaults (**CC0/BY/BY-SA**, **800 px** short side, category term).

## What is still not green, stated plainly

1. **A rendered asset** — blocked only by the 4,096 MB RAM floor on a locked, loaded desktop.
2. **V3 / UIA parity** — blocked by the lock screen; the pause itself is gone.
3. **Chrome Connect parity** — needs a configured runner (`CHROMECONNECT_CLI`) and CDP :9222, or
   the documented UIA route.
4. **GitHub's unreachable objects** — the public refs are clean; forcing GitHub GC needs a support
   request naming the repository.
5. **SEC-2** — the offsite, encrypted copy of the backup bundle still needs the owner's passphrase
   and destination.
6. Every commit hash in reports written before the purge is **stale**; tag names are stable.
