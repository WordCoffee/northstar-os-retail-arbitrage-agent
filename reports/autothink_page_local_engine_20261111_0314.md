# /ui/autothink — inspection and local-engine fix (2026-11-11 03:14)

Entry point: the operator pasted `127.0.0.1:8101/ui/autothink`. Server answered
**200**, the SPA shell loaded, and the page's two data calls worked — but the
page rendered **"Installed Models: 0 — none detected"** next to a hardcoded
green `live · local engine` badge while Ollama was up with **14 tags**.

## What was actually wrong (root cause, not a symptom)

`OLLAMA_HOST` is Ollama's **bind** address on this box: `0.0.0.0:11434`. It is
not a URL.

```
main._ollama_base_url() -> '0.0.0.0:11434'
httpx.get('0.0.0.0:11434/api/tags') -> UnsupportedProtocol:
  Request URL is missing an 'http://' or 'https://' protocol
```

The `except` in `/api/v1/models` swallowed that and returned `installed: []`,
so the catalogue claimed the engine had no models. `text_local_status` was
dropped entirely as a consequence (it only appears when models resolve).

Same raw-env read existed in two more modules, both wrapped in `try/except`, so
they failed silently into their fallbacks:

* `Northstar_backend/listing_forge.py` `_call_llm()`
* `Northstar_backend/social_pulse.py` caption generation

`local_vision.py`, `local_screen.py` and `tools/gpu_budget.py` had each already
grown their own copy of the same normaliser after hitting this trap — the
backend route was simply never converted.

## Change (commit a33a6ee5)

* **new** `Northstar_backend/local_engine_url.py` — one shared
  `normalise_host()` / `ollama_base_url()`: bare `host:port` gains a scheme,
  `0.0.0.0` and `::` (bind addresses) become loopback, `localhost` is left
  alone, non-default ports kept, env precedence `OLLAMA_BASE_URL` →
  `TY_OLLAMA_URL` → `OLLAMA_HOST`.
* `main.py`, `listing_forge.py`, `social_pulse.py` now call it.
* `northstar-os-ui/src/pages/Autothink.jsx` — the badge and the Engine metric
  derive from the probe (`checking` / `up` / `no-models` / `down`) instead of
  hardcoding `live · local engine`, and the T2 metric no longer falls back to a
  tag that is not the configured default. Matches the existing conditional
  badge pattern in `Hub.jsx` / `Auctioneer.jsx`.

## Evidence

| Check | Result |
|---|---|
| live `/api/v1/models` before | `installed: []`, no `text_local_status` |
| live `/api/v1/models` after (backend restarted, `-NoTunnel -NoAutothink -NoComfy`) | `installed: 14`, `text_local_status {"T1":"ok","T2":"ok","T3":"ok"}`, T2 `bojo` |
| Vite proxy `:8101/api/v1/models` | 14 installed, T2 `bojo` |
| `:8101/api/autothink/history` | 200, total 2 |
| `:8101/ui/autothink` | 200 |
| `pytest Northstar_backend/test_local_engine_url.py` | 15 passed |
| `pytest test_local_vision + test_local_screen + test_local_engine_url` | 87 passed |
| `pytest test_listing_render + test_seo_listing + test_social_frames + test_social_validate` | 49 passed |
| `npm run test:ui` | 221 pass / 0 fail, exit 0 |
| `npm run test:contrast` | 11 pairs pass WCAG AA, exit 0 |
| `npm run verify:galactic` | all checks pass |
| `npm run build` | 0 errors, 1.63 s |
| pre-commit gitleaks | 6.38 KB scanned, no leaks |

Backend was restarted through the product's own `scripts/launch_alpha.ps1`
(8000 freed, relaunched, health OK, assets OK). AutothinK on :8100 was already
down before the restart and stays down (`-NoAutothink`), i.e. unchanged.

Note: the first restart was run with `-Gate` and that **locked
`/api/v1/models`** behind the private-alpha allowlist (previously open on this
instance). Re-run without `-Gate` restored the prior behaviour — the operator's
instance is back as it was.

## Found, not changed (needs a decision)

1. **`.badge` / `.badge-*` have no CSS at all.** Twelve pages use
   `<span className={`badge badge-${tone}`}>` (`PageHead`, model chips) and no
   stylesheet in `northstar-os-ui/src` defines the class — a repo-wide grep for
   `\.badge` in `*.css` returns nothing. They render as plain unstyled text.
   `tokens.css` has a styled `.pill-*` family, so the likely intent is to map
   badges onto pills, but that is a visual decision across 12 pages and was not
   taken unilaterally.
2. `OfferChisel.jsx` and `TownCrier.jsx` still carry a hardcoded
   `live · local engine` badge — same defect, same fix, not applied here.
3. `00_STATE.json` was deliberately not edited: a parallel session was
   committing to `staging` during this work (`tools/seller_tester/scorers.py`,
   `reports/ty/*` were dirty, commit 11973d05 landed mid-session), and the
   parallel-lane rule says one writer per file.

## Not touched

Amazon, spending, credentials, Chrome, the model fleet. Local engine only.
