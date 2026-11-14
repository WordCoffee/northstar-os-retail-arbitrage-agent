# `scorecards --json` — the help told the truth, the code did not (2026-11-14)

**Outcome: closed.** `tools/scorecards.py --json` is documented as "measurement only" but
wrote `ty/scorecards.json` and `ty/TARGET_SPEC.md` on every run. That is how the previous
unit's refresh was applied before its diff was taken, and the earlier verifier had already
noted the same behaviour (`reports/ty/d15_verification.md:426`).

## What changed

| command | before | after |
|---|---|---|
| `scorecards.py` | measures, writes both files, prints the summary | unchanged |
| `scorecards.py --json` | **wrote both files**, printed the score map | writes both files (now documented), prints the score map |
| `scorecards.py --no-write` | did not exist | **measures and prints; neither file is touched** |

`--json` keeps writing because an existing documented workflow depends on it
(`reports/ty/sel01e_checks.md` runs `seller_scores.py --write` then `scorecards.py --json` on
the same data). The docstring and argparse help now say so, and `--no-write` provides the
measurement-only command the docs had promised.

## Measured

- `python -m pytest test_scorecards.py -q` → **12 passed** (2 new: `--json` writes and prints;
  `--no-write` leaves both files absent).
- The wider scorecard group → **59 passed**, exit 0.
- `python tools/scorecards.py --no-write` on the live repo → exit 0, and `git status ty/` is
  empty: the published scorecard and spec are untouched.

No Amazon, no spend, no GPU, no browser, no credential read. Soak, quiet-window waiter and
`state/vision/PAUSE` untouched.
