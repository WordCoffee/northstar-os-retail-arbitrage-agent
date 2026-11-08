"""Seller-Tester output scores, per service.

The owner's instruction (2026-11-08): *add seller-tester output scores to the scorecards so
artefacts alone can't raise them.* Tests prove that a code path runs; they do not prove that
what comes out is worth selling. This module turns a real Seller-Tester pass into a number a
scorecard can use, and a service with no scored output gets 0 with that reason.

Attribution is declared, never guessed: a brief belongs to a service only through the
`service` field in `ty/seller_briefs.json` (default: the product-picture service, Design
Studio, because every brief in the catalogue today is a product picture).

    python -m tools.seller_tester run --limit 30     # the pass
    python tools/seller_scores.py --write            # the scores the scorecard reads
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

ROOT = Path(__file__).resolve().parents[1]
BRIEFS = ROOT / "ty" / "seller_briefs.json"
OUT = ROOT / "ty" / "seller_scores.json"
SUMMARY = ROOT / "state" / "seller" / "last_run.json"
MIN_SCORED = 5


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _read(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def brief_services(briefs: Any = None) -> Dict[str, str]:
    """brief id -> service. Declared in the brief, defaulting to design-studio."""
    payload = briefs if briefs is not None else (_read(BRIEFS) or {})
    items = payload.get("briefs") if isinstance(payload, dict) else payload
    out: Dict[str, str] = {}
    for brief in items or []:
        if not isinstance(brief, dict) or not brief.get("id"):
            continue
        out[str(brief["id"])] = str(brief.get("service") or "design-studio")
    return out


def build(*, summary: Optional[Dict[str, Any]] = None,
          briefs: Any = None) -> Dict[str, Any]:
    """Aggregate one pass into per-service means, with the sample size attached."""
    data = summary if summary is not None else _read(SUMMARY)
    if not isinstance(data, dict):
        return {"services": {}, "reason": "no seller-tester pass on disk", "at": _now()}
    mapping = brief_services(briefs)
    rows = data.get("results") or data.get("outputs") or []
    buckets: Dict[str, Dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        service = mapping.get(str(row.get("brief_id") or ""), "design-studio")
        score = row.get("score")
        try:
            value = float(score)
        except (TypeError, ValueError):
            continue
        bucket = buckets.setdefault(service, {"scores": [], "passed": 0})
        bucket["scores"].append(value)
        if row.get("passed"):
            bucket["passed"] += 1
    services = {
        service: {"mean": round(sum(bucket["scores"]) / len(bucket["scores"]), 1),
                  "scored": len(bucket["scores"]),
                  "passed": bucket["passed"],
                  "at": data.get("generated_at") or _now()}
        for service, bucket in buckets.items() if bucket["scores"]
    }
    return {"services": services, "at": _now(),
            "pass": {key: data.get(key) for key in ("scored", "passed", "mean_score")}}


def write(*, out: Optional[Path] = None) -> Dict[str, Any]:
    payload = build()
    target = Path(out or OUT)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return {"ok": True, "path": str(target), **payload}


def score_for(service_id: str, *, data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """The seller dimension for one service: a mean, or a named zero.

    A service with fewer than MIN_SCORED outputs is not scored: five lucky pictures are not
    a service that ships.
    """
    payload = data if data is not None else (_read(OUT) or {})
    row = (payload.get("services") or {}).get(service_id)
    if not row:
        return {"score": 0.0,
                "evidence": "no Seller-Tester output scored for this service"}
    scored = int(row.get("scored") or 0)
    if scored < MIN_SCORED:
        return {"score": 0.0,
                "evidence": f"only {scored} Seller-Tester output(s) scored for this service"}
    return {"score": float(row.get("mean") or 0.0),
            "evidence": (f"{scored} Seller-Tester outputs, mean {row.get('mean')}, "
                         f"{row.get('passed')} passed")}


def main(argv: Optional[list] = None) -> int:
    parser = argparse.ArgumentParser(description="Seller-Tester output scores")
    parser.add_argument("--write", action="store_true")
    ns = parser.parse_args(argv)
    result = write() if ns.write else build()
    print(json.dumps(result, indent=2, default=str)[:2000])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
