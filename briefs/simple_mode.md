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

**Brief approved 2026-10-24.** The flow is signed off once S1–S7 are shown with evidence; that is
verification, not design.

| Check | Evidence | State |
|---|---|---|
| S1 | desktop capture; mobile capture now expressible (`screenshot <path> @390x844`) | desktop done, mobile pending one run |
| S2 | pre-flight card | pending capture |
| S3 | question state | pending capture |
| S4 | mid-run tool progress | pending capture |
| S5 | downloadable file + change log | artifact exists (`2136ae5b…`); change-log surface pending |
| S6 | SEO tie-in on the result card | pending capture |
| S7 | Autothink handoff with a brief | `specialists/router.py scope()` returns the offer + estimate; no transport yet |
