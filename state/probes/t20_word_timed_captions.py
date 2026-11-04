"""Contract: caption cues use measured word timings when the engine has them.

Segment timing distributed by character length is a fallback, not a
measurement. This probe feeds a transcript with word timings and requires the
cue boundaries to come from those words; a segment without word timings must
say `timing: "segment"` instead of pretending.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Northstar_backend"))

import video_captions as vc  # noqa: E402


def main() -> int:
    transcript = {
        "segments": [
            {"start": 0.0, "end": 1.8, "text": "six oz pouch",
             "words": [
                 {"word": "six", "start": 0.10, "end": 0.40},
                 {"word": "oz", "start": 0.40, "end": 0.70},
                 {"word": "pouch", "start": 0.90, "end": 1.60},
             ]},
            {"start": 1.8, "end": 3.0, "text": "one ingredient"},
        ]
    }
    cues = vc.cues_from_transcript(transcript, max_chars=24)
    for cue in cues:
        print(cue["start"], cue["end"], repr(cue["text"]), cue["words"])
    assert len(cues) == 2, cues
    first, second = cues
    assert first["text"] == "six oz pouch"
    assert first["start"] == 0.1, first
    assert first["end"] == 1.6, first
    assert second["start"] == 1.8, second

    words = vc.words_from_segments(transcript["segments"])
    assert [w["timing"] for w in words[:3]] == ["word", "word", "word"]
    assert all(w["timing"] == "segment" for w in words[3:]), words[3:]

    fallback = vc.words_from_segments([{"start": 2.0, "end": 3.0, "text": "two words"}])
    assert [w["timing"] for w in fallback] == ["segment", "segment"]
    print("t20 word-timed captions: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
