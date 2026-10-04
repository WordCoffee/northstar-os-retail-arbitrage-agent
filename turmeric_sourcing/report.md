# South Asia Turmeric Sourcing — Report

**Run:** 3 (2026-10-04)
**Outcome:** **BLOCKED** — per instruction 6 (profile isolation unprovable)
**Supplier pages opened this run: 0**
**Checkpoints:** `turmeric_sourcing/evidence.md`

---

## 1. Tooling / preflight result

Raw-browser surface remains verifiably absent: **0** `tools.browser.*`, **0** raw Playwright
tools, **6** `tools.chromeconnect.*`. Chrome Connect guardrails intact, fingerprint
`3595c933f9c3f163…`.

**Setup could not be completed. Two blockers, both structural.**

### BLOCKER 1 — no profile, including "Mogra Sourcing", can satisfy the isolation proof

Traced end to end:

1. `scripts/chromecontrol-mcp-server.js:72-85` — `bridgeProfileReport()` asks the transport for
   `verifyIsolation()`, else `profileReport()`, else **returns `null`**.
2. `scripts/chromecontrol-playwright-bridge.js:448-462` — exports contain **neither**
   `verifyIsolation` **nor** `profileReport`.
3. ⇒ `bridgeProfileReport()` returns `null` **unconditionally**.
4. `mcp-server.js:278` — `satisfied = !!(bridge && …)` → always `false`.
5. `lib/chromecontrol/pw-tool.js:193-201` — under `require_isolated`, `isolated` is `false`
   from the fallback → refusal `isolated_profile_required`.
6. `chromecontrol-playwright-bridge.js:188` — `verifyAttachment()` **hardcodes**
   `isolated_profile: false`.

The transport is missing the capability the gate depends on. This is not a misconfiguration
that setup can repair, and it is not fixable by choosing a different profile. The bridge header
(lines 7-22) confirms the design: this transport attaches to the operator's real profile and
must never substitute a fresh isolated one. The isolation concept belongs to an unwired path.

The bridge's own stated position: *"Isolation cannot be proven from outside the browser. The
controller refuses rather than assuming."*

**Default T2 was not used, and no blank, fresh or substitute browser was opened.** Per
instruction 6, this is a BLOCKED stop — no fallback was taken.

### BLOCKER 2 — the approved sourcing allowlist cannot be added safely

`policy.js:250-261` freezes `IMMUTABLE_GUARDRAILS` from the live arrays at load;
`fingerprint()` (`:264-279`) hashes those tables to `3595c933f9c3f163…`. Adding sourcing origins
moves that operator-approved fingerprint, breaking the baseline that `lessons.js`, the gate and
the test suite verify — and that fingerprint is what authorises runs.

Note the trap: `assertGuardrailsIntact().intact` would still read `true`, because the frozen
copies derive from the edited arrays at load. Integrity would *look* intact while the approved
baseline had silently moved. That is precisely why this was not done as a side effect of a
sourcing task.

**`policy.js` was not modified.** The read-only sourcing policy was not installed.

### Profile inventory observed (read-only)

| Directory | Name | Signed-in account |
|---|---|---|
| Default | T2 | t2holdingsltd@gmail.com |
| Profile 1 | Ty | mediablitz07@gmail.com |
| Profile 2 | Work | t2holdingsltd2@gmail.com |
| Profile 3 | Work | fishandcheeseent@gmail.com |
| Profile 4 | **Mogra** | **mograorganics@gmail.com** |
| Profile 5 | The Johnsons | mrandmrstj07@gmail.com |
| Profile 6 | Work | northstarosllc@gmail.com |
| **Profile 7** | **Northstar Research** | **none — signed out** |

- **`Profile 7` "Northstar Research" is already a signed-out profile** (`user_name: null`). It is
  the closest existing match to the intent behind "Mogra Sourcing", but it still cannot pass
  Blocker 1, so it does not unblock the run.
- **Naming hazard:** `Profile 4` is named "Mogra" and is signed in as `mograorganics@gmail.com` —
  Mogra Organics, the company being researched. Verified: `resolveProfile("Mogra Sourcing")` does
  **not** fuzzy-match "Mogra" (`"mogra".includes("mogra sourcing") === false`) and fails closed
  correctly. But a shorter reference such as "Mogra" **would** bind to the signed-in client
  account. Any new profile must not share a prefix with "Mogra".

### Why the picker was not launched

Isolation cannot be proven for any profile, so a picker selection could not have changed the
outcome. Launching it would have required a persistent change to your Chrome setup with no
possible benefit. Available on request.

## 2. Organic culinary turmeric powder — 5 candidates

| # | Candidate | Status |
|---|---|---|
| 1–5 | — | **NOT FOUND** |

No qualifying evidence observed. Zero pages opened.

## 3. Dried whole turmeric / fingers / root — 5 candidates

| # | Candidate | Status |
|---|---|---|
| 1–5 | — | **NOT FOUND** |

No qualifying evidence observed. Zero pages opened.

## 4. U.S. honorable mentions

**NONE.** No U.S. supplier page was opened.

## 5. Canadian honorable mentions

**NONE.** No Canadian supplier page was opened.

## 6. Excluded leads

**None observed** — zero listing pages opened. This is not a claim that no lead would be excluded.

The earlier Alibaba pass produced 17 rows, **all excluded**: all 17 were `CN` (China) and Alibaba
is excluded by the brief. Not reused, re-anchored or re-scoped.

## 7. BLOCKED-ORIGIN log

**Actual `BLOCKED-ORIGIN` events: 0.** No navigation was attempted, so no origin was reached or
refused at the origin level. The picker/profile gate blocked the run before any origin test.

Prospective origins that remain unavailable (read-only public pages, **none visited**):

| Origin | Purpose |
|---|---|
| `npop.nic.in` | India NPOP organic certification registry |
| `tracenet.net` | India organic Transaction Certificate traceability |
| `agriculture.gov.in` | APEDA export / registration evidence |
| `spicesboard.in` / `indianspice.in` | Spices Board export-presence evidence |
| `usda.gov` | Organic Integrity Database certificate cross-check |
| individual supplier domains (India, Sri Lanka, Nepal, Bangladesh, Pakistan, Bhutan) | country, product form, price/MOQ, lead time |

No web-search or fetch tool exists in this catalog, so even lead *discovery* is impossible. The
existing allowlist contains no South Asian supplier origin.

## 8. Evidence gaps and the exact documents required next

Nothing supplier-specific is outstanding, because no candidate evidence was gathered. Required
**before any outreach**:

- **Organic certificate** — certifier name, certificate number, scope, crop, validity dates.
  Cross-check USDA Organic Integrity Database; for India, TraceNet / APEDA.
- **Transaction Certificate (TC)** — covering the specific lot and shipment.
- **COA** — heavy metals, pesticide residues, lead chromate limits.
- **Invoice / export documents** — IEC and Spices Board registration, export licence,
  commercial-invoice capability.
- **Sample terms** — sample cost, lead time, refundability against a first order.
- **Carton / case specification** — net weight per case, to permit any cost normalisation.

## 9. Supplier-stated timing vs hypothetical air transit — recorded separately

**Supplier-stated lead time:** `UNKNOWN` for all 10 slots. No supplier page was opened.

**Hypothetical only — stated by no supplier:** air transit to the U.S. of **6–21 business days
after goods are ready** (2–5 export handling + 2–6 air carriage + 1–5 customs/arrival + 1–5
domestic delivery).

These fields are never merged. The hypothetical range is a planning assumption only — not a quote,
not a promise, and never to be added to or substituted for a supplier's stated lead time.

## 10. What is required before any run can proceed

Two reviewed code changes, both outside what a sourcing task should touch:

1. **Implement `verifyIsolation()` (or `profileReport()`) on the transport bridge** so the
   isolation gate has a real signal instead of returning `null`. This is the actual blocker.
2. **Add the sourcing origins as a separate policy table with its own fingerprint**, rather than
   editing `DOMAIN_ALLOWLIST`, so the approved guardrail fingerprint `3595c933…` does not move.

Neither was performed. `policy.js`, the allowlist, guard code, profile logic and the session
manager are unmodified. No supplier was contacted, nothing was submitted, and no purchase,
listing, pricing or transaction action was taken or prepared.

---

No purchase authorization is implied by this report.
