# DataForSEO Live Pilot Plan — One Approved ASIN

**Status: NOT YET AUTHORIZED.** Next live activity is gated behind explicit
approval and code-path resolution (see §3).

## 1. Intended first pilot

The intended first live pilot is a **single mapping-approved ASIN** using:

- Create: `POST /v3/merchant/amazon/sellers/task_post`
- Family: `sellers` (Merchant Standard)
- Body: ASIN-driven (`asin` field sourced from the approved shortlist)
- Retrieve: `GET /v3/merchant/amazon/sellers/task_get/<task_id>`

This path is chosen because Seller data is the most constrained and
most purchase-signals-relevant family (per-seller price, condition, shipment,
seller rating), and it is the narrowest possible probe of the live transport
without touching Costco COGS, fee evidence, or Amazon eligibility.

## 2. Blocking behavior (current state — MUST be resolved before live)

**The current code path cannot submit a `sellers` task.** In
`validation_run.cmd_execute_dataforseo`, rows whose
`validation_type == "seller_offer"` are classified as
`mapping_incompatible` and are **never submitted**:

> `if validation_type != "product": raise GuardError(...)` (inside
> `_StandardClient.submit` for the DataForSEO transport).

Because the pilot targets the `sellers` family, this `seller_offer` path is
the exact code path under test. **Pilot readiness = NOT READY** until this
narrow code path is resolved and verified offline.

Concretely, achieving readiness requires:
1. a mapping-approved planning/submission path for Merchant `sellers`
   (`sellers` task_post with an ASIN body),
2. offline unit + harness coverage asserting: ASIN in body, family=`sellers`,
   no keyword/search_term, allowlist rejection of non-`sellers` families on
   this path, and the exact URL
   `https://api.dataforseo.com/v3/merchant/amazon/sellers/task_post`,
3. no-regression on the `product`/`asin` submit paths and on the 40402 repair
   preservation.

## 3. Expected creation acceptance (sellers family)

A `sellers` task_post create is accepted only when **all** hold:

- top-level `status_code == 20000`,
- top-level `tasks_error` is `0` / absent,
- `tasks[0]` exists and is a dict,
- task-level `status_code == 20100`,
- task-level `status_message == "Task Created."` (case-insensitive, trimmed),
- task-level `cost > 0` (provider-reported; `0`/`null` → rejected),
- task-level `id` is a non-empty, slash-free UUID-like string,
- `task.path == ["v3","merchant","amazon","sellers","task_post"]`,
- body `asin` matches the approved pilot ASIN (cross-checked post-retrieve).

Ledger updates only on this outcome: `state="submitted"`, `remote_task_id`
set, `actual_cost_cents` from provider `cost`, reservation committed.

## 4. No-retrieval-until-approved policy

- No `task_get`/Labs request is issued for a pilot ASIN until its create
  response is accepted **and** the operator runs
  `retrieve-dataforseo --run <run-id> --confirm <run-id>` with the transport
  re-enabled.
- Retrieval uses `merchant_task_get_url("sellers", remote_task_id)` (not
  `task_post` URL, not `product_info`).
- Retrieval failures (HTTP 404, malformed, id mismatch, wrong family) fail
  the ASIN gracefully and are bookkept `needs_manual_reconciliation` or the
  relevant `provider_rejected_*` — never auto-retried, never mutating the
  canonical benchmark source.

## 5. Exact stop conditions (abort the probe, never proceed)

Abort immediately on any of:

- provider rejection (any `provider_rejected_*`),
- path/URL mismatch (route is not `sellers` task_post/task_get),
- zero or negative provider-reported `cost`,
- malformed response (not a dict / missing `tasks`),
- missing, non-UUID-like, or slash-containing `task_id`,
- returned ASIN does not match the approved pilot ASIN (mapping conflict),
- budget breach (single-ASIN probe exceeds the one-run USD 0.01 cap),
- task-level wrong family (e.g. create returns a `products`/`asin` task),
- secret-like output in the response (redact, halt, manual review),
- persistence failure (raw-evidence write error),
- timeout / `AmbiguousTransportError` (post-failure ambiguity) — marked
  `needs_manual_reconciliation`, never retried.

## 6. Fields expected from Seller data (documented scope only)

From a successfully retrieved `sellers` task result, the adapter observes:

- per-seller `condition`,
- per-seller `price` (currency/value),
- `shipment` details,
- seller `rating` / `rating_count`.

Everything else is intentionally out of scope for this probe.

## 7. Fields that remain Unknown until explicitly present in real evidence

Until a real retrieved record explicitly carries the signal (never inferred):

- Buy Box owner,
- Buy Box price,
- seller count if a complete explicit offer roster is not returned,
- UPC/EAN/GTIN,
- monthly unit sales, FBA fee, referral fee,
- COGS (Costco cost basis),
- Amazon purchase authorization.

## 8. Authorization checklist (complete before live)

- [ ] mapping-approved Merchant `sellers` submit/retrieve path implemented
- [ ] offline tests green: URL + ASIN body + no keyword + allowlist + 40402
      repair preservation + one-ASIN positive-cost acceptance predicate
- [ ] `SCANNER_LIVE_ALLOWED` + `DATAFORSEO_TRANSPORT_ENABLED=true` set locally
      for exactly one invocation, then restored to `false`
- [ ] explicit run-id / confirm token match (`authorize-check --confirm <id>`)

**Remaining implementation blocker:** *Create an explicitly mapping-approved
Merchant Sellers planning/submission path; keep unresolved mappings
blocked.*
