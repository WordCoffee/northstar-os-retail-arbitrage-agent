"""Digest Generator — milestone protocol per §5 of the charter.

Produces a report every 3 hours of activity and once daily. The report format:
- done: what was completed
- in progress: current tasks
- queued: items in needs-you queue
- denied: items denied
- anomalies: watchdog triggers, test drops, hash mismatches
- disk: free disk status
- time used: wall-clock time per run
"""

import json
import os
import glob
from datetime import datetime, timezone
from typing import Dict, List, Any

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LEDGER_PATH = os.path.join(REPO_ROOT, "shared", "steward", "ledger.jsonl")
QUEUE_PATH = os.path.join(REPO_ROOT, "shared", "steward", "needs_you_queue.jsonl")
STATE_PATH = os.path.join(REPO_ROOT, "00_STATE.json")
STEWARD_DIR = os.path.join(REPO_ROOT, "steward")
DIGEST_DIR = os.path.join(REPO_ROOT, "reports", "steward_digests")

from steward.needs_you_queue import NeedsYouQueue  # noqa: E402  (import after class def in __init__)


def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_json(path: str, default: Any = None) -> Any:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return default


def _json_dump(path: str, data: Any) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def build_digest(engine, cycle_number: int = 0) -> Dict[str, Any]:
    """Build a 3-hour milestone digest.

    Includes:
      - done (completed tasks/phases)
      - in_progress (what's current)
      - queued (from needs-you queue + open worktrees)
      - denied (from needs-you queue)
      - anomalies (watchdog triggers, hash drops, test count drops)
      - disk (free space, pause status)
      - time_used (wall-clock from start of cycle)
      - model: small model accuracy summary
      - summary: overall status
    """
    # --- Load ledger stats ---
    ledger_summary = engine.get_ledger_summary() if hasattr(engine, 'get_ledger_summary') else {"total_entries": 0}
    total_entries = ledger_summary.get("total_entries", 0)

    # --- Load queue stats ---
    queue = NeedsYouQueue(QUEUE_PATH)
    pending_items = queue.list_pending()
    denied_items = [i for i in pending_items if i.get("status") == "denied"]
    approved_items = [i for i in pending_items if i.get("status") == "approved"]

    # --- Anomaly gathering ---
    anomalies = []
    # Check last few ledger entries for watchdog_pause events
    if os.path.isfile(LEDGER_PATH):
        try:
            with open(LEDGER_PATH, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        entry = json.loads(line)
                        if entry.get("event") == "watchdog_pause":
                            anomalies.append({
                                "type": "watchdog_pause",
                                "time": entry.get("timestamp_utc"),
                                "reasons": entry.get("reasons", [])[:3],  # top 3
                            })
                        elif entry.get("event") == "provenance_violation":
                            anomalies.append({
                                "type": "provenance_violation",
                                "time": entry.get("timestamp_utc"),
                                "detail": entry.get("detail", "unknown"),
                            })
        except Exception:
            pass

    # Check if any items denied in queue today
    today_str = _now_utc().split("T")[0]
    denied_today = [i for i in pending_items
                     if i.get("status") == "denied"
                     and i.get("date_utc", "").split("T")[0] == today_str]

    # --- Dig disk ---
    try:
        import shutil
        total, used, free = shutil.disk_usage(REPO_ROOT)
        free_gb = free / (1024 ** 3)
    except Exception:
        free_gb = 0.0

    # --- Wall time ---
    # Pull from 00_STATE.json if available
    state = _load_json(STATE_PATH, {})
    time_used = state.get("wall_time_used_hours", 0.0)

    # --- Model evaluation (quick stats from test run) ---
    model_stats = _load_json(os.path.join(STEWARD_DIR, "model_eval_stats.json"), {})

    # --- Build the digest ---
    digest = {
        "cycle_number": cycle_number,
        "timestamp_utc": _now_utc(),
        "format_version": "1.0.0",
        "status": {
            "total_decisions": total_entries,
            "pending_queue_items": len(pending_items),
            "approved_items": len(approved_items),
            "denied_items_today": len(denied_today),
            "anomalies_last_3h": len(anomalies),
            "free_disk_gb": free_gb,
            "wall_time_used_hours": time_used,
            "model_stats": model_stats,
        },
        "anomalies": anomalies[-6:],  # last 6 watchdog anomalies, truncate to 3h window
        "pending_queue": pending_items[:10],  # top 10
        "recent_denials": denied_items[:10],
        "summary": _build_summary(pending_items, denied_items, anomalies, free_gb),
    }

    # Write to dated file: digest-<date>.md
    date_str = _now_utc().split("T")[0]
    out_path = os.path.join(DIGEST_DIR, f"digest-{date_str}.md")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    _json_dump(out_path, digest)  # Actually write markdown

    # Also write a human-readable markdown version
    md_path = os.path.join(DIGEST_DIR, f"digest-{date_str}_human.md")
    markdown = _digest_to_markdown(digest)
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(markdown)

    return digest


def _digest_to_markdown(digest: Dict[str, Any]) -> str:
    """Convert the internal digest dict to a human-readable markdown report."""
    s = digest["status"]
    lines = [
        f"# Northstar Steward Digest — {digest['timestamp_utc'][:10]}",
        f"",
        f"## Status Summary",
        f"- **Total Decisions:** {s['total_decisions']}",
        f"- **Pending Queue Items:** {s['pending_queue_items']}",
        f"- **Approved Items:** {s['approved_items']}",
        f"- **Denied Items Today:** {s['denied_items_today']}",
        f"- **Anomalies (last 3h):** {s['anomalies_last_3h']}",
        f"- **Free Disk:** {s['free_disk_gb']:.1f} GB",
        f"- **Wall Time Used:** {s['wall_time_used_hours']:.1f} hours",
        f"- **Model Stats:** accuracy={s['model_stats'].get('accuracy', 'N/A')}, "
        f"false_approve={s['model_stats'].get('false_approve_rate', 'N/A')}, "
        f"seconds/decision={s['model_stats'].get('seconds_per_decision', 'N/A')}",
        f"",
        f"## Recent Anomalies",
    ]
    for a in digest.get("anomalies", [])[:6]:
        lines.append(f"- **{a.get('type', 'unknown')}** @ {a.get('time', '?')}: "
                       f"{a.get('reason', a.get('detail', 'no detail'))[:120]}")
    lines.append(f"")
    lines.append(f"## Pending Queue (top 10)")
    for q in digest.get("pending_queue", [])[:10]:
        what = q.get("what", "?")[:60]
        risk = q.get("risk", "?")[:60]
        lines.append(f"- **{q.get('id', '?')}**: {what} … risk: {risk}")
    lines.append(f"")
    lines.append(f"## Recent Denials")
    for d in digest.get("recent_denials", [])[:10]:
        what = d.get("what", "?")[:60]
        reason = d.get("reason", d.get("why", "?")[:60])
        lines.append(f"- **{d.get('id', '?')}**: {what} … reason: {reason}")
    lines.append(f"")
    lines.append(f"## What to do next")
    pending = digest["status"]["pending_queue_items"]
    if pending > 0:
        lines.append(f"- {pending} items in the needs-you queue — review and approve/deny.")
    lines.append(f"- Check watchdog triggers: any persisted PAUSE flags?")
    lines.append(f"- Verify 00_STATE.json wall_time_used and disk status.")
    lines.append(f"")
    lines.append(f"---\n")
    lines.append(f"*This digest is auto-generated every 3 hours of activity. "
                  f"The owner reviews and approves/denies items in the needs-you queue.*")
    return "\n".join(lines)


def _build_summary(pending_items: List[Dict], denied_items: List[Dict],
                   anomalies: List[Dict], free_gb: float) -> str:
    """Human-readable summary string."""
    parts = []
    if pending_items:
        parts.append(f"{len(pending_items)} pending decisions in queue.")
    if denied_items:
        parts.append(f"{len(denied_items)} items denied today.")
    if anomalies:
        parts.append(f"{len(anomalies)} anomalies detected.")
    if free_gb < 20.0:
        parts.append(f"Disk low: {free_gb:.1f} GB free (< 20 GB minimum).")
    if not parts:
        parts.append("All systems nominal — no immediate attention required.")
    return " ".join(parts)


def daily_digest() -> Dict[str, Any]:
    """Build a full daily digest (one per day). Calls build_digest with special marker."""
    # Reuse build_digest but write to a daily file
    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    digest_path = os.path.join(DIGEST_DIR, f"digest-{date_str}.md")
    # The caller should route to markdown generation; here we just ensure the file exists.
    if not os.path.isfile(digest_path):
        # We'll defer to build_digest later; just create the placeholder.
        _json_dump(digest_path, {"status": {"total_decisions": 0, "pending_queue_items": 0},
                                   "anomalies": [], "pending_queue": [], "recent_denials": [],
                                   "summary": "Daily digest pending — see later cycle."})
    return _load_json(digest_path, {"status": {}, "anomalies": []})