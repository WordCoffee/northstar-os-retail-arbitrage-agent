# Self assessment

Written when the stuck rule fires (5 consecutive cycles across all workstreams with
nothing merged), and after each unit. No optimism: measured state and cause.

## 2026-11-07 — D0

Director program started from `reports/ty/director_work_order.md` (saved verbatim).
Rollback tag `director-baseline` made before any unit work.

The previous autonomy loop shipped one bundle end-to-end (cycle 45, commit `1f6e0e89`,
tag `autonomy-cycle-45`) and then starved honestly. The cause was not the loop: every
remaining item had an acceptance check that was already green or pointed at a file that
did not exist, and a check that cannot be red cannot prove a patch. That is the gap this
order exists to close — derive work from the mandate and score it, instead of waiting for
a defect scanner to find something.

The old loop is halted with `STOP` so the baseline measurement is clean; D2 replaces it.
