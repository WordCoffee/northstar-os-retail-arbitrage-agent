"""Northstar Steward Watchdog — standalone safety machinery.

Per charter §4.5: A deterministic watchdog (no LLM) can pause everything, and
the Steward cannot disable it.

The watchdog runs every minute (via Windows Task Scheduler or as a separate
process) and checks:
  - Heartbeats from Steward/Builder/Tester/Reviewer
  - Wall-time and attempt caps
  - Free disk below threshold → pause everything
  - Forbidden-path changes in any diff
  - Hash mismatch on charter, policy files, or watchdog itself
  - Test count dropping
  - Diff far larger than task's declared scope
  - More than 3 attempts on one item
  - 2 failed phases in a row

On trigger: writes PAUSE, records why, notifies through digest and local
Windows notification. The Steward can never disable it.
"""

import json
import os
import sys
import time
import hashlib
from datetime import datetime, timezone, timedelta

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # project root
STEWARD_DIR = os.path.join(REPO_ROOT, "steward")
LEDGER_PATH = os.path.join(REPO_ROOT, "shared", "steward", "ledger.jsonl")
CHARTER_PATH = os.path.join(REPO_ROOT, "shared", "steward", "charter.json")
AGENTS_MD = os.path.join(REPO_ROOT, "AGENTS.md")
CONSTITUTION = os.path.join(REPO_ROOT, "docs", "OPERATING_CONSTITUTION.md")
POLICY_FILES = [
    os.path.join(REPO_ROOT, "shared", "master-brain", "brain_policy.json"),
    os.path.join(REPO_ROOT, "shared", "usage-caps.json"),
    os.path.join(REPO_ROOT, "chromecontrol_policy_owner.json"),
]

PAUSE_FILE = os.path.join(STEWARD_DIR, "STOP")
STATE_FILE = os.path.join(REPO_ROOT, "00_STATE.json")
LAST_TEST_COUNT_FILE = os.path.join(STEWARD_DIR, "last_test_count.json")
PAUSED_FILE = os.path.join(STEWARD_DIR, "PAUSED.json")
WATCHDOG_HASH_FILE = os.path.join(STEWARD_DIR, "watchdog_hash.json")

CAPS = {
    "wall_time_hours": 8,
    "attempts_per_item": 3,
    "daily_task_cap": 20,
    "free_disk_gb_minimum": 20.0,
    "free_disk_pause": 10.0,
    "tool_calls_per_item": 1000,
}

# Expected hash of this watchdog file (verifies integrity of itself).
# This will be computed once at first run and then checked on each run.
WATCHDOG_SELF_HASH_PATH = os.path.join(STEWARD_DIR, "watchdog.py")


def _sha256_file(path: str) -> Optional[str]:
    if not os.path.isfile(path):
        return None
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(8192), b""):
            h.update(block)
    return h.hexdigest()


def _json_load(path: str, default: Any = None) -> Any:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return default


def _json_dump(path: str, data: Any) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


class Watchdog:
    """Standalone safety monitor. No LLM. Halts on any violation."""

    def __init__(self):
        self.reasons = []
        self._expected_watchdog_hash = self._load_expected_hash()

    def _load_expected_hash(self) -> Optional[str]:
        data = _json_load(WATCHDOG_HASH_FILE, {})
        return data.get("watchdog_hash")

    def _save_watchdog_hash(self, path: str) -> None:
        h = _sha256_file(path)
        if h:
            _json_dump(WATCHDOG_HASH_FILE, {"watchdog_hash": h, "updated_at": datetime.now(timezone.utc).isoformat()})
            self._expected_watchdog_hash = h

    # ------------------------------------------------------------------
    # Check methods (return True if violation found)
    # ------------------------------------------------------------------

    def check_kill_switch(self) -> Optional[str]:
        """If STOP file exists, pause everything."""
        if os.path.isfile(PAUSE_FILE):
            return f"KILL_SWITCH: {PAUSE_FILE} exists"
        return None

    def check_away_mode_expiry(self) -> Optional[str]:
        """Away mode expires after 48h without owner check-in. Drop to maintenance."""
        state = _json_load(STATE_FILE, {})
        away = state.get("away_mode", {})
        if away.get("enabled"):
            expiry_ts = away.get("expiry_utc")
            now = datetime.now(timezone.utc)
            if expiry_ts:
                expiry = datetime.fromisoformat(expiry_ts.replace("Z", "+00:00"))
                if now > expiry:
                    return "AWAY_MODE_EXPIRED: maintenance only (no new feature work, no class B)"
                # If it's expired but still within some grace period, still pause
                gap_hours = (now - expiry).total_seconds() / 3600
                if gap_hours > 24:
                    return "AWAY_MODE_EXPIRED: maintenance only"
        return None

    def check_free_disk(self) -> Optional[str]:
        """Free disk below threshold pauses everything."""
        try:
            import shutil
            total, used, free = shutil.disk_usage(REPO_ROOT)
            free_gb = free / (1024 ** 3)
            if free_gb < CAPS["free_disk_gb_minimum"]:
                return f"DISK_LOW: {free_gb:.1f} GB free (min {CAPS['free_disk_gb_minimum']})"
        except Exception as exc:
            return f"DISK_CHECK_ERROR: {exc}"
        return None

    def check_forbidden_path_diff(self, diff_paths: list) -> Optional[str]:
        """If diff contains forbidden paths (charter/policy/watchdog/audit), pause."""
        forbidden_files = [
            AGENTS_MD, CONSTITUTION, PAUSE_FILE, WATCHDOG_SELF_HASH_PATH,
            LEDGER_PATH,
        ]
        forbidden_files.extend(POLICY_FILES)
        found = []
        for p in diff_paths:
            norm = os.path.normpath(p).lower().replace("\\", "/")
            for fb in forbidden_files:
                fb_norm = os.path.normpath(fb).lower().replace("\\", "/")
                fb_rel = fb_norm.replace(REPO_ROOT.lower().replace("\\", "/"), "").lstrip("/")
                fb_basename = os.path.basename(fb_norm)
                if norm == fb_norm or norm == fb_rel or norm == fb_basename or norm.endswith("/" + fb_rel):
                    found.append(p)
                    break
        if found:
            return f"FORBIDDEN_PATH_DIFF: {found}"
        return None

    def check_watchdog_hash_integrity(self) -> Optional[str]:
        """Hash mismatch on watchdog itself → tampering detected."""
        current = _sha256_file(WATCHDOG_SELF_HASH_PATH)
        expected = self._expected_watchdog_hash
        if expected is None:
            # First run: save the expected hash.
            self._save_watchdog_hash(WATCHDOG_SELF_HASH_PATH)
            return None
        if current != expected:
            return f"WATCHDOG_HASH_MISMATCH: expected {expected[:12]}... got {current[:12]}..."
        return None

    def check_charter_policy_hash(self) -> Optional[str]:
        """Hash mismatch on charter/policy files → unauthorized change."""
        files = [CHARTER_PATH] + POLICY_FILES + [AGENTS_MD, CONSTITUTION]
        stored = _json_load(os.path.join(STEWARD_DIR, "protected_hashes.json"), {})
        mismatches = []
        for fpath in files:
            h = _sha256_file(fpath)
            if h is None:
                continue
            if stored.get(fpath) is None:
                stored[fpath] = h
            elif stored[fpath] != h:
                mismatches.append(fpath)
        if mismatches:
            _json_dump(os.path.join(STEWARD_DIR, "protected_hashes.json"), stored)
            return f"PROTECTED_FILE_CHANGE: {mismatches}"
        return None

    def check_test_count_dropping(self, current_count: int) -> Optional[str]:
        """Test count dropped → regression risk."""
        last = _json_load(LAST_TEST_COUNT_FILE, {})
        prev = last.get("test_count")
        if prev is not None and current_count < prev:
            return f"TEST_COUNT_DROP: {prev} -> {current_count}"
        _json_dump(LAST_TEST_COUNT_FILE, {"test_count": current_count, "at": datetime.now(timezone.utc).isoformat()})
        return None

    def check_diff_scope(self, diff_paths: list, declared_max: int) -> Optional[str]:
        """Diff larger than declared scope → overreach."""
        if len(diff_paths) > declared_max:
            return f"DIFF_SCOPE_EXCEEDED: {len(diff_paths)} files > declared max {declared_max}"
        return None

    def check_attempts(self, task_id: str, attempts: int) -> Optional[str]:
        """More than 3 attempts on one item → stop."""
        if attempts >= CAPS["attempts_per_item"]:
            return f"ATTEMPTS_EXCEEDED: {task_id} has {attempts} attempts (cap {CAPS['attempts_per_item']})"
        return None

    def check_tool_calls(self, task_id: str, tool_calls: int) -> str:
        """Tool-call cap per item -> stop."""
        if tool_calls >= CAPS["tool_calls_per_item"]:
            return f"TOOL_CALL_CAP_EXCEEDED: {task_id} has {tool_calls} tool calls (cap {CAPS['tool_calls_per_item']})"
        return None

    def check_phases_failing(self, failed_phases: int) -> Optional[str]:
        """2 failed phases in a row → pause."""
        if failed_phases >= 2:
            return f"PHASES_FAILED: {failed_phases} consecutive failures"
        return None

    def check_wall_time(self, start_time_iso: str) -> Optional[str]:
        """8 hours wall time per run."""
        try:
            start = datetime.fromisoformat(start_time_iso.replace("Z", "+00:00"))
            elapsed_hours = (datetime.now(timezone.utc) - start).total_seconds() / 3600
            if elapsed_hours > CAPS["wall_time_hours"]:
                return f"WALL_TIME_EXCEEDED: {elapsed_hours:.1f}h > {CAPS['wall_time_hours']}h"
        except Exception:
            pass
        return None

    # ------------------------------------------------------------------
    # Main cycle
    # ------------------------------------------------------------------

    def run_cycle(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Run one watchdog cycle. Returns {paused: bool, reasons: list}."""
        self.reasons = []

        # Collect all violation checks.
        checks = [
            ("kill_switch", self.check_kill_switch()),
            ("away_mode", self.check_away_mode_expiry()),
            ("free_disk", self.check_free_disk()),
            ("forbidden_path", self.check_forbidden_path_diff(context.get("diff_paths", []))),
            ("watchdog_hash", self.check_watchdog_hash_integrity()),
            ("charter_policy_hash", self.check_charter_policy_hash()),
            ("test_count_drop", self.check_test_count_dropping(context.get("test_count", 0))),
            ("diff_scope", self.check_diff_scope(context.get("diff_paths", []), context.get("declared_max_files", 100))),
            ("attempts", self.check_attempts(context.get("task_id", ""), context.get("attempts", 0))),
            ("phases_failed", self.check_phases_failing(context.get("failed_phases", 0))),
            ("wall_time", self.check_wall_time(context.get("run_started_at", datetime.now(timezone.utc).isoformat()))),
        ]

        for name, reason in checks:
            if reason:
                self.reasons.append({"check": name, "reason": reason})

        paused = len(self.reasons) > 0

        # Write pause state.
        pause_state = {
            "paused": paused,
            "reasons": self.reasons,
            "at": datetime.now(timezone.utc).isoformat(),
            "cycle": context.get("cycle", 0),
        }
        _json_dump(PAUSED_FILE, pause_state)

        if paused:
            self._notify_windows(pause_state)

        return pause_state

    def _notify_windows(self, state: Dict[str, Any]) -> None:
        """Emit a local Windows notification + write to pause log."""
        msg = " | ".join(r["reason"] for r in state["reasons"] if r)
        # Write to a pause notification file (non-blocking, no subprocess).
        try:
            notify_path = os.path.join(STEWARD_DIR, "watchdog_notify.txt")
            with open(notify_path, "w", encoding="utf-8") as f:
                f.write(f"{state['at']}: PAUSED - {msg}\n")
        except Exception:
            pass
        # Always append to ledger as best-effort.
        try:
            ledger_entry = {
                "event": "watchdog_pause",
                "reasons": self.reasons,
                "timestamp_utc": state["at"],
            }
            with open(LEDGER_PATH, "a", encoding="utf-8") as f:
                f.write(json.dumps(ledger_entry, sort_keys=True) + "\n")
        except Exception:
            pass
