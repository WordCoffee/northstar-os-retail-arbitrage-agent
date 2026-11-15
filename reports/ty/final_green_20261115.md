# Final green state — 2026-11-15

Owner-authorized close-out. Paired with `security_history_purge_20261115.md`.

## Live stack

| component | state |
|---|---|
| backend `127.0.0.1:8000` | `{"status":"ok","service":"northstar-backend"}` |
| UI `127.0.0.1:8101` | HTTP 200 |
| ComfyUI `127.0.0.1:8188` | **0.43.0**, listening |
| FLUX gateway `127.0.0.1:8190` | `status ok`, model **flux-3-image-klein**, all three weights present, 16 steps |

**Media lane: ARMED, AND IT RENDERS.** `NORTHSTAR_NO_MEDIA=0`, ComfyUI **0.43.0** and the gateway on
:8190 (`flux-3-image-klein`, all weights present) are running detached. The free-RAM floor was
lifted by the owner, and a real render through `/api/design-studio/generate` succeeded:

```
RENDER OK 48.0 s  asset da50d861-a532-43ba-9c1d-66be54b85598
1024x1024 image/png  Northstar_backend/data/studio_generated/ab8ad729….png
```

Read back through `GET /api/design-studio/assets/{id}` and opened with Pillow (1024×1024 RGB).
Evidence: `reports/ty/media_render_20261115.json`.

## Vision pause and parity

`state/vision/PAUSE` was **removed** on the owner's word. The owner unlocked the desktop and Chrome
Profile 6 was opened for the UIA route. The parity suite was executed:

| command | result |
|---|---|
| `parity --run --twice` (default vision+chromeconnect) | `not_run` twice: no CDP at :9222; no `CHROMECONNECT_CLI` runner |
| `parity --run --backend uia` | **ran: 4 / 10 tasks passed**, recovery **failed** (`first_attempt_ok` and `second_attempt_ok` both false) |

The desktop is no longer the blocker; the UIA challenger itself is **4/10**, and the Chrome Connect
incumbent needed for a parity comparison is not configured. The V3 gate is therefore **not met**.
Evidence: `reports/ty/parity_uia_20261115.json` (and `d8_parity_run1/2.json`).

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
| Playwright: research, listings, golden-goose, PPC primary action (desktop + iPhone 12 WebKit) | **8 passed, 2 skipped (37.7 s)** — the 2 skips are the listings spec's phone duplicate by design |
| gitleaks (mirror + working repo) | **0 findings** each |
| UIA parity (`--backend uia`) | **ran: 4 / 10 passed**, recovery failed; Chrome Connect incumbent not configured |

## Owner decisions recorded

`ty/product_decisions.json`: Listings G2 accepted as an **honest zero** (watchtower scope); PPC
target ad type **Sponsored Products** (owner-confirmed in `ad_copy.py` + briefs; 9 tests pass);
reference media defaults (**CC0/BY/BY-SA**, **800 px** short side, category term).

## What is still not green, stated plainly

1. **V3 / UIA parity** — the suite now runs (desktop unlocked, Chrome Profile 6 open) but passes
   **4 / 10** with recovery failed. This is a real tool-quality gap, not a lock/refusal.
2. **Chrome Connect parity** — the incumbent comparison needs a configured runner
   (`CHROMECONNECT_CLI`) or CDP :9222; neither is present, so a challenger-vs-incumbent verdict
   cannot be produced.
3. **GitHub's unreachable objects** — the public refs are clean; forcing GitHub GC needs a support
   request naming the repository.
4. **SEC-2** — the offsite, encrypted copy of the backup bundle still needs the owner's passphrase
   and destination.
5. Every commit hash in reports written before the purge is **stale**; tag names are stable.

**Rendered asset: done** — `da50d861…`, 1024×1024 PNG, 48 s, persisted and read back.
