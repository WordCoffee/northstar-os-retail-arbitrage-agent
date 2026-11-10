"""Add the three model-authored behavioral-fix tasks to the loop registry.

Idempotent: re-running replaces entries with the same id instead of duplicating.
The probes under state/probes/ are the independent acceptance evidence: they are
NOT in write_paths, so the model can neither edit them nor see them.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REG = ROOT / "config" / "continuous_loop_tasks.json"

NOTE = ("Local-only defensive fix for the 2026-11-01 Ty autonomy directive. "
        "No auth, no payment, no browser, no credential, no external I/O. "
        "The acceptance probe is independent of the implementation and is not "
        "writable by the model.")

TASKS = [
    {
        "id": "ty-dpi-image-guard",
        "name": "Print gate refuses an impossible image/quad pairing",
        "schema_version": 2,
        "authorized": True,
        "authorization_note": NOTE,
        "risk": "low",
        "risk_class": "low",
        "execution": "ty",
        "objective": (
            "Fix print_prep.dpi_report so the reported DPI cannot be produced from a "
            "quad that does not belong to the image it is given. Today the function "
            "measures the quad and ignores image_size completely, so a quad measured on "
            "a large render replayed against a tiny file still reports a printable DPI. "
            "Raise ValueError when image_size is not two positive numbers and when the "
            "measured face is wider or taller than the image. Keep the normal path "
            "working: a valid image that contains the quad must still return a report. "
            "Only Northstar_backend/print_prep.py may change."),
        "dependencies": [],
        "write_paths": ["Northstar_backend/print_prep.py"],
        "read_paths": ["Northstar_backend/print_prep.py"],
        "checks": [{"name": "dpi image guard probe", "cwd": ".",
                    "cmd": ["python", "state/probes/t1_dpi_image_guard.py"]}],
        "acceptance_commands": [["python", "state/probes/t1_dpi_image_guard.py"]],
        "commit_paths": ["Northstar_backend/print_prep.py"],
        "commit_message": "fix(print): refuse a dieline quad that cannot belong to the image",
        "required_artifact": "Northstar_backend/print_prep.py",
        "timeout_seconds": 900,
        "max_repairs": 1,
        "max_steps": 8,
        "model": "bojo:gpu-orig",
        "provider": "ollama",
    },
    {
        "id": "ty-frame-fill-guard",
        "name": "Framing a cutout refuses an impossible fill and an empty subject",
        "schema_version": 2,
        "authorized": True,
        "authorization_note": NOTE,
        "risk": "low",
        "risk_class": "low",
        "execution": "ty",
        "objective": (
            "Fix image_prep.frame_on_white so it cannot silently emit a broken listing "
            "image. Today fill=0, fill<0 and fill>1 are accepted: the product is scaled "
            "past the frame and clipped, or vanishes. A fully transparent cutout is also "
            "accepted and returns a blank white square, while listing_image.hero_on_white "
            "already refuses the same input. Raise ValueError when fill is not a finite "
            "number in (0, 1], and raise ValueError for an empty cutout. Keep fill=0.85 "
            "and fill=1.0 working for a normal cutout. Only "
            "Northstar_backend/image_prep.py may change."),
        "dependencies": [],
        "write_paths": ["Northstar_backend/image_prep.py"],
        "read_paths": ["Northstar_backend/image_prep.py"],
        "checks": [{"name": "frame fill guard probe", "cwd": ".",
                    "cmd": ["python", "state/probes/t2_frame_fill_guard.py"]}],
        "acceptance_commands": [["python", "state/probes/t2_frame_fill_guard.py"]],
        "commit_paths": ["Northstar_backend/image_prep.py"],
        "commit_message": "fix(image): refuse an impossible fill and an empty cutout when framing",
        "required_artifact": "Northstar_backend/image_prep.py",
        "timeout_seconds": 900,
        "max_repairs": 1,
        "max_steps": 8,
        "model": "bojo:gpu-orig",
        "provider": "ollama",
    },
    {
        "id": "ty-hero-fill-guard",
        "name": "Listing hero refuses an impossible fill fraction",
        "schema_version": 2,
        "authorized": True,
        "authorization_note": NOTE,
        "risk": "low",
        "risk_class": "low",
        "execution": "ty",
        "objective": (
            "Fix listing_image.hero_on_white so an impossible fill cannot ship a cropped "
            "MAIN image. Today fill=0, negative fills, fill>1, NaN and inf are accepted: "
            "the subject is scaled beyond the canvas and cut off, or disappears. Raise "
            "ValueError when fill is not a finite number in (0, 1]. Keep the normal path: "
            "fill=0.85 and fill=1.0 on a normal cutout must still return a square PNG with "
            "the subject visible, and an empty subject must still raise ValueError. Only "
            "Northstar_backend/listing_image.py may change."),
        "dependencies": [],
        "write_paths": ["Northstar_backend/listing_image.py"],
        "read_paths": ["Northstar_backend/listing_image.py"],
        "checks": [{"name": "hero fill guard probe", "cwd": ".",
                    "cmd": ["python", "state/probes/t3_hero_fill_guard.py"]}],
        "acceptance_commands": [["python", "state/probes/t3_hero_fill_guard.py"]],
        "commit_paths": ["Northstar_backend/listing_image.py"],
        "commit_message": "fix(listing): refuse an impossible fill fraction on the hero image",
        "required_artifact": "Northstar_backend/listing_image.py",
        "timeout_seconds": 900,
        "max_repairs": 1,
        "max_steps": 8,
        "model": "bojo:gpu-orig",
        "provider": "ollama",
    },
]


def main() -> int:
    data = json.loads(REG.read_text(encoding="utf-8-sig"))
    tasks = data["tasks"]
    ids = {t.get("id") for t in tasks}
    added = []
    for task in TASKS:
        if task["id"] in ids:
            tasks[:] = [task if t.get("id") == task["id"] else t for t in tasks]
        else:
            tasks.append(task)
            added.append(task["id"])
    data["updated_at"] = "2026-11-01"
    REG.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"added": added, "total": len(tasks),
                      "ids": [t["id"] for t in tasks]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
