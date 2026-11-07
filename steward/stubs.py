"""Stubs (§4.8): STUB, xfail, and blocker entry management.

Per charter §4.8: "Stubs: allowed only as STUB(<blocker-id>) with an xfail
test and a blockers-file entry. A stub is never 'done'."

This module provides:
- STUB marker format and validation
- xfail test generation for stubs
- Blocker file entry management (shared/steward/blockers.jsonl)
"""

import json
import os
import re
from datetime import datetime, timezone
from typing import Dict, List, Optional

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BLOCKERS_FILE = os.path.join(REPO_ROOT, "shared", "steward", "blockers.jsonl")


class StubMarker:
    """A stub marker in code: STUB(<blocker-id>)."""

    PATTERN = re.compile(r"STUB\(([A-Z0-9_-]+)\)")

    @staticmethod
    def format(blocker_id: str) -> str:
        """Format a stub marker for code insertion."""
        return f"STUB({blocker_id})"

    @staticmethod
    def parse(text: str) -> List[str]:
        """Extract all STUB markers from text."""
        return StubMarker.PATTERN.findall(text)

    @staticmethod
    def validate(text: str, blockers_file: Optional[str] = None) -> bool:
        """Validate that every STUB marker has a corresponding blocker entry."""
        markers = StubMarker.parse(text)
        if not markers:
            return True
        blockers = load_blockers(blockers_file)
        blocker_ids = {b.get("id") for b in blockers}
        return all(m in blocker_ids for m in markers)


def load_blockers(path: Optional[str] = None) -> List[Dict]:
    """Load all blocker entries from the blockers file.

    Deduplicates by ``id`` (last write wins) so repeated add/close cycles or
    stale duplicate rows cannot inflate the list.
    """
    path = path or BLOCKERS_FILE
    entries = []
    if not os.path.isfile(path):
        return entries
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    entries.append(json.loads(line))
    except (OSError, json.JSONDecodeError):
        return entries
    # Deduplicate by id, keeping the last occurrence.
    seen = {}
    for e in entries:
        seen[e.get("id")] = e
    return list(seen.values())


def add_blocker(blocker_id: str, description: str, file_path: str,
                xfail_test: Optional[str] = None, path: Optional[str] = None) -> Dict:
    """Add a new blocker entry to the blockers file.

    If an entry with the same id already exists, it is replaced in place rather
    than duplicated.
    """
    target = path or BLOCKERS_FILE
    entry = {
        "id": blocker_id,
        "description": description,
        "file_path": file_path,
        "xfail_test": xfail_test,
        "status": "open",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    existing = load_blockers(target)
    new_entries = [e for e in existing if e.get("id") != blocker_id]
    new_entries.append(entry)
    with open(target, "w", encoding="utf-8") as f:
        for e in new_entries:
            f.write(json.dumps(e, sort_keys=True, separators=(",", ":")) + "\n")
    return entry


def close_blocker(blocker_id: str) -> bool:
    """Close a blocker entry (mark as resolved)."""
    entries = load_blockers()
    found = False
    new_entries = []
    for e in entries:
        if e.get("id") == blocker_id:
            e["status"] = "resolved"
            e["resolved_at"] = datetime.now(timezone.utc).isoformat()
            found = True
        new_entries.append(e)
    if found:
        with open(BLOCKERS_FILE, "w", encoding="utf-8") as f:
            for e in new_entries:
                f.write(json.dumps(e, sort_keys=True, separators=(",", ":")) + "\n")
    return found


def generate_xfail_test(stub_marker: str, test_name: str) -> str:
    """Generate an xfail test for a stub marker."""
    return f'''import pytest

@pytest.mark.xfail(reason="STUB: {stub_marker} - not yet implemented")
def test_{test_name}():
    """This test is expected to fail until {stub_marker} is resolved."""
    raise NotImplementedError("STUB: {stub_marker}")
'''