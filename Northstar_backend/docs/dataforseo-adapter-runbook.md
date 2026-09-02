# DataForSEO Amazon Merchant Standard Adapter — Operator Runbook

**Scope.** A single Bright Data-shortlisted, mapping-approved ASIN can later be
cross-checked against DataForSEO's **Merchant Standard** queue. This adapter is
**OFFLINE BY DEFAULT** and makes **zero network calls** unless *every* gate
below is satisfied AND the strict runtime transport is explicitly enabled for
exactly one approved invocation.

**Modules.** `proof_batch_contracts.py` (authoritative predicates, state
vocabulary, URL builders) and `dataforseo_adapter.py` (offline
routing/transport/ledger/normalizer). The guarded run orchestration lives in
`validation_run.py` (`python validation_run.py <command>`).

**Authoritative contract.** `random-dataforseo-amazon-stuff-api.txt`
(ingested read-only). The endpoint paths below are the exact strings produced
by `merchant_task_post_url`/`merchant_task_get_url`/`labs_live_url` in
`proof_batch_contracts.py`, derived from that contract. No other endpoints are
used and none should be invented.

---

## 1. Merchant Standard families (authoritative)

DataForSEO Merchant Standard exposes three task families under
`/v3/merchant/amazon/<family>/`. The adapter validates the family with
`_require_merchant_family` and rejects anything else at the allowlist
(`dataforseo_adapter.classify_endpoint` / `ALLOWED_MERCHANT_TASK_TYPES`):

| Family | Create endpoint | Retrieve endpoint |
|--------|-----------------|-------------------|
| `products` | `POST /v3/merchant/amazon/products/task_post` | `GET /v3/merchant/amazon/products/task_get/{task_id}` |
| `asin`     | `POST /v3/merchant/amazon/asin/task_post`     | `GET /v3/merchant/amazon/asin/task_get/{task_id}`     |
| `sellers`  | `POST /v3/merchant/amazon/sellers/task_post`  | `GET /v3/merchant/amazon/sellers/task_get/{task_id}`  |

Family-specific bodies:
- **`products`** — keyword-driven; the body carries a `keyword` sourced
  offline from the candidate benchmark title. No `asin`/`query`/`search_term`
  is ever sent in the request body (see Unknown policy). The first result
  item is inspected for the target ASIN.
- **`asin`** — ASIN-driven (`asin` in body).
- **`sellers`** — ASIN-driven; returns a per-seller offer roster.
- A task created on the wrong family (e.g. `product_info`) is a **path
  mismatch** and is rejected (see §4).

**DataForSEO Labs Live** (read-only inspection, separate routing) uses
`labs_live_url(family)`:
`POST /v3/dataforseo_labs/amazon/<family>/live` — **immediate, inline
result only** (no `task_id`/`task_get`). Allowed families:
`product_rank_overview`, `ranked_keywords`, `bulk_search_volume`,
`related_keywords`. Labs auto-submit is gated off by default
(`DATAFORSEO_LABS_AUTO_SUBMIT`); inspection only until separately approved.

> **Deprecated route (historical only).** `/v3/merchant/amazon/product_info`
> and `/seller_info` are **not** valid Standard routes. Envelopes that hit
> them are path mismatches (see §4) and are never retried on that route.

---

## 2. Acceptance success (authoritative predicate: `evaluate_dataforseo_task_post`)

A **Merchant Standard task_post create** is successful only when **all** hold:

- top-level `status_code == 20000` (one envelope-level OK),
- top-level `tasks_error` is `0` / absent,
- `tasks` is a non-empty list and `tasks[0]` is a dict,
- **task-level** `status_code == 20100`, task-level `status_message` is one of
  `"Task Created."` / `"task created"` (case-insensitive, trimmed),
- task-level `cost > 0` (provider-reported; `0`/`null` → rejected),
- task-level `id` is a non-empty, slash-free UUID-like string,
- `task.path` exactly equals `["v3","merchant","amazon",<family>,"task_post"]`
  (checked via `expected_task_post_path(family)`).

Any deviation → a `provider_rejected_*` classification (never `submitted`).
The accepted ledger state is `DATAFORSEO_ACCEPTED_STATE` = `"submitted"`
(**not** renamed to `queued_or_submitted`; this name is preserved to keep the
repaired run consistent).

A **Merchant Standard task_get retrieval** is successful only when:
- top-level `status_code == 20000`,
- task-level `status_code == 20000` and `status_message` in `{"ok.","ok"}`,
- the retrieved `id` matches the expected task id and belongs to the
  expected family,
- `tasks[0].result` is parseable.

A **DataForSEO Labs live** call is successful only when the response carries
an immediate task-level `status_code == 20000` with a parseable inline result
(no `task_get` step; Labs has no async retrieval).

---

## 3. Cost, reservation, idempotency, and retry policy

- Each planned task reserves a **local** estimate of
  `DATAFORSEO_ESTIMATED_COST_CENTS` (= `5`) in the ledger
  (`ledger_add_planned` in `validation_run.py`).
- Reservations release only on rejection paths: `provider_rejected_*`,
  `mapping_incompatible`. They are **not** released for `submitted`/
  `queued_or_submitted`/`ready_to_retrieve`/`needs_manual_reconciliation`
  (incomplete spend). `Ledger.total_reserved()` reflects this exactly.
- On a successful create, `actual_cost_cents` is set from the
  provider-reported `task.cost` (not the local estimate).
- **Idempotency:** per `(provider, asin, validation_type)` key. A row that
  already has a `remote_task_id` is never re-posted (skipped in
  `cmd_execute_dataforseo`).
- **No automatic retry.** Provider rejections, `mapping_incompatible`,
  `schema_validation_failed`, `persistence_failure`, and
  `needs_manual_reconciliation` are never auto-retried. A `40402` path
  mismatch specifically routes to `provider_rejected_invalid_path` and that
  route is permanently off-limits for the run (see §4).
- **Endpoint-family isolation:** a `products` task_post body contains only a
  `keyword`; a `sellers` task requires an ASIN; an `asin` task requires an
  ASIN. Family identifiers are never cross-loaded between families.

---

## 4. Historical `product_info` rejection (preserved, never retried)

All 10 raw envelopes in
`data/validation-runs/data-validation-20asin-live-001/raw/dataforseo/*.json`
are structurally identical **submission responses**: HTTP 200,
`status_code=40402`, `status_message="Invalid Path."`, `cost=0`,
`result=null`, `data=null`, `tasks_error=1`, with a single `tasks[0].id`
recorded. Under the authoritative predicate these classify as
**`provider_rejected_invalid_path`**:

- the route was `/v3/merchant/amazon/product_info/task_post`, which is not a
  valid Merchant Standard family (`/product_info` is not `products`/`asin`/
  `sellers`);
- the task-level `40402` is a path/route error, so **no valid task was
  created**;
- provider-reported `cost` was `0` on every envelope (local estimate of
  `5` cents was reserved but released on rejection);
- ledger rows were repaired to `provider_rejected_invalid_path` (and
  `reserved_cost_cents` released accordingly — run reserved 100→50
  depending on planned rows);
- that route is **never** automatically retried.

These 10 raw envelope files are immutable evidence and must remain byte-for-
byte unchanged.

---

## 5. Mapping gates, Unknown policy, and raw evidence

- **Mapping gate (current blocker).** `seller_offer` rows are classified
  `mapping_incompatible` and are **never submitted** (see §6 pilot plan).
  `product` tasks require an offline-sourced `keyword` (no marketplace
  search; never fabricated); `asin`/`sellers` tasks require an ASIN.
- **Unknown policy (never fabricate).** Until a real retrieved provider
  record explicitly carries a signal, the following stay `Unknown`/`null`
  and are never synthesized: UPC/EAN/GTIN, monthly unit sales, FBA fee,
  referral fee, COGS, Buy Box owner, Buy Box price, seller count when not
  determinable from an explicit offer roster. The Scout renderer shows
  "Unavailable/Unknown" — never `0` and never an aggregate.
- **Raw-evidence persistence.** `store_raw` writes each provider envelope to
  `data/validation-runs/<run-id>/raw/dataforseo/<asin>-<family>.jsonl`
  (append-only). It never mutates the canonical 20-ASIN benchmark source or
  any existing producer artifact (scanner cache, Costco catalog, ASIN
  benchmarks).

---

## 6. Failure taxonomy

The provider/adapter result is one of:

| Result | Meaning |
|--------|---------|
| `matched` | observed values agree with the Bright Data record |
| `mismatch` | conflict (asin / title / brand / observed_price); both observed values preserved, `review_flags` raised |
| `incomplete` | provider returned no usable observed fields |
| `provider_error` / `needs_manual_reconciliation` | the provider call failed or post state is ambiguous |
| `provider_rejected_invalid_path` | task-level `40402` / wrong route |
| `provider_rejected_auth` | task-level `401` / auth |
| `provider_rejected_validation` | task-level `40400` / invalid params |
| `provider_rejected_budget` | task-level `402` / insufficient credits |
| `provider_rejected_unknown` | any other non-creating non-20000 state, or zero/negative cost |
| `mapping_incompatible` | family mapping not approved (e.g. `seller_offer`) |

`compare_with_bright_data` (in `dataforseo_adapter.py`) produces
`matched`/`mismatch`/`incomplete` from the normalized record only; it never
infers sales, fees, Buy Box ownership, Amazon restrictions, invoice quality,
authenticity, account eligibility, or purchase authorization. Per policy,
`purchase_authorized` is always `false`.

---

## 7. Offline workflow (always safe; zero network)

```powershell
python validation_run.py preflight   --run <run-id>
python validation_run.py report-plan --run <run-id>
python validation_run.py authorize-check --run <run-id> [--confirm <run-id>]
python validation_run.py report --run <run-id>
```

These commands are fail-closed offline: no network at import, plan,
authorize-check, preflight, report-plan, or report time. `preflight`/`report`
report `enabled=false`, `LIVE_CALLS_MADE=0`, the budget ceiling, reserved
ledger cents, and idempotency key prefixes (12-char redaction only).

---

## 8. Live workflow (only if/ when separately authorized)

The transport is gated by a strictly-parsed, local, runtime switch in
`validation_run._transport_enabled`, read from the local process environment
on every call:

- Only the exact normalized value `true` enables the transport;
- unset / empty / `false` / `1` / `yes` / malformed / any other value →
  **disabled** (fail-closed);
- no checked-in constant enables it.

An authorized, one-run live probe therefore requires BOTH
`SCANNER_LIVE_ALLOWED=true` and `DATAFORSEO_TRANSPORT_ENABLED=true` set
**locally** for the single invocation, then restored to disabled immediately:

```powershell
$env:SCANNER_LIVE_ALLOWED="true"
$env:DATAFORSEO_TRANSPORT_ENABLED="true"
$env:DATAFORSEO_LOGIN="login@example.com"
$env:DATAFORSEO_PASSWORD="pw"
python validation_run.py authorize-check --run <run-id> --confirm <run-id>
python validation_run.py execute-dataforseo --run <run-id> --confirm <run-id>
python validation_run.py retrieve-dataforseo --run <run-id> --confirm <run-id>
$env:DATAFORSEO_TRANSPORT_ENABLED="false"
$env:SCANNER_LIVE_ALLOWED="false"
```

Submission uses the family-aware client in `_dataforseo_standard_client`
(`merchant_task_post_url("products")` for the `product` type, with the
keyword body from §1). Retrieval uses `merchant_task_get_url(family, id)`
(§1) and never auto-retries. Repair is read-only against the preserved
envelope store:

```powershell
python validation_run.py repair-dataforseo --run <run-id>
```

---

## 9. IMPORTANT — DataForSEO evidence is never purchase authorization

A `matched` DataForSEO cross-check is a **secondary identity/offer
observation** only. It is **not** a purchase authorization. All
purchase-eligibility decisions remain governed by the existing shortlist,
Costco cost-basis, fee engine, ASIN/pack mapping, Amazon listing
eligibility, margin, supply, and concentration controls — each of which is
a separate, mandatory gate. DataForSEO may never mark an ASIN
purchase-authorized. The current default for all DataForSEO-derived
purchase signals is `false`.
