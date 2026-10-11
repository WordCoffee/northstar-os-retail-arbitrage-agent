# Generation Arming Checklist

**Current state: UNARMED.** Nothing in the Design Studio calls an image or video
model. Every generate path is a request recorder whose honest terminal state is
"Blocked — provider required". This document is what the owner must work through
BEFORE anything is armed.

Nothing here is implemented as an automatic behaviour. Arming is a deliberate,
one-time, owner decision.

---

## 1. What "armed" means in code

The shared router exposes the arming state. The Studio reads it and refuses to
run while it is false:

| Check | Where | Behaviour when false |
|---|---|---|
| Media generation armed | `model_router.media_live_armed()` | every generate action returns `unarmed` |
| Per-provider armed | `model_router.provider_armed(provider)` | that provider is refused, others unaffected |
| Cloud spend armed | `model_router.cloud_live_armed()` | cloud tiers refused; local stays available |

The Studio treats an **unreadable** arming state as UNARMED. Unknown is never
armed.

## 2. Spend and time caps (set before arming)

| Cap | Suggested starting value | Why |
|---|---|---|
| Per-run credit cap | 20 | One bad prompt cannot exhaust a month |
| Per-day credit cap | 100 | A loop cannot run all night |
| Per-day wall-clock cap | 60 minutes of GPU | Thermal and power, and it bounds a runaway loop |
| Per-job timeout | 10 minutes | A stuck job must fail, not hang |
| Max jobs per project | 50 | Bounds a single project's spend |

Every cap must be enforced **server-side**. A client-side cap is a suggestion.

### 2b. Per-tenant job limits (multi-tenant safety)

The caps above are per project. A hosted deployment also needs limits that make
one tenant unable to spend or queue everyone else's budget:

| Limit | Suggested starting value | Enforced where |
|---|---|---|
| Concurrent generation jobs per tenant | 2 | job queue admission |
| Queued (not started) jobs per tenant | 10 | queue admission; the 11th is refused with a stated reason |
| Generation credits per tenant per day | 100 | the same ledger that records spend |
| Wall-clock GPU minutes per tenant per day | 60 | the worker's accounting |
| Jobs per tenant per hour | 20 | admission, so a loop is throttled, not banned |

Rules that make the limits honest:

- A refusal is **reported** to the tenant with the limit's name and its reset
  time; it is never a silent drop and never a "retry later" with no reason.
- The limit check happens **before** the job is enqueued, so a refused job
  costs nothing and leaves no half-written record.
- An unreadable counter is treated as **at the limit** (fail closed), the same
  way an unreadable arming state is treated as UNARMED.
- Limits are configuration, not code: changing a number does not require a
  release, and every change is recorded in the audit log.

## 3. Audit log (required before arming)

Every generate call must record, append-only:

- who (user id), when (ISO timestamp), project id, asset id
- provider, model, tier, and the full parameter set
- the cost preview that was shown AND the amount actually charged
- the outcome, including failures and cancellations
- the resulting asset id and its provenance metadata

The Studio already stores this shape in `ds_jobs`. Arming requires that the
write happens **before** the provider call, so a crash cannot lose the record.

## 4. Kill switch (required before arming)

Three independent ways to stop, all server-side:

1. **Disarm the flag** — set the arming env var to off and restart. This is the
   normal stop.
2. **Per-provider disable** — takes effect without a restart.
3. **Hard stop** — a documented procedure to stop the worker and the queue
   consumer, and to leave in-flight jobs in a recoverable state.

The kill switch must be testable while unarmed. Test it before you need it.

## 5. What stays blocked even when armed

These are not preferences. They are enforced by the disclosure and fidelity
gates regardless of the arming state:

- **The product region is never generated.** `fidelityMode: 'generated'` is a
  blocking mode, so an asset whose product was generated cannot export.
- **A generated person auto-flags and auto-applies the marker.** The seller
  cannot switch the marker off; they can only correct the classification.
- **Seller attestation is still required** for any asset containing a generated
  person.
- **The compare step is still required** for any asset containing the product.
- **The full pre-flight still runs**, including the Amazon spec rules.

## 6. Minimum worthwhile model set (when you do arm)

Ordered by what a seller actually needs first:

| Purpose | Why first |
|---|---|
| Background removal / white-background main image | Deterministic, cheapest, highest compliance value. Do this with code, not a model. |
| Background and scene generation around a masked product | The core listing-image use |
| Relighting and shadow | Makes a composite read as one photograph |
| Angle variants | Secondary slots |
| Product video / UGC clips | Last: the most expensive and the most failure-prone on 16 GB |

## 7. Honest limitations to accept before arming

- A local 16 GB GPU is marginal for video. Expect short clips at limited
  resolution, not Veo-class output.
- Custom brand models (LoRA) take hours per brand and need a storage plan.
- Generated text inside an image is unreliable. The Studio renders text as
  vector layers for exactly this reason; do not let a model draw the words.
- The fidelity threshold is an engineering tripwire, not an Amazon figure. It
  will refuse some legitimate re-shoots and will miss a small, plausible
  in-product edit.
- No sample of real re-shoots has been measured against the thresholds.

## 8. Config sketch (documentation only — none of this is set today)

If arming is ever approved, these are the NAMES the deployment would use. All
are absent/empty in the beta, and the hosted overlay must keep them that way
(the compose guard fails a deploy that sets an arming flag to 1):

```
# Provider arming (both required for any cloud spend):
CLOUD_MODEL_LIVE=            # empty/0 = cloud tiers refused
MEDIA_GEN_LIVE=              # empty/0 = image/video generation refused

# Caps (server-side; the values are examples, not recommendations):
GEN_MAX_CREDITS_PER_RUN=20
GEN_MAX_CREDITS_PER_DAY=100
GEN_MAX_GPU_MINUTES_PER_DAY=60
GEN_JOB_TIMEOUT_SECONDS=600
GEN_MAX_JOBS_PER_PROJECT=50

# Per-tenant limits:
GEN_MAX_CONCURRENT_PER_TENANT=2
GEN_MAX_QUEUED_PER_TENANT=10
GEN_MAX_CREDITS_PER_TENANT_DAY=100
GEN_MAX_GPU_MINUTES_PER_TENANT_DAY=60
GEN_MAX_JOBS_PER_TENANT_HOUR=20
```

The read-only status endpoint `/api/design-studio/generation-status` reports the
live state; a missing flag reads UNARMED with its reason. This document changes
nothing by itself: generation **remains UNARMED** until every sign-off box
below is ticked and the owner says so explicitly.

## 9. Sign-off

| Step | Done | Date | Notes |
|---|---|---|---|
| Caps set and enforced server-side | ☐ | | |
| Audit log writes before the provider call | ☐ | | |
| Kill switch tested while unarmed | ☐ | | |
| One provider armed in isolation | ☐ | | |
| First run: background only, no people, no product region | ☐ | | |
| Reviewed the first ten outputs by hand | ☐ | | |
| Decided whether the marker is auto-applied or seller-toggled | ☐ | | |
