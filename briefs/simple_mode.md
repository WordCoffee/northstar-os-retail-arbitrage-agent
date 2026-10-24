# Brief — Simple Mode flow (§11B.1, §11C)

**In the operator's words:** *"Users interact through Simple Mode: a chat box with filters
(Creative, Grow/Research, Operate) plus an Auto option… Bojo is a router… It handles Creative, Grow
and Research, and Operate work, small utilities like a calculator app, and chained multi-agent jobs.
Serious coding and task management belong to Autothink."*

## Intended experience

One box. You type what you want; Bojo decides whether to answer, build, or hand off. Before it
spends time or credits it tells you **what it will do, which specialists, what it still needs, and
what it will cost**. While it works you see honest progress. When it finishes you get **files you can
download** and **a change log**, plus how the result ties to your keywords.

## Pass/fail checks (7)

| # | Check | Evidence |
|---|---|---|
| S1 | Composer is the largest control on screen; one row of controls, options collapsed | desktop + mobile screenshot |
| S2 | A heavy request shows **plan + agents + missing inputs + estimated cost BEFORE** work starts | screenshot of the pre-flight card |
| S3 | Missing inputs are asked as **questions**, and nothing is invented to fill them | screenshot of the question state |
| S4 | Live progress is visible per tool run (not a spinner pretending to work) | screenshot mid-run |
| S5 | A completed job returns a **downloadable file** and a **change log** | artifact + screenshot |
| S6 | Every output shows its **SEO tie-in** (keywords covered / missing) | screenshot of the result card |
| S7 | A large engineering request is **handed to Autothink with a brief**, not attempted | screenshot of the handoff |

## Two routing tests added to the suite

- **BOJO-UTIL**: "make me a quick tip calculator" → Bojo builds it (no handoff).
- **BOJO-CODE**: "refactor the listings service to async and add tests" → Autothink handoff + brief.

## Non-goals

Bojo does not become an IDE. It does not perform multi-file refactors, test-suite surgery or task
management.

## Sign-off

Operator approves this brief before the Simple Mode changes; final sign-off on the flow after
screenshots.
