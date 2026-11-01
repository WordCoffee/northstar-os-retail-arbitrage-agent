"""PROBE B — an unreadable HITL record must not vanish from the count.

`agent_kernel.hitl_counts` skips a corrupt or unreadable `hitl_*.json` with a bare
`continue`. The operator then sees a queue with fewer items than exist, and no
signal that anything was dropped.

Required behaviour:
  * valid records are still counted exactly as before
  * unreadable records are reported (a `skipped` count at minimum)
  * `total` still means the number of counted statuses, not files on disk
"""
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "Northstar_backend"))

from agent_kernel.hitl_counts import hitl_counts

failures = []


def check(label, ok, detail=""):
    print(("PASS " if ok else "FAIL ") + label + (f": {detail}" if detail else ""))
    if not ok:
        failures.append(label)


root = Path(tempfile.mkdtemp())
hitl = root / "state" / "hitl"
hitl.mkdir(parents=True)
(hitl / "hitl_a.json").write_text(json.dumps({"status": "pending"}), encoding="utf-8")
(hitl / "hitl_b.json").write_text(json.dumps({"status": "approved"}), encoding="utf-8")
(hitl / "hitl_c.json").write_text("{ this is not json", encoding="utf-8")
(hitl / "hitl_d.json").write_bytes(b"\x00\x01binary")

counts = hitl_counts(root)
check("pending counted", counts.get("pending") == 1, str(counts))
check("approved counted", counts.get("approved") == 1, str(counts))
check("counted total unchanged", counts.get("total") == 2, str(counts))
check("unreadable records are reported", int(counts.get("skipped") or 0) == 2, str(counts))

empty = Path(tempfile.mkdtemp())
clean = hitl_counts(empty)
check("a missing state dir still returns zeros", clean.get("total") == 0, str(clean))

if failures:
    print(f"\nRESULT FAIL ({len(failures)}): {failures}")
    raise SystemExit(1)
print("\nRESULT PASS")
raise SystemExit(0)
