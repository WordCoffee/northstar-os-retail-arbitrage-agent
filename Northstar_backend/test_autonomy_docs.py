from pathlib import Path


def test_autonomy_docs_cover_the_long_campaign_controls():
    text = (Path(__file__).resolve().parents[1] / "docs" / "CONTINUOUS_LOOP.md").read_text(
        encoding="utf-8")
    for token in ("--ready", "--max-consecutive-failures", "--status",
                  "autonomy_log_YYYYMMDD.log", "no service"):
        assert token in text
