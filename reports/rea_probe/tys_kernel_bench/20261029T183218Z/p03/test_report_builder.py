from report_builder import (build_report, filter_rows, healthy, merge_reports,
                            parse_rows, render_markdown, sort_rows, summarise,
                            validate_rows)

SAMPLE = [
    "# lane,ok,seconds",
    "coding,true,12.5",
    "label,false,3.0",
]


def test_parse_skips_comments_and_blanks():
    rows = parse_rows(["", "# header", "coding,true,1.0", "   "])
    assert rows == [{"lane": "coding", "ok": "true", "seconds": "1.0"}]


def test_summary_totals():
    summary = summarise(parse_rows(SAMPLE))
    assert summary["rows"] == 2
    assert summary["passed"] == 1
    assert summary["failed"] == 1
    assert summary["total_seconds"] == 15.5
    assert summary["lanes"] == ["coding", "label"]


def test_valid_rows_have_no_problems():
    assert validate_rows(parse_rows(SAMPLE)) == []
    assert build_report(SAMPLE)["problems"] == []


def test_bad_seconds_are_reported():
    problems = validate_rows([{"lane": "x", "ok": "true", "seconds": "soon"}])
    assert problems and "bad seconds" in problems[0]


def test_renders_carry_the_numbers():
    report = build_report(SAMPLE)
    assert "1/2 passed" in report["table"]
    assert report["csv"].splitlines()[0] == "lane,ok,seconds"


def test_healthy_needs_a_clean_pass():
    assert healthy(build_report(SAMPLE)) is False
    assert healthy(build_report(["coding,true,1.0"])) is True


def test_sort_and_filter_keep_the_same_rows():
    rows = parse_rows(SAMPLE)
    assert [row["lane"] for row in sort_rows(rows)] == ["coding", "label"]
    assert [row["lane"] for row in sort_rows(rows, reverse=True)] == ["label", "coding"]
    assert [row["lane"] for row in filter_rows(rows, ok_only=True)] == ["coding"]
    assert filter_rows(rows, lane="label")[0]["ok"] == "false"


def test_merge_reports_adds_up():
    merged = merge_reports([build_report(SAMPLE), build_report(["label,true,1.0"])])
    assert merged["summary"]["rows"] == 3
    assert merged["summary"]["total_seconds"] == 16.5
    assert "2/3 passed" in merged["table"]


def test_markdown_renderer():
    report = build_report(SAMPLE)
    text = render_markdown(report["rows"], report["summary"])
    assert "| coding | true | 12.5 |" in text
    assert "**1/2 passed**" in text
