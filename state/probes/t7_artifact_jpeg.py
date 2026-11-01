"""PROBE D — a JPEG artifact must be classified as an image, not as binary.

`agent_kernel.artifacts.artifact_kind` decides how an evidence artefact is labelled.
It recognises PNG and MP4 by magic bytes but has no JPEG branch, so a perfectly
valid `.jpg` produced by the A+ lane (which may emit JPEG when a module exceeds
2 MB) is reported as `binary`. Evidence then cannot tell a rendered module from an
opaque blob.

Required behaviour:
  * a valid JPEG (SOI `FF D8 FF` … EOI `FF D9`) → `image_jpeg`
  * a `.jpg` whose magic bytes are wrong → `jpeg_invalid`
  * PNG and MP4 behaviour is unchanged
"""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "Northstar_backend"))

from agent_kernel.artifacts import artifact_kind

# Smallest structurally valid JPEG: SOI, APP0/JFIF, EOI.
JPEG = bytes.fromhex(
    "ffd8ffe000104a46494600010100000100010000"
    "ffdb004300" + "08" * 64 +
    "ffc0000b080001000101011100" +
    "ffda0008010100003f00d2cf20" +
    "ffd9")

failures = []


def check(label, ok, detail=""):
    print(("PASS " if ok else "FAIL ") + label + (f": {detail}" if detail else ""))
    if not ok:
        failures.append(label)


root = Path(tempfile.mkdtemp())

good = root / "module.jpg"
good.write_bytes(JPEG)
check("valid jpeg classified as an image", artifact_kind(good) == "image_jpeg",
      f"got {artifact_kind(good)!r}")

bad = root / "broken.jpg"
bad.write_bytes(b"not-a-jpeg")
check("broken jpeg magic refused", artifact_kind(bad) == "jpeg_invalid",
      f"got {artifact_kind(bad)!r}")

png = root / "label.png"
png.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 16)
check("png unchanged", artifact_kind(png) == "label_png", f"got {artifact_kind(png)!r}")

mp4 = root / "ad.mp4"
mp4.write_bytes(b"\x00\x00\x00\x18ftypisom" + b"\x00" * 8)
check("mp4 unchanged", artifact_kind(mp4) == "ad_video", f"got {artifact_kind(mp4)!r}")

text = root / "notes.md"
text.write_text("x", encoding="utf-8")
check("text unchanged", artifact_kind(text) == "text", f"got {artifact_kind(text)!r}")

if failures:
    print(f"\nRESULT FAIL ({len(failures)}): {failures}")
    raise SystemExit(1)
print("\nRESULT PASS")
raise SystemExit(0)
