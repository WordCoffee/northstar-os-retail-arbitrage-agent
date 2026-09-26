# OpenRouter Auth + Cost-Routing Audit — 2026-09-24T07:06Z

## 1. Root cause of the 401

**Classification: MALFORMED_KEY in `.env` (root) + dotenv parse breakage.**
The key itself is **valid** (see §3). The failure was caused by junk/malformed lines
in the root `.env` that corrupted naive parsing and could produce a garbage or
empty Bearer token:

- Root `C:\...\Northstar OS Retail Arbitrage Agent\.env` line 87:
  `OpenRouter API KEY" sk-or-v1-...` — a **stray duplicate of the real key**
  embedded in a non-`KEY=VALUE` statement (contains a `"` and no `=`), which
  python-dotenv could not parse (`python-dotenv could not parse statement
  starting at line 87`) and which would break any naive split-on-`=` loader.
- Root `.env` line 92: `relace API key: rlc-...` — same malformed shape
  (`python-dotenv could not parse statement starting at line 92`).
- A naive PowerShell `Select-String 'OPENROUTER'` first-match on line 86
  (`#OpenRouter NorthstarOS build API Key`, a comment) splits to one part → empty
  token → `Authorization: Bearer ` → **401 on every call**, exactly matching the
  reported symptom (including `/api/v1/auth/key`).

The canonical line `OPENROUTER_API_KEY=sk-or-v1-...` (line 95) was always present
and well-formed; it was simply being masked by the malformed neighbours in any
fragile parse, and python-dotenv logged warnings while parsing past them.

Not the cause: `Northstar_backend/.env` was already clean (single canonical line,
same key). Variable naming is **consistent** everywhere — every reference uses
`OPENROUTER_API_KEY` (no `OPENROUTER_KEY` / `OPENROUTER_APIKEY` mismatches).

## 2. Exact fix applied

Root `.env`:
- Line 87 (`OpenRouter API KEY" sk-or-v1-...`) → replaced with a comment:
  `# OpenRouter API KEY (duplicate, malformed line removed; canonical value on OPENROUTER_API_KEY line below)`
- Line 92 (`relace API key: rlc-...`) → replaced with a comment:
  `# relace API key (malformed line neutralized to a comment; value not removed)`

Both `.env` files now contain exactly **one** `OPENROUTER_API_KEY=` line, zero
malformed non-comment/non-assignment lines, and python-dotenv parses cleanly
(no warnings). No secret values were printed, logged, or committed. Backup of the
pre-edit root `.env` is at `C:\Users\T2Hol\AppData\Local\Temp\opencode\dotenv_backup_20260924.txt`.

No code, model names, routing logic, budget caps, or approval gates were changed.

## 3. Validation: `/api/v1/auth/key` now returns 200

Run using the repo's own secret-loading pattern (python-dotenv from repo root,
then the exact PowerShell manual-parse path):

- `python` + `requests` + `load_dotenv()` → **HTTP 200**
- PowerShell: parse canonical `OPENROUTER_API_KEY=` line → `Authorization: Bearer {key}`
  → **HTTP 200**

Response body (scrubbed, no secret material): valid key, `is_free_tier=false`,
`limit=50`, `limit_remaining≈30.04`, `expires_at=2027-03-18T21:23:00.005Z`,
`usage_monthly≈19.96`, daily ≈2.29. Key is healthy and funded → no owner action
required.

## 4. OpenRouter call-site inventory + cost routing (Phase 6)

Only **one** real OpenRouter HTTP call exists in the codebase:

| Call site | Current provider config | Status |
|---|---|---|
| `autothink/backend/llm_adapter.py:245` (`requests.post(OPENROUTER_URL, ...)`) | **No `provider` object, no `only:[...]`, no `allow_fallbacks`.** Model slugs: `deepseek/deepseek-v4-flash-0731:free` (T1), `deepseek/deepseek-v4-flash-0731` (T2), `deepseek/deepseek-v4.1-flash` (T3) | **Already cost-aware by default** — no pin sent, OpenRouter's default provider routing applies. No lock to correct. |
| `Northstar_backend/model_router.py:76` `CLOUD_PROVIDER_PINS` (`T2: relace/fp4`, `T3: deepinfra/fp8`) | Pin metadata returned in `Resolution.pin` (`model_router.py:181`) | **Not transmitted** — `llm_adapter.py` never reads the pin into the request. Config metadata only; no actual single-provider lock in flight. Flagged for manual review (see §5). |
| `shared/model-suite.json` `cloud_pin` entries | Same pins declared in config overlay | Same — metadata only. |
| Legacy `OPENAI_API_KEY` fallback lane (`llm_adapter.py:83,219-229`) | Explicitly **not supported** (returns `provider_not_supported`) | Left unchanged — intentional. |

**Recommendations (require operator approval before changing behavior):**
1. **Optional explicit sort** on the live call site — add to the request body:
   `"provider": {"sort": "price", "allow_fallbacks": true}` at
   `llm_adapter.py:236` body — makes cost-first intent explicit instead of
   relying on OpenRouter's default. No behavior change expected; OpenRouter
   already sorts by price by default.
2. **`max_price` ceiling** for high-frequency automated calls (T1/T2 lanes):
   current listed OpenRouter prices — `deepseek/deepseek-v4-flash-0731` in
   $0.00000003/tok, out $0.00000032/tok; `deepseek/deepseek-v4.1-flash` in
   $0.00000014/tok, out $0.00000042/tok. A safe ceiling of
   `{"prompt": 0.0000005, "completion": 0.000001}` per token would cap a 2k-token
   exchange well under $0.01. **Not applied** — awaiting approval.
3. **`CLOUD_PROVIDER_PINS`** — either wire them into the request (only when a
   documented reason exists) or delete the dead config. Currently inert.

## 5. Deliberately left unchanged

- Legacy `OPENAI_API_KEY` lane — returns `provider_not_supported` by design; not
  an OpenRouter pin.
- `CLOUD_PROVIDER_PINS` / `cloud_pin` — not transmitted anywhere; flagged above
  rather than silently wiring or deleting them.
- All safety controls intact: `CLOUD_MODEL_LIVE=1` gate (`cloud_live_armed`),
  `provider`/`tier` consent policy, budget/credit weights, approval gates — none
  modified.

## 6. Secret hygiene confirmation

No secret values were printed, logged, echoed, or committed. Output used only:
length, prefix (`sk-or-v1-`), SHA-256 of the loaded value, and the scrubbed
`/auth/key` response (label removed). No `.env` value appears in any report or
git diff. `.env` is confirmed gitignored (`git check-ignore` → `.env`,
`Northstar_backend/.env`).

## 7. Scope confirmation

No unrelated code, business logic, or safety controls modified. Only the root
`.env` was edited (2 malformed lines → comments). No live paid generation call
was made — stopped after read-only key validation succeeded.

## Evidence

- `python-dotenv` parse: 0 malformed statements after fix (was 2).
- `OPENROUTER_API_KEY` line count in both `.env` files: 1.
- `/api/v1/auth/key` → 200 (python + PowerShell paths), key valid, funded.
- `autothink/tests/test_llm_adapter.py` → 11/11 passed; `test_model_router.py` → 22 passed.

---

## Addendum — 2026-09-24T07:06Z (operator approvals)

1. **Approved routing change applied**: `autothink/backend/llm_adapter.py:236-244` body now
   sends `"provider": {"sort": "price", "allow_fallbacks": True}` — explicit cost-first
   routing on the live OpenRouter call. Tests re-run GREEN (11/11 autothink, 22/22
   model_router). No `max_price` ceiling added (per operator: deferred until per-model
   thresholds are scoped in the canonical economics/provider registry work).
2. **`CLOUD_PROVIDER_PINS` clarification**: **stub/display-only, not dead in the strict
   sense.** Trace: read into `Resolution.pin` (`model_router.py:150,181`), surfaced in the
   catalog (`model_router.py:338` → `/api/autothink/models`) and the AutothinK run response
   (`server.py:149`), asserted in tests (`test_model_router.py:56,58`). The single live call
   site (`llm_adapter.py:245`) builds its own request body and **never reads the pin** — it
   is inert metadata pending the canonical provider/economics registry. Logged as
   **Known Gap #9** in `docs/northstar-phase1b/15-known-gaps.md`.
3. **Git hygiene confirmed**: `git log -- .env` → no commits; `git diff --cached` → empty
   (nothing staged); `git check-ignore -v .env` → ignored via `.gitignore:2`. The `.env`
   edit was never committed. No commit/push was made in this task.