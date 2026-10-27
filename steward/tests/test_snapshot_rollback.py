"""Snapshot/rollback tests: change, snapshot, restore, hashes equal; quarantine delete and restore."""

import hashlib
import json
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from steward.folder_grants import (
    snapshot_write,
    quarantine_delete,
    SNAPSHOTS_DIR,
    QUARANTINE_DIR,
)


class TestSnapshotRollback(unittest.TestCase):
    """Snapshot/rollback cycle integrity tests."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.test_file = os.path.join(self.tmpdir, "test_file.txt")
        with open(self.test_file, "w", encoding="utf-8") as f:
            f.write("original content")

    def tearDown(self):
        if os.path.isdir(self.tmpdir):
            shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _hash_file(self, path):
        with open(path, "rb") as f:
            return hashlib.sha256(f.read()).hexdigest()

    def test_snapshot_restore_hashes_equal(self):
        """Change file, snapshot, restore, hashes must be equal."""
        # Take snapshot of original
        snap_path = snapshot_write(self.test_file, "test_snapshot")
        self.assertIsNotNone(snap_path, "Snapshot should be created")
        self.assertTrue(os.path.isfile(snap_path), f"Snapshot not created at {snap_path}")

        # Modify file
        with open(self.test_file, "w", encoding="utf-8") as f:
            f.write("modified content")

        # Restore from snapshot
        shutil.copy2(str(snap_path), self.test_file)

        # Hashes must be equal (content must match original)
        with open(self.test_file, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertEqual(content, "original content",
                         f"Restore failed: got '{content}'")

    def test_quarantine_delete_and_restore(self):
        """Quarantine a file, verify it's gone from original location, restore, verify content."""
        # Quarantine
        q_path = quarantine_delete(self.test_file)
        self.assertIsNotNone(q_path, "Quarantine should return a path")
        self.assertFalse(os.path.isfile(self.test_file),
                         "File should be removed from original location after quarantine")
        self.assertTrue(os.path.isfile(q_path),
                        f"Quarantined file not found at {q_path}")

        # Restore
        shutil.copy2(str(q_path), self.test_file)
        self.assertTrue(os.path.isfile(self.test_file),
                        f"Restored file not found at {self.test_file}")
        with open(self.test_file, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertEqual(content, "original content",
                         f"Restored content mismatch: '{content}'")


if __name__ == "__main__":
    unittest.main()