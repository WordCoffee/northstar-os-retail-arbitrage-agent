# Provider key verification — Bright Data, ChocoData, Rainforest

Date: 2026-11-02
Batch: `PROVIDER-KEYS-VERIFY`
Scope: confirm the three rotated provider keys authenticate, and make sure the
project actually reads them from the file that was updated (repo-root `.env`).

Every check below is **zero-credit and Amazon-free**: no Amazon host or Amazon
API was contacted and no provider credit was spent. Bright Data was checked
against its customer zone-metadata API, ChocoData against `/api/v1/usage`, and
Rainforest against `/account`. No secret value was read into any output, log or
file.

---

## 1. Where the keys live

| Key | repo-root `.env` (updated 2026-11-02) | `Northstar_backend/.env` (2026-10-09) |
|---|---|---|
| `BRIGHTDATA_UNLOCKER_API_KEY` | present | present but **different (stale)** |
| `BRIGHTDATA_API_KEY` | present (same token as above) | present but **different (stale)** |
| `CHOCODATA_API_KEY` | present | present but **different (stale)** |
| `RAINFOREST_API_KEY` | present | **absent** |
| `BRIGHTDATA_UNLOCKER_ZONE` | `northstaros` | `northstaros` (identical) |

Measured before the fix: a standalone `import bright_data_client` /
`amazon_search` resolved the key digests from `Northstar_backend/.env`
(stale values), and `RainforestClient.from_env().configured` was `False`.
That is the "not visible" symptom: the file the operator updated was not the
file the provider modules were reading.

## 2. Live authentication results

| Provider | Key | HTTP | Verdict |
|---|---|---|---|
| Bright Data (Web Unlocker) | `BRIGHTDATA_UNLOCKER_API_KEY` | 200 | **key valid** |
| Bright Data (customer API) | `BRIGHTDATA_API_KEY` | 200 | **key valid** (same token) |
| ChocoData | `CHOCODATA_API_KEY` | 200 (`/usage`) | **key valid** |
| Rainforest | `RAINFOREST_API_KEY` | 200 (`/account`) | **key valid** |

Account state read back from the providers themselves:

- **Bright Data** — zones on the account: `retailarbitrage` (deleted),
  `northstaros` (**deleted**), `web_unlocker1` (**active**). The project's
  `BRIGHTDATA_UNLOCKER_ZONE` points at `northstaros`, which no longer exists,
  so every Web Unlocker call would fail on zone resolution. The token itself
  is fine (200 on `/zone/get_all_zones`). `/datasets/v3/*` returns 404 — the
  Datasets API is not provisioned on this account (unchanged; the datasets
  lane stays unavailable).
- **ChocoData** — plan `free`, `credits_remaining: 0`. The key authenticates,
  but every scrape returns `402 INSUFFICIENT_CREDITS` ("Out of credits"). Not
  usable until the workspace is topped up or replanned.
- **Rainforest** — plan `Free`, `credits_used: 0`, `credits_remaining: 100`,
  reset `2026-12-03`. Fully working.

## 3. What was changed

### 3.1 New: `Northstar_backend/env_bootstrap.py`

`load_project_env()` implements the already-recorded decision
(`dual_dotenv_divergence_backend_shadowing`, resolved 2026-09-13, option (c):
repo-root `.env` is authoritative, backend modules pin it by explicit path).

Load order, `override=False` throughout so a real process env always wins:

1. `<repo>/.env` — authoritative
2. `<repo>/Northstar_backend/.env` — only fills keys the root file omits

It never returns, prints or logs a value. `env_source_report()` reports which
file a variable came from, by comparison only.

### 3.2 Wired into the three providers' modules

| File | Before | After |
|---|---|---|
| `Northstar_backend/bright_data_client.py` | `load_dotenv()` | `load_project_env()` |
| `Northstar_backend/amazon_search.py` (2 sites) | `load_dotenv()` | `load_project_env()` |
| `Northstar_backend/offer_enrichment.py` | `load_dotenv()` | `load_project_env()` |
| `Northstar_backend/rainforest_client.py` | `load_dotenv()` | `load_project_env()` |

Scoped deliberately to the three providers in this request. The other ~20
backend modules that call a bare `load_dotenv()` are untouched (same latent
issue, no behaviour change made without need).

### 3.3 New: `scripts/verify_provider_keys.py`

Repeatable, secret-safe verification: presence + public key-format prefix +
HTTP status + provider account figures, with a `--json` mode. Exit 0 only when
every provider authenticates **and** has no blocker.

## 4. Verification after the change

```
bright_data_client.BRIGHTDATA_UNLOCKER_API_KEY -> 05beaa9860  (root)
amazon_search.CHOCODATA_API_KEY                -> 9a1dc26e9f  (root)
rainforest configured                          -> True
```

API process (`import main`): `env_source_report` reports **`root`** for
`BRIGHTDATA_UNLOCKER_API_KEY`, `CHOCODATA_API_KEY`, `RAINFOREST_API_KEY`,
`BRIGHTDATA_UNLOCKER_ZONE`, `SCANNER_SEARCH_SOURCE`; and
`RainforestClient.from_env().configured == True`.

Tests — provider surface green:

```
pytest test_bright_data_client.py test_universal_search.py test_offer_enrichment.py
       test_rainforest_client.py test_env_hygiene.py test_scavio_client.py
=> 147 passed
```

Full suite: `5762 passed, 31 failed, 117 skipped, 2 xfailed` (12:02).
The 31 failures are **pre-existing in this working tree**, not caused by this
change: the four edited modules plus `env_bootstrap.py` were stashed and the
failing tests re-run — they fail identically with the change removed. They sit
in autothink routes/auth, agent_kernel `local_model`, session-cookie contract,
shell modes and UI route contracts, all in files already modified before this
session.

## 5. Blockers left (operator-side)

1. **Bright Data zone** — `.env` line 39 `BRIGHTDATA_UNLOCKER_ZONE=northstaros`
   points at a deleted zone. Set it to the account's active zone
   `web_unlocker1` (one-line edit; the file is permission-protected against
   agent writes) or recreate a `northstaros` zone in the Bright Data console.
   No key change is needed.
2. **ChocoData credits** — workspace is at 0 credits. Any top-up is a spend and
   needs fresh approval; until then this provider is not usable.
3. **Bright Data Datasets API** — `/datasets/v3/*` 404s on this account. Not a
   key problem; the datasets lane simply is not provisioned.

## 6. Not done (deliberately)

- No live Web Unlocker / ChocoData / Rainforest data request was issued — every
  one of those spends credits, which is a standing gate. The end-to-end 1-credit
  proof is queued, not run.
- No `.env` value was written, copied or moved, and `.env` itself was not
  editable (permission denied) — only its non-secret zone line is recommended.
- Nothing was committed to `.env`; both env files remain untracked.
