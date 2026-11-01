"""PROBE A — a hard budget must stop AT the limit, not one step past it.

`agent_kernel.budget.BudgetTracker._check` compares with `>` after incrementing,
so `max_steps=3` allows a fourth step and `max_tokens=N` allows N+1. The module's
own contract is "a limit is a stop, not a warning".

Required behaviour:
  * after exactly max_steps calls to step(), `exhausted` is True and 0 remain
  * after max_tokens tokens are consumed, `exhausted` is True
  * a budget that is not yet reached is not exhausted
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "Northstar_backend"))

from agent_kernel.budget import BudgetTracker
from agent_kernel.model import Budget

failures = []


def check(label, ok, detail=""):
    print(("PASS " if ok else "FAIL ") + label + (f": {detail}" if detail else ""))
    if not ok:
        failures.append(label)


steps = BudgetTracker(Budget(max_steps=3, max_wall_s=60, max_tokens=None),
                      clock=lambda: 0.0)
for _ in range(2):
    steps.step()
check("two of three steps is not exhausted", steps.exhausted is False,
      f"stopped={steps.state.stopped!r}")
steps.step()
check("three of three steps is exhausted", steps.exhausted is True,
      f"stopped={steps.state.stopped!r}")
check("no steps remain", steps.remaining()["steps"] == 0,
      f"remaining={steps.remaining()['steps']}")

tokens = BudgetTracker(Budget(max_steps=10, max_wall_s=60, max_tokens=100),
                       clock=lambda: 0.0)
tokens.tokens(100)
check("the token limit is a stop", tokens.exhausted is True,
      f"stopped={tokens.state.stopped!r} tokens={tokens.state.tokens}")

if failures:
    print(f"\nRESULT FAIL ({len(failures)}): {failures}")
    raise SystemExit(1)
print("\nRESULT PASS")
raise SystemExit(0)
