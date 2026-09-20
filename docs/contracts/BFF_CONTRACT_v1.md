# Northstar OS — BFF / API Contract v1

**Contract id:** `bff/v1`
**Status:** FROZEN for Phase C implementation (designed in Phase B, B1). Schemas
only — this document does NOT implement every endpoint.
**Owner:** Master Brain. **Change process:** additive only within `v1`; any
breaking change requires `bff/v2` and an operator-approved migration.
**Phase alignment:** Alpha Build Blueprint Phase B / B1 ("Endpoint spec: opaque
job IDs (`job_id` ↔ `scan_id`), status lifecycle, no-leak response shape").

This contract is the single response-shape law for every service surfaced by
the Northstar OS backend: **SourceScout, ListingForge, AdPilot, SocialPulse,
Golden Goose, AutoThink**. It defines the uniform envelope, the opaque job
model, the standard error taxonomy, and the no-leak allowlist. Service-specific
payloads live in their own seam specs (see `GOLDEN_GOOSE_SEAM_v1.md`).

---

## 1. Principles

1. **One envelope.** Every JSON response is wrapped in the envelope of §2.
   No service invents its own top-level shape.
2. **Opaque identifiers only.** External callers never see raw scan ids,
   numeric DB ids, provider task ids, or internal correlation ids. They see
   `job_…` / `res_…` / `req_…` tokens (§4).
3. **No leakage.** Provider/vendor names, routing logic, model ids, prompts,
   cost formulas, credentials, internal filesystem paths, and stack traces are
   **never** present in any payload (§6). This is enforced by the export
   sanitizer design (B4) and audited in D1.
4. **Honest states.** Loading/empty/error are first-class, explicit, and
   never faked as success (§3).
5. **`scan_id` is internal.** The backend may correlate a job to an internal
   `scan_id`; that mapping is server-side only.

---

## 2. Response envelope

All responses (success, empty, error) use this shape:

```jsonc
{
  "contract": "bff/v1",          // literal
  "request_id": "req_7f3a…",     // opaque, per-response correlation token
  "status": "ok",                // "ok" | "empty" | "error"
  "data": { /* resource or list */ },   // null when status="error"
  "error": null,                 // BffError object when status="error", else null
  "meta": {
    "service": "golden_goose",   // service key (never a provider/vendor)
    "version": "v1"
  }
}
```

**HTTP mapping**

| `status` | HTTP | Meaning |
|---|---|---|
| `ok` | 200 | Populated result (`data.items` non-empty, or a single resource). |
| `empty` | 200 | Valid request, no rows/resources. `data.items == []` (or `data` present but empty). **Not an error.** |
| `error` | 4xx/5xx | See §5 taxonomy. `data` is `null`, `error` is populated. |

**List data shape**

```jsonc
"data": {
  "items": [ /* resource objects */ ],
  "page": { "limit": 50, "returned": 12, "has_more": false, "cursor": null }
}
```

**Single-resource data shape**

```jsonc
"data": { "id": "ggo_…", /* resource fields */ }
```

> **Rule:** a service must use `status:"empty"` (HTTP 200) rather than a 4xx
> for "no results yet", and must never return `status:"ok"` with a fabricated
> or zero-filled row.

---

## 3. Loading / empty / error semantics

- **Loading** is a client concern; the API does not emit a "loading" payload.
  A job in `queued`/`running` (§4) is the server-side analogue.
- **Empty** = `status:"empty"`, `data.items:[]`, and an optional non-leaky
  `data.reason` enum: `no_reports_yet | no_matches | filtered_out | not_entitled`.
  `reason` values are fixed enums and must not contain provider/cost detail.
- **Error** = `status:"error"` with a §5 error object. Partial success is
  expressed per-item in `data.items[*].warnings` (never by leaking a raw
  provider error string).

---

## 4. Opaque job model

A **job** represents any asynchronous unit of work (a scan, an enrichment, an
export). External callers address jobs only by an opaque `job_id`.

**Job resource** (`GET /api/v1/jobs/{job_id}` → `data`):

```jsonc
{
  "job_id": "job_9c1d…",         // opaque; prefix job_
  "service": "golden_goose",     // service key
  "operation": "goose.scan",     // dotted, service-scoped, fixed enum
  "state": "queued",             // queued | running | done | failed | cancelled
  "created_at": "2026-09-19T20:00:00Z",
  "updated_at": "2026-09-19T20:00:12Z",
  "progress_pct": 0,             // 0..100 integer, or null when indeterminate
  "result_ref": null,            // opaque res_ token when state="done", else null
  "error": null,                 // §5 error when state="failed", else null
  "links": { "self": "/api/v1/jobs/job_9c1d…" }
}
```

**State machine** (only these transitions are legal):

```
queued ──▶ running ──▶ done
  │           │
  │           ├──▶ failed
  └───────────┴──▶ cancelled
done / failed / cancelled are terminal.
```

**Identifier rules**

| Token | Format | Visibility | Notes |
|---|---|---|---|
| `job_id` | `job_` + 32 lowercase hex | public | opaque; generated server-side |
| `result_ref` | `res_` + 32 lowercase hex | public | points at a result set, not a file path |
| `request_id` | `req_` + 32 lowercase hex | public | per-response correlation |
| `scan_id` | internal | **never exposed** | server-side mapping only (`job_id ↔ scan_id`) |

Generation must use a cryptographically-random source. Sequential/numeric ids
are forbidden.

---

## 5. Standard error taxonomy

```jsonc
"error": {
  "code": "entitlement_required",
  "message": "This plan does not unlock this capability.",
  "retryable": false,
  "details": null            // optional, non-leaky, schema-validated
}
```

| `code` | HTTP | Meaning |
|---|---|---|
| `invalid_request` | 400 | Malformed/invalid parameters. |
| `unauthorized` | 401 | Missing/invalid session. |
| `forbidden` | 403 | Gate not armed / action hard-stopped (e.g. live scan in alpha). |
| `entitlement_required` | 403 | Plan does not entitle the requested capability. |
| `not_found` | 404 | Unknown id (opaque ids fail closed). |
| `conflict` | 409 | State conflict (e.g. transitioning a terminal job). |
| `rate_limited` | 429 | Caller rate exceeded. |
| `provider_unavailable` | 502 | Upstream data source unavailable (generic — **no provider name**). |
| `not_implemented` | 501 | Endpoint intentionally not implemented; the server returns this honestly instead of a fake success (used by `functions/api/transcribe.js`). |

> **E3 decision (2026-09-20):** `/api/transcribe` is **intentionally deferred**
> — the 501 `not_implemented` stub is the **frozen behavior through Phase E**
> (and until a later phase explicitly scopes STT). Rationale: speech-to-text
> needs either a self-hosted whisper-class backend or a paid STT API; both are
> out of alpha scope and any paid provider call is a §3 Hard-Stop action
> requiring named approval (and would incur per-call cost). The BFF contract's
> honest-stub rule applies: never fake a transcription result. Target phase:
> post-alpha (Phase F / hosted-release) with an explicit provider + cost
> approval.
| `internal_error` | 500 | Unhandled server fault (generic — **no stack trace**). |

**Rules:** `message` is human-readable and leaks nothing; `details` is
optional and must pass §6; `retryable` is a boolean hint only. Raw exception
strings, provider status codes, and vendor names never appear.

---

## 6. No-leak allowlist (the "response shape" rule)

No payload at any depth may contain these — enforced by key deny-list + value
scanner in the sanitizer (B4 design) and verified in the D1 audit:

**Forbidden keys (case-insensitive, any depth):**
`provider`, `vendor`, `provider_id`, `vendor_id`, `api_key`, `apikey`,
`secret`, `token`, `password`, `credential`, `authorization`, `auth_header`,
`routing`, `route`, `model`, `model_id`, `prompt`, `system_prompt`,
`cost_formula`, `cost_cents`, `unit_cost_usd`, `internal`, `raw`,
`report_path`, `file_path`, `filesystem`, `path`, `stack`, `traceback`,
`exception`, `env`, `dotenv`.

**Forbidden value tokens (substring, case-insensitive):**
`bright data`, `brightdata`, `chocodata`, `easyparser`, `openwebninja`,
`unwrangle`, `scavio`, `canopy`, `dataforseo`, `firecrawl`, `scrape.do`,
`rapidapi`, `ollama`, `openrouter`, `deepseek`, `relace`, `deepinfra`,
`open-inference`; plus absolute filesystem paths (`[A-Za-z]:\`, `/Users/`,
`/home/`, `/tmp/`, `\\\\`), API-key-shaped strings, and JWTs.

**Allowed:** user-facing product data (brand, title, ASIN, price, ROI, tier,
scores, dates), service keys, opaque ids, fixed enums, and boolean flags.

> Provider/retailer note: a **retailer** name that is product data (e.g. a
> store the item was sourced from) is permitted only if it is genuinely part
> of the user-facing value and never reveals the *data provider* or the
> *routing*. When in doubt, omit.

---

## 7. Endpoint map (schemas only — no implementation here)

Uniform job verbs; each service plugs its own operation enum.

| Method | Path | Response `data` | Notes |
|---|---|---|---|
| `GET` | `/api/v1/{service}/…` | resource / list | read endpoints per service |
| `POST` | `/api/v1/{service}/jobs` | `{ job: <Job> }` | creates a job, returns opaque `job_id` |
| `GET` | `/api/v1/jobs/{job_id}` | `<Job>` | status; fail-closed on unknown id |
| `GET` | `/api/v1/jobs/{job_id}/result` | result set | only when `state="done"`; else `conflict` |
| `GET` | `/api/v1/{service}/entitlements` | `{ plan, categories, exports }` | derived from `shared/subscription-plans.json` (+ seam mapping) |

**Service keys:** `sourcescout`, `listingforge`, `adpilot`, `socialpulse`,
`golden_goose`, `autothink`.

**Example operation enums (non-exhaustive):** `goose.scan`,
`sourcescout.discover`, `listingforge.generate`, `adpilot.review`,
`socialpulse.draft`, `autothink.run`.

---

## 8. Versioning & compatibility

- `contract: "bff/v1"` is present on every response so clients can assert.
- Additive fields are allowed within `v1`; removals/renames require `v2`.
- Deprecations are announced in this doc and mirrored in `00_STATE.json`.
- Unknown `error.code` values must be treated as `internal_error` by clients.

---

## 9. Cross-check — Golden Goose `/api/golden-goose/opportunities` (as built in B2)

Current shape (report-backed, offline):
`{ "status": "ok"|"no_data", "report_meta": {...}, "summary": {...}, "opportunities": [ {_scored_to_dicts shape} ] }`

| Contract rule | Conforms? | Required change (Phase C) |
|---|---|---|
| Uniform envelope (`contract`, `request_id`, `data`, `error`, `meta`) | **No** | Wrap as `{contract, request_id, status, data:{items,…}, error, meta}`. |
| `status` enum `ok/empty/error` | **No** | `"ok"`→`ok`; `"no_data"`→`empty` (HTTP 200). |
| Opaque job model | **No** | Add `job_id`/`job` linkage; `scan_id` stays internal. |
| No provider/vendor names in payload | **Yes** | None. `source_store` is retailer product data, permitted. |
| No internal filesystem paths | **No — LEAK** | `report_meta.report_path` is currently included (set in `main.py` and echoed by the endpoint). Must be stripped. |
| No cost-formula/routing fields | **Yes** | None (economic values like net/ROI are product outputs, allowed). |
| Empty semantics | Partial | Use `status:"empty"` + `data.reason`, not a bespoke `no_data`. |

**Also:** `POST /api/golden-goose/scan-mock` returns `summary`/`opportunities`/
`meta` inline (same envelope gaps), and `POST /api/golden-goose/scan` returns
**403 in alpha** (unchanged; see the GG seam spec).

---

## 10. Conformance checklist (for Phase C)

- [ ] Every endpoint returns the §2 envelope with `contract:"bff/v1"`.
- [ ] `request_id` emitted per response; opaque jobs use §4 id rules.
- [ ] No §6 forbidden key/value anywhere (sanitizer test + D1 audit).
- [ ] `empty` used instead of 4xx for "no rows".
- [ ] Errors use only §5 codes; `message` is leak-free.
- [ ] `report_path` (and any filesystem path) removed from all payloads.

---

*Designed Phase B (B1), 2026-09-19. FROZEN for Phase C. Schemas only.*