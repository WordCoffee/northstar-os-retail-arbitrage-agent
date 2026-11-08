"""Report building for the weekly ops digest.

Everything lives in this one module for now: parsing, validation, summarising
and both renderers. It has grown past the point where a single file is
comfortable, and the next increment does not belong in it.
"""
from __future__ import annotations

import csv
import io
import json

COLUMNS = ("lane", "ok", "seconds")


def parse_rows(raw_lines):
    """Parse '<lane>,<ok>,<seconds>' lines, skipping blanks and comments."""
    rows = []
    for line in raw_lines:
        text = line.strip()
        if not text or text.startswith("#"):
            continue
        parts = [part.strip() for part in text.split(",")]
        if len(parts) != len(COLUMNS):
            raise ValueError(
                "expected %d fields, got %d: %r" % (len(COLUMNS), len(parts), text))
        rows.append({"lane": parts[0], "ok": parts[1], "seconds": parts[2]})
    return rows


def validate_rows(rows):
    """Return a list of human-readable problems; empty means clean."""
    problems = []
    for row in rows:
        lane = row.get("lane") or ""
        if not lane:
            problems.append("empty lane")
            continue
        if str(row.get("ok")).strip().lower() not in ("true", "false"):
            problems.append("bad ok flag for %s: %r" % (lane, row.get("ok")))
        try:
            seconds = float(row.get("seconds"))
        except (TypeError, ValueError):
            problems.append("bad seconds for %s: %r" % (lane, row.get("seconds")))
            continue
        if seconds < 0:
            problems.append("negative seconds for %s" % lane)
    return problems


def as_bool(value):
    return str(value).strip().lower() == "true"


def summarise(rows):
    seconds = [float(row["seconds"]) for row in rows]
    passed = [row for row in rows if as_bool(row["ok"])]
    return {
        "rows": len(rows),
        "passed": len(passed),
        "failed": len(rows) - len(passed),
        "total_seconds": round(sum(seconds), 3),
        "mean_seconds": round(sum(seconds) / len(seconds), 3) if seconds else 0.0,
        "lanes": sorted({row["lane"] for row in rows}),
    }


def render_table(rows, summary):
    width = max([len(row["lane"]) for row in rows] + [4])
    out = ["%s  %-6s %s" % ("lane".ljust(width), "ok", "seconds")]
    out.append("%s  %s %s" % ("-" * width, "-" * 6, "-" * 7))
    for row in rows:
        out.append("%s  %-6s %s" % (row["lane"].ljust(width),
                                    str(row["ok"]).lower(), row["seconds"]))
    out.append("")
    out.append("%d/%d passed, total %ss" % (summary["passed"], summary["rows"],
                                            summary["total_seconds"]))
    return "\n".join(out)


def render_csv(rows):
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=list(COLUMNS))
    writer.writeheader()
    for row in rows:
        writer.writerow(row)
    return buffer.getvalue()


def render_markdown(rows, summary):
    out = ["| lane | ok | seconds |", "| --- | --- | --- |"]
    for row in rows:
        out.append("| %s | %s | %s |" % (row["lane"], str(row["ok"]).lower(),
                                        row["seconds"]))
    out.append("")
    out.append("**%d/%d passed**, total %ss" % (summary["passed"], summary["rows"],
                                               summary["total_seconds"]))
    return "\n".join(out)


def sort_rows(rows, key="lane", reverse=False):
    return sorted(rows, key=lambda row: str(row.get(key) or ""), reverse=reverse)


def filter_rows(rows, lane=None, ok_only=False):
    kept = []
    for row in rows:
        if lane is not None and row["lane"] != lane:
            continue
        if ok_only and not as_bool(row["ok"]):
            continue
        kept.append(row)
    return kept


def build_report(raw_lines):
    rows = parse_rows(raw_lines)
    problems = validate_rows(rows)
    summary = summarise(rows)
    return {
        "rows": rows,
        "problems": problems,
        "summary": summary,
        "table": render_table(rows, summary),
        "csv": render_csv(rows),
    }


def to_json(report):
    return json.dumps(report, indent=2, sort_keys=True)


def merge_reports(reports):
    rows = [row for report in reports for row in report["rows"]]
    problems = [problem for report in reports for problem in report["problems"]]
    summary = summarise(rows)
    return {
        "rows": rows,
        "problems": problems,
        "summary": summary,
        "table": render_table(rows, summary),
        "csv": render_csv(rows),
    }


def healthy(report):
    return not report["problems"] and report["summary"]["failed"] == 0
