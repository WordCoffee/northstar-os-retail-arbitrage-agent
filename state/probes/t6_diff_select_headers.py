"""PROBE C — a selected-hunk diff must still be a valid diff.

`agent_kernel.diff.select_hunks` joins the hunk bodies and drops the `--- a/file`
and `+++ b/file` headers, so the result cannot be applied by the kernel's editor
or by `git apply`: it is a fragment with no target file. Reviewers select hunks
from this text, so the selection must remain self-describing.

Required behaviour:
  * selecting one hunk keeps the file headers and exactly one hunk
  * selecting both hunks keeps both and the headers
  * selecting nothing returns an empty string
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "Northstar_backend"))

from agent_kernel.diff import parse_diff, select_hunks

DIFF = """--- a/x.txt
+++ b/x.txt
@@ -1,2 +1,2 @@
-old
+new
 same
@@ -10 +10 @@
-late
+later
"""

failures = []


def check(label, ok, detail=""):
    print(("PASS " if ok else "FAIL ") + label + (f": {detail}" if detail else ""))
    if not ok:
        failures.append(label)


one = select_hunks(DIFF, [1])
check("one hunk keeps the file header",
      one.startswith("--- a/x.txt\n+++ b/x.txt\n"), repr(one[:40]))
check("one hunk parses as exactly one hunk", len(parse_diff(one)) == 1,
      str(len(parse_diff(one))))
check("the selected hunk is the second one", "late" in one and "old" not in one, "")

both = select_hunks(DIFF, [0, 1])
check("both hunks parse as two", len(parse_diff(both)) == 2, str(len(parse_diff(both))))
check("both hunks keep the header", both.startswith("--- a/x.txt\n+++ b/x.txt\n"),
      repr(both[:40]))

check("nothing selected is empty", select_hunks(DIFF, []) == "",
      repr(select_hunks(DIFF, [])[:40]))

if failures:
    print(f"\nRESULT FAIL ({len(failures)}): {failures}")
    raise SystemExit(1)
print("\nRESULT PASS")
raise SystemExit(0)
