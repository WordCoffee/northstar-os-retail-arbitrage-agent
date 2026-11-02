"""Accounting for the OpenCode Go author lane — conservative, append-only.

Go's rolling limits are dollar-value and there is no usage API, so every request is
recorded with the cost the CLI reports (`step_finish.cost`) together with its token
counts, and the windows are summed from the ledger. Before a task is opened, the
projected spend is checked against the conservative shares of each window.

    python scripts/go_usage.py --summary
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parents[1]
LEDGER = ROOT / "state" / "go_usage_ledger.jsonl"

#: Go's published rolling limits (recorded 2026-11-02 from the operator's plan).
LIMITS_USD = {"5h": 12.0, "week": 30.0, "month": 60.0}
WINDOW_S = {"5h": 5 * 3600, "week": 7 * 86400, "month": 30 * 86400}
#: Halt-opening shares, per campaign, conservative by design.
HALT_SHARE = {"5h": 0.60, "week": 0.50, "month": 0.50}
MODEL_PRICING = {"opencode-go/deepseek-v4.1-flash":
                 {"input": 0.15, "output": 0.60, "cache_read": 0.003}}


def record(entry: Dict[str, Any]) -> None:
    """Append one request. Never rewrites a line."""
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    row = dict(entry)
    row.setdefault("recorded_at", time.strftime("%Y-%m-%dT%H:%M:%S"))
    row.setdefault("epoch", time.time())
    with open(LEDGER, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")


def entries() -> List[Dict[str, Any]]:
    if not LEDGER.is_file():
        return []
    out = []
    for line in LEDGER.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except ValueError:
            continue
    return out


def totals(now: Optional[float] = None) -> Dict[str, Dict[str, float]]:
    """Spend per rolling window, plus the remaining headroom to each halt share."""
    now = time.time() if now is None else float(now)
    rows = entries()
    out: Dict[str, Dict[str, float]] = {}
    for name, seconds in WINDOW_S.items():
        cutoff = now - seconds
        spent = sum(float(r.get("cost_usd") or 0.0) for r in rows
                    if float(r.get("epoch") or 0) >= cutoff)
        limit = LIMITS_USD[name]
        share_cap = round(limit * HALT_SHARE[name], 4)
        out[name] = {"spent_usd": round(spent, 6),
                     "limit_usd": limit,
                     "halt_at_usd": share_cap,
                     "headroom_usd": round(share_cap - spent, 6),
                     "used_share": round(spent / limit, 4) if limit else 0.0}
    out["total_spent_usd"] = {"spent_usd": round(sum(
        float(r.get("cost_usd") or 0.0) for r in rows), 6)}
    return out


def preflight(estimate_usd: float, *, now: Optional[float] = None) -> Dict[str, Any]:
    """May the campaign open another task? Refuses on the conservative shares."""
    est = max(0.0, float(estimate_usd or 0.0))
    windows = totals(now)
    for name in WINDOW_S:
        w = windows[name]
        if w["spent_usd"] + est > w["halt_at_usd"]:
            return {"ok": False, "window": name,
                    "reason": (f"{name} window would reach "
                               f"${w['spent_usd'] + est:.4f} of a "
                               f"${w['halt_at_usd']:.2f} halt cap"),
                    "windows": windows}
    return {"ok": True, "windows": windows}


def estimate_tokens(prompt: str, output_tokens: int = 400) -> Dict[str, float]:
    """Fallback estimate when the CLI reports no usage."""
    price = MODEL_PRICING["opencode-go/deepseek-v4.1-flash"]
    prompt_tokens = max(1, len(prompt) // 4)
    cost = (prompt_tokens * price["input"] + output_tokens * price["output"]) / 1_000_000
    return {"input_tokens": prompt_tokens, "output_tokens": output_tokens,
            "cost_usd": round(cost, 8), "source": "estimate"}


def summary_text() -> str:
    w = totals()
    parts = [f"{name}: ${w[name]['spent_usd']:.4f}/${w[name]['halt_at_usd']:.2f} halt"
             for name in ("5h", "week", "month")]
    return " | ".join(parts)


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--summary", action="store_true")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    w = totals()
    print(json.dumps(w, indent=2) if args.json else summary_text())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
