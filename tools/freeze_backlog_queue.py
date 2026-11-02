"""Freeze the backlog queue: the three probe-backed creative defects.

`cost_model` was inspected and rejected for this pass: fees, refunds and credit
weighting are billing logic, which the directive excludes.
"""
from __future__ import annotations

import json
from pathlib import Path

REG = Path(__file__).resolve().parents[1] / "config" / "continuous_loop_tasks.json"

CONTRACTS = [
    {
        "id": "ty-dpi-image-guard",
        "name": "Print gate refuses an impossible image/quad pairing",
        "objective": (
            "Northstar_backend/print_prep.py has one behavioural defect: dpi_report() "
            "measures the quad and ignores image_size completely, so a quad measured on a "
            "large render replayed against a tiny file still reports a printable DPI and the "
            "300 DPI print gate can be satisfied by a file that could never print. Read the "
            "file and fix dpi_report so it raises ValueError when image_size is not two "
            "positive numbers and when the measured face is wider or taller than the image; "
            "a consistent pair must still return the report. The read-only probe "
            "state/probes/t1_dpi_image_guard.py is the contract - run it to check your change; "
            "if it fails, edit the source file - never the probe. Change only that file."),
        "write_paths": ["Northstar_backend/print_prep.py"],
        "read_paths": ["Northstar_backend/print_prep.py",
                       "state/probes/t1_dpi_image_guard.py"],
        "probe": ["python", "state/probes/t1_dpi_image_guard.py"],
        "commit_message": "fix(print): refuse a dieline quad that cannot belong to the image",
    },
    {
        "id": "ty-frame-fill-guard",
        "name": "Framing a cutout refuses an impossible fill and an empty subject",
        "objective": (
            "Northstar_backend/image_prep.py has one behavioural defect: frame_on_white() "
            "accepts fill=0, negative fills and fill>1, so the product is scaled past the frame "
            "and clipped, and it accepts a fully transparent cutout and returns a blank white "
            "square as if it were a product. Read the file and fix frame_on_white so a "
            "non-finite fill or one outside (0, 1] raises ValueError, and an empty cutout raises "
            "ValueError; a normal cutout at fill 0.85 and 1.0 must still frame. The read-only "
            "probe state/probes/t2_frame_fill_guard.py is the contract - run it to check your "
            "change; if it fails, edit the source file - never the probe. Change only that file."),
        "write_paths": ["Northstar_backend/image_prep.py"],
        "read_paths": ["Northstar_backend/image_prep.py",
                       "state/probes/t2_frame_fill_guard.py"],
        "probe": ["python", "state/probes/t2_frame_fill_guard.py"],
        "commit_message": "fix(image): refuse an impossible fill and an empty cutout when framing",
    },
    {
        "id": "ty-hero-fill-guard",
        "name": "Listing hero refuses an impossible fill fraction",
        "objective": (
            "Northstar_backend/listing_image.py has one behavioural defect: hero_on_white() "
            "accepts fill=0, negative fills, fill>1, NaN and inf, so the MAIN image is cropped "
            "with the product cut off or invisible. Read the file and fix hero_on_white so a "
            "non-finite fill or one outside (0, 1] raises ValueError; keep the existing "
            "empty-subject refusal and the normal path (fill 0.85 and 1.0 on a normal cutout "
            "still return a square PNG with the subject visible). The read-only probe "
            "state/probes/t3_hero_fill_guard.py is the contract - run it to check your change; "
            "if it fails, edit the source file - never the probe. Change only that file."),
        "write_paths": ["Northstar_backend/listing_image.py"],
        "read_paths": ["Northstar_backend/listing_image.py",
                       "state/probes/t3_hero_fill_guard.py"],
        "probe": ["python", "state/probes/t3_hero_fill_guard.py"],
        "commit_message": "fix(listing): refuse an impossible fill fraction on the hero image",
    },
]


def main() -> int:
    data = json.loads(REG.read_text(encoding="utf-8-sig"))
    tasks = {t["id"]: t for t in data["tasks"]}
    for spec in CONTRACTS:
        task = tasks.get(spec["id"]) or {"id": spec["id"], "schema_version": 2,
                                         "execution": "ty", "risk": "low",
                                         "risk_class": "low", "dependencies": []}
        task.update({
            "name": spec["name"],
            "authorized": True,
            "authorization_note": (
                "Local-only behavioural fix frozen by the 2026-11-02 backlog pass. No auth, "
                "tenancy, billing, security, provider or external I/O. The probe is read-only "
                "and outside the author's write scope."),
            "contract_version": 1,
            "objective": spec["objective"],
            "write_paths": spec["write_paths"],
            "read_paths": spec["read_paths"],
            "checks": [{"name": spec["id"], "cwd": ".", "cmd": list(spec["probe"])}],
            "acceptance_commands": [list(spec["probe"])],
            "commit_paths": list(spec["write_paths"]),
            "commit_message": spec["commit_message"],
            "required_artifact": spec["write_paths"][0],
            "timeout_seconds": 600,
            "max_repairs": 1,
            "max_steps": 8,
            "model": "qwen3.5:4b",
            "provider": "ollama",
            "num_ctx": 8192,
            "native_tools": True,
            "allowed_tools": ["read", "ast_edit", "run", "finish"],
            "author_lane": "opencode-go/deepseek-v4.1-flash (supervisor handoff)",
        })
        task.pop("blocked", None)
        tasks[spec["id"]] = task
    data["tasks"] = list(tasks.values())
    data["updated_at"] = "2026-11-02"
    REG.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"frozen": [c["id"] for c in CONTRACTS],
                      "authorized_ty": [t["id"] for t in data["tasks"]
                                        if t.get("authorized") and t.get("execution") == "ty"]},
                     indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
