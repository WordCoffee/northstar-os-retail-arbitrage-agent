"""Hash-chained Decision Ledger — append-only, immutable audit chain.

Per charter §4.1: Every decision is a record: id, requester, class, decision,
rationale, evidence refs, time. Hash-chained (reuse the audit chain approach).
Append-only. Verified by the watchdog.

Ledger entries are stored in shared/steward/ledger.jsonl.
Each entry has a sha256 hash linking it to the prior entry's hash (genesis has hash of "genesis").
"""

import hashlib
import json
import os
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LEDGER_PATH = os.path.join(REPO_ROOT, "shared", "steward", "ledger.jsonl")


def genesis_hash() -> str:
    """The genesis hash (first entry) — hash of 'genesis'."""
    return hashlib.sha256(b"genesis").hexdigest()


def compute_entry_hash(prev_hash: str, entry: Dict) -> str:
    """Compute SHA-256 hash for this entry = SHA-256(prev_hash + JSON of entry, sorted keys)."""
    ordered = json.dumps(entry, sort_keys=True, separators=(",", ":"))
    data = prev_hash + ordered
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def load_ledger() -> List[Dict]:
    """Load the full append-only ledger from disk. Returns empty list if nonexistent."""
    entries = []
    if not os.path.isfile(LEDGER_PATH):
        return entries
    try:
        with open(LEDGER_PATH, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    entries.append(json.loads(line))
    except (json.JSONDecodeError, OSError):
        return entries
    return entries


def append_entry(requester: str, request_class: str, decision: str,
                 rationale: str, evidence_refs: Optional[List[str]] = None) -> Dict:
    """Append a new entry to the ledger and return the entry dict.

    The entry is hash-chained to the prior entry. The returned dict includes
    the entry's own sha256 hash for reference.
    """
    entries = load_ledger()
    # Find the last entry that has a sha256 hash (skip watchdog_pause entries).
    prev_hash = genesis_hash()
    for e in reversed(entries):
        if "sha256" in e and isinstance(e["sha256"], str):
            prev_hash = e["sha256"]
            break

    # Build the entry structure.
    entry = {
        "id": f"ledger-{int(time.time()*1000)}-{len(entries)}",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "requester": requester,
        "class": request_class,
        "decision": decision,
        "rationale": rationale,
        "evidence_refs": evidence_refs or [],
        "prev_hash": prev_hash,
    }

    # Compute hash: SHA-256(prev_hash + json(entry sorted keys))
    entry["sha256"] = compute_entry_hash(prev_hash, {k: v for k, v in entry.items()
                                                   if k != "sha256" and k != "prev_hash"})

    # Append as JSONL line.
    with open(LEDGER_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, sort_keys=True, separators=(",", ":")) + "\n")

    # Also verify against existing entries and record verification result.
    # (Watchdog will re-verify on each cycle.)
    # Also, record the head hash.
    _record_head_hash(entry["sha256"])

    return entry


def _record_head_hash(head_hash: str) -> None:
    """Write the current head hash to a known path; used by watchdog verification."""
    head_path = os.path.join(REPO_ROOT, "shared", "steward", "ledger_head_hash.txt")
    with open(head_path, "w", encoding="utf-8") as f:
        f.write(head_hash)


def verify_ledger_integrity() -> Tuple[bool, Optional[str]]:
    """Verify the hash chain across all ledger entries.

    Returns (ok, broken_at) where broken_at is the entry id where the chain fails,
    or None if all is well.
    """
    entries = load_ledger()
    if not entries:
        return True, None  # Nothing to verify; no breakage.

    expected_hash = genesis_hash()
    for i, entry in enumerate(entries):
        # Skip entries without sha256 (watchdog_pause entries, etc.)
        if "sha256" not in entry:
            continue
        # Each entry's sha256 should equal expected_hash.
        if entry.get("sha256") != expected_hash:
            # The hash at this position is wrong.
            # Find the actual prev hash from the prior ledger entry.
            actual_prev = genesis_hash()
            for j in range(i - 1, -1, -1):
                if "sha256" in entries[j]:
                    actual_prev = entries[j]["sha256"]
                    break
            if entry.get("prev_hash") != actual_prev:
                return False, entry.get("id", f"entry-{i}")
            # Also attempt to compute from prev.
            computed = compute_entry_hash(actual_prev, {k: v for k, v in entry.items()
                                               if k not in ("sha256", "prev_hash")})
            if computed != entry.get("sha256"):
                return False, entry.get("id", f"entry-{i}")
        # Move to next expected hash.
        expected_hash = entry["sha256"]
    return True, None


def get_ledger_summary() -> Dict:
    """Return a summary of the ledger: last few entries, chain status, health."""
    entries = load_ledger()
    ok, broken = verify_ledger_integrity()
    last_5 = entries[-5:] if len(entries) >= 5 else entries
    return {
        "total_entries": len(entries),
        "chain_integrity": "ok" if ok else "broken",
        "broken_at": broken,
        "last_5_ids": [e["id"] for e in last_5],
        "last_5_time": [e["timestamp_utc"] for e in last_5],
        "last_5_classes": [e["class"] for e in last_5],
        "head_hash": entries[-1]["sha256"] if entries else genesis_hash(),
    }