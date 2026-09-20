"""Golden Goose observability toolkit (Phase F/S11c — FIXES_50 subset).

#24 metrics emission   #26 latency percentiles   #27 structured logs
#28 debug mode         #29 replay               #36 compress/purge
#39 cost tracking      #40 quota projection

Offline, pure, no network. File writes are local + scoped to a debug dir.
"""

from __future__ import annotations

import gzip
import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional


# --- #26 latency percentiles -------------------------------------------------

def percentile(values: Iterable[float], p: float) -> Optional[float]:
    vs = sorted(values)
    if not vs:
        return None
    k = (len(vs) - 1) * (p / 100.0)
    lo = int(k)
    hi = min(lo + 1, len(vs) - 1)
    frac = k - lo
    return vs[lo] * (1 - frac) + vs[hi] * frac


@dataclass
class LatencyTracker:
    _samples: List[float] = field(default_factory=list)

    def record(self, ms: float) -> None:
        self._samples.append(ms)

    def summary(self) -> Dict[str, Optional[float]]:
        return {
            "count": len(self._samples),
            "p50": percentile(self._samples, 50),
            "p95": percentile(self._samples, 95),
            "p99": percentile(self._samples, 99),
        }


# --- #24 metrics + #39 cost tracking + #27 structured logs ------------------

class MetricsStore:
    """Append-only local metrics (JSONL)."""

    def __init__(self, path: Optional[Path] = None) -> None:
        self.path = path

    def emit(self, metrics: Dict[str, Any]) -> None:
        if not self.path:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(metrics) + "\n")


class StructuredLogger:
    """Emit one JSON object per line (correlation-ready)."""

    @staticmethod
    def line(*, level: str, event: str, scan_id: Optional[str] = None,
             asin: Optional[str] = None, **extra: Any) -> str:
        record = {"ts": time.time(), "level": level, "event": event}
        if scan_id:
            record["scan_id"] = scan_id
        if asin:
            record["asin"] = asin
        record.update(extra)
        return json.dumps(record)


class AuditWriter:
    """FIXES_50 #22 — discrete per-ASIN audit trail (JSONL, append-only).

    Every provider/adapter call for an ASIN gets one line with the canonical
    error taxonomy (gg_errors.ErrorCode) when it failed, plus latency/credits
    where available. Files are local and scoped; nothing here sends anywhere.
    """

    def __init__(self, root: Path) -> None:
        self.root = root

    def path_for(self, asin: str) -> Path:
        tag = (asin or "global").replace("/", "_")[:12]
        return self.root / ("%s.audit.jsonl" % tag)

    def write(self, *, asin: str, provider: str, action: str, status: str,
              latency_ms: Optional[float] = None, credits: Optional[int] = None,
              error_code: Optional[str] = None, scan_id: Optional[str] = None,
              extra: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        entry: Dict[str, Any] = {
            "ts": time.time(),
            "asin": asin or "",
            "provider": provider,
            "action": action,
            "status": status,          # ok | error
            "code": error_code or ("ok" if status == "ok" else "UNKNOWN"),
        }
        if latency_ms is not None:
            entry["latency_ms"] = latency_ms
        if credits is not None:
            entry["credits"] = credits
        if scan_id:
            entry["scan_id"] = scan_id
        if extra:
            entry.update(extra)
        self.root.mkdir(parents=True, exist_ok=True)
        with self.path_for(asin).open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry) + "\n")
        return entry

    def entries_for(self, asin: str) -> List[Dict[str, Any]]:
        p = self.path_for(asin)
        if not p.exists():
            return []
        out = []
        with p.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    out.append(json.loads(line))
        return out


# --- #28 debug mode + #29 replay + #36 compress/purge -------------------------

class DebugStore:
    """Local debug artifact store (raw responses) with gzip + purge."""

    def __init__(self, root: Path, *, debug: bool = False, ttl_days: int = 7) -> None:
        self.root = root
        self.debug = debug or _debug_env()
        self.ttl_days = ttl_days

    def save_raw(self, name: str, payload: Any) -> Optional[Path]:
        if not self.debug:
            return None
        self.root.mkdir(parents=True, exist_ok=True)
        p = (self.root / name).with_suffix(".json.gz")
        with gzip.open(p, "wt", encoding="utf-8") as fh:
            json.dump(payload, fh)
        return p

    def load_for_replay(self, name: str) -> Optional[Any]:
        p = (self.root / name).with_suffix(".json.gz")
        if not p.exists():
            return None
        with gzip.open(p, "rt", encoding="utf-8") as fh:
            return json.load(fh)

    def purge(self, now: Optional[float] = None) -> int:
        now = time.time() if now is None else now
        removed = 0
        for p in self.root.glob("*.json.gz"):
            if (now - p.stat().st_mtime) > self.ttl_days * 86400:
                p.unlink()
                removed += 1
        return removed


def _debug_env() -> bool:
    import os
    return os.getenv("GOLDEN_GOOSE_DEBUG", "").strip() == "1"


class CostTracker:
    """#39 per-provider credit run totals (best-effort, no billing)."""

    def __init__(self) -> None:
        self._totals: Dict[str, int] = {}

    def charge(self, provider: str, credits: int) -> None:
        self._totals[provider] = self._totals.get(provider, 0) + int(credits)

    def totals(self) -> Dict[str, int]:
        return dict(self._totals)

    def total(self) -> int:
        return sum(self._totals.values())


# --- #40 quota projection ------------------------------------------------------

def project_scans(monthly_limit: int, spent: int, avg_credits_per_scan: int) -> Dict[str, Any]:
    """Project how many more scans the current monthly quota supports."""
    remaining = max(0, monthly_limit - spent)
    projected = remaining // avg_credits_per_scan if avg_credits_per_scan else 0
    return {
        "monthly_limit": monthly_limit,
        "spent": spent,
        "remaining": remaining,
        "avg_credits_per_scan": avg_credits_per_scan,
        "projected_scans_remaining": projected,
    }


# --- #9 quota pre-scan hook ------------------------------------------------------

QUOTA_WARN_FRACTION = 0.20  # warn when < 20% of the monthly quota remains


def quota_precheck(monthly_limit: int, spent: int, avg_credits_per_scan: int) -> Dict[str, Any]:
    """FIXES_50 #9 — pre-scan quota check (pure; the caller decides stopping).

    Returns a warning payload when projected remaining quota falls below
    QUOTA_WARN_FRACTION of the monthly limit. No ledger interaction here —
    the caller passes the numbers it trusts.
    """
    proj = project_scans(monthly_limit, spent, avg_credits_per_scan)
    pct = (proj["remaining"] / monthly_limit) if monthly_limit else 0.0
    warned = pct < QUOTA_WARN_FRACTION
    return {
        "projection": proj,
        "remaining_pct": round(pct, 4),
        "warn_threshold_pct": QUOTA_WARN_FRACTION,
        "warned": warned,
        "message": (
            ("WARN: projected quota remaining (%.0f%%) is below the %.0f%% "
             "pre-scan threshold (%d credits left).")
            % (pct * 100, QUOTA_WARN_FRACTION * 100, proj["remaining"])
            if warned
            else "Quota precheck OK."
        ),
    }