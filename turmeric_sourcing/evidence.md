# Turmeric sourcing — evidence checkpoint

## Run 3 — 2026-10-04 — BLOCKED: ISOLATION UNPROVABLE FOR EVERY PROFILE; ZERO OBSERVATIONS

Zero supplier pages opened. Zero candidates. Zero exclusions. The profile picker was
**not** launched — see "Why no picker" below. Nothing inferred.

### BLOCKER 1 — no Chrome profile can ever satisfy the isolation proof

Traced end to end, then confirmed against the live preflight result:

| # | Location | Fact |
|---|---|---|
| 1 | `scripts/chromecontrol-mcp-server.js:72-85` | `bridgeProfileReport()` asks the transport for `verifyIsolation()`, else `profileReport()`, else **returns `null`** |
| 2 | `scripts/chromecontrol-playwright-bridge.js:448-462` | exports are `transport, bindProfile, closeSessions, sessionReports, listProfiles, resolveProfile, runningChromeProfiles, verifyAttachment, resolveExecutable, localPlaywrightMcpCli, mcpCommand, OPERATOR_USER_DATA_DIR, chromePath` — **neither `verifyIsolation` nor `profileReport` exists** |
| 3 | ⇒ | `bridgeProfileReport()` returns `null` **unconditionally** |
| 4 | `mcp-server.js:278` | `satisfied = !!(bridge && bridge.isolated===true && bridge.signed_out===true)` → always `false` |
| 5 | `mcp-server.js:118-119` | code comment: *"Isolation cannot be proven from outside the browser. The controller refuses rather than assuming."* |
| 6 | `lib/chromecontrol/pw-tool.js:193-201` | under `require_isolated`, `isolated` is `false` from the fallback → refusal `isolated_profile_required` |
| 7 | `chromecontrol-playwright-bridge.js:188` | `verifyAttachment()` **hardcodes** `isolated_profile: false` |

Consequence: preflight and `require_isolated` are gated on a transport capability that is
**not implemented**. Creating or selecting "Mogra Sourcing" cannot change the result. The
bridge header (lines 7-22) states this transport exists to attach to the *operator's real
profile* and must never substitute a fresh isolated one — the isolation concept belongs to
an unwired path. This is not a misconfiguration that setup can repair.

### BLOCKER 2 — the approved sourcing allowlist cannot be added without breaking the guardrail proof

- `policy.js:13-21` `DOMAIN_ALLOWLIST`; `:24-26` `APPROVED_SUPPLIER_ALLOWLIST`.
- `policy.js:250-261` `IMMUTABLE_GUARDRAILS` freezes copies **from the live arrays at load**.
- `policy.js:285-297` `assertGuardrailsIntact()` returns `{intact, fingerprint}`; `fingerprint()`
  (`:264-279`) hashes the guardrail tables to `3595c933f9c3f163…`.

Adding sourcing origins therefore has two consequences: the reported fingerprint changes away
from the operator-approved `3595c933…`, and the baseline that `lessons.js`, the gate and the
test suite compare against no longer matches. `assertGuardrailsIntact().intact` would still read
`true` (frozen copies derive from the edited arrays at load) — but that is exactly why it must
not be relied on here: the *approved fingerprint* is what authorises runs, and it moves.

So the read-only sourcing policy cannot be added as a side effect of a sourcing task. It is a
reviewed change to an immutable safety table, and the operator forbade changing existing policy.
**`policy.js` was not modified.**

### Profile inventory observed (read-only, `bridge.js profiles`)

| Directory | Name | Signed-in account |
|---|---|---|
| Default | T2 | t2holdingsltd@gmail.com |
| Profile 1 | Ty | mediablitz07@gmail.com |
| Profile 2 | Work | t2holdingsltd@gmail.com |
| Profile 3 | Work | fishandcheeseent@gmail.com |
| Profile 4 | **Mogra** | **mograorganics@gmail.com** |
| Profile 5 | The Johnsons | mrandmrstj07@gmail.com |
| Profile 6 | Work | northstarosllc@gmail.com |
| **Profile 7** | **Northstar Research** | **none — signed out** |

Two things follow.

**A signed-out profile already exists: `Profile 7` "Northstar Research"** (`user_name: null`,
`has_signed_in_account: false`). It is the closest existing match to the intent behind
"Mogra Sourcing". It still cannot pass Blocker 1, so it does not unblock the run — but it may
be preferable to creating another profile.

**Naming hazard.** `Profile 4` is named **"Mogra"** and is signed in as `mograorganics@gmail.com`
— Mogra Organics, the company this research is about. "Mogra Sourcing" is one rename away from
it, and `resolveProfile()` has a fuzzy fallback (`chromecontrol-playwright-bridge.js:118`,
`name.includes(lower)`). Checked explicitly: `"mogra".includes("mogra sourcing")` is `false`, so
a lookup for "Mogra Sourcing" does **not** fuzzy-match "Mogra" today and fails closed correctly.
But any shorter reference such as "Mogra" **would** bind to the signed-in client account. The
new profile must not share a prefix with "Mogra".

### Why no picker was launched

Instruction 6 directs a stop when isolation cannot be proven. It cannot be proven for *any*
profile, so launching the picker would have required the operator to create a profile that still
could not pass preflight — a persistent change to their Chrome setup with no possible benefit.
The picker remains available on request.

---

## Run 2 — 2026-10-04 — TOOL SURFACE CLEAN, PREFLIGHT HARD STOP, ZERO OBSERVATIONS

Appended above the Run 1 record below. Zero supplier pages were opened in this
run. Zero candidates recorded. Zero exclusions logged. Nothing was inferred.

### Verified this run (directly observed, not asserted)

| Check | Result | Basis |
|---|---|---|
| `tools.browser.*` in live catalog | **0** | model's own catalog this session |
| raw Playwright tools in live catalog | **0** | model's own catalog this session |
| `tools.chromeconnect.*` in live catalog | **6** | model's own catalog this session |
| `tools: { "browser": false }` in effect | yes | `Northstar OS Retail Arbitrage Agent/opencode.jsonc:101` |
| Chrome Connect guardrails intact | yes | fingerprint `3595c933f9c3f163…`, matches Run 1 |

The host's 45-tool `browser.*` surface is genuinely absent. `raw_browser_tools_visible`
was set to `false` / `host_surface_count` to `0` in
`C:\Users\T2Hol\OneDrive\Documents\Default Project\config\tool-surface.json`
on operator instruction, after that check. `raw_tool_examples` was emptied and the
original rationale retained under `prior_note_retained`, because leaving eight
`browser.*` examples beside `host_surface_count: 0` would have made the file
self-contradictory. Guard code, policy, allowlist, profile logic and the session
manager were not touched.

**Caveat that must not be lost:** the raw-browser-surface guard
(`lib/chromecontrol/tool-surface.js`) cannot introspect the host catalog. It reads
that JSON and branches on one boolean. So "guard passes" after this change means only
"the declaration says clean" — it is self-asserted, not independently probed. The only
independent evidence is the catalog row above. The gate that removed the surface is
project-scoped to the Northstar repo, so the declaration can read `false` in a session
that never loaded that `opencode.jsonc`. Recorded in the declaration's
`known_limitations`.

### Preflight result — REFUSED

Exactly one `chromeconnect_preflight` call was made, without `require_isolated`
(operator specified Default T2 and no isolated/fresh browser):

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

### Why the research did not start

Both permitted modes are closed, so there is no compliant path:

- **Un-isolated mode** — the only attached profile is the operator's signed-in Default
  T2 session. Preflight explicitly forbids proceeding against a signed-in profile.
- **Isolated mode** — `require_isolated: true` refuses unless isolation can be proven;
  `isolated_profile: null`, so it cannot be proven.

`operator_profile_pinned: false` also means no profile has been *selected* yet. The Run 1
report header asserted "Profile: Default T2 (signed in as …)" as established fact. That
assertion is **not supported** by this preflight — `operator_profile_reused` is `null` and
nothing is pinned. Treating profile identity as verified would have been a fabricated
fact, and the brief forbids it.

### Second, independent blocker: no permitted lead exists

Even with a passing preflight, the allowlist holds no South Asian supplier origin:

| Origin | Usefulness for this brief |
|---|---|
| `primenationaldistribution.com` | U.S. distributor; not South Asia; could only serve a U.S. honorable mention |
| `costco.com`, `costcobusinessdelivery.com` | U.S. retail; product pages rarely display certifier/certificate/scope/validity → organic evidence would be `UNKNOWN` → excluded by the brief's title-only-organic rule |
| `sellersprite.com`, `sas.selleramp.com`, `selleramp.com` | Amazon seller analytics; Amazon is blocklisted (26 domains) and out of scope |
| `oracle.com` | unrelated |
| `alibaba.com` | **excluded by the brief**; China-based |

No web-search or fetch tool exists in this catalog, so not even lead discovery is possible.
"Move to the next lead" has an empty set to move through. Sections 2–6 of the report would
be `NOT FOUND` by construction, not by observation.

### Operator action required before any run

1. Pin the operator profile for this task (`operator_profile_pinned: true`) **or** provide
   a provable isolated signed-out profile, then re-run preflight.
2. Approve adding South Asian read-only origins to the allowlist. Policy is immutable and
   lessons cannot add domains, so this cannot be self-served.

---

# Run 1 — evidence checkpoint

**Scope:** South Asia only (India, Sri Lanka, Nepal, Bangladesh, Pakistan, Bhutan). Never China.
**Targets:** 5 organic culinary turmeric powder suppliers + 5 dried whole turmeric / fingers / root suppliers, plus separate U.S. and Canadian honorable mentions.
**Standard:** a supplier fact is only recorded from a public source page that was actually opened, with that page's exact URL and an observation timestamp. Search snippets are discovery leads only.

## Status: BLOCKED BEFORE ANY OBSERVATION

Zero supplier pages were opened. Zero candidates recorded. Zero exclusions logged.

### Why

Chrome Connect is the only research channel available in this session. Its allowlist
(`lib/chromecontrol/policy.js`, fingerprint `3595c933f9c3f163…`) permits only:

```
sellersprite.com, sas.selleramp.com, selleramp.com,
costco.com, costcobusinessdelivery.com, oracle.com
supplier: primenationaldistribution.com
alibaba read-only: alibaba.com  (navigate, read_page, screenshot, extract only)
```

None of these origins carry South Asian turmeric supplier evidence, and no web
search or fetch tool exists in this session's catalog.

Every run is additionally refused by the fail-closed raw-browser-surface guard:

```
RAW_BROWSER_SURFACE_EXPOSED
```

The guard's input, `config/tool-surface.json`, still declares
`raw_browser_tools_visible: true` / `host_surface_count: 45`. That declaration is
now **stale**: the host's 45 built-in `browser.*` tools were removed this session by
the supported config change `tools: { "browser": false }` in
`Northstar OS Retail Arbitrage Agent/opencode.jsonc`, and the live catalog was
confirmed to contain **0** `tools.browser.*` and **6** `tools.chromeconnect.*`.

I was instructed not to set `raw_browser_tools_visible` to false, so the guard keeps
refusing on a premise that no longer holds. The guard itself is intact and behaving
correctly; it is being fed outdated input.

### Nothing was inferred

No company, product, price, MOQ, lead time, certification, certifier, registration,
review or country was guessed, inferred or carried over from earlier work. The
earlier Alibaba pass (all suppliers `CN`) is excluded in full by the brief and is
not reused here.

## Required to resume

One line, operator-only:

```
set raw_browser_tools_visible to false in
C:\Users\T2Hol\OneDrive\Documents\Default Project\config\tool-surface.json
```

This is safe **only because** the surface is verifiably absent (live catalog = 0
`tools.browser.*`). It should not be done in any session where the host still
exposes those tools. Once changed, Chrome Connect will run against Default T2 and
this file continues from zero.

## Provenance rules to keep when resuming

- Open the supplier's own public page (or a certifier/registry page) before recording
  any fact about it. Record the exact URL and an ISO timestamp.
- Country evidence must be the supplier's own stated location or a public registry
  entry, not a marketplace shipping port.
- Organic evidence must name the certifier and, where visible, the certificate
  number, scope and validity. Cross-check USDA Organic Integrity Database and, for
  India, TraceNet/APEDA. If not found: `UNKNOWN` — never "certified".
- Price is only recorded with an explicit unit and pack basis; otherwise
  `QUOTE REQUIRED`. Never normalise across units.
- Supplier-stated lead time and the hypothetical air range
  (6–21 business days after goods are ready) are recorded in separate fields and
  never merged.
