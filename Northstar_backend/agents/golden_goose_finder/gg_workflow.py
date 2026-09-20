"""Golden Goose workflow toolkit (Phase F/S11d — FIXES_50 subset).

#34 cache TTL   #35 lazy enrichment   #37 streaming report writes
#41 interactive CLI   #42 scan diff   #44 config profiles   #45 scheduler
#46 webhook (stub)   #47 annotations   #48 rollback util   #50 docs auto-gen

Offline; nothing in this module sends network traffic (webhook is a stub),
schedules background jobs, or mutates protected state.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence

# --- #34 cache TTL --------------------------------------------------------------

class TTLCache:
    def __init__(self, ttl_seconds: float = 3600.0) -> None:
        self.ttl = ttl_seconds
        self._store: Dict[str, tuple] = {}

    def get(self, key: str) -> Optional[Any]:
        item = self._store.get(key)
        if item is None:
            return None
        value, ts = item
        if time.time() - ts > self.ttl:
            self._store.pop(key, None)
            return None
        return value

    def set(self, key: str, value: Any) -> None:
        self._store[key] = (value, time.time())


# --- #7 scan-timeout budget ------------------------------------------------------

class ScanBudget:
    """FIXES_50 #7 — hard scan-timeout budget.

    A scan starts a budget; when the deadline passes the scan must stop and
    report ``scan_complete: false`` (partial results are honest results).
    Pure and clock-injectable for tests.
    """

    def __init__(self, timeout_seconds: float, started_at: Optional[float] = None) -> None:
        self.timeout_seconds = timeout_seconds
        self.started_at = time.time() if started_at is None else started_at

    @property
    def deadline(self) -> float:
        return self.started_at + self.timeout_seconds

    def expired(self, now: Optional[float] = None) -> bool:
        return (time.time() if now is None else now) >= self.deadline

    def remaining(self, now: Optional[float] = None) -> float:
        return max(0.0, self.deadline - (time.time() if now is None else now))

    def checkpoint(self, now: Optional[float] = None) -> Dict[str, Any]:
        now = time.time() if now is None else now
        expired = now >= self.deadline
        return {
            "timeout_seconds": self.timeout_seconds,
            "deadline": self.deadline,
            "remaining_seconds": round(max(0.0, self.deadline - now), 3),
            "complete": not expired,
        }


# --- #35 lazy enrichment selector ----------------------------------------------

def needs_lazy_enrichment(opp: Dict[str, Any]) -> bool:
    """Only enrich candidates that pass economics (lazy seller enrichment)."""
    net = opp.get("net_profit_per_unit")
    return isinstance(net, (int, float)) and net > 0


# --- #37 streaming report writes ------------------------------------------------

def write_rows_streaming(path: Path, rows: Iterable[Dict[str, Any]], chunk: int = 100) -> int:
    """Write rows incrementally (JSONL). Returns the row count written."""
    path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with path.open("a", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r) + "\n")
            count += 1
    return count


def read_stream(path: Path) -> Iterable[Dict[str, Any]]:
    if not path.exists():
        return
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                yield json.loads(line)


# --- #42 scan diff ---------------------------------------------------------------

def asin_key(e: Dict[str, Any]) -> str:
    return str(e.get("amazon_asin") or e.get("asin") or "")


# --- #25 tier-regression detection ---------------------------------------------

TIER_ORDER = {"HIGH": 4, "MEDIUM": 3, "LOW": 2, "REJECT": 1, "UNKNOWN": 0}


def tier_regressions(prev: Sequence[Dict[str, Any]], curr: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """FIXES_50 #25 — detect ASINs whose tier DROPPED between scans.

    Only strictly-downward moves count (HIGH->MEDIUM/LOW/REJECT, MEDIUM->LOW/
    REJECT, LOW->REJECT). Drops out of the report entirely are NOT regressions
    (they are covered by diff_reports' dropped list). Pure; no send.
    """
    p = {asin_key(e): str((e.get("tier") or "UNKNOWN")).upper() for e in prev}
    c = {asin_key(e): str((e.get("tier") or "UNKNOWN")).upper() for e in curr}
    out = []
    for a in sorted(c):
        if a and a in p and TIER_ORDER.get(c[a], 0) < TIER_ORDER.get(p[a], 0):
            out.append({
                "asin": a,
                "previous_tier": p[a],
                "current_tier": c[a],
                "dropped": True,
            })
    return out


def compose_tier_alert(regressions: Sequence[Dict[str, Any]], max_items: int = 10) -> Dict[str, Any]:
    """No-send alert payload for tier regressions (operator wires delivery)."""
    return {
        "code": "tier_regression" if regressions else "ok",
        "severity": "warning" if regressions else "info",
        "count": len(regressions),
        "regressions": [
            {k: r[k] for k in ("asin", "previous_tier", "current_tier")}
            for r in regressions[:max_items]
        ],
        "channel": None,
    }


def diff_reports(prev: Sequence[Dict[str, Any]], curr: Sequence[Dict[str, Any]]) -> Dict[str, List[str]]:
    p = {asin_key(e): e for e in prev}
    c = {asin_key(e): e for e in curr}
    added = [a for a in c if a not in p]
    dropped = [a for a in p if a not in c]
    tier_changed = sorted(a for a in c if a in p and (p[a].get("tier") != c[a].get("tier")))
    return {"added": sorted(added), "dropped": sorted(dropped), "tier_changed": tier_changed}


# --- #44 config profiles ----------------------------------------------------------

PROFILE_DEFAULTS: Dict[str, Dict[str, Any]] = {
    "aggressive": {"roi_floor": 15.0, "min_monthly_sales": 400},
    "conservative": {"roi_floor": 30.0, "min_monthly_sales": 1000, "max_fba_sellers": 1},
    "default": {"roi_floor": 10.0, "min_monthly_sales": 600},
}


def resolve_profile(profile: Optional[str] = None, **overrides: Any) -> Dict[str, Any]:
    base = dict(PROFILE_DEFAULTS.get(profile or "default", PROFILE_DEFAULTS["default"]))
    base.update({k: v for k, v in overrides.items() if v is not None})
    return base


# --- #41 interactive CLI -----------------------------------------------------------

def confirm_continue(prompt: str = "Continue?", default: bool = True) -> bool:
    """Interactive yes/no; robust fallback to `default` when non-tty."""
    import sys
    try:
        if not sys.stdin.isatty():
            return default
        answer = input("%s [Y/n] " % prompt).strip().lower()
    except (EOFError, OSError):
        return default
    if answer in ("y", "yes"):
        return True
    if answer in ("n", "no"):
        return False
    return default


# --- #45 scheduler (local stub) ------------------------------------------------------

@dataclass
class Job:
    name: str
    schedule_cron: str
    fn: str = ""          # dotted module path stub


@dataclass
class SchedulerStub:
    jobs: List[Job] = field(default_factory=list)

    def schedule(self, name: str, cron: str) -> Job:
        j = Job(name=name, schedule_cron=cron)
        self.jobs.append(j)
        return j

    def jobs_list(self) -> List[Dict[str, str]]:
        return [{"name": j.name, "cron": j.schedule_cron} for j in self.jobs]

    def dry_run(self, now: Optional[float] = None) -> List[Dict[str, Any]]:
        """FIXES_50 #45 — validate + compute next-fire ONLY; never executes.

        Proves the jobs *would* fire on schedule without running anything.
        """
        out = []
        base = time.time() if now is None else now
        for j in self.jobs:
            if not validate_cron(j.schedule_cron):
                out.append({"name": j.name, "cron": j.schedule_cron, "valid": False})
                continue
            nxt = cron_next_minute(j.schedule_cron, base)
            out.append({
                "name": j.name, "cron": j.schedule_cron, "valid": True,
                "next_fire_epoch": nxt,
            })
        return out


# --- #45 local cron validator + next-fire (dry-run only) -------------------------

_CRON_RANGES = ((0, 59), (0, 23), (1, 31), (1, 12), (0, 6))


def _parse_cron_field(token: str, lo: int, hi: int, allow_sunday_7: bool = False) -> Optional[set]:
    """Parse one cron field token into a set of allowed values (or None)."""
    allowed: set = set()
    for part in str(token).split(","):
        part = part.strip()
        if not part:
            return None
        step = 1
        base = part
        if "/" in part:
            base, _, step_s = part.rpartition("/")
            try:
                step = int(step_s)
            except ValueError:
                return None
            if step <= 0:
                return None
        if base == "*":
            allowed.update(range(lo, hi + 1, step))
        elif "-" in base:
            a_s, _, b_s = base.partition("-")
            try:
                a, b = int(a_s), int(b_s)
            except ValueError:
                return None
            if a < lo or b > hi or a > b:
                return None
            allowed.update(range(a, b + 1, step))
        else:
            try:
                v = int(base)
            except ValueError:
                return None
            if v == 7 and allow_sunday_7:
                v = 0
            if v < lo or v > hi:
                return None
            if step != 1:
                return None
            allowed.add(v)
    return allowed


def _cron_fields(expr: str) -> Optional[List[set]]:
    fields = str(expr or "").split()
    if len(fields) != 5:
        return None
    out = []
    for i, (token, (lo, hi)) in enumerate(zip(fields, _CRON_RANGES)):
        parsed = _parse_cron_field(token, lo, hi, allow_sunday_7=(i == 4))
        if parsed is None:
            return None
        out.append(parsed)
    return out


def validate_cron(expr: str) -> bool:
    """FIVE standard fields (minute hour day month weekday), numeric tokens:
    '*', '*/n', 'a-b', 'a', 'a,b'. DOW 0/7 = Sunday. Returns False otherwise."""
    return _cron_fields(expr) is not None


def cron_next_minute(expr: str, now: float) -> Optional[int]:
    """Epoch (UTC, minute-aligned) of the next minute matching ``expr`` after
    ``now``, or None if none fires within a 48h horizon. Pure, clock-injected."""
    fields = _cron_fields(expr)
    if fields is None:
        return None
    minute, hour, dom, month, dow = fields
    dom_wild = set(dom) == set(range(1, 32))
    dow_wild = set(dow) == set(range(0, 7))
    start = int(now) + 60
    horizon = start + 48 * 3600
    for epoch in range(start, horizon, 60):
        dt = datetime.fromtimestamp(epoch, tz=timezone.utc)
        if dt.minute not in minute or dt.hour not in hour or dt.month not in month:
            continue
        py_dow = (dt.weekday() + 1) % 7   # cron convention: 0=Sunday
        if dom_wild and dow_wild:
            day_ok = True
        elif dow_wild:
            day_ok = dt.day in dom
        elif dom_wild:
            day_ok = py_dow in dow
        else:
            day_ok = (dt.day in dom) or (py_dow in dow)
        if day_ok:
            return epoch
    return None


# --- #46 webhook (local test stub — never sends) --------------------------------------

def webhook_notify(url: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    import logging
    logging.getLogger("northstar.webhook").info(
        "[webhook:stubbed] url=%s payload=%s", url, json.dumps(payload)[:200]
    )
    return {"status": "stubbed", "would_post_to": url, "payload": payload}


# --- #47 annotations -------------------------------------------------------------------

class AnnotationStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._items: List[Dict[str, Any]] = []
        if path.exists():
            self._load()

    def tag(self, asin: str, note: str) -> Dict[str, Any]:
        entry = {"asin": asin, "note": note, "at": time.time()}
        self._items.append(entry)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("w", encoding="utf-8") as fh:
            json.dump(self._items, fh)
        return entry

    def _load(self) -> None:
        try:
            with self.path.open("r", encoding="utf-8") as fh:
                self._items = json.load(fh)
        except Exception:
            self._items = []

    def all(self) -> List[Dict[str, Any]]:
        return list(self._items)


# --- #48 rollback (plan util — actual revert is operator) ------------------------------

def rollback_plan(scan_keys: Sequence[str], target_key: str) -> Dict[str, Any]:
    """Compute which scan runs a rollback to `target_key` would remove."""
    if target_key not in scan_keys:
        return {"target": target_key, "would_remove": [], "ok": False}
    idx = scan_keys.index(target_key)
    return {
        "target": target_key,
        "would_remove": list(scan_keys[idx + 1:]),
        "ok": True,
    }


# --- #50 docs auto-gen ------------------------------------------------------------------

def generate_cli_docs(prog: str, args_help: Sequence[tuple]) -> str:
    lines = ["# %s — reference" % prog, "", "| flag | help |", "|---|---|"]
    for flag, help_ in args_help:
        lines.append("| `%s` | %s |" % (flag, help_.replace("|", "\\|")))
    return "\n".join(lines) + "\n"