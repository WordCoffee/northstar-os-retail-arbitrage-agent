"""Needs-You Queue — per charter §4.2.

Each item: what, why, risk, what happens if ignored, one-click approve/deny.
Extended from the existing admin room queue.
"""

import json
import os
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
QUEUE_FILE = os.path.join(REPO_ROOT, "shared", "steward", "needs_you_queue.jsonl")


class NeedsYouQueue:
    """Queue of items requiring owner attention (Class C items, ambiguities, failures)."""

    def __init__(self, path: Optional[str] = None):
        self.path = path or QUEUE_FILE
        if not os.path.isfile(self.path):
            open(self.path, "a", encoding="utf-8").close()

    def add_item(self, what: str, why: str, risk: str, if_ignored: str,
                 source_request: Optional[Dict] = None) -> str:
        item = {
            "id": f"need-{int(datetime.now(timezone.utc).timestamp()*1000):d}",
            "what": what,
            "why": why,
            "risk": risk,
            "if_ignored": if_ignored,
            "status": "pending",
            "date_utc": datetime.now(timezone.utc).isoformat(),
            "source_request_id": source_request.get("id", "unknown") if source_request else None,
            "approve": None,
            "deny": None,
            "notes": source_request.get("notes", []) if source_request else [],
        }
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(item, sort_keys=True, separators=(",", ":")) + "\n")
        return item["id"]

    def list_pending(self) -> List[Dict]:
        items = []
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        item = json.loads(line)
                        if item.get("status") == "pending":
                            items.append(item)
        except (OSError, json.JSONDecodeError):
            return items
        return items

    def approve(self, item_id: str, owner_notes: Optional[str] = None) -> bool:
        with open(self.path, "r", encoding="utf-8") as f:
            lines = f.read().strip().split("\n")
        found = False
        new_lines = []
        for line in lines:
            line = line.strip()
            if not line:
                continue
            item = json.loads(line)
            if item.get("id") == item_id:
                item["status"] = "approved"
                item["approve"] = datetime.now(timezone.utc).isoformat()
                item["approve_notes"] = owner_notes
                found = True
            new_lines.append(json.dumps(item, sort_keys=True, separators=(",", ":")))
        if found:
            with open(self.path, "w", encoding="utf-8") as f:
                for nl in new_lines:
                    f.write(nl + "\n")
        return found

    def deny(self, item_id: str, owner_notes: Optional[str] = None) -> bool:
        with open(self.path, "r", encoding="utf-8") as f:
            lines = f.read().strip().split("\n")
        found = False
        new_lines = []
        for line in lines:
            line = line.strip()
            if not line:
                continue
            item = json.loads(line)
            if item.get("id") == item_id:
                item["status"] = "denied"
                item["deny"] = datetime.now(timezone.utc).isoformat()
                item["deny_notes"] = owner_notes
                found = True
            new_lines.append(json.dumps(item, sort_keys=True, separators=(",", ":")))
        if found:
            with open(self.path, "w", encoding="utf-8") as f:
                for nl in new_lines:
                    f.write(nl + "\n")
        return found
