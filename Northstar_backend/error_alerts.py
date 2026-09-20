"""Error-rate alerting logic (Phase F/S4).

Threshold-based detection over a rolling window — pure, offline, and network
FREE by design (this module never sends anything; the operator wires a channel
later per MONITORING_SETUP.md). Wired to the health pattern via
``GET /api/monitoring/error-alerts`` (bff/v1 envelope).
"""

from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Deque, Dict, Optional, Tuple


@dataclass
class ErrorRateTracker:
    """In-memory rolling error-rate tracker.

    Records HTTP status codes and computes the 5xx fraction over a window.
    Meant to be fed by the request path (e.g. middleware or a reporting hook);
    an empty tracker reports no breach.
    """

    window_seconds: float = 300.0
    default_threshold: float = 0.05      # >5% 5xx over the window
    min_requests: int = 10               # don't alert on tiny samples
    _samples: Deque[Tuple[float, int]] = field(default_factory=deque)

    def record(self, status: int, at: Optional[float] = None) -> None:
        ts = time.time() if at is None else at
        self._samples.append((ts, int(status)))
        cutoff = ts - self.window_seconds
        while self._samples and self._samples[0][0] < cutoff:
            self._samples.popleft()

    def window(self) -> Tuple[int, int]:
        """(total_requests, 5xx_count) within the current window."""
        total = len(self._samples)
        five = sum(1 for _, s in self._samples if 500 <= s < 600)
        return total, five

    def rate(self) -> Optional[float]:
        total, five = self.window()
        if total == 0:
            return None
        return five / total

    def breached(self, threshold: Optional[float] = None) -> bool:
        """True when 5xx fraction exceeds threshold AND sample is large enough."""
        total, five = self.window()
        if total < self.min_requests:
            return False
        rate = (five / total) if total else 0.0
        return rate > (threshold if threshold is not None else self.default_threshold)

    def summary(self) -> Dict[str, Any]:
        total, five = self.window()
        rate = self.rate()
        return {
            "window_seconds": self.window_seconds,
            "total_requests": total,
            "five_xx": five,
            "five_xx_rate": (round(rate, 4) if rate is not None else None),
            "threshold": self.default_threshold,
            "min_requests": self.min_requests,
            "breached": self.breached(),
        }


# Singleton fed by the request path (optional wiring).
tracker = ErrorRateTracker()


def compose_alert(summary: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Build an alert payload (NO network send — operator wires delivery)."""
    s = summary or tracker.summary()
    code = "error_rate_breached" if s["breached"] else "ok"
    severity = "critical" if s["breached"] else "info"
    return {
        "code": code,
        "severity": severity,
        "message": (
            "5xx rate %.1f%% exceeds the %.1f%% threshold over %ss window "
            "(sample %d)." % ((s["five_xx_rate"] or 0) * 100,
                              (s["threshold"] or 0) * 100,
                              s["window_seconds"], s["total_requests"])
            if s["breached"]
            else "Error rate within threshold."
        ),
        "retryable": False,
        "channel": None,   # operator wires email/Slack/webhook later (S4 doc)
    }