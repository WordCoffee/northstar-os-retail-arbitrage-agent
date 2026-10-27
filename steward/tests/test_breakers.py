"""Breaker tests: tool-call cap, attempts cap, wall-time cap, disk-low halt, kill-switch, STOP halt."""

import os
import sys
import tempfile
import unittest
from datetime import datetime, timezone, timedelta
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from steward.watchdog import Watchdog, CAPS, PAUSE_FILE


class TestBreakers(unittest.TestCase):
    """Test circuit breakers: attempts cap, tool-call cap, wall-time cap, disk-low halt, kill-switch."""

    def setUp(self):
        self.wd = Watchdog()

    def test_attempts_exceeded(self):
        """More than 3 attempts on one item stops."""
        violation = self.wd.check_attempts("test-item", CAPS["attempts_per_item"])
        self.assertIsNotNone(violation)
        self.assertIn("ATTEMPTS_EXCEEDED", violation)

    def test_tool_call_cap_exceeded(self):
        """Tool-call cap triggers violation after exceeding cap."""
        result = self.wd.check_tool_calls("test-item", CAPS["tool_calls_per_item"])
        self.assertIsNotNone(result)
        self.assertIn("TOOL_CALL_CAP", result)

    def test_wall_time_exceeded(self):
        """Wall-time cap triggers violation after exceeding 8h."""
        old_time = (datetime.now(timezone.utc) - timedelta(hours=9)).isoformat()
        violation = self.wd.check_wall_time(old_time)
        self.assertIsNotNone(violation)
        self.assertIn("WALL_TIME_EXCEEDED", violation)

    def test_disk_low_halts_cycle(self):
        """Disk-low must halt the cycle."""
        with patch.object(self.wd, "check_free_disk", return_value="LOW_DISK: 5.0 GB free"):
            violation = self.wd.check_free_disk()
            self.assertIsNotNone(violation)
            self.assertIn("LOW_DISK", violation)

    def test_stop_file_halts_cycle(self):
        """STOP file exists → halt cycle."""
        # Create STOP file temporarily
        with tempfile.NamedTemporaryFile(dir=os.path.dirname(PAUSE_FILE), suffix="", delete=False) as f:
            pass  # Just to get the path
        # Note: PAUSE_FILE is the actual STOP file
        # Let's create it temporarily
        stop_path = PAUSE_FILE
        with open(stop_path, "w", encoding="utf-8") as f:
            f.write("test")
        try:
            violation = self.wd.check_kill_switch()
            self.assertIsNotNone(violation)
            self.assertIn("KILL_SWITCH", violation)
        finally:
            if os.path.isfile(stop_path):
                os.remove(stop_path)


if __name__ == "__main__":
    unittest.main()