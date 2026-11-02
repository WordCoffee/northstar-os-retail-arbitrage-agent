"""PROBE E — a degenerate dieline quad must be refused, not measured.

`print_prep.face_pixels` measures the face as the mean of opposite edges. A collinear
or coincident quad has zero area but still yields positive edge means, so the print
gate receives a "face" that no die can cut.

Required behaviour:
  * a collinear quad is refused with ValueError
  * a quad whose corners coincide is refused with ValueError
  * a valid quad still returns width/height
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "Northstar_backend"))

import print_prep

failures = []


def check(label, ok, detail=""):
    print(("PASS " if ok else "FAIL ") + label + (f": {detail}" if detail else ""))
    if not ok:
        failures.append(label)


def refused(label, quad):
    try:
        got = print_prep.face_pixels(quad)
    except ValueError as exc:
        check(label, True, str(exc)[:80])
        return
    except Exception as exc:  # noqa: BLE001
        check(label, False, f"raised {type(exc).__name__}")
        return
    check(label, False, f"accepted -> {got}")


refused("collinear quad", [[0, 0], [5, 0], [10, 0], [15, 0]])
refused("coincident corners", [[7, 7], [7, 7], [7, 7], [7, 7]])
refused("two points repeated", [[0, 0], [0, 0], [0, 100], [0, 100]])

try:
    good = print_prep.face_pixels([[0, 0], [100, 0], [100, 200], [0, 200]])
    check("valid quad", good["width"] == 100 and good["height"] == 200, str(good))
except Exception as exc:  # noqa: BLE001
    check("valid quad", False, f"raised {type(exc).__name__}: {exc}")

if failures:
    print(f"\nRESULT FAIL ({len(failures)}): {failures}")
    raise SystemExit(1)
print("\nRESULT PASS")
raise SystemExit(0)
