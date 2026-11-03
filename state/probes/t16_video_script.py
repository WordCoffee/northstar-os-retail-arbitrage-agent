"""Contract: scene durations add up to the placement window, exactly.

A script is not a list of nice sentences; it is a budget. This probe asks the
planner for 15 s and 30 s TikTok windows and an Amazon widescreen window, then
checks that the scenes, frames and beats agree with the contract:

  * durations sum to the requested window,
  * frame counts sum to the preset's target frame count,
  * every scene has art direction that survives the text-safe lane,
  * the hook is 3-5 words, and every on-screen line fits,
  * every scene has a voiceover line.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Northstar_backend"))

import text_fidelity  # noqa: E402
import video_formats  # noqa: E402
import video_script  # noqa: E402

PRODUCT = {
    "brand": "MOGRA",
    "product": "LION'S MANE",
    "subtitle": "MUSHROOM POWDER",
    "weight": "6 oz (170 g)",
    "claims": ["100% PURE", "NO FILLERS"],
}


def main() -> int:
    for platform, seconds in (("tiktok", 15), ("tiktok", 30),
                              ("shorts", 15), ("amazon-ad-16x9", 15)):
        plan = video_formats.plan(platform, seconds)
        result = video_script.plan_scenes(PRODUCT, platform=platform,
                                          seconds=seconds, seed=7)
        print(f"{platform} {seconds:g}s: scenes={len(result['scenes'])} "
              f"sum={result['sum_seconds']}s frames={result['sum_frames']}/"
              f"{result['target_frames']} hook={result['scenes'][0]['on_screen_text']!r}")
        assert abs(result["sum_seconds"] - float(plan["seconds"])) <= 1e-6, result
        assert result["sum_frames"] == plan["target_frames"], result
        assert all(result["checks"].values()), result["checks"]
        assert len(result["scenes"]) == len(video_script.BEATS)
        for scene in result["scenes"]:
            assert scene["end"] > scene["start"], scene
            assert scene["prompt"].strip(), scene
            # the prompt must survive the text-safe sanitiser with art direction left
            prep = text_fidelity.sanitize_brief_for_render(scene["prompt"])
            assert prep["brief_empty"] is False, (scene["beat"], prep)
            assert prep["expected_terms"] == [], (scene["beat"], prep["expected_terms"])
            assert len(scene["on_screen_text"]) <= 34, scene
            assert scene["voiceover"].strip(), scene
        if not plan["compliance"]["verified"]:
            assert result["compliance"]["verified"] is False, result
            print("  (compliance verified: false, as declared for this preset)")
    print("t16 video script planner: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
