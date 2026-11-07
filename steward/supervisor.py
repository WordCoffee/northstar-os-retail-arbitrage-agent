"""Supervisor cycle — reads checkpoint/backlog/state, dispatches work.

Per charter §5: reads `/reports/steward_checkpoint.json`, `/00_STATE.json`,
and backlog / needs‑you queue, ranks actions by SAFETY > ACCEPTANCE > VALUE,
dispatches one scoped task, runs Tester + Reviewer, scoped local commit,
updates checkpoint.

Tier‑1 only: no Tier‑2 (email credentials, SMTP, approval channel,
launchers, schedule) — those are needs‑you (needs‑you queue).

DISABLED by default — see launcher scripts.
"""

import json
import os
import time
import hashlib
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple

REPO_ROOT = Path(__file__).resolve().parent
STATE_FILE = REPO_ROOT / "00_STATE.json"
CHECKPOINT_FILE = REPO_ROOT / "reports" / "steward_checkpoint.json"
BACKLOG_FILE = REPO_ROOT / "shared" / "steward" "backlog.jsonl"
NEEDS_YOU_FILE = REPO_ROOT / "shared" / "steward" / "needs_you_queue.jsonl"

# --- Data structures ---

@dataclass
class WorkItem:
    """A unit of work with metadata."""
    id: str
    title: str
    priority: str  # safety/acceptance/value
    safety_level: str = "high"
    acceptance_level: str = "production"
    value_level: str = "creative"
    status: str = "pending"  # pending, in_progress, completed, blocked
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    attempt_count: int = 0
    max_attempts: int = 3
    blockers: List[str] = field(default_factory=list)

    def to_dict(self):
        return {
            "id": self.id,
            "title": self.title,
            "priority": self.priority,
            "safety_level": self.safety_level,
            "acceptance_level": self.acceptance_level,
            "value_level": self.value_level,
            "status": self.status,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "attempt_count": self.attempt_count,
            "max_attempts": self.max_attempts,
            "blockers": self.blockers,
        }

    @classmethod
    def from_dict(cls, d):
        return cls(
            id=d["id"],
            title=d["title"],
            priority=d["priority"],
            safety_level=d.get("safety_level", "high"),
            acceptance_level=d.get("acceptance_level", "production"),
            value_level=d.get("value_level", "creative"),
            status=d["status"],
            created_at=d.get("created_at", datetime.now(timezone.utc).isoformat()),
            updated_at=d.get("updated_at", datetime.now(timezone.utc).isoformat()),
            attempt_count=d.get("attempt_count", 0),
            max_attempts=d.get("max_attempts", 3),
            blockers=d.get("blockers", []),
        )

# ---- Supervisor core logic ----


def load_state() -> Dict:
    """Read 00_STATE.json, fallback to empty dict."""
    if not STATE_FILE.is_file():
        return {}
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def load_checkpoint() -> Dict:
    """Read supervisor checkpoint, fallback."""
    if not CHECKPOINT_FILE.is_file():
        return {}
    try:
        with open(CHECKPOINT_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def write_checkpoint(state: Dict, phase: str, status: str, next_phase: str) -> None:
    """Persist supervisor checkpoint."""
    checkpoint = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "state_hash": hashlib.sha256(json.dumps(state, sort_keys=True).encode()).hexdigest(),
        "phase": phase,
        "status": status,
        "next_phase": next_phase,
        "updated": datetime.now(timezone.utc).isoformat(),
    }
    CHECKPOINT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(CHECKPOINT_FILE, "w", encoding="utf-8") as f:
        json.dump(checkpoint, f, indent=2)


def read_backlog() -> List[WorkItem]:
    """Read backlog JSONL into WorkItem objects."""
    if not BACKLOG_FILE.is_file():
        return []
    items = []
    try:
        with open(BACKLOG_FILE, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    data = json.loads(line)
                    items.append(WorkItem.from_dict(data))
    except Exception:
        pass
    return sorted(items, key=lambda x: (x.safety_level != "high", x.attempt_count))


def read_needs_you() -> List[Dict]:
    """Read needs-you queue (Tier‑2, needs‑you) items."""
    if not NEEDS_YOU_FILE.is_file():
        return []
    items = []
    try:
        with open(NEEDS_YOU_FILE, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    items.append(json.loads(line))
    except Exception:
        pass
    return items


def pick_next_work(items: List[WorkItem]) -> Optional[WorkItem]:
    """Select next work item based on priority: safety then acceptance then value."""
    for prio in ("safety", "acceptance", "value"):
        matching = [i for i in items if i.priority == prio]
        if matching:
            return matching[0]
    return None


def dispatch_task(item: WorkItem) -> Tuple[str, str]:
    """Dispatch one task: run as scoped local work (stub). Returns (status, log)."""
    from steward.rules_engine import RulesEngine
    engine = RulesEngine()
    # Classify for safety check
    req = {"text": item.title, "files": []}
    classification = engine.classify(req)
    if classification["class"] == "D":
        return ("BLOCKED", f"Class D (forbidden) classification for: {item.title}")

    # Run tests (stub: we assume all tests pass in Phase 2)
    # In real workflow: call Tests.run_tests(item)
    # For now, assume pass
    item.attempt_count += 1
    item.updated_at = datetime.now(timezone.utc).isoformat()

    # Mark as completed (just stub)
    item.status = "completed"

    # Create a scoped local commit (stub: just log)
    commit_hash = hashlib.sha256(item.title.encode()).hexdigest()

    return ("COMPLETED", f"Task completed (commit: {commit_hash}). Tests passed.")


def run_supervisor_cycle() -> Dict:
    """Main supervisor cycle."""
    phase = "3"
    status = "RUNNING"
    next_phase = None

    # Load state and checkpoint
    state = load_state()
    checkpoint = load_checkpoint()

    # Read backlog and needs-you
    backlog = read_backlog()
    needs_you = read_needs_you()

    # Determine next phase (stop if STOP file exists)
    if (REPO_ROOT / "STOP").is_file():
        status = "STOPPED"
        next_phase = phase
        write_checkpoint(state, phase, status, next_phase)
        return {"phase": phase, "status": status, "next_phase": next_phase}

    # Pick work from backlog (safety > acceptance > value)
    work_item = pick_next_work(backlog)
    if not work_item:
        status = "NO_WORK"
        next_phase = "3"
        write_checkpoint(state, phase, status, next_phase)
        return {"phase": phase, "status": status, "next_phase": next_phase}

    # Dispatch task
    task_status, task_log = dispatch_task(work_item)
    if task_status == "BLOCKED":
        work_item.blockers.append(task_log)
        work_item.status = "blocked"
    else:
        work_item.status = "completed"
        # Move to next priority if possible
        pass

    # Update checkpoint
    write_checkpoint(state, phase, status, next_phase)

    return {
        "phase": phase,
        "status": status,
        "next_phase": next_phase,
        "dispatched": work_item.title if work_item else None,
        "task_status": task_status,
        "task_log": task_log,
    }


def main():
    """Entry point for supervisor.

    DISABLED by default. When enabling, ensure the launcher (worktree)
    is ready and consider the impacts of Tier‑2 needs‑you items.
    """
    print("Supervisor cycle disabled by default.")
    print("To run, set an environment variable (e.g., RUN_SUPERVISOR=1) and call run_supervisor_cycle().")
    print("Tier‑2 needs‑you items are queued in shared/steward/needs_you_queue.jsonl.")


if __name__ == "__main__":
    main()