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