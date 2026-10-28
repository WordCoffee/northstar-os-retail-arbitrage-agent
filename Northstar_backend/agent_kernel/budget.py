"""Hard budgets: steps, wall clock, tokens. A limit is a stop, not a warning."""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Callable, Optional

from .model import Budget


@dataclass
class BudgetState:
    steps: int = 0
    tokens: int = 0
    started_at: float = 0.0
    stopped: Optional[str] = None

    def to_dict(self) -> dict:
        return {"steps": self.steps, "tokens": self.tokens,
                "started_at": self.started_at, "stopped": self.stopped}


class BudgetTracker:
    def __init__(self, budget: Budget, *, clock: Callable[[], float] = time.time):
        self.budget = budget
        self.clock = clock
        self.state = BudgetState(started_at=clock())

    def step(self) -> None:
        self.state.steps += 1
        self._check()

    def tokens(self, n: int) -> None:
        self.state.tokens += max(0, int(n))
        self._check()

    def _check(self) -> None:
        if self.state.steps > self.budget.max_steps:
            self.state.stopped = "max_steps"
        if self.elapsed_s() > self.budget.max_wall_s:
            self.state.stopped = "max_wall_s"
        if self.budget.max_tokens and self.state.tokens > self.budget.max_tokens:
            self.state.stopped = "max_tokens"

    def elapsed_s(self) -> float:
        return max(0.0, self.clock() - self.state.started_at)

    @property
    def exhausted(self) -> bool:
        return self.state.stopped is not None

    def remaining(self) -> dict:
        return {"steps": max(0, self.budget.max_steps - self.state.steps),
                "wall_s": max(0.0, self.budget.max_wall_s - self.elapsed_s()),
                "tokens": (None if self.budget.max_tokens is None
                           else max(0, self.budget.max_tokens - self.state.tokens))}

    def snapshot(self) -> dict:
        return {**self.state.to_dict(), "remaining": self.remaining(),
                "exhausted": self.exhausted}
