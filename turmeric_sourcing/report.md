# South Asia Turmeric Sourcing — Report

**Run:** 2 (2026-10-04)
**Observation window:** 2026-10-04T02:23:11-05:00
**Checkpoints:** `turmeric_sourcing/evidence.md`
**Supplier pages opened this run: 0**

---

## 1. Tooling / preflight result

**Raw-browser surface — genuinely absent, verified this run.**

| Check | Result | Basis |
|---|---|---|
| `tools.browser.*` in live catalog | **0** | model's own catalog, this session |
| raw Playwright tools in live catalog | **0** | model's own catalog, this session |
| `tools.chromeconnect.*` in live catalog | **6** | model's own catalog, this session |
| `"browser": false` gate in effect | yes | `Northstar OS Retail Arbitrage Agent/opencode.jsonc:101` |
| Chrome Connect guardrails intact | yes | fingerprint `3595c933f9c3f163…`, unchanged from Run 1 |

On operator instruction, `raw_browser_tools_visible` was set to `false` and
`host_surface_count` to `0` in
`C:\Users\T2Hol\OneDrive\Documents\Default Project\config\tool-surface.json`
(2026-10-04T02:23:11-05:00). `raw_tool_examples` was emptied and the original
rationale preserved under `prior_note_retained`. Guard code, Chrome Connect policy,
the allowlist, profile logic and the session manager were **not** modified.

> **What "guard passes" does and does not mean.** `lib/chromecontrol/tool-surface.js`
> cannot introspect the host tool catalog — its own header states this. It reads that
> JSON and branches on one boolean. After this edit the guard would proceed, but that
> result is **self-asserted, not independently probed**: it confirms the declaration says
> clean, nothing more. The only independent evidence is the catalog table above. The gate
> that removed the surface is **project-scoped** to the Northstar repo, so this
> declaration can read `false` in a session that never loaded that `opencode.jsonc`.
> Recorded in the declaration's `known_limitations`.

**Preflight — REFUSED.** One `chromeconnect_preflight` call, made without
`require_isolated` (operator specified Default T2 and no isolated/fresh browser):

```
attach_mode:                    extension
operator_profile_pinned:        false
isolated_profile:               null
isolated_signed_out_satisfied:  false
operator_profile_reused:        null
instruction: "STOP AND ASK THE OPERATOR. ChromeConnect cannot prove an isolated,
 signed-out profile from here. Do not proceed against a signed-in profile and do not
 infer that extension mode means isolated."
```

**Research did not run.** Both permitted modes are closed, so no compliant path existed:

- *Un-isolated* — the only attached profile is the operator's signed-in Default T2
  session, and preflight explicitly forbids proceeding against a signed-in profile.
- *Isolated* — `require_isolated: true` refuses unless isolation can be proven;
  `isolated_profile: null`, so it cannot be proven.

**Correction to Run 1.** That report's header stated "Profile: Default T2 (`Default`,
signed in as `t2holdingsltd@gmail.com`)" as fact. This preflight does not support it:
`operator_profile_pinned: false` and `operator_profile_reused: null` mean no profile has
been selected or verified. Profile identity remains **UNVERIFIED** and is not claimed here.

## 2. Organic culinary turmeric powder — 5 candidates

| # | Candidate | Status |
|---|---|---|
| 1 | — | **NOT FOUND** |
| 2 | — | **NOT FOUND** |
| 3 | — | **NOT FOUND** |
| 4 | — | **NOT FOUND** |
| 5 | — | **NOT FOUND** |

**NOT FOUND** = no qualifying evidence was observed. Zero pages opened; the run was
refused at preflight, before navigation. This is not a judgement that such suppliers do
not exist — it is the absence of any observation.

## 3. Dried whole turmeric / fingers / root — 5 candidates

| # | Candidate | Status |
|---|---|---|
| 1 | — | **NOT FOUND** |
| 2 | — | **NOT FOUND** |
| 3 | — | **NOT FOUND** |
| 4 | — | **NOT FOUND** |
| 5 | — | **NOT FOUND** |

Same basis as section 2. Zero pages opened.

## 4. U.S. honorable mentions

**NONE.** No U.S. supplier page was opened.

## 5. Canadian honorable mentions

**NONE.** No Canadian supplier page was opened.

## 6. Excluded leads

**None observed in this run** — zero listing pages were opened, so there is nothing to
exclude. This is not a claim that no lead would be excluded.

For completeness: the earlier Alibaba pass produced 17 supplier/product rows. **Every one
is excluded** by the brief — all 17 were `CN` (China), and Alibaba is excluded outright.
That dataset was not reused, re-anchored or re-scoped.

## 7. BLOCKED-ORIGIN log

**Actual `BLOCKED-ORIGIN` events this run: 0.** Preflight refused before any navigation was
attempted, so no origin was ever reached and nothing was blocked at the origin level.

The table below is therefore **prospective** — origins that would be refused, recorded for
the operator. They are listed as not attempted. No URL was requested and no response was
received, so no status code or refusal message is claimed.

| Origin (not attempted) | Purpose it would serve | Recorded |
|---|---|---|
| `npop.nic.in` | India NPOP organic certification registry | 2026-10-04T02:23:11-05:00 |
| `tracenet.net` | India organic Transaction Certificate traceability | 2026-10-04T02:23:11-05:00 |
| `agriculture.gov.in` | APEDA export / registration evidence | 2026-10-04T02:23:11-05:00 |
| `spicesboard.in` / `indianspice.in` | Spices Board export-presence evidence | 2026-10-04T02:23:11-05:00 |
| `usda.gov` | Organic Integrity Database certificate cross-check | 2026-10-04T02:23:11-05:00 |
| individual Indian / Sri Lankan supplier domains | supplier country, product form, price/MOQ, lead time | 2026-10-04T02:23:11-05:00 |

All are read-only public pages. None were visited. Adding any origin requires explicit
operator approval — policy is immutable and lessons cannot add domains.

**The permitted set contains no South Asian supplier origin at all:**

| Allowed origin | Usefulness for this brief |
|---|---|
| `primenationaldistribution.com` | U.S. distributor; not South Asia; at best a U.S. honorable mention |
| `costco.com`, `costcobusinessdelivery.com` | U.S. retail; rarely displays certifier / certificate no. / scope / validity → organic evidence would be `UNKNOWN` → excluded by the title-only-organic rule |
| `sellersprite.com`, `sas.selleramp.com`, `selleramp.com` | Amazon seller analytics; Amazon is blocklisted (26 domains) and out of scope |
| `oracle.com` | unrelated |
| `alibaba.com` | excluded by the brief; China-based |

No web-search or fetch tool exists in this catalog, so even lead *discovery* is impossible.
"Move to the next lead" had an empty set to move through.

## 8. Evidence gaps and the exact documents required next

No candidate evidence was gathered, so nothing supplier-specific is outstanding. The
documents required **before any outreach** remain unrequested:

- **Organic certificate** — certifier name, certificate number, scope, crop, validity dates.
  Cross-check USDA Organic Integrity Database; for India, TraceNet / APEDA.
- **Transaction Certificate (TC)** — covering the specific lot and shipment.
- **COA** — heavy metals, pesticide residues, lead chromate limits.
- **Invoice / export documents** — IEC and Spices Board registration, export licence,
  commercial-invoice capability.
- **Sample terms** — sample cost, lead time, refundability against a first order.
- **Carton / case specification** — net weight per case, to permit any cost normalisation.

## 9. Supplier-stated timing vs hypothetical air transit — recorded separately

**Supplier-stated lead time:** `UNKNOWN` for all 10 slots. No supplier page was opened, so
no supplier stated anything.

**Hypothetical only — stated by no supplier:** air transit to the U.S. of
**6–21 business days after goods are ready**
(2–5 export handling + 2–6 air carriage + 1–5 customs/arrival + 1–5 domestic delivery).

These two fields are never merged. The hypothetical range is a planning assumption only —
not a quote, not a promise, and never to be added to or substituted for a supplier's own
stated lead time.

## 10. Operator action required before any run can proceed

1. **Resolve the profile gate.** Pin the operator profile for this task
   (`operator_profile_pinned: true`), or make a provable isolated signed-out profile
   available, then re-run preflight. Until then Chrome Connect will refuse.
2. **Approve the allowlist additions** listed in section 7. This cannot be self-served.

Neither was performed. No supplier was contacted. Nothing was submitted. No purchase,
listing, pricing or transaction action was taken or prepared.

---

No purchase authorization is implied by this report.
