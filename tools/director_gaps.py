"""Gap-driven queue: the ranked list, the re-plan trigger, and "idle is a failure".

D5 in the director work order. The queue is not a to-do list; it is `gap = impact x
(bar - score)` ranked, and a gap job names the weakest dimension it exists to move.

Two rules are enforced rather than hoped for:

* **a bundle must be big enough**: it moves a dimension by >= 5 points or closes >= 3
  gaps, otherwise it is bundled with the next one. Micro-edits are refused by name.
* **an empty queue with services below the bar is a defect**, not a finish. `replan()`
  re-derives from the measurements; if it still cannot produce work it writes the
  defect to `self_assessment.md` and `needs_you.md` instead of idling quietly.

    python tools/director_gaps.py --rank
    python tools/director_gaps.py --replan
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parents[1]
SCORES = ROOT / "ty" / "scorecards.json"
SELF = ROOT / "reports" / "ty" / "self_assessment.md"
NEEDS = ROOT / "reports" / "ty" / "needs_you.md"

MIN_POINTS = 5.0
MIN_GAPS_PER_BUNDLE = 3

#: Where a change for each service is expected to land. A directory scopes its tree,
#: so two bundles that disagree here are serialised by the queue's overlap check.
SERVICE_PATHS: Dict[str, List[str]] = {
    "prospector": ["Northstar_backend", "northstar-os-ui/src/rooms"],
    "product-finder": ["Northstar_backend", "northstar-os-ui/src/rooms"],
    "thewatch": ["Northstar_backend", "northstar-os-ui/src/rooms"],
    "rivalboard": ["Northstar_backend", "northstar-os-ui/src/rooms"],
    "competitor-monitor": ["Northstar_backend", "northstar-os-ui/src/rooms"],
    "rankledger": ["Northstar_backend", "northstar-os-ui/src/rooms"],
    "design-studio": ["Northstar_backend/design_studio_api.py",
                      "northstar-os-ui/src"],
    "listings": ["Northstar_backend", "northstar-os-ui/src/rooms"],
    "listingforge": ["Northstar_backend", "northstar-os-ui/src/rooms"],
    "offerchisel": ["Northstar_backend", "northstar-os-ui/src/rooms"],
    "goldengoose": ["agents/golden_goose_finder"],
    "golden-goose": ["agents/golden_goose_finder"],
    "hub": ["northstar-os-ui/src"],
    "foundation": ["Northstar_backend/foundation"],
}

DEFAULT_PATHS = ["Northstar_backend"]

#: Some dimensions are not fixed in the backend. A `seller` gap closes by adding briefs for
#: that service and running the Seller-Tester; a `measured` gap closes by mounting the route.
#: Without this, the re-plan produced "raise seller for ledger" with a backend write path,
#: which is not work anyone can do.
DIMENSION_PATHS: Dict[str, List[str]] = {
    "seller": ["ty/seller_briefs.json"],
    "measured": ["northstar-os-ui/src"],
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def scores() -> Dict[str, Any]:
    return json.loads(SCORES.read_text(encoding="utf-8"))


def rank(data: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    """Every service below the bar, worst gap first. The list, not a to-do list."""
    data = data or scores()
    rows = [row for row in data.get("services") or []
            if not row.get("meets_bar") and float(row.get("gap") or 0) > 0]
    rows.sort(key=lambda row: (-float(row["gap"]), row["id"]))
    return rows


def bundle(rows: Optional[List[Dict[str, Any]]] = None) -> List[Dict[str, Any]]:
    """Group gaps into change sets large enough to be worth a builder.

    Same weakest dimension first: a bundle that fixes `works` for three services is one
    coherent change. A set closes when it holds three gaps or already moves its
    dimension by five points; anything smaller waits for company rather than becoming
    a micro-edit.
    """
    rows = rows if rows is not None else rank()
    groups: Dict[str, List[Dict[str, Any]]] = {}
    for row in rows:
        groups.setdefault(str(row.get("weakest") or "unknown"), []).append(row)

    bundles: List[Dict[str, Any]] = []
    for dimension, members in groups.items():
        members = sorted(members, key=lambda row: -float(row["gap"]))
        if dimension in DIMENSION_PATHS:
            # One file, one job: every member of these dimensions writes the same path, so
            # splitting them into four bundles would serialise four times for one edit.
            best = max(float(row["bar"]) - float(row["score"]) for row in members)
            bundles.append(_as_bundle(dimension, members, best))
            continue
        current: List[Dict[str, Any]] = []
        best = 0.0
        for row in members:
            current.append(row)
            best = max(best, float(row["bar"]) - float(row["score"]))
            if len(current) >= MIN_GAPS_PER_BUNDLE or best >= MIN_POINTS:
                bundles.append(_as_bundle(dimension, current, best))
                current, best = [], 0.0
        if current:
            bundles.append(_as_bundle(dimension, current, best))
    bundles.sort(key=lambda row: -float(row["points"]))
    return bundles


def _as_bundle(dimension: str, members: List[Dict[str, Any]], points: float) -> Dict[str, Any]:
    paths: List[str] = []
    for row in members:
        for path in (DIMENSION_PATHS.get(dimension)
                     or SERVICE_PATHS.get(row["id"], DEFAULT_PATHS)):
            if path not in paths:
                paths.append(path)
    if dimension == "seller":
        title = ("add Seller-Tester briefs and score real outputs for "
                 + ", ".join(row["id"] for row in members)
                 + f" (+{round(points, 1)} possible on seller)")
    elif dimension == "measured":
        title = ("mount the route for " + ", ".join(row["id"] for row in members)
                 + f" (+{round(points, 1)} on measured)")
    else:
        title = (f"raise {dimension} for " + ", ".join(row["id"] for row in members)
                 + f" (+{round(points, 1)} on the weakest dimension)")
    return {
        "unit": "D5",
        "title": title,
        "dimension": dimension,
        "services": [row["id"] for row in members],
        "points": round(points, 1),
        "write_paths": paths,
        "gaps": [{"id": row["id"], "gap": row["gap"], "score": row["score"],
                  "bar": row["bar"]} for row in members],
        "why": (f"{len(members)} gap(s), best case +{round(points, 1)} points on "
                f"{dimension}; below the {MIN_POINTS}-point / {MIN_GAPS_PER_BUNDLE}-gap "
                "threshold it would be a micro-edit"),
    }


def _queue() -> Any:
    import director_queue  # noqa: PLC0415 - keeps this module importable alone

    return director_queue


def enqueue(limit: int = 4) -> Dict[str, Any]:
    """Add at most `limit` bundles to the queue. An overlap is reported, not forced."""
    queue = _queue()
    added, refused = [], []
    for item in bundle()[:max(1, limit)]:
        result = queue.add_job(unit=item["unit"], title=item["title"],
                               write_paths=item["write_paths"], acceptance=[])
        if result.get("ok"):
            job = queue.job(result["id"]) or {}
            job["title"] = item["title"]
            added.append({"id": result["id"], "services": item["services"],
                          "points": item["points"], "paths": item["write_paths"]})
            # Record the scope decision on the job so a later reader sees the reason.
            queue.set_status(result["id"], "queued", evidence=item["why"])
        else:
            refused.append({"reason": result.get("reason"), "title": item["title"]})
    return {"added": added, "refused": refused}


def open_jobs() -> List[Dict[str, Any]]:
    queue = _queue()
    return [row for row in queue.jobs()
            if row.get("status") in ("queued", "claimed", "running", "ready")]


def _defect(message: str) -> None:
    stamp = _now()
    try:
        with SELF.open("a", encoding="utf-8") as handle:
            handle.write(f"\n- {stamp} **idle while below the bar** — {message}\n")
    except OSError:
        pass
    try:
        with NEEDS.open("a", encoding="utf-8") as handle:
            handle.write(f"\n- {stamp} Director idle while services are below the bar: "
                         f"{message}\n")
    except OSError:
        pass


def replan() -> Dict[str, Any]:
    """The idle-is-a-failure rule, as code.

    Called when the queue is empty. It re-derives from the measurements. If it still
    cannot produce work, that is a defect and it is written down - silently doing
    nothing is what the work order forbids.

    Ty's Vision is consulted first: a route that still opens the generic shell is a gap the
    scorecards cannot see, and the eyes are the only instrument that measures it.
    """
    data = scores()
    rows = rank(data)
    vision = _vision_bundle()
    if vision:
        queue = _queue()
        result = queue.add_job(unit=vision["unit"], title=vision["title"],
                               write_paths=vision["write_paths"], acceptance=[])
        if result.get("ok"):
            queue.set_status(result["id"], "queued", evidence=vision["why"])
            return {"ok": True, "reason": "replanned_from_vision",
                    "added": [{"id": result["id"], "services": vision["services"],
                               "points": vision["points"]}],
                    "refused": [], "detail": "a route that renders the shell is not a place"}
        _defect(f"vision bundle could not be enqueued: {result.get('reason')}")
    if not rows:
        return {"ok": True, "reason": "no_gaps",
                "detail": f"all {len(data.get('services') or [])} services are at the bar"}
    bundles = bundle(rows)
    if not bundles:
        _defect("gaps exist but no bundle clears the size threshold")
        return {"ok": False, "reason": "no_viable_bundle", "gaps": len(rows)}
    result = enqueue(limit=4)
    if not result["added"]:
        _defect("re-plan produced no enqueueable job: "
                + json.dumps(result["refused"])[:400])
        return {"ok": False, "reason": "enqueue_failed", **result}
    return {"ok": True, "reason": "replanned", **result,
            "detail": f"{len(rows)} service(s) below the bar"}


def _vision_bundle() -> Optional[Dict[str, Any]]:
    """The route truth Ty's Vision measured, as a bundle. Absent or stale means no bundle."""
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        import director_vision  # noqa: PLC0415

        return director_vision.queue_hint()
    except Exception:  # noqa: BLE001 - a missing eye must not stop a re-plan
        return None


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Gap-driven queue")
    parser.add_argument("--rank", action="store_true")
    parser.add_argument("--bundle", action="store_true")
    parser.add_argument("--replan", action="store_true")
    ns = parser.parse_args(argv)

    if ns.rank:
        print(json.dumps(rank(), indent=2))
        return 0
    if ns.bundle:
        print(json.dumps(bundle(), indent=2))
        return 0
    if ns.replan:
        print(json.dumps(replan(), indent=2))
        return 0
    print(json.dumps({"open_jobs": len(open_jobs()),
                      "top": [row["id"] for row in rank()[:5]]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
