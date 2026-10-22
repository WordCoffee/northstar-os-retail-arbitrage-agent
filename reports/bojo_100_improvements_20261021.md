# Bojo — 100 new improvements for request handling, modes and production

**Date:** 2026-10-21 · **Branch:** `feature/v4.1-mesh`
**Scope:** additive to `reports/improvement_register_500_20261019.md` (which covers
tests, data, DB, auth, ops). Nothing here repeats those 500 items.

**North-star metrics for this register**
- `thinking_tokens / accepted_answer` — lower is smarter.
- `chatter_ratio` — output tokens that are not answer content. Target **< 5 %**.
- `first_token_s` — p50 < 1.5 s, p95 < 3 s.
- `answer_acceptance` — % of turns the operator does not regenerate or correct.

Every item is written as **Action → Verify**, so it can be closed with evidence.

---

## 1. Mode architecture — creative / standard / thinking (1–15)

1. Add `mode: creative|standard|thinking` to `TurnIn` as a **first-class field**
   orthogonal to the `thinking` effort. Verify: OpenAPI shows it; invalid value 422.
2. Server-owned `MODE_CONTRACT` map (directive + effort + temperature + tool policy
   + answer budget), mirroring `_THINKING_HINT`. Verify: unit test per mode.
3. **Creative**: 3 options by default, one-line rationale each, no self-verification,
   temp 0.8, medium effort. Verify: golden prompt returns exactly 3 options.
4. **Standard**: answer-first, ≤1 clarifying question, temp 0.35, medium + discipline.
   Verify: no preamble in first 40 chars on golden prompts.
5. **Thinking**: plan → verify → answer, explicit assumptions, temp 0.2, xhigh.
   Verify: golden math/code set passes at ≥90 %.
6. Mode-aware tool allowlist: creative gets image/video/pricing; thinking gets
   research/DB/verification; standard gets the union minus destructive tools.
   Verify: tool list in the SSE `start` frame differs per mode.
7. Mode-aware answer budget (creative 120 words/option, standard 120, thinking 400).
   Verify: p95 completion tokens per mode within ±15 %.
8. Persist the mode per session, override per turn. Verify: reopening a session
   restores the badge; a one-off override does not mutate the session.
9. Keyboard shortcuts 1/2/3 in the composer + a tooltip stating the tradeoff.
   Verify: Playwright asserts mode changes without a mouse.
10. Mode telemetry: tokens, latency, regenerate rate, follow-up rate per mode.
    Verify: `/api/ops/status` exposes the four aggregates.
11. Golden set per mode (20 prompts each) run in CI. Verify: 60 prompt→expectation pairs.
12. Clarification policy per mode: creative produces a draft first, thinking may ask
    one question, standard answers then offers refinement. Verify: prompt fixtures.
13. `auto` mode: classifier selects creative/standard/thinking and the UI shows **why**
    ("code detected → thinking"). Verify: 20-case routing table.
14. Mode presets bound to the six work foci so the operator chooses once.
    Verify: switching focus sets the default mode and shows it.
15. A/B each mode against the current default on the same 20 prompts; keep the winner.
    Verify: recorded acceptance + latency table.

## 2. Overthinking control (16–30)

16. Split the output budget: `thinking_allowance` + `answer_reserve` so an answer can
    never be starved by reasoning. Verify: forced long-reasoning prompt still answers.
17. Soft convergence instruction: "if not resolved in ~300 words, answer with the best
    hypothesis and name the uncertainty". Verify: median thinking tokens drop ≥25 % on
    the hard set with no accuracy loss.
18. Two-pass escalation: run medium first; escalate to xhigh only when a self-check
    fails or the model flags low confidence. Verify: hard-set accuracy within 2 pts,
    mean latency down ≥30 %.
19. Self-check only on checkable outputs (math, code, data claims), never on creative
    copy. Verify: creative mode makes zero verification passes.
20. Loop detection: if reasoning repeats a step, inject "already established" once.
    Verify: synthetic repeat prompt terminates earlier than baseline.
21. Per-mode thinking caps (creative 600, standard 1,500, thinking 4,000 tokens).
    Verify: p95 thinking tokens under cap per mode.
22. Pre-turn estimate: show "≈15 s / 90 s / 5 min" from intent + length, with a
    one-click downgrade. Verify: estimate error < 2× on 20 turns.
23. Compress tool results before they re-enter context (summarise >2 KB outputs).
    Verify: prefill tokens per tool round drop ≥40 %.
24. Context pruning: keep only the last two tool results unless referenced.
    Verify: long tool chains stay under the context budget.
25. Session answer cache: identical question + unchanged data returns the prior answer
    with "answered at HH:MM". Verify: second identical turn <1 s.
26. Early stop: if the answer already satisfies the contract, stop the stream.
    Verify: completion tokens drop on the simple set without acceptance loss.
27. Verification loops capped: 0 (creative), 1 (standard), 2 (thinking).
    Verify: counters in telemetry.
28. On truncation, retry once at **lower** effort with a narrower question (we already
    detect `done_reason=length`); never repeat the same expensive run.
    Verify: truncation→recovery test.
29. Post-hoc restatement stripper (server-side) for the first paragraph.
    Verify: fixture with a restating answer is normalised.
30. Track `thinking_tokens_per_correct_answer` per mode/model; alert on regression.
    Verify: daily aggregate in the ops surface.

## 3. Killing useless chatter (31–42)

31. **Answer-first contract**: the first token is the answer, not a preamble.
    Verify: first 40 chars contain no banned opener on 50 prompts.
32. Banned-phrase list (~30: "Great question", "Sure!", "Let me", "I'd be happy to",
    "As an AI", "In conclusion") enforced by a server-side stripper.
    Verify: fixtures + a lint over stored messages.
33. No tool narration; progress is an SSE event, not prose. Verify: no "I'll search"
    in the transcript during a tool turn.
34. No closing filler unless the turn is a plan/quote. Verify: last sentence lint.
35. Length budget enforced per mode, truncated at a sentence boundary, with "more".
    Verify: p95 word count per mode.
36. **One-question rule**: at most one clarifying question, only when the answer would
    otherwise be wrong. Verify: ≤1 `?` sentence in 95 % of turns.
37. Never echo the operator's message back. Verify: n-gram overlap check.
38. Never list capabilities unless asked. Verify: golden prompt "what can you do".
39. Formatting discipline: no headers under 5 lines; bullets only for ≥3 items.
    Verify: renderer test on fixtures.
40. `chatter_ratio` metric persisted per message. Verify: dashboard + target <5 %.
41. A/B prompt-level suppression vs post-processing; keep the one with higher
    acceptance. Verify: recorded experiment.
42. Honest dead-end template: one line ("I don't have that data") + the next step.
    Verify: golden prompt with unknown data.

## 4. Understanding the request (43–54)

43. Local intent classifier (rules + 0.6B embed model): create / research / operate /
    explain. Verify: 100-case labelled set, ≥90 % accuracy, <100 ms.
44. Ambiguity detector: two plausible readings → one question (thinking) or both
    variants (creative). Verify: fixture pairs.
45. Missing-info checklist per intent (listing: brand, product, size, keywords;
    ad: channel, hook, offer). Verify: 20 prompts produce the right checklist.
46. Turn-slot extraction (brand, product, channel, budget, deadline) into a structured
    object attached to the turn. Verify: JSON schema + 20 fixtures.
47. Reference resolution for "that one / the second / the last image" against recent
    artifacts. Verify: 10-turn reference fixture.
48. Follow-up vs new-topic detection so the assistant stops re-asking known facts.
    Verify: repeated-fact prompt does not re-ask.
49. Language mirroring + locale number/date formatting. Verify: one prompt per locale.
50. Urgency detection ("asap") → draft mode, with the tradeoff stated in one line.
    Verify: urgency prompt yields draft + tradeoff.
51. Scope guard: live/paid actions return the exact approval phrase, not a refusal
    essay. Verify: purchase/listing prompts.
52. Spend gate: no credit-consuming job without an explicit confirm in the turn.
    Verify: plan card requires a click; API test rejects a bare execute.
53. "Explain your last answer" reuses the stored trace instead of re-running the model.
    Verify: zero model calls on that intent.
54. Persist the parsed intent with the turn so "why did it do that?" is answerable.
    Verify: trace panel shows intent, mode, tools, tokens.

## 5. Tool use and grounding (55–66)

55. Tool-first for factual questions: call the data tool before answering, never guess.
    Verify: 20 factual prompts produce a tool call.
56. Provenance in the answer ("from your catalog: 12 SKUs"). Verify: citation present
    when a tool returned data.
57. Tool failure → honest one-liner + retry path; never a fabricated result.
    Verify: forced failure test.
58. Per-mode/focus tool schema trimming to cut prefill. Verify: prefill tokens per
    turn down ≥30 %.
59. Parallel independent tool calls. Verify: two-tool prompt completes in ~max(t1,t2).
60. Tool budget per turn + "needs another step" message instead of silent stop.
    Verify: budget counter in telemetry.
61. Session cache for idempotent reads. Verify: repeated read = 0 calls.
62. Validate tool args against the schema before execution. Verify: malformed args
    rejected with a clear message.
63. Dry-run for destructive tools (publish, price change). Verify: dry-run returns a
    diff, executes nothing.
64. Human-readable progress (phase + %), never raw logs. Verify: SSE payload schema.
65. Result diffing for monitoring ("changed since yesterday"). Verify: two snapshots
    produce a diff.
66. Cited Amazon policy claims (link + effective date), never invented rules.
    Verify: policy answer contains a source and date.

## 6. Memory and personalisation (67–74)

67. Facts carry confidence + `last_verified`; stale facts expire. Verify: TTL test.
68. "Remember this" / "forget that" commands with confirmation. Verify: 2 prompts.
69. Session close summary (5 bullets) feeds the next session. Verify: next-session
    context includes it.
70. Learn from edits: if the operator always shortens, default shorter. Verify:
    preference counter changes the budget after 5 edits.
71. Conflict detection ("last week you said X"). Verify: contradictory facts prompt.
72. Retrieval trace: "why did you say that?" → source rows. Verify: trace panel.
73. Scrubber on ingest: never store secrets/PII. Verify: fixture with a key-shaped
    string is rejected.
74. Memory inspector (list/edit/delete) in the UI. Verify: Playwright CRUD.

## 7. Production readiness (75–86)

75. Latency SLOs per mode (p50/p95) with alerts. Verify: metrics endpoint + alert rule.
76. Error budget: % turns ending in fallback/truncation, tracked daily.
    Verify: dashboard, alert at 2 %.
77. Golden set of 100 real operator requests with expected behaviours, run per change.
    Verify: CI job, <10 min.
78. Shadow eval: new prompt vs old on the same 100, no user impact.
    Verify: report diff.
79. Prompt version registry (hash + changelog) so regressions are bisectable.
    Verify: every turn logs a prompt version hash.
80. Model registry: name, quant, ctx, VRAM, speed, licence in one file.
    Verify: health surface reads it.
81. Degradation ladder: xhigh → medium → off → honest error. Verify: forced failures
    walk the ladder.
82. Per-account rate limit + render queue with position. Verify: queue depth API.
83. Idempotency keys on turns (no double charge on retry). Verify: replay test.
84. Crash recovery: resume a streamed turn from the last persisted token.
    Verify: kill mid-stream, reopen, no duplicate message.
85. Bojo health surface: model loaded, VRAM free, queue depth, voice engine, embed lane.
    Verify: one endpoint, one UI badge.
86. Runbook: ten failure modes with the first command for each. Verify: doc + drill.

## 8. UI visual fidelity (87–96)

87. Screenshot harness: 3 breakpoints × 3 themes, baselines committed, diff on change.
    Verify: one command produces a delta report.
88. Visual token spec (type scale, spacing, colour, radii) + a test that fails on
    off-spec values in CSS. Verify: CSS lint.
89. Gargantua fidelity check: lensing, Doppler asymmetry, photon ring against film
    frames at three angles. Verify: side-by-side sheet, human sign-off.
90. Canvas never reduces text contrast: automated AA check at every scroll position.
    Verify: contrast test over the canvas.
91. Simple mode measured in the DOM: 16.5 px / 820 px, not just declared.
    Verify: Playwright computed style.
92. Mode switcher visual: three states, one-line tradeoff, no ambiguity.
    Verify: screenshot + keyboard test.
93. Streaming feel: first token <1.5 s; typing indicator only after 400 ms.
    Verify: timing trace.
94. Designed error states (model down, voice down, queue full) each with a next action.
    Verify: 3 mock states.
95. Mobile 390 px: composer + canvas, no horizontal scroll, thumb-reachable send.
    Verify: Playwright viewport test.
96. "Why this took 5 minutes" panel: mode, thinking tokens, tool calls, model.
    Verify: panel opens from the message menu.

## 9. Domain knowledge and research pipeline (97–100)

97. Standing scanner (reuse `tools/scan_video_ecosystem.py`) for Amazon SP-API, Ads API,
    listing tooling and image-gen repos; monthly diff with a shortlist.
    Verify: scheduled run writes a dated report.
98. Amazon knowledge pack: policy, fee rules, listing requirements, ad specs as
    versioned snapshots with effective dates and citations.
    Verify: every policy answer cites pack version + date.
99. Image-gen eval: 20 product prompts × 3 engines, scored on label fidelity, realism,
    brand fit; choose per job type. Verify: scored matrix, no engine chosen by vibes.
100. Ad creative library: hook / angle / CTA templates per platform (Amazon, Meta,
     TikTok) that Bojo instantiates. Verify: 10 templates, each with a filled example.

---

## First twelve (ship in this order)

| # | item | why first |
|---|---|---|
| 1 | mode field + server contract | everything else keys off it |
| 31 | answer-first contract | hours, large perceived quality gain |
| 16 | split thinking/answer budget | removes the empty-answer class |
| 32 | banned-phrase stripper | measurable chatter drop |
| 55 | tool-first grounding | kills invented facts |
| 43 | intent classifier | makes `auto` mode possible |
| 77 | 100-turn golden set | no more subjective "feels better" |
| 87 | screenshot harness | settles the visual question with pixels |
| 97 | standing scanner | keeps the ecosystem shortlist current |
| 18 | two-pass escalation | speed without quality loss |
| 80 | model registry | ends config drift |
| 94 | designed error states | production feel |

## What "production ready" means here

A turn is production-ready when: first token < 1.5 s (p50), chatter < 5 %, no empty
answer on the hard set, every factual claim traceable to a tool result, every failure
has an honest state in the UI, and the Golden 100 pass on the current commit.
