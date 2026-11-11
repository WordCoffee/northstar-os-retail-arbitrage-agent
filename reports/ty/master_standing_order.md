# MASTER STANDING ORDER — run Northstar OS to launch (Nov 11 to Nov 30, 2026)

This replaces the habit of the owner relaying review notes. Ty does that review itself, every
cycle, and only stops for the owner-only items below. Save this verbatim to
`reports/ty/master_standing_order.md` and re-read it at the start of every session.

Model: DeepSeek V4.1 Flash 1017, pinned, logged in every digest and handoff; never switch
silently. Verifier on a different model if available. No questions. No chat reports between
units. A text-only reply while the queue has items is a failure. Idle means re-plan.

1. Rules that never change
Hard lines: no Amazon properties, no money, no credentials, no invite-gate or admin bypass, no
paid-model actions, no hook bypass, no force-push, no history rewrite, no key rotation, no repo
visibility changes, never print secret values. Irreversible external actions go to needs_you.md.
One director per queue. Write the lease first, then stop anything else. A restore point exists
before every unit.
Builder count follows the free-RAM governor; one GPU lane; only code changes trigger full
suites; visual and creative bundles go to staging review packs, never straight to main.
Quarantine, never delete. Never lower a bar, weight, or assertion without a logged reason and
verifier sign-off.
2. What "launch-ready" means (per core service)

A service is launch-ready only when ALL are true, each with command output:

A Playwright click path does the seller's real job end to end (desktop Chromium and iPhone 12
WebKit), persists the result, and reads it back.
The seller and correct dimensions are measured on real briefs or seeded data, never assumed.
The service has its own purpose-built workspace in the shell (not the generic chat page), with
the scene events, DevBanner, canUseService stub, and open-tab context reaching Bojo.
Every Bojo tool it declares is wired and offered; every status badge is derived from a real
probe, never hardcoded; failures show "unavailable", never a plausible default.
The independent verifier reproduced the numbers.

Report two numbers separately and never merge them: scorecard at-bar (a measurement of the
scorecard) and launch-ready (all five above). 22 of 29 at-bar means nothing for launch until
the core six pass the five gates.

3. Priorities, in order, with dates

Core six: Listings, Product pictures, PPC, Golden Goose, Research, Design Studio.

Today: reconcile tool offering. An earlier report said all seven reg-03 handlers were offered
(44 wired, 0 declared); test_tool_offering.py now fails 8 because plan_campaign and
scan_products and others look unwired. Find out whether the work was lost in a merge or the
claim was wrong, fix it, and write the answer in the digest.
By Nov 20: the six core service workspaces (block3), each with its click-path test. Then the
remaining services by Nov 24 on default scene plus workspace.
In parallel from now: seller end-to-end tests (block4) for the core six, one per service,
deterministic checks first.
By Nov 24: production hardening (block5): production bundle assertion, health and readiness,
backup and restore test, rate limits and error pages, performance budgets, accessibility gate on
core routes, credit-gate stub that deducts before the job runs, docs/UX_SYSTEM.md, runbook.
Anything needing payments, hosting, or a domain goes to needs_you.md as one exact action.
Product pictures: finish D-021 and D-022 (shadow and white composite), then stop. Time-box: two
days total, then record what is left and move on.
If not already done: Ollama bind and firewall check (set to 127.0.0.1 unless LAN use is stated,
old value in the restore file), engine probe "unavailable" state with a test,
swallowed-exception scan, shared .badge styles, replace hardcoded "live" badges.
The 6 queued small fixes (fix-product-finder-wiring, fix-seller-offer-caption,
fix-golden-goose-scoring, fix-chat-composer-spec, retire-goldengoose-alias,
fix-po006-stray-dashes) are bundled into ONE unit, not six.
Freeze Nov 25: bug fixes and hardening only. Nov 30: final report stating each core service's
measured launch state plainly, including anything not ready.

4. Daily routine (run it yourself, no prompt needed)

Start of day: re-rank by what blocks launch for the core six, using the launch-ready gates. End
of day: write the digest. Each cycle: bundle the largest coherent change set; no micro-edits; no
unit longer than one day; measurement-tooling work (scorers, instruments, audits) is capped at
20% of cycles unless it blocks a core service. If a unit overruns, record why and move on.

5. Self-review pass (this replaces the outside reviewer)

After every merged unit, before starting the next, check and record in the digest:

Does the headline claim match what was measured? Quote the measurement.
Is any number blended across modes or sample types? Split it.
Did any test assertion get weaker? List each with the reason.
Any exception swallowed into a plausible default? Any hardcoded status?
Is anything declared but not wired, or built but not offered or reachable by click?
Any new listening port, secret-shaped string, license problem, or file written outside scope?
Is a score gaming a cheap dimension (a handler exists, a file exists) instead of a seller
outcome? Say so.
Do public or reference images used for evaluation stay eval-only with license and attribution on
file?

Fix anything found in the same unit or queue it with a rank. Never leave a finding unrecorded.

6. Owner digest (daily, reports/ty/digest_<date>.md, top section)
Launch table for the core six: scorecard score, launch-ready gates passed (x of 5), what blocks
it, days left.
What changed today: merged units, per-mode picture results with n, pass, mean.
Needs you, max 3, one exact action each: keys to rotate and repo to make private (until done),
unlock the desktop for V3/V9, a reboot for the proof, Openverse key if still needed, the missing
uploaded-reference product photos (use existing Mogra and Word Coffee photos first; ask only for
what does not exist). Never block the queue on these.
Risks: minimum free RAM, token use against the daily cap, model id.
7. Stuck rules

Three failed attempts: quarantine with a diagnosis and take the next independent job. Five
cycles with nothing merged: write a diagnosis to self_assessment.md, change approach, and
continue. Never idle while any core service is below the launch-ready gates.

8. Start

Resume line for a fresh session: "Hi, I'd like to give a work order to Ty. Resume the director
program under the master standing order. Read reports/ty/master_standing_order.md, ty/MANDATE.md,
reports/ty/director_queue.json, reports/ty/handoff.md, and needs_you.md, then continue from the
first unfinished unit."

Begin with item 1 of section 3 now.
