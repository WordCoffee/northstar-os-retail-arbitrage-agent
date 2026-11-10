"""Deterministic workspace seeds for every NS-PROJ-20 brief.

`seed(project, brief)` builds the minimal, realistic starting state a brief
needs before an agent runs. It reads nothing outside `project`, writes nothing
outside `project`, and touches neither the network nor a model. Every byte is
fixed at import time, so two runs of the same brief produce identical trees.

Two briefs arrive as an empty workspace on purpose: p13 (canvases come from
`presets.js`) and p14 (the clip comes from the FFmpeg probe). p11 ships a plate
marker only, because the label itself is produced by `pouch_label`.

CLI:
    python tools/coding_seed.py --selftest      seed all 20 into a temp dir,
                                                print what exists, prove the
                                                fixtures behave, then remove it.
"""
from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Callable, Dict, List, Tuple

ROOT = Path(__file__).resolve().parents[1]
BRIEFS_PATH = ROOT / "eval/projects/ns_proj_20.json"
BRIEF_IDS = tuple("p%02d" % n for n in range(1, 21))

# Files/artefacts each brief's seed must leave behind (posix, relative).
EXPECTED: Dict[str, Tuple[str, ...]] = {
    "p01": ("calc.py", "test_calc.py"),
    "p02": ("README.md",),
    "p03": ("report_builder.py", "test_report_builder.py"),
    "p04": ("config.py", "test_config.py"),
    "p05": ("broken.py",),
    "p06": ("admin_setting.json", "settings_capture.txt"),
    "p07": ("runbook.md", "hosts.txt"),
    "p08": ("run_state.json",),
    "p09": ("state_check.json",),
    "p10": ("evidence/ops_week_41.json", "evidence/ops_week_42.json"),
    "p11": ("plate_path.txt",),
    "p12": ("front.txt", "back.txt", "front.sha256"),
    "p13": (),
    "p14": (),
    "p15": ("listing.txt", "rubric.md"),
    "p16": ("campaign.md",),
    "p17": ("plan_v1.json",),
    "p18": ("handoff.md",),
    "p19": ("config.txt", "notes.txt", "changes.diff"),
    "p20": (
        "skeleton.json",
        "run.py",
        "nodes/collect.py",
        "nodes/summarise.py",
        "nodes/verify.py",
    ),
}

# Directories the seed creates but leaves empty.
EXPECTED_DIRS: Dict[str, Tuple[str, ...]] = {"p11": ("out",)}


# --------------------------------------------------------------------------
# tiny deterministic writers
# --------------------------------------------------------------------------

def _write(path: Path, text: str) -> bytes:
    """Write UTF-8 bytes with no newline translation; return what was written."""
    data = text.encode("utf-8")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return data


def _write_json(path: Path, payload: Any) -> bytes:
    return _write(path, json.dumps(payload, indent=2, sort_keys=True) + "\n")


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


# --------------------------------------------------------------------------
# p01 - failing unit test
# --------------------------------------------------------------------------

P01_CALC = '''\
"""Tiny arithmetic helpers used by the billing report."""


def add(a, b):
    return a - b


def subtract(a, b):
    return add(a, -b)


def total(values):
    running = 0
    for value in values:
        running = add(running, value)
    return running
'''

P01_TEST = '''\
from calc import add, subtract, total


def test_add():
    assert add(2, 3) == 5


def test_subtract():
    assert subtract(5, 3) == 2


def test_total():
    assert total([1, 2, 3]) == 6
'''


def _seed_p01(project: Path) -> None:
    _write(project / "calc.py", P01_CALC)
    _write(project / "test_calc.py", P01_TEST)


# --------------------------------------------------------------------------
# p02 - service with no endpoint yet
# --------------------------------------------------------------------------

P02_README = '''\
# Ledger service

Read-only reporting service for the finance team. Today the service is a stub:
it starts, loads its configuration and registers no routes at all.

## Constraints

1. Storage is read-only. No schema migration is ever added to this service.
2. One route per increment, each with its own test.
3. JSON responses only; no HTML templates.

## Next increment

Add a single **GET** route that returns the current ledger period, plus a test
that exercises it. The route name, method and response shape are agreed in
`endpoint.md` before the code is written.
'''


def _seed_p02(project: Path) -> None:
    _write(project / "README.md", P02_README)


# --------------------------------------------------------------------------
# p03 - one oversized module plus the tests that pin its behaviour
# --------------------------------------------------------------------------

P03_MODULE = '''\
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
    return "\\n".join(out)


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
    return "\\n".join(out)


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
'''

P03_TEST = '''\
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
'''


def _seed_p03(project: Path) -> None:
    _write(project / "report_builder.py", P03_MODULE)
    _write(project / "test_report_builder.py", P03_TEST)


# --------------------------------------------------------------------------
# p04 - config module with no flag yet
# --------------------------------------------------------------------------

P04_CONFIG = '''\
"""Runtime configuration for the ledger service.

Defaults live in code and environment variables override them. There is no
feature-flag mechanism yet, so every setting below is unconditional.
"""
from __future__ import annotations

DEFAULTS = {
    "service_name": "ledger",
    "max_retries": 3,
    "timeout_seconds": 30,
    "read_only": True,
}

TRUTHY = ("1", "true", "yes", "on")
FALSY = ("0", "false", "no", "off")


def coerce(raw):
    """Turn an environment string into a bool, an int, or the raw text."""
    text = str(raw).strip()
    if text.lower() in TRUTHY:
        return True
    if text.lower() in FALSY:
        return False
    try:
        return int(text)
    except ValueError:
        return text


def get(name, default=None, environ=None):
    env = {} if environ is None else environ
    if name in env:
        return coerce(env[name])
    if name in DEFAULTS:
        return DEFAULTS[name]
    return default


def load(environ=None):
    env = {} if environ is None else environ
    settings = dict(DEFAULTS)
    names = list(DEFAULTS) + sorted(set(env) - set(DEFAULTS))
    for name in names:
        value = get(name, environ=env)
        if value is not None:
            settings[name] = value
    return settings
'''

P04_TEST = '''\
from config import DEFAULTS, coerce, get, load


def test_defaults_are_the_documented_values():
    assert DEFAULTS["max_retries"] == 3
    assert DEFAULTS["timeout_seconds"] == 30
    assert DEFAULTS["read_only"] is True


def test_unknown_key_returns_the_default():
    assert get("no_such_setting") is None
    assert get("no_such_setting", "fallback") == "fallback"


def test_load_without_environ_is_the_defaults():
    assert load() == DEFAULTS
    assert load({}) == DEFAULTS


def test_environ_overrides_and_coerces():
    settings = load({"max_retries": "5", "read_only": "false"})
    assert settings["max_retries"] == 5
    assert settings["read_only"] is False


def test_coerce_shapes():
    assert coerce("6") == 6
    assert coerce("on") is True
    assert coerce("off") is False
    assert coerce("ledger") == "ledger"
'''


def _seed_p04(project: Path) -> None:
    _write(project / "config.py", P04_CONFIG)
    _write(project / "test_config.py", P04_TEST)


# --------------------------------------------------------------------------
# p05 - broken build (one syntax error, nothing else)
# --------------------------------------------------------------------------

P05_BROKEN = '''\
"""Tally helpers for the render queue."""


def total(items):
    running = 0
    for item in items
        running += item
    return running


def mean(items):
    return total(items) / len(items)
'''


def _seed_p05(project: Path) -> None:
    _write(project / "broken.py", P05_BROKEN)


# --------------------------------------------------------------------------
# p06 - admin setting fixture (read-only audit input)
# --------------------------------------------------------------------------

P06_SETTING = {
    "panel": "Admin > Settings > Security",
    "setting_key": "org.mfa_require_all",
    "display_label": "Require MFA for all members",
    "observed_value": False,
    "observed_at": "2026-10-27T14:05:00Z",
    "scope": "organisation org-t2",
    "capture": "settings_capture.txt",
    "note": "Value read from the rendered control; no change was submitted.",
}

P06_CAPTURE = '''\
GET /admin/settings/security   (read-only capture, 2026-10-27T14:03Z)

  [x] Require MFA for members with the admin role
  [ ] Require MFA for all members              <- observed checked=False
  [x] Session timeout: 30 minutes
  [ ] Allow personal access tokens
'''


def _seed_p06(project: Path) -> None:
    _write_json(project / "admin_setting.json", P06_SETTING)
    _write(project / "settings_capture.txt", P06_CAPTURE)


# --------------------------------------------------------------------------
# p07 - browser runbook stub plus the host table it has to fill in
# --------------------------------------------------------------------------

P07_RUNBOOK = '''\
# Runbook: read the published pricing limits

Status: stub. Not authorised to run yet.

## Intended task

Read the published plan limits from the public pricing page. Read-only: no
account, no cart, no form submission, no download.

## Host

TODO: name the single host this run may touch (see `hosts.txt`).

## Grant

TODO: capability (`read_only`) and expiry in UTC, at most 24 hours out.

## Refusals

- Never sign in, never solve a CAPTCHA, never enter credentials.
- Stop and report at consent, rate limit, paywall or a CAPTCHA.
- Never submit a form; the grant covers reading only.
'''

P07_HOSTS = '''\
# Per-run browser host grants for this workspace.
# Format: <host>  <capability>  <expires_utc>
# An expiry of "unset" means the grant is not authorised yet.
pricing.example.com   read_only   unset
docs.example.com      read_only   unset
'''


def _seed_p07(project: Path) -> None:
    _write(project / "runbook.md", P07_RUNBOOK)
    _write(project / "hosts.txt", P07_HOSTS)


# --------------------------------------------------------------------------
# p08 - run blocked on an operator gate, with a checkpoint to resume from
# --------------------------------------------------------------------------

P08_STATE = {
    "run_id": "run-2026-10-27-a",
    "goal": "Publish the weekly ops digest to the finance channel",
    "status": "blocked",
    "blocked_on": "operator_gate:spend_approval",
    "checkpoint": {
        "id": "ckpt-0003",
        "path": "state/ckpt-0003.json",
        "steps_done": [1, 2],
        "created_at": "2026-10-27T11:42:00Z",
    },
    "steps": [
        {"n": 1, "id": "collect_evidence", "status": "done",
         "evidence": "evidence/ops_week_41.json"},
        {"n": 2, "id": "assemble_digest", "status": "done",
         "evidence": "state/digest_draft.md"},
        {"n": 3, "id": "publish_digest", "status": "blocked",
         "reason": "paid credit spend requires a fresh operator approval"},
        {"n": 4, "id": "notify_finance", "status": "pending"},
    ],
    "rule": "Resume from ckpt-0003; do not repeat steps 1 or 2.",
}


def _seed_p08(project: Path) -> None:
    _write_json(project / "run_state.json", P08_STATE)


# --------------------------------------------------------------------------
# p09 - an external change that must be asserted before reporting done
# --------------------------------------------------------------------------

P09_STATE = {
    "run_id": "run-2026-10-27-b",
    "change": {
        "what": "operator toggled org.mfa_require_all",
        "path": "org.mfa_require_all",
        "from": False,
        "to": True,
        "applied_at": "2026-10-27T16:20:00Z",
        "applied_by": "operator",
    },
    "assertion": {
        "path": "org.mfa_require_all",
        "expected": True,
        "observed": None,
        "verdict": "unknown",
        "recorded_at": None,
    },
    "rule": "unknown is not pass: an unread value may never be reported as done",
}


def _seed_p09(project: Path) -> None:
    _write_json(project / "state_check.json", P09_STATE)


# --------------------------------------------------------------------------
# p10 - two weeks of local evidence for the digest
# --------------------------------------------------------------------------

P10_WEEK_41 = {
    "week": "2026-W41",
    "source": "local evidence export, no live calls",
    "lanes": {
        "coding": {"runs": 14, "passed": 12, "failed": 2},
        "browser": {"runs": 5, "passed": 5, "failed": 0},
        "label": {"runs": 3, "passed": 2, "failed": 1},
    },
    "renders_completed": 9,
    "operator_gates": 2,
    "missing": [],
}

P10_WEEK_42 = {
    "week": "2026-W42",
    "source": "local evidence export, no live calls",
    "lanes": {
        "coding": {"runs": 11, "passed": 11, "failed": 0},
        "browser": {"runs": 4, "passed": 3, "failed": 1},
        "label": {"runs": 2, "passed": 2, "failed": 0},
    },
    "renders_completed": None,
    "operator_gates": 1,
    "missing": [
        {"field": "renders_completed", "why": "render worker offline all week"},
    ],
}


def _seed_p10(project: Path) -> None:
    _write_json(project / "evidence/ops_week_41.json", P10_WEEK_41)
    _write_json(project / "evidence/ops_week_42.json", P10_WEEK_42)


# --------------------------------------------------------------------------
# p11 - plate marker only; the label itself comes from pouch_label
# --------------------------------------------------------------------------

P11_MARKER = '''\
# Plate marker. The pouch face is MEASURED from this render by pouch_label;
# this workspace only records which plate and which copy to use.
plate: Northstar_backend/data/studio_generated/2e4a7ab96e9941479b068792f592864d.png
logo: Northstar_backend/assets/brand/mogra_logo.png
title: ORGANIC LION'S MANE
subtitle: MUSHROOM POWDER
weight: 6 oz (170 g)
output: out/label.png
'''


def _seed_p11(project: Path) -> None:
    _write(project / "plate_path.txt", P11_MARKER)
    (project / "out").mkdir(parents=True, exist_ok=True)


# --------------------------------------------------------------------------
# p12 - front panel frozen, back panel carries one legal-copy defect
# --------------------------------------------------------------------------

P12_FRONT = '''\
MOGRA ORGANICS
ORGANIC LION'S MANE
MUSHROOM POWDER
DIETARY SUPPLEMENT
6 oz (170 g)
'''

# The defect is the misspelled regulator name on the disclaimer line.
P12_BACK = '''\
SUPPLEMENT FACTS
Serving size: 1 tsp (2 g)   Servings per container: about 85

Amount per serving
Lion's Mane (Hericium erinaceus) fruiting body powder   2000 mg
* Daily value not established.

WARNING: These statements have not been evaluated by the Food and Drug
Adminstration. This product is not intended to diagnose, treat, cure, or
prevent any disease. Consult a physician before use if pregnant, nursing, or
taking medication.

Distributed by Mogra Organics, LLC. Austin, TX 78701.
Product of USA.
'''


def _seed_p12(project: Path) -> None:
    front = _write(project / "front.txt", P12_FRONT)
    _write(project / "back.txt", P12_BACK)
    digest = hashlib.sha256(front).hexdigest()
    _write(project / "front.sha256", "%s  front.txt\n" % digest)


# --------------------------------------------------------------------------
# p13 and p14 - deliberately empty workspaces
# --------------------------------------------------------------------------
# p13 canvases are produced by northstar-os-ui/src/studio/engine/presets.js and
# p14's clip is produced by the FFmpeg probe. Seeding either would be fake input.

def _seed_empty(project: Path) -> None:
    project.mkdir(parents=True, exist_ok=True)


# --------------------------------------------------------------------------
# p15 - listing to score, rubric to score it against
# --------------------------------------------------------------------------

P15_LISTING = '''\
Title: Mogra Organics Organic Lion's Mane Mushroom Powder - 6 oz, 85 Servings

Bullets:
- WILD-HARVESTED FRUITING BODIES ONLY: no mycelium, no fillers, no grain.
- 6 OZ STAND-UP POUCH: about 85 servings at 2 g each.
- HOT WATER OR SMOOTHIE: dissolves clean, mild savoury flavour.
- THIRD-PARTY TESTED: every batch, heavy metals and microbials.
- USDA ORGANIC: certified organic, non-GMO, vegan, gluten free.

Description:
Mogra Organics Organic Lion's Mane Mushroom Powder is a single-ingredient
extract made from whole fruiting bodies. It is milled fine enough to dissolve
in hot water and is unsweetened, so it works in coffee, broth or a smoothie.
Each 6 oz pouch holds about 85 two-gram servings.

Keywords: lion's mane powder, organic mushroom powder, lion mane supplement

Images: 5 of 7 slots filled.
A+ content: none.
Price: not supplied in this fixture.
'''

P15_RUBRIC = '''\
# Listing rubric (v1)

Score each dimension 0-5 and cite the line of `listing.txt` you scored.

| Dimension | Weight | What a 5 looks like |
| --- | --- | --- |
| Title | 20% | Primary keyword first, under 200 chars, no promos |
| Bullets | 20% | Five benefit-led bullets, each with a concrete number |
| Description | 15% | Answers the top five buyer questions, no claims |
| Keywords | 10% | Present in copy, no stuffing |
| Images | 15% | All seven slots filled, one scale reference |
| A+ content | 10% | At least three modules with sourced specs |
| Compliance | 10% | No disease claims, disclaimer present, weights consistent |

## Unmeasurable from this fixture

These dimensions cannot be scored from the supplied files and must be named as
unmeasured rather than guessed:

- Price competitiveness (no price in the fixture)
- BSR / sales velocity (no live data, and no live call is authorised)
- Review count and rating (no live data)
- Conversion rate (needs live traffic)
'''


def _seed_p15(project: Path) -> None:
    _write(project / "listing.txt", P15_LISTING)
    _write(project / "rubric.md", P15_RUBRIC)


# --------------------------------------------------------------------------
# p16 - two-lane campaign stub
# --------------------------------------------------------------------------

P16_CAMPAIGN = '''\
# Campaign: inspect first, browse second

Status: stub. No lane is authorised yet.

## Objective

Answer one question: which plans are published on the vendor's pricing page,
and what does each include.

## Lane 1 - inspect (local, no network)

- [ ] TODO: read the local fixtures and list what is already known
- [ ] TODO: name the single fact still missing
- [ ] Produce `inspect.json`

## Gate 1 - human review

The run stops here and waits. Lane 2 does not begin until the operator
approves the host and the expiry in writing. A gate is a stop, not a pause.

## Lane 2 - browser (read-only, per-host grant)

- [ ] TODO: one host, capability `read_only`, expiry at most 24 hours
- [ ] TODO: extract only the fact named in Lane 1
- [ ] Stop at consent, rate limit or CAPTCHA; never sign in

## Evidence

Each lane writes its own evidence file; the campaign is done only when both
are present and the gate record names who approved what.
'''


def _seed_p16(project: Path) -> None:
    _write(project / "campaign.md", P16_CAMPAIGN)


# --------------------------------------------------------------------------
# p17 - a plan whose verification failed
# --------------------------------------------------------------------------

P17_PLAN = {
    "plan_version": 1,
    "goal": "Assemble a 15-second vertical ad and verify it before reporting done",
    "created_at": "2026-10-27T09:10:00Z",
    "status": "failed",
    "nodes": [
        {"id": "n1", "action": "scale the plate to 1080x1920", "status": "done"},
        {"id": "n2", "action": "mux the narration track onto the clip", "status": "done"},
        {"id": "n3", "action": "ffprobe the result against the checks", "status": "failed"},
    ],
    "failed_assertion": {
        "node": "n3",
        "check": "duration_12_15",
        "observed_seconds": 18.4,
        "expected": "12-15",
        "evidence": "ffprobe format.duration=18.4",
    },
    "note": "Do not retry this plan as written: the timeline itself is too long.",
}


def _seed_p17(project: Path) -> None:
    _write_json(project / "plan_v1.json", P17_PLAN)


# --------------------------------------------------------------------------
# p18 - handoff stub, half filled in
# --------------------------------------------------------------------------

P18_HANDOFF = '''\
# Handoff

## Goal

Close the weekly ops digest for run-2026-10-27-a: one digest assembled from
local evidence, no invented numbers, every gap named.

## Decisions

- Evidence is read from `evidence/` only; no live calls.
- A missing number is reported as missing, never estimated.
- TODO: decide who publishes, and whether publishing needs an approval.

## Evidence

- `evidence/ops_week_41.json` - complete
- `evidence/ops_week_42.json` - `renders_completed` missing
- TODO: add the digest draft path once written

## Next step

Resume at the digest assembly step. Do not re-collect what is already here.

## Known unknowns

- The render worker was offline all week; the real count is unknown.
'''


def _seed_p18(project: Path) -> None:
    _write(project / "handoff.md", P18_HANDOFF)


# --------------------------------------------------------------------------
# p19 - two text files and a two-hunk diff (one hunk per file)
# --------------------------------------------------------------------------

P19_CONFIG_OLD = '''\
service = ledger
retries = 1
timeout = 30
'''

P19_CONFIG_NEW = '''\
service = ledger
retries = 3
timeout = 30
'''

P19_NOTES_OLD = '''\
# Ops notes
- render worker offline since Monday
- digest not published
'''

P19_NOTES_NEW = '''\
# Ops notes
- render worker restarted Tuesday 09:00
- digest not published
'''


def _unified(old: str, new: str, name: str) -> str:
    """A tight (context=1) unified diff for one file, generated from the text."""
    diff = difflib.unified_diff(
        old.splitlines(keepends=True),
        new.splitlines(keepends=True),
        fromfile="a/" + name,
        tofile="b/" + name,
        n=1,
    )
    return "".join(diff)


def p19_diff() -> str:
    return (_unified(P19_CONFIG_OLD, P19_CONFIG_NEW, "config.txt")
            + _unified(P19_NOTES_OLD, P19_NOTES_NEW, "notes.txt"))


def _seed_p19(project: Path) -> None:
    _write(project / "config.txt", P19_CONFIG_OLD)
    _write(project / "notes.txt", P19_NOTES_OLD)
    _write(project / "changes.diff", p19_diff())


# --------------------------------------------------------------------------
# p20 - a small three-node project skeleton that already runs
# --------------------------------------------------------------------------

P20_SKELETON = {
    "project": "close-out-demo",
    "nodes": [
        {"id": "n1", "name": "collect", "script": "nodes/collect.py", "depends_on": []},
        {"id": "n2", "name": "summarise", "script": "nodes/summarise.py",
         "depends_on": ["n1"]},
        {"id": "n3", "name": "verify", "script": "nodes/verify.py",
         "depends_on": ["n2"]},
    ],
    "evidence": "run_log.json",
}

P20_RUN = '''\
"""Run the three-node project end to end and leave a run log behind."""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
NODES = ["nodes/collect.py", "nodes/summarise.py", "nodes/verify.py"]


def main():
    log = []
    for rel in NODES:
        run = subprocess.run([sys.executable, rel], cwd=str(ROOT),
                             capture_output=True, text=True)
        log.append({"node": rel, "returncode": run.returncode,
                    "stdout": (run.stdout or "").strip()[-400:],
                    "stderr": (run.stderr or "").strip()[-400:]})
        if run.returncode != 0:
            break
    (ROOT / "run_log.json").write_text(
        json.dumps({"nodes": log}, indent=2) + "\\n", encoding="utf-8")
    ok = len(log) == len(NODES) and all(e["returncode"] == 0 for e in log)
    print("run ok" if ok else "run failed at %s" % log[-1]["node"])
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
'''

P20_COLLECT = '''\
"""Node 1: collect the week's order counts."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = {"orders": [12, 7, 5], "currency": "USD"}

out = ROOT / "data" / "collected.json"
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(DATA), encoding="utf-8")
print("collected %d days" % len(DATA["orders"]))
'''

P20_SUMMARISE = '''\
"""Node 2: summarise what node 1 collected."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
source = json.loads((DATA / "collected.json").read_text(encoding="utf-8"))
summary = {"days": len(source["orders"]), "total_orders": sum(source["orders"]),
           "currency": source["currency"]}
(DATA / "summary.json").write_text(json.dumps(summary), encoding="utf-8")
print("summary total %d" % summary["total_orders"])
'''

P20_VERIFY = '''\
"""Node 3: assert the summary before anyone reports it."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
summary = json.loads((ROOT / "data" / "summary.json").read_text(encoding="utf-8"))

assert summary["total_orders"] == 24, summary
assert summary["days"] == 3, summary
print("verified total %d across %d days" % (summary["total_orders"],
                                            summary["days"]))
'''


def _seed_p20(project: Path) -> None:
    _write_json(project / "skeleton.json", P20_SKELETON)
    _write(project / "run.py", P20_RUN)
    _write(project / "nodes/collect.py", P20_COLLECT)
    _write(project / "nodes/summarise.py", P20_SUMMARISE)
    _write(project / "nodes/verify.py", P20_VERIFY)


# --------------------------------------------------------------------------
# dispatch
# --------------------------------------------------------------------------

SEEDS: Dict[str, Callable[[Path], None]] = {
    "p01": _seed_p01, "p02": _seed_p02, "p03": _seed_p03, "p04": _seed_p04,
    "p05": _seed_p05, "p06": _seed_p06, "p07": _seed_p07, "p08": _seed_p08,
    "p09": _seed_p09, "p10": _seed_p10, "p11": _seed_p11, "p12": _seed_p12,
    "p13": _seed_empty, "p14": _seed_empty, "p15": _seed_p15, "p16": _seed_p16,
    "p17": _seed_p17, "p18": _seed_p18, "p19": _seed_p19, "p20": _seed_p20,
}


def brief_id(brief: Any) -> str:
    """Accept a brief dict, a bare id string, or an object with `.id`."""
    if isinstance(brief, dict):
        value = brief.get("id")
    elif isinstance(brief, str):
        value = brief
    else:
        value = getattr(brief, "id", None)
    bid = str(value or "").strip()
    if not bid:
        raise ValueError("brief has no id")
    return bid


def seed(project: Path, brief: dict) -> None:
    """Create the deterministic starting workspace for one brief."""
    bid = brief_id(brief)
    make = SEEDS.get(bid)
    if make is None:
        raise ValueError("no seed defined for brief %r" % bid)
    project = Path(project)
    project.mkdir(parents=True, exist_ok=True)
    make(project)


def briefs(path: Path | None = None) -> List[dict]:
    data = json.loads(Path(path or BRIEFS_PATH).read_text(encoding="utf-8"))
    return list(data.get("briefs") or [])


def expected_for(bid: str) -> Tuple[str, ...]:
    return EXPECTED.get(bid, ())


def missing_for(project: Path, bid: str) -> List[str]:
    return [rel for rel in expected_for(bid) if not (project / rel).is_file()]


def seed_all(root: Path) -> Dict[str, Any]:
    """Seed every brief under `root/<id>` and report what landed on disk."""
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    rows = []
    for brief in briefs():
        bid = brief_id(brief)
        project = root / bid
        seed(project, brief)
        present = [rel for rel in expected_for(bid) if (project / rel).is_file()]
        missing = [rel for rel in expected_for(bid) if not (project / rel).is_file()]
        dirs = {rel: (project / rel).is_dir() for rel in EXPECTED_DIRS.get(bid, ())}
        rows.append({"id": bid, "title": brief.get("title", ""),
                     "dir": str(project), "expected": list(expected_for(bid)),
                     "present": present, "missing": missing, "dirs": dirs,
                     "empty_by_design": not expected_for(bid)})
    return {
        "root": str(root),
        "briefs": len(rows),
        "seeded": sum(1 for r in rows if not r["missing"]),
        "ok": all(not r["missing"] and all(r["dirs"].values()) for r in rows),
        "rows": rows,
    }


# --------------------------------------------------------------------------
# selftest: prove the fixtures behave, in a temp dir only
# --------------------------------------------------------------------------

def _run(cwd: Path, *args: str, timeout: int = 120) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, *args], cwd=str(cwd),
                          capture_output=True, text=True, timeout=timeout)


def _tree(root: Path) -> Dict[str, str]:
    """sha256 of every file under root, keyed by relative posix path."""
    out = {}
    for path in sorted(Path(root).rglob("*")):
        if path.is_file():
            out[path.relative_to(root).as_posix()] = hashlib.sha256(
                path.read_bytes()).hexdigest()
    return out


def _expect_failing_pytest(project: Path) -> Tuple[bool, str]:
    code = (
        "import calc, test_calc\n"
        "assert calc.add(2, 3) == -1, 'add() no longer carries the bug'\n"
        "try:\n"
        "    test_calc.test_add()\n"
        "except AssertionError:\n"
        "    pass\n"
        "else:\n"
        "    raise SystemExit('test_add passed before the fix')\n"
        "print('bug present, test failing')\n"
    )
    done = _run(project, "-c", code)
    return done.returncode == 0, (done.stdout or done.stderr).strip()[:160]


def _expect_green_tests(project: Path, modules: List[str]) -> Tuple[bool, str]:
    code = (
        "import importlib\n"
        "for name in %r:\n"
        "    mod = importlib.import_module(name)\n"
        "    for fn in sorted(dir(mod)):\n"
        "        if fn.startswith('test_'):\n"
        "            getattr(mod, fn)()\n"
        "print('tests green')\n" % (modules,)
    )
    done = _run(project, "-c", code)
    return done.returncode == 0, (done.stdout or done.stderr).strip()[:160]


_HUNK = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")


def _parse_diff(text: str) -> List[Dict[str, Any]]:
    files: List[Dict[str, Any]] = []
    current: Dict[str, Any] | None = None
    hunk: Dict[str, Any] | None = None
    for line in text.splitlines():
        if line.startswith("--- "):
            current = {"old": line[4:].split("\t")[0], "hunks": []}
            files.append(current)
            hunk = None
        elif line.startswith("+++ "):
            continue
        elif line.startswith("@@"):
            match = _HUNK.match(line)
            if not match or current is None:
                raise ValueError("bad hunk header: %r" % line)
            hunk = {"old_start": int(match.group(1)),
                    "old_len": int(match.group(2) or 1),
                    "new_len": int(match.group(4) or 1),
                    "lines": []}
            current["hunks"].append(hunk)
        elif hunk is not None:
            hunk["lines"].append(line)
    return files


def _check_diff(project: Path) -> Tuple[bool, str]:
    try:
        files = _parse_diff(_read(project / "changes.diff"))
    except ValueError as exc:
        return False, str(exc)
    hunks = sum(len(entry["hunks"]) for entry in files)
    if hunks != 2:
        return False, "expected 2 hunks, found %d" % hunks
    for entry in files:
        rel = entry["old"][2:] if entry["old"].startswith("a/") else entry["old"]
        target = project / rel
        if not target.is_file():
            return False, "diff names a missing file: %s" % rel
        old = target.read_text(encoding="utf-8").splitlines()
        for hunk in entry["hunks"]:
            minus = sum(1 for line in hunk["lines"] if line[:1] in (" ", "-"))
            plus = sum(1 for line in hunk["lines"] if line[:1] in (" ", "+"))
            if minus != hunk["old_len"] or plus != hunk["new_len"]:
                return False, "hunk counts disagree in %s" % rel
            pos = hunk["old_start"] - 1
            for line in hunk["lines"]:
                tag, body = line[:1], line[1:]
                if tag == "+":
                    continue
                if pos >= len(old) or old[pos] != body:
                    return False, "hunk does not apply to %s at line %d" % (rel, pos + 1)
                pos += 1
    return True, "%d hunks across %d files, both apply" % (hunks, len(files))


def _checks(root: Path) -> Dict[str, Dict[str, Any]]:
    """Behavioural proofs, one per brief that ships executable fixtures."""
    checks: Dict[str, Dict[str, Any]] = {}

    def record(name: str, ok: bool, detail: str) -> None:
        checks[name] = {"ok": bool(ok), "detail": detail}

    p01 = root / "p01"
    ok, detail = _expect_failing_pytest(p01)
    record("p01_failing_test_reproducible", ok, detail)

    p03 = root / "p03"
    ok, detail = _expect_green_tests(p03, ["test_report_builder"])
    record("p03_baseline_tests_green", ok, detail)

    p04 = root / "p04"
    ok, detail = _expect_green_tests(p04, ["test_config"])
    record("p04_baseline_tests_green", ok, detail)
    flag_code = (
        "import config\n"
        "keys = [k for k in config.DEFAULTS\n"
        "        if 'flag' in k.lower() or k.lower().startswith('feature')]\n"
        "assert not keys, keys\n"
        "print('no feature flag in DEFAULTS (%d keys)' % len(config.DEFAULTS))\n"
    )
    done = _run(p04, "-c", flag_code)
    record("p04_no_flag_yet", done.returncode == 0,
           (done.stdout or done.stderr).strip()[:160])

    p05 = root / "p05"
    done = _run(p05, "-m", "py_compile", "broken.py")
    record("p05_build_broken", done.returncode != 0,
           "py_compile=%d" % done.returncode)

    p12 = root / "p12"
    front = (p12 / "front.txt").read_bytes()
    recorded = _read(p12 / "front.sha256").split()[0]
    record("p12_front_hash_matches",
           recorded == hashlib.sha256(front).hexdigest(), recorded[:16])
    back = _read(p12 / "back.txt")
    record("p12_back_has_one_defect",
           "Adminstration" in back and "Administration" not in back,
           "misspelled regulator name present")

    p19 = root / "p19"
    ok, detail = _check_diff(p19)
    record("p19_diff_two_hunks_applied", ok, detail)

    p20 = root / "p20"
    done = _run(p20, "run.py")
    record("p20_skeleton_runs", done.returncode == 0,
           (done.stdout or done.stderr).strip()[:160])

    return checks


def selftest(keep: bool = False) -> Dict[str, Any]:
    base = Path(tempfile.mkdtemp(prefix="ns_proj_20_seed_"))
    first, second = base / "a", base / "b"
    try:
        report = seed_all(first)
        seed_all(second)
        deterministic = _tree(first) == _tree(second)
        checks = _checks(first)
        report["checks"] = checks
        report["deterministic"] = deterministic
        report["ok"] = bool(report["ok"] and deterministic
                            and all(c["ok"] for c in checks.values()))
        return report
    finally:
        if keep:
            print("kept: %s" % base, file=sys.stderr)
        else:
            shutil.rmtree(base, ignore_errors=True)


def main(argv: List[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--selftest", action="store_true",
                    help="seed all 20 into a temp dir, print what exists, remove it")
    ap.add_argument("--all", dest="seed_all_to", default="",
                    help="seed all 20 into this directory (no checks)")
    ap.add_argument("--keep", action="store_true", help="keep the selftest temp dir")
    args = ap.parse_args(argv)

    if args.selftest:
        report = selftest(keep=args.keep)
        print(json.dumps(report, indent=2))
        return 0 if report["ok"] else 1
    if args.seed_all_to:
        report = seed_all(Path(args.seed_all_to))
        print(json.dumps({"root": report["root"], "briefs": report["briefs"],
                          "seeded": report["seeded"], "ok": report["ok"],
                          "missing": {r["id"]: r["missing"]
                                      for r in report["rows"] if r["missing"]}},
                         indent=2))
        return 0 if report["ok"] else 1
    ap.print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
