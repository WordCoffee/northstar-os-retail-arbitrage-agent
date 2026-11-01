"""Rewrite the three Ty objectives as behavioural contracts (idempotent)."""
from __future__ import annotations

import json
from pathlib import Path

REG = Path(__file__).resolve().parents[1] / "config" / "continuous_loop_tasks.json"

T1 = (
    "Edit ONLY the dpi_report function in Northstar_backend/print_prep.py, using the "
    "ast_edit tool with op=replace_function_body and target=dpi_report. The source you "
    "supply is the function body WITHOUT the def line. The new body must: (1) validate "
    "image_size first - it must be a list or tuple of exactly two numbers, both greater "
    "than zero, otherwise raise ValueError; (2) after px = face_pixels(quad), raise "
    "ValueError when the measured face width is greater than image_size[0] or its height "
    "is greater than image_size[1]; (3) keep the existing return dict unchanged. Do not "
    "rewrite the whole file. state/probes/t1_dpi_image_guard.py is READ-ONLY: never write "
    "it. When done, call run with python state/probes/t1_dpi_image_guard.py and repair "
    "from its output.")

T2 = (
    "Edit ONLY the frame_on_white function in Northstar_backend/image_prep.py, using the "
    "ast_edit tool with op=replace_function_body and target=frame_on_white. The source you "
    "supply is the function body WITHOUT the def line. The new body must: (1) validate "
    "fill first - it must be a finite number with 0 < fill <= 1, otherwise raise "
    "ValueError; (2) after product = trim_to_alpha(rgba), raise ValueError with the text "
    "empty_subject when the product has no visible pixels; (3) keep the rest of the "
    "existing behaviour. Do not rewrite the whole file. "
    "state/probes/t2_frame_fill_guard.py is READ-ONLY: never write it. When done, call run "
    "with python state/probes/t2_frame_fill_guard.py and repair from its output.")

T3 = (
    "Edit ONLY the hero_on_white function in Northstar_backend/listing_image.py, using the "
    "ast_edit tool with op=replace_function_body and target=hero_on_white. The source you "
    "supply is the function body WITHOUT the def line. The new body must validate fill "
    "first: it must be a finite number with 0 < fill <= 1, otherwise raise ValueError; "
    "keep the rest of the existing behaviour, including the empty-subject refusal. Do not "
    "rewrite the whole file. state/probes/t3_hero_fill_guard.py is READ-ONLY: never write "
    "it. When done, call run with python state/probes/t3_hero_fill_guard.py and repair "
    "from its output.")

OBJECTIVES = {"ty-dpi-image-guard": T1, "ty-frame-fill-guard": T2, "ty-hero-fill-guard": T3}


def main() -> int:
    data = json.loads(REG.read_text(encoding="utf-8-sig"))
    for task in data["tasks"]:
        if task.get("id") in OBJECTIVES:
            task["objective"] = OBJECTIVES[task["id"]]
    REG.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    print("updated:", sorted(OBJECTIVES))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
