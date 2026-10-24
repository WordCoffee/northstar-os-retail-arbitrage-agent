# Decisions log

Newest first. Each entry records what was decided, why, and what it costs.

---

## D-2026-10-23-07 — Bojo becomes a deterministic router; the model stays the writer

**Decision.** `specialists/router.py` classifies every turn before the model runs and prepends one
line to the system directive (`[router] package_designer — ask for: dims, company`). Routing is
rule-based, not model-based.

**Why.** The blueprint's §2 problem 3 is that one assistant does router and specialist work. A
model-based router would make routing non-deterministic and untestable, and would consume the same
GPU budget as the work itself. Rules are auditable and the suite can assert them.

**Cost.** The router is lexical: a request that never names a domain ("make it pop") routes
`unclear` and asks. That is the intended failure mode, not a defect.

---

## D-2026-10-23-06 — the specialist layer may not import a network client

**Decision.** `test_no_egress.py` fails the build if `specialists/*.py` imports `requests`, `httpx`,
`urllib`, `socket`, `aiohttp` … or contains a URL outside the approved host set.

**Why.** Blueprint §11. A static check in CI cannot be undone by a runtime config change.

**Cost.** Any future agent that legitimately needs a data source must import it from an approved
adapter module outside `specialists/`, which is the correct seam anyway.

---

## D-2026-10-23-05 — a missing legal fact is drawn on the artwork, not omitted

**Decision.** With `allow_incomplete`, the back panel prints `[MISSING: company address]` in the
layout rather than leaving a gap or a plausible placeholder.

**Why.** An omitted field looks finished and ships. A visible marker cannot be missed at review.
Blueprint §10: label content must come only from user-provided facts.

**Cost.** The artwork is ugly until the facts arrive. That is the point.

---

## D-2026-10-23-04 — the flat dieline width is reported separately from the pouch width

**Decision.** `dieline.flat_width_mm` / `flat_height_mm` are the sheet; `dieline.meta.width_mm` is
the pouch. Both are returned.

**Why.** A test compared them and failed: `build_from_template("doypack", …)` returns the FLAT sheet
(113 mm) at the top level while the pouch is 95 mm. Anyone reading `width_mm` without knowing this
would mis-report every package.

**Cost.** Two similar-looking numbers; mitigated by naming and by the regression test.

---

## D-2026-10-23-03 — quoted spans and negated spans are removed before routing

**Decision.** `router._strip_quoted` and `router._drop_negated` blank quoted spans and everything
after a negator *within its clause*.

**Why.** Two real bugs: an apostrophe in "Lion's Mane" was treated as an opening quote and silently
deleted the weight and dimensions from a complete brief; and dropping the whole clause on negation
threw away the agent the operator actually asked for ("I don't need a video, just the A+ modules").

**Cost.** The regex is deliberately conservative: a straight apostrophe is only a quote when it is
not glued to a word.

---

## D-2026-10-23-02 — Advanced view is out of scope; Simple view is the product

**Decision.** Operator instruction: "skip advanced view we are only focused on simple view."
D-14 is therefore closed as intended behaviour, not a defect. `shell_router.ADMIN_ROLES` still
gains `owner` (a correct role-ladder fix with a regression test) but nothing depends on it.

**Why.** Every room route resolving to a chat focus is the design. The consequence is that the
chat must carry the full workflow — which is exactly what the specialist agents are for.

**Cost.** Service workspaces cannot be acceptance-tested through the browser at this tier. Recorded
in `reports/northstar_acceptance_20261023/defects.md`.

---

## D-2026-10-23-01 — no Tier A repo adopted this pass

**Decision.** None of the listed repositories was cloned, vendored, or adapted. Specs describe
Northstar's own behaviour and mark every unobserved competitor claim UNVERIFIED.

**Why.** §3.1 clean-room discipline and §3.5 anti-fabrication. Writing a capability map of a repo
nobody read would be invention.

**Cost.** The specs are thinner than they will be after a real study pass. `provenance.csv` carries
explicit `NOT ADOPTED / NOT REVIEWED` rows so the gap is visible rather than implied as done.
