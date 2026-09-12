# Northstar OS / T2 Holdings — Agent Prompt Batch

A single master file of prompts you can paste into OpenHands (or any autonomous coding agent) when working in your sandboxed copy of the Northstar OS / Retail Arbitrage project.

## Global Safety Prompt (include with every session)

```text
You are an autonomous coding agent working in a sandboxed copy of the Northstar OS / T2 Holdings repo.

Non‑negotiable rules:
- Do NOT read, write, or create .env files.
- Do NOT make real network/API calls (Costco, Scavio, Amazon, Easyparser, Bright Data, etc.).
- Do NOT change finance.py, pricing.py, product_analysis.py, or the CSV contract without explicit permission.
- Do NOT touch production data exports or live keys.
- Treat yourself as a junior developer: plan first, tests first, then smallest possible diffs.
- Every change must have offline tests and clear verification commands.

Before any work:
1) Inspect relevant files.
2) Propose a short plan with file list, behaviors, and test commands.
3) Wait for my approval.
```

## 1. Scanner Robustness & Fallback Behavior

```text
Task: Audit and improve the kirkland scanner pipeline for robustness when upstream enrichment (Scavio, Easyparser, Bright Data) is unavailable.

Steps:
- Find all code paths that depend on Scavio or offer enrichment.
- Ensure missing or exhausted credits produce explicit states like "upstream_unavailable" or "offer_enrichment_unavailable", never zeros or fake defaults.
- Preserve cached historical data where present; do not clear valid cache on failure.
- Add focused tests that simulate exhausted credits / enrichment disabled and assert:
  * No outbound API calls.
  * Scanner responses use honest Unknown/Unavailable labels.
  * Cached fields remain unchanged.
- Present a diff and the exact test commands you ran.
```

## 2. Costco API Client Hardening

```text
Task: Harden costco_api_client.py around the new count/country params and data envelope.

- Identify all call sites for the Costco API.
- Add validation and error handling for:
  * Missing or malformed count/country.
  * Unexpected response shapes (missing "data" envelope, partial records).
- Improve logging or internal reporting so a single failed refresh cannot silently skew catalog counts.
- Extend existing tests (no live calls) to cover:
  * Proper use of count/country.
  * Handling of empty or malformed responses.
- Keep CSV contract and buffered-cost logic exactly as‑is.
```

## 3. Pack-Size Conflict Detection & Review Queue

```text
Task: Strengthen pack_size_conflict handling across the stack.

- Locate where pack_size_conflict is detected and surfaced (backend + UI).
- Ensure conflicting rows:
  * Stay out of CSV exports used for purchase-authorized sourcing.
  * Are clearly flagged in the UI as "Held for review" with reasons.
- Add tests that:
  * Create synthetic pack conflicts.
  * Verify they are held, not forced into CSV.
  * Confirm stale/typo rows (like "Krikland") remain untouched.
- Propose a small internal "review queue" concept that can later be wired into a human workflow, but do not add storage or new APIs yet.
```

## 4. Margin Calculator Guardrails & UX Polish

```text
Task: Audit the Margin Calculator for safety and clarity.

- Confirm it never mutates Scout source-cost data or CSV values.
- Tighten input parsing:
  * Treat blanks as "not provided", not zero.
  * Enforce min/max ranges where appropriate (e.g., negative referral fee blocked).
- Improve tooltips to explicitly state:
  * Which inputs must come from invoices vs. discovery.
  * That calculator results are scenarios, not live commitments.
- Add tests (JS/TypeScript or harness-based) that:
  * Feed in edge cases (blank, NaN, negative values).
  * Assert outputs remain consistent and no source data is changed.
```

## 5. Risk Engine Calibration & Explainability

```text
Task: Make the Risk Engine more explainable without changing formulas.

- Inventory current inputs and thresholds for Low/Moderate/High.
- Add a structured "reason list" format:
  * Each reason should reference the underlying metric (margin, volatility, sourcing risk, account risk).
- Ensure the UI surfaces reasons in a consistent order and clearly separates "assumption-based" vs. "data-backed".
- Add unit tests for:
  * Each risk tier with constructed scenarios.
  * The presence and formatting of reasons for each tier.
- Do not alter any numeric thresholds; only improve clarity and coverage.
```

## 6. Cycle Planner Edge-Case Coverage

```text
Task: Cover edge cases in the Cycle Planner (days-of-cover, reorder point, triggers).

- Audit the math for daily rate, days-of-cover, and reorder points.
- Ensure null/unknown inputs propagate as nulls, not zeros.
- Add test scenarios for:
  * Extremely slow movers.
  * Extremely fast movers.
  * Zero sales, partial data, and sudden demand spikes.
- Surface a subtle UI hint when inputs are too sparse to trust derived suggestions (e.g., "Insufficient sales history for a reliable reorder point").
```

## 7. Portfolio View Safety & Concentration Caps

```text
Task: Strengthen Portfolio view so it cannot silently encourage single-ASIN overconcentration.

- Add non-binding "soft caps" per ASIN and per category based on configuration constants (e.g., no ASIN > X% of working capital).
- Have the UI show warnings when a scenario breaches caps ("Scenario exceeds single-ASIN exposure cap").
- Ensure portfolio data remains local/demo-only and cannot be mistaken for live accounting.
- Add tests that:
  * Construct scenarios with overconcentration.
  * Assert warnings appear and totals remain correct.
```

## 8. Audit Logs & Provenance for Scanner/Planner

```text
Task: Implement lightweight internal audit logs for key actions: scanner refreshes, margin calculations, risk runs, and cycle plans.

- Design a minimal logging schema (timestamp, action, inputs summary, source type: discovery vs invoice).
- Implement logging in a way that:
  * Does not leak secrets.
  * Can be toggled on/off via config.
- Add tests that:
  * Run representative flows.
  * Assert log entries are written and contain no sensitive fields (keys, full URLs).
- Do not add external logging services; keep it local and configurable.
```

## 9. Offline Test Discovery & Coverage Map

```text
Task: Build an internal "test coverage map" for the Northstar OS components.

- Enumerate current test files and map them to modules/features (scanner, Costco client, UI, risk, cycle, portfolio).
- Generate an internal report (Markdown or JSON) listing:
  * Which components have strong coverage.
  * Which have minimal or no coverage.
- Propose (do NOT implement yet) 5–10 high-value new test targets.
- Ensure the report generation itself can run as an offline command (e.g., python tools/test_map.py) and integrate with your automation pipeline.
```

## 10. UI Regression Harness Improvements

```text
Task: Enhance the UI test harness to better catch regressions in filters, sorts, and skeleton/error states.

- Review existing test_ui_display.cjs.
- Add scenarios for:
  * Theme toggling with reduced-motion settings.
  * Filter combinations that yield no results but should show honest empty-state messages.
  * Sorts with mixed null and non-null values to ensure cmpDesc behavior is consistent.
- Validate that unknown values never render as "$0" or misleading numbers.
- Keep existing test command structure; just extend coverage.
```

## 11. CSV Contract Sanity Checker

```text
Task: Implement a CSV sanity checker for the catalog file used by the scanner.

- Build a small script (python or Node) that:
  * Loads the CSV.
  * Validates required fields, types, and value ranges.
  * Flags anomalies (negative costs, zero weights, missing names).
- Integrate it as a pre-flight check in offline workflows (e.g., a "check-catalog" command before running certain tests).
- Add tests with synthetic CSV files containing anomalies and verify they are caught and reported clearly, not fixed automatically.
```

## 12. Source-of-Truth Separation (Discovery vs Invoice)

```text
Task: Create explicit guardrails between "discovery" and "purchase-authorized" data.

- Identify all places where costco_online discovery data is used.
- Introduce a helper module that:
  * Tags data as discovery vs invoice-confirmed.
  * Refuses to treat discovery data as fully trusted input for certain flows.
- Update code paths to call this helper rather than inline checks.
- Add tests ensuring:
  * Discovery-only data cannot drive certain scaling decisions without an invoice flag.
  * Invoice-confirmed rows behave as before.
```

## 13. Automation-Friendly Configuration Layer

```text
Task: Make key safety toggles automation-friendly without exposing secrets.

- Document and centralize config flags for:
  * Enrichment on/off.
  * Cache usage.
  * Logging/audit verbosity.
- Build a small config module that agents and scripts can read/write (within constraints), e.g., a YAML/JSON without credentials.
- Ensure config changes are themselves testable and that incorrect values produce safe defaults, not crashes.
```

## 14. Bug-Fix Ticket Template (Agent-Friendly)

```text
Task: Prepare a reusable "bug-fix ticket" template for coding agents.

- Create a Markdown template that includes:
  * Bug description.
  * Expected behavior.
  * Current tests that fail or need adding.
  * Files likely involved.
  * Commands to run.
- Use existing real bugs you've fixed as examples.
- Adjust prompts so the agent:
  * Always starts with a plan and test additions.
  * Never merges code without your review.
```

## 15. Feature Implementation Template (Agent-Friendly)

```text
Task: Prepare a reusable "feature implementation" template.

- Provide sections for:
  * Business goal (inventory velocity, risk visibility, etc.).
  * Acceptance criteria (UI states, backend behaviors, tests).
  * Non-negotiable safety constraints (no live APIs in tests, no formula changes, etc.).
- Include a checklist the agent must satisfy before presenting a diff:
  * Plan reviewed.
  * New tests written and passing.
  * No changes to restricted modules or secrets.
```

## 16. OpenHands Sandbox Smoke Test

```text
Task: Define a minimal "sandbox smoke test" prompt for OpenHands.

- The prompt should instruct the agent to:
  * List files in the mounted workspace.
  * Read a small subset (README, key test files).
  * Run a single offline test command (e.g., python -m unittest test_scanner_endpoint).
- Confirm behavior:
  * No .env access.
  * No network calls.
- Use this prompt as the first run on any new OpenHands setup to validate sandbox wiring before bigger tasks.
```

## 17. Vulnerability Scan + PR Workflow (Dry-Run Plan)

```text
Task: Design (do not fully implement yet) a vulnerability scan + PR workflow inspired by other agents.

- Identify a suitable scanner you could run locally.
- Draft an internal script or plan that:
  * Scans the repo.
  * Produces reports.
  * Suggests code changes in a separate branch or PR without direct commits.
- Ensure the plan includes:
  * Clear boundaries around dependencies vs application logic.
  * No external calls to production services.
- Summarize as a Markdown doc for later automation.
```

## 18. Agent-Assisted Workflow Documentation

```text
Task: Improve README / developer docs specifically for agent-assisted workflows.

- Add sections on:
  * Safe folders to mount in agents.
  * Restricted files/modules.
  * Approved test commands.
  * Typical ticket-to-change lifecycle using OpenHands.
- Include 2–3 example prompts from this batch so future automation runs are consistent.
```

## 19. Test Data Generators for Key Flows

```text
Task: Build small, deterministic test data generators for scanner, risk engine, and cycle planner.

- For each major component:
  * Create a function that returns a set of canonical test inputs (e.g., a few ASIN scenarios).
  * Use these in tests instead of ad hoc fixture definitions.
- Ensure generators live in a test-only module and never bleed into production paths.
- This will make it easier for agents to add or modify tests without breaking shared fixtures.
```

## 20. UI Accessibility & Performance Pass

```text
Task: Run an agent-driven accessibility/performance pass on the SPA.

- Have the agent:
  * Audit ARIA attributes, keyboard navigation, and reduced-motion support.
  * Check for unnecessary re-renders or heavy components in common flows.
- Propose micro-optimizations and a11y fixes with minimal code churn.
- Add at least one automated test or lint rule to prevent regressions (e.g., a11y linting).
```

## 21. Error-State UX Hardening

```text
Task: Make error/retry UX more explicit for scanner and enrichment failures.

- Ensure error banners:
  * Differentiate "no candidates" vs "pipeline unavailable" vs "enrichment disabled".
- Add tests covering each state to confirm banners and retry actions render correctly.
- Avoid phrasing that suggests the issue is on Amazon's side when it is a local config or credit exhaustion.
```

## 22. Cross-Component Consistency Checks

```text
Task: Add consistency checks across scanner, margin calculator, risk engine, and cycle planner.

- Verify that an ASIN's cost, sale price, and key attributes are consistent across components.
- Implement a small diagnostic view or script that:
  * Loads a few ASINs.
  * Cross-checks values and flags discrepancies.
- Keep it offline and internally focused; no new APIs.
```

## 23. Agent Performance & Cost Metrics (Manual Logging)

```text
Task: Start tracking agent-run tasks and their "value per run".

- For each automated prompt you use:
  * Log what task it tackled, how long it ran, and what useful artifacts it produced (tests, bugfixes, docs).
- Use this to decide which categories of prompts are worth automating more (tests, small features, refactors) vs which still need you directly (new sourcing strategies, financial model changes).
```

## 24. Future Prompt Slot (Editable)

```text
Task: Use this slot for your next custom T2 Holdings OS improvement.

- Describe the business goal clearly.
- Specify acceptance criteria and safety constraints.
- Follow the same plan-first, tests-first, sandbox-only pattern before allowing edits.
```