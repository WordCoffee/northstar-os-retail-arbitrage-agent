# Northstar OS — Build Blueprint v2 (2026-10-23)

**Supersedes §12 (phases) and adds §11A, §11B, §11C.** Sections 0–10 and 13–15 of the original
blueprint stand unchanged except where named here.

---

## §11A — Cloud readiness (new)

**Position:** local is the development setup; production runs on cloud models and cloud services,
billed as usage + a software fee at a **60–70 % target margin**. Everything switches local → cloud
**by configuration only**.

### A1. Model gateway (build first)

Agents request a **role**, never a model:

```
reasoning · tool_calling · image · video · voice · embeddings
```

- `shared/model-roles.json` maps role → ordered provider chain (local now, cloud later).
- One adapter per provider, **same interface**: `complete(role, payload) -> {ok, text|bytes, usage, cost}`.
- Adapters: `local_ollama`, `comfyui`, `stub_cloud` (for acceptance), cloud providers later.
- No agent may import a provider SDK directly. This is enforced by a test, not by convention.

### A2. Usage ledger

Every call writes: **user, tenant, job, agent, role, provider, model, tokens | GPU-seconds, raw cost,
customer charge, margin, idempotency key, timestamp**.

- Price table per provider/model in `shared/provider-prices.json`.
- Margin rule configurable **per plan and per service** in `shared/margin-rules.json`.
- Per-user spending caps; a cost estimate is shown **before** an expensive job.
- Monthly margin report from the ledger (no sampling, no estimates).

### A3. Reliability

Retries with exponential backoff, **fallback chain per role**, async jobs with status + webhooks,
idempotency keys so a retry never double-charges.

### A4. Isolation

Tenant isolation for reports, brand kit, assets and Master Brain memory. Provider keys server-side
only; never in a client bundle, a prompt, a log or a commit.

### A5. Acceptance (replaces the old no-egress test)

1. Swap **every** role to `stub_cloud` by config; **all agent tests pass unchanged**.
2. The ledger shows the correct cost and charge for stub calls (checked against the price table).
3. A **forced provider failure** triggers the fallback and produces no user-visible error.
4. `gateway_test.py` fails if any model or data call **bypasses the gateway** or reaches a
   non-approved host.

---

## §11B — Bojo's scope (new) and the celestial theme

### B1. Bojo is a broad seller assistant

Bojo = Perplexity-Computer / Claude-Cowork class assistant for an Amazon seller. In scope:
**Creative, Grow, Research, Operate**, small utilities (a calculator, a unit converter, a checklist),
and **chained multi-agent jobs**.

**Out of scope:** serious coding and task management — those belong to **Autothink**. Bojo must
**offer a handoff with a brief** rather than attempt them badly.

Bojo always shows, before heavy work: **plan, agents, missing inputs, estimated cost**. During work:
live progress. After work: **downloadable files + a change log**. Every output carries its
**SEO tie-in**.

Two routing tests are added:
- a small utility Bojo should build itself;
- a large engineering request it must hand to Autothink with a brief.

### B2. Celestial theme (the Interstellar request is **unmet**)

The Interstellar-inspired theme was requested and a plain black background shipped. Treat as unmet.

**Layered background**
1. deep blue-black vertical gradient (space black → midnight blue),
2. star field at **three depths** with slow parallax,
3. faint nebula washes (low-alpha, large radius),
4. **one warm accretion-disk glow** behind key areas — the chat box above all.

**Palette** — space black / midnight blue base; warm amber + gold accents; cool silver-blue
secondary text. **Contrast must be checked**, not assumed.

**Surfaces** — frosted glass panels, thin luminous borders, slow purposeful motion,
**reduced-motion support**. Lightweight canvas or CSS only: it must never slow chat or compete with
GPU render jobs.

**Acceptance:** desktop **and** mobile screenshots against this spec, plus a contrast check.

---

## §11C — Vision fidelity (new)

Before building any feature:

1. A **one-page brief**: the request in the operator's words, the intended experience, and
   **3–7 pass/fail checks**. **Operator approves it first.**
2. A **reference board** for visual work.

After any UI or image change:

3. Drive the app with **Chrome Connect**, take **desktop and mobile** screenshots,
4. report each check as **PASS/FAIL with evidence**.

**No silent substitutions.** If something cannot be met, say so and offer options.
Operator signs off on **the theme**, **Simple Mode flow**, and **Package Designer output**.

---

## §12 — Revised phases

| Phase | Content | Status |
|---|---|---|
| 0 | Audit (read-only) | **DONE** |
| 1 | Study (Tier A repos, Tier B behaviour) | **in progress** — Packify live; 7 Tier A + 10 Tier B open |
| **1B (new)** | **Gateway + usage ledger**, the three **briefs** (theme, Simple Mode, Package Designer), and the **theme fix** | **starting now** |
| 2 | Test harness (22 tasks) + baseline | **DONE** |
| 3 | Package Designer | **DONE** (gusset side-panel = L4) |
| 4 | Listing + PPC | **DONE** (bulk writer shipped) |
| 5 | Image/A+, Social, Video, Content agents | **DONE** (planning + validation; renders not exercised) |
| 6 | Router + manager model selection — **plus the Bojo/Autothink scope boundary** | router DONE; boundary + benchmark open |
| 7 | **Cloud cutover rehearsal** + hardening (queue, observability, cost, rollback) | open |

## §15 — Definition of done (revised)

A phase is done only when:

- the **gateway check** passes (`gateway_test.py`) — no call bypasses the gateway;
- the **cloud readiness test** passes — every role on `stub_cloud`, agent tests unchanged, correct
  per-call **cost and margin** in the ledger, fallback on forced failure with no user-visible error;
- the work **matches an approved brief** (§11C), evidenced by desktop + mobile screenshots and a
  PASS/FAIL per check;
- provenance is recorded (REBUILT / ADAPTED + licence), and nothing unverified is claimed.
