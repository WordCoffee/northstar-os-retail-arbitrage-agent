"""PROBE T1 — the print gate must refuse a quad that cannot belong to the image.

`print_prep.dpi_report(profile, image_size, quad)` computes DPI from the QUAD only
and never looks at `image_size`. A quad measured on a 2000 px render, replayed
against a 200 px file, still reports a printable DPI — so the 300 DPI gate can be
satisfied by a file that could never print.

Required behaviour:
  * a non-positive image size is refused
  * a face larger than the image it claims to describe is refused
  * a consistent pair still reports a DPI (the fix must not refuse everything)
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "Northstar_backend"))

import geometry_profiles
import print_prep

failures = []


def expect_refusal(label, fn):
    try:
        value = fn()
    except ValueError as exc:
        print(f"PASS {label}: refused -> {str(exc)[:110]}")
        return
    except Exception as exc:  # noqa: BLE001 - a different exception is still a miss
        failures.append(label)
        print(f"FAIL {label}: raised {type(exc).__name__}, wanted ValueError")
        return
    failures.append(label)
    print(f"FAIL {label}: accepted -> {str(value)[:130]}")


profile = geometry_profiles.profile("bottle")
quad = profile["quad"]
print("profile quad:", quad)

expect_refusal("zero image size", lambda: print_prep.dpi_report(profile, (0, 0), quad))
expect_refusal("negative image size", lambda: print_prep.dpi_report(profile, (-5, 100), quad))
expect_refusal("face larger than the image",
               lambda: print_prep.dpi_report(profile, (100, 100), quad))

try:
    good = print_prep.dpi_report(profile, (800, 1200), quad)
except Exception as exc:  # noqa: BLE001
    failures.append("positive control")
    print(f"FAIL positive control raised {type(exc).__name__}: {exc}")
else:
    worst = float(good.get("worst") or 0)
    if worst <= 0:
        failures.append("positive control")
        print(f"FAIL positive control reported worst={worst}")
    else:
        print(f"PASS positive control: worst={worst} dpi")

if failures:
    print(f"\nRESULT FAIL ({len(failures)}): {failures}")
    raise SystemExit(1)
print("\nRESULT PASS")
raise SystemExit(0)
