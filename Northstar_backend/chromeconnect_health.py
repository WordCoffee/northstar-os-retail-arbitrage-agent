"""Chrome Connect health, evidence, and alerts (Phase 5).

Adapter health tracking (green/DEGRADED/red), evidence records on every
extracted value, screenshot capture metadata, and alert aggregation.

Provenance: In-house implementation. No external code.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# Health states
# ---------------------------------------------------------------------------

class HealthState(str, Enum):
    GREEN = "green"
    DEGRADED = "degraded"
    RED = "red"
    UNKNOWN = "unknown"


@dataclass
class AdapterHealth:
    name: str
    origin: str
    state: HealthState = HealthState.UNKNOWN
    last_run: Optional[str] = None
    last_success: Optional[str] = None
    success_count: int = 0
    failure_count: int = 0
    consecutive_failures: int = 0
    degraded_reason: Optional[str] = None
    avg_time_s: float = 0.0
    total_runs: int = 0

    def record_success(self, time_s: float) -> None:
        self.state = HealthState.GREEN
        self.last_run = datetime.now(timezone.utc).isoformat()
        self.last_success = self.last_run
        self.success_count += 1
        self.consecutive_failures = 0
        self.degraded_reason = None
        self.total_runs += 1
        # Rolling average
        if self.total_runs == 1:
            self.avg_time_s = time_s
        else:
            self.avg_time_s = round(
                (self.avg_time_s * (self.total_runs - 1) + time_s) / self.total_runs, 3
            )

    def record_failure(self, reason: str) -> None:
        self.last_run = datetime.now(timezone.utc).isoformat()
        self.failure_count += 1
        self.consecutive_failures += 1
        self.total_runs += 1
        if self.consecutive_failures >= 3:
            self.state = HealthState.RED
        else:
            self.state = HealthState.DEGRADED
        self.degraded_reason = reason

    def record_degraded(self, reason: str) -> None:
        self.state = HealthState.DEGRADED
        self.degraded_reason = reason
        self.last_run = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "origin": self.origin,
            "state": self.state.value,
            "last_run": self.last_run,
            "last_success": self.last_success,
            "success_count": self.success_count,
            "failure_count": self.failure_count,
            "consecutive_failures": self.consecutive_failures,
            "degraded_reason": self.degraded_reason,
            "avg_time_s": self.avg_time_s,
            "total_runs": self.total_runs,
        }


# ---------------------------------------------------------------------------
# Evidence record
# ---------------------------------------------------------------------------

@dataclass
class EvidenceRecord:
    field_name: str
    value: Any
    source_url: str
    observed_at: str
    selector_version: str
    confidence: float
    extraction_method: str = "selector"  # selector | adaptive | ai | vision
    screenshot_hash: Optional[str] = None
    status: str = "OK"  # OK | UNKNOWN | DEGRADED

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def make_evidence(
    field_name: str,
    value: Any,
    source_url: str,
    selector_version: str = "1.0.0",
    confidence: float = 1.0,
    method: str = "selector",
    screenshot_hash: Optional[str] = None,
) -> EvidenceRecord:
    """Create an evidence record for an extracted field."""
    if value is None:
        status = "UNKNOWN"
    else:
        status = "OK"
    return EvidenceRecord(
        field_name=field_name,
        value=value,
        source_url=source_url,
        observed_at=datetime.now(timezone.utc).isoformat(),
        selector_version=selector_version,
        confidence=confidence,
        extraction_method=method,
        screenshot_hash=screenshot_hash,
        status=status,
    )


# ---------------------------------------------------------------------------
# Alert system
# ---------------------------------------------------------------------------

@dataclass
class Alert:
    severity: str  # info | warning | error | critical
    category: str  # adapter_degraded | adapter_failed | transport | profile | cost
    message: str
    adapter: Optional[str] = None
    timestamp: str = ""
    acknowledged: bool = False

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class AlertManager:
    """In-memory alert store with severity filtering."""

    def __init__(self) -> None:
        self._alerts: List[Alert] = []

    def add(self, severity: str, category: str, message: str,
            adapter: Optional[str] = None) -> Alert:
        alert = Alert(severity=severity, category=category, message=message, adapter=adapter)
        self._alerts.append(alert)
        return alert

    def unacknowledged(self, min_severity: Optional[str] = None) -> List[Alert]:
        sev_order = {"info": 0, "warning": 1, "error": 2, "critical": 3}
        threshold = sev_order.get(min_severity, 0) if min_severity else 0
        return [a for a in self._alerts
                if not a.acknowledged and sev_order.get(a.severity, 0) >= threshold]

    def acknowledge(self, index: int) -> bool:
        if 0 <= index < len(self._alerts):
            self._alerts[index].acknowledged = True
            return True
        return False

    def acknowledge_all(self) -> int:
        count = 0
        for a in self._alerts:
            if not a.acknowledged:
                a.acknowledged = True
                count += 1
        return count

    def count_by_severity(self) -> Dict[str, int]:
        counts: Dict[str, int] = {"info": 0, "warning": 0, "error": 0, "critical": 0}
        for a in self._alerts:
            if not a.acknowledged:
                counts[a.severity] = counts.get(a.severity, 0) + 1
        return counts

    def to_list(self) -> List[Dict[str, Any]]:
        return [a.to_dict() for a in self._alerts]


# ---------------------------------------------------------------------------
# Health registry
# ---------------------------------------------------------------------------

class HealthRegistry:
    """Registry of adapter health states."""

    def __init__(self) -> None:
        self._adapters: Dict[str, AdapterHealth] = {}
        self.alerts = AlertManager()

    def register(self, name: str, origin: str) -> AdapterHealth:
        if name not in self._adapters:
            self._adapters[name] = AdapterHealth(name=name, origin=origin)
        return self._adapters[name]

    def get(self, name: str) -> Optional[AdapterHealth]:
        return self._adapters.get(name)

    def record_success(self, name: str, time_s: float) -> None:
        if name in self._adapters:
            self._adapters[name].record_success(time_s)

    def record_failure(self, name: str, reason: str) -> None:
        if name in self._adapters:
            self._adapters[name].record_failure(reason)
            self.alerts.add("error", "adapter_failed",
                           f"Adapter {name} failed: {reason}", adapter=name)

    def record_degraded(self, name: str, reason: str) -> None:
        if name in self._adapters:
            self._adapters[name].record_degraded(reason)
            self.alerts.add("warning", "adapter_degraded",
                           f"Adapter {name} degraded: {reason}", adapter=name)

    def all_health(self) -> List[Dict[str, Any]]:
        return [a.to_dict() for a in self._adapters.values()]

    def degraded_adapters(self) -> List[str]:
        return [name for name, a in self._adapters.items()
                if a.state in (HealthState.DEGRADED, HealthState.RED)]

    def summary(self) -> Dict[str, Any]:
        states = [a.state.value for a in self._adapters.values()]
        return {
            "total_adapters": len(self._adapters),
            "green": states.count("green"),
            "degraded": states.count("degraded"),
            "red": states.count("red"),
            "unknown": states.count("unknown"),
            "alerts": self.alerts.count_by_severity(),
            "unacknowledged_alerts": len(self.alerts.unacknowledged()),
        }


# ---------------------------------------------------------------------------
# Screenshot metadata (QA per deploy)
# ---------------------------------------------------------------------------

@dataclass
class ScreenshotSpec:
    viewport_width: int
    viewport_height: int
    label: str  # e.g. "mobile", "tablet", "desktop"

QA_VIEWPORTS = [
    ScreenshotSpec(390, 844, "mobile"),
    ScreenshotSpec(768, 1024, "tablet"),
    ScreenshotSpec(1440, 900, "desktop"),
]


@dataclass
class QAResult:
    url: str
    viewport: str
    width: int
    height: int
    console_errors: List[str] = field(default_factory=list)
    network_errors: List[str] = field(default_factory=list)
    screenshot_path: Optional[str] = None
    screenshot_hash: Optional[str] = None
    passed: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def run_qa_check(
    url: str,
    viewports: Optional[List[ScreenshotSpec]] = None,
) -> List[QAResult]:
    """Generate QA check specs for a URL across viewports.

    Returns a list of QAResult templates (screenshot capture is done
    by the caller via Chrome Connect or Playwright).
    """
    if viewports is None:
        viewports = QA_VIEWPORTS
    results = []
    for vp in viewports:
        results.append(QAResult(
            url=url,
            viewport=vp.label,
            width=vp.viewport_width,
            height=vp.viewport_height,
        ))
    return results


# ---------------------------------------------------------------------------
# Dashboard data aggregator
# ---------------------------------------------------------------------------

def dashboard_data(registry: HealthRegistry) -> Dict[str, Any]:
    """Aggregate health data for the ChromeConnect admin room."""
    return {
        "health": registry.summary(),
        "adapters": registry.all_health(),
        "degraded": registry.degraded_adapters(),
        "alerts": registry.alerts.to_list(),
        "alert_counts": registry.alerts.count_by_severity(),
        "qa_viewports": [{"label": v.label, "width": v.viewport_width, "height": v.viewport_height}
                        for v in QA_VIEWPORTS],
    }
