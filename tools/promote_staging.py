"""Item 5 — move `main` only when three gates pass, and name the gate that refuses.

`main` is the branch customers are served from, so a promotion cannot be "the tests looked
green once". Three gates are evaluated in this order, each with the evidence it read:

1. **suite** — a full serialised run is green *and* its test-id list still matches the
   baseline by name. A run file older than the newest commit on the source branch is
   stale: it cannot speak for code that did not exist when it ran.
2. **verifier** — an independent session reproduced the scorecard deltas (an `agree`
   verdict exists) and no open FAILED unit is inside the bundle.
3. **bundle** — nothing visual or creative is being auto-promoted. A commit under
   `northstar-os-ui/src/` is visual unless it is a test, a render, research, an export or
   a digest composite. Visual work needs a human to look at it, so it is refused by name
   and a review pack is written instead.

    python tools/promote_staging.py --check               # report eligibility, change nothing
    python tools/promote_staging.py --check --review       # ...and write the visual review pack
    python tools/promote_staging.py --promote              # merge source -> target when eligible
    python tools/promote_staging.py --revert promote/...   # undo a promotion merge

Refusals exit 2 and print the gate's key (`suite_stale`, `verifier_failed_unit_in_bundle`,
`bundle_visual`, ...). A refusal never moves a branch and never deletes a tag.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

ROOT = Path(__file__).resolve().parents[1]

DEFAULT_BASELINE_IDLIST = Path("reports/ty/_idlist_20261107.txt")
SUITE_DIR = Path("reports/ty")
VERDICT_FILE = Path("reports/ty/d15_verification.md")
FINDINGS_FILE = Path("reports/ty/verifier_findings.json")
PROMOTION_RECORD = Path("reports/ty/item5_promotion.md")
SCORECARDS = Path("ty/scorecards.json")

# A path under northstar-os-ui/src/ is creative unless it is one of these.
CREATIVE_EXEMPT_PREFIXES = (
    "northstar-os-ui/src/renders/",
    "northstar-os-ui/src/research/",
    "northstar-os-ui/src/exports/",
    "reports/ty/digest_composites_",
)
TEST_PATTERN = re.compile(
    r"(^|/)(test_[^/]*\.py|.*_test\.py|.*\.test\.(js|jsx|ts|tsx)|.*\.spec\.(js|jsx|ts|tsx)|__tests__/)"
)

SUMMARY_FIELD = re.compile(r"(\d+)\s+(passed|failed|errors?|skipped|xfailed|xpassed|warnings?)\b")
STAMP = re.compile(r"(\d{8})")


class Refusal(Exception):
    """A named refusal: the gate that failed and the evidence that failed it."""

    def __init__(self, key: str, message: str) -> None:
        super().__init__(f"{key}: {message}")
        self.key = key
        self.message = message


@dataclass
class Gate:
    key: str
    title: str
    ok: bool = False
    blockers: List[str] = field(default_factory=list)
    evidence: List[str] = field(default_factory=list)
    facts: Dict[str, Any] = field(default_factory=dict)

    def fail(self, key: str, message: str) -> "Gate":
        self.ok = False
        self.blockers.append(f"{key}: {message}")
        return self

    def as_dict(self) -> Dict[str, Any]:
        return {
            "gate": self.key,
            "title": self.title,
            "ok": self.ok,
            "blockers": self.blockers,
            "evidence": self.evidence,
            "facts": self.facts,
        }


@dataclass
class Commit:
    sha: str
    date: str
    subject: str
    body: str


class Repo:
    """git, rooted at one worktree, with the arguments this tool needs."""

    def __init__(self, root: Path) -> None:
        self.root = Path(root)

    def git(self, *args: str, check: bool = True) -> str:
        proc = subprocess.run(
            ["git", "--no-pager", *args],
            cwd=str(self.root),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        if check and proc.returncode != 0:
            raise RuntimeError(f"git {' '.join(args)} failed: {proc.stderr.strip() or proc.stdout.strip()}")
        return proc.stdout

    def ok(self, *args: str) -> bool:
        return subprocess.run(
            ["git", "--no-pager", *args],
            cwd=str(self.root),
            capture_output=True,
            text=True,
        ).returncode == 0

    def head_ref(self) -> str:
        return self.git("symbolic-ref", "--short", "-q", "HEAD", check=False).strip()

    def rev(self, ref: str) -> str:
        return self.git("rev-parse", ref).strip()

    def commit_time(self, ref: str) -> int:
        return int(self.git("log", "-1", "--format=%ct", ref).strip() or 0)

    def commits_between(self, target: str, source: str) -> List[Commit]:
        raw = self.git("log", "--format=%x01%H%x1f%ad%x1f%s%x1f%b", "--date=short",
                       f"{target}..{source}")
        out: List[Commit] = []
        for chunk in raw.split("\x01"):
            chunk = chunk.strip("\n")
            if not chunk:
                continue
            parts = chunk.split("\x1f")
            if len(parts) < 3:
                continue
            out.append(Commit(parts[0].strip(), parts[1].strip(), parts[2].strip(),
                              parts[3].strip() if len(parts) > 3 else ""))
        return out

    def changed_paths(self, target: str, source: str) -> List[str]:
        raw = self.git("diff", "--name-only", f"{target}..{source}")
        return [line.strip() for line in raw.splitlines() if line.strip()]

    def show(self, ref: str, path: str) -> Optional[str]:
        proc = subprocess.run(
            ["git", "--no-pager", "show", f"{ref}:{path}"],
            cwd=str(self.root),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        return proc.stdout if proc.returncode == 0 else None


# --------------------------------------------------------------------------- gate 1


def parse_summary(text: str) -> Optional[Dict[str, int]]:
    """The last pytest summary line, as counts. None when there is no summary."""
    counts: Dict[str, int] = {}
    for line in reversed(text.splitlines()):
        if " passed" not in line and " failed" not in line and " error" not in line:
            continue
        found = SUMMARY_FIELD.findall(line)
        if not found:
            continue
        for number, word in found:
            word = "error" if word.startswith("error") else word.rstrip("s") if word in ("warnings", "errors") else word
            counts[word] = counts.get(word, 0) + int(number)
        if "passed" in counts:
            return counts
    return None


def read_text(path: Path) -> str:
    """Read a report as text. The suite logs were written by PowerShell as UTF-16LE."""
    raw = path.read_bytes()
    if raw[:200].count(b"\x00") > 20:
        try:
            text = raw.decode("utf-16")
        except UnicodeDecodeError:
            text = raw.decode("utf-16-le", errors="replace")
    else:
        text = raw.decode("utf-8", errors="replace")
    return text.replace("\x00", "")


def newest_suite_report(root: Path, explicit: Optional[Path] = None) -> Optional[Path]:
    """The newest `_fullsuite_final_*.txt`; a final run outranks an earlier red one."""
    if explicit is not None:
        return explicit if explicit.exists() else None
    folder = root / SUITE_DIR
    final = sorted(folder.glob("_fullsuite_final_*.txt"),
                   key=lambda p: p.stat().st_mtime, reverse=True)
    if final:
        return final[0]
    candidates = sorted(folder.glob("_fullsuite_*.txt"),
                        key=lambda p: p.stat().st_mtime, reverse=True)
    return candidates[0] if candidates else None


def idlist_candidates(root: Path, report: Path, baseline: Path) -> List[Path]:
    """Id lists that could belong to this run, by the date stamp in the report name."""
    folder = root / SUITE_DIR
    match = STAMP.search(report.name)
    if match:
        named = [folder / f"_idlist_full_{match.group(1)}.txt",
                 folder / f"_idlist_{match.group(1)}.txt"]
        found = [p for p in named if p.exists()]
        if found:
            return found
    others = [p for p in folder.glob("_idlist_*.txt")
              if "gapbatch" not in p.stem and p.resolve() != baseline.resolve()]
    return sorted(others, key=lambda p: p.stat().st_mtime, reverse=True)[:1]


def load_ids(path: Path) -> List[str]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict):
        ids = data.get("ids") or data.get("results") or []
        return list(ids.keys()) if isinstance(ids, dict) else [str(x) for x in ids]
    return [str(x) for x in data]


def gate_suite(repo: Repo, source: str, explicit: Optional[Path],
               baseline: Path) -> Gate:
    gate = Gate("suite", "full suite green, compared by test name")
    root = repo.root
    report = newest_suite_report(root, explicit)
    if report is None:
        return gate.fail("suite_missing", f"no run report under {SUITE_DIR}/_fullsuite_*.txt")

    text = read_text(report)
    summary = parse_summary(text)
    gate.facts["report"] = str(report.relative_to(root)) if report.is_relative_to(root) else str(report)
    if summary is None:
        return gate.fail("suite_unparsable", f"{report.name} has no pytest summary line")
    gate.facts["summary"] = summary
    gate.evidence.append(
        "summary: " + ", ".join(f"{v} {k}" for k, v in summary.items())
    )

    red = summary.get("failed", 0) + summary.get("error", 0)
    if red or summary.get("passed", 0) == 0:
        gate.fail("suite_red", f"{report.name} is not green "
                  f"({summary.get('failed', 0)} failed, {summary.get('error', 0)} errors)")

    run_mtime = int(report.stat().st_mtime)
    newest = repo.commit_time(source)
    gate.facts["run_mtime"] = run_mtime
    gate.facts["newest_commit"] = newest
    gate.facts["newest_commit_iso"] = datetime.fromtimestamp(newest).isoformat(timespec="seconds") if newest else ""
    gate.evidence.append(
        f"run written {datetime.fromtimestamp(run_mtime).isoformat(timespec='seconds')}, "
        f"newest {source} commit {gate.facts['newest_commit_iso']}"
    )
    if run_mtime < newest:
        lag = newest - run_mtime
        gate.fail("suite_stale", f"{report.name} is {lag}s older than the newest commit on {source}; "
                  "the run cannot speak for code it predates")

    candidates = idlist_candidates(root, report, baseline)
    if not candidates or not baseline.exists():
        gate.fail("suite_idlist_missing",
                  f"cannot compare ids: run idlist={candidates}, baseline={baseline}")
        return gate
    outcomes = sum(summary.get(k, 0) for k in ("passed", "skipped", "xfailed", "xpassed"))
    ids_path = candidates[0]
    for candidate in candidates:
        if len(load_ids(candidate)) == outcomes:
            ids_path = candidate
            break
    run_ids = load_ids(ids_path)
    base_ids = load_ids(baseline)
    added = [i for i in run_ids if i not in set(base_ids)]
    removed = [i for i in base_ids if i not in set(run_ids)]
    gate.facts.update({
        "idlist": str(ids_path.relative_to(root)) if ids_path.is_relative_to(root) else str(ids_path),
        "run_ids": len(run_ids),
        "baseline_ids": len(base_ids),
        "added": added,
        "removed": removed,
    })
    gate.evidence.append(
        f"ids: {len(run_ids)} in {ids_path.name} vs {len(base_ids)} in {baseline.name} "
        f"-> {len(added)} added, {len(removed)} removed"
    )
    gate.evidence.append(
        f"run outcomes {outcomes} vs {len(run_ids)} ids: "
        + ("reconcile" if outcomes == len(run_ids) else "do not reconcile (counted, not blocking)")
    )
    if added:
        gate.evidence.append("added: " + ", ".join(sorted(added)[:6])
                             + (f" (+{len(added) - 6} more)" if len(added) > 6 else ""))
    if removed:
        gate.evidence.append("removed: " + ", ".join(sorted(removed)[:10]))
        gate.fail("suite_coverage_regression",
                  f"{len(removed)} test id(s) present on the baseline are gone from the run: "
                  + ", ".join(sorted(removed)[:5]))

    if not gate.blockers:
        gate.ok = True
    return gate


# --------------------------------------------------------------------------- gate 2


def parse_verdicts(text: str) -> List[Tuple[str, str, str]]:
    """(unit, item, verdict) from the D15 verdict table."""
    rows: List[Tuple[str, str, str]] = []
    row = re.compile(r"^\|\s*\d+\s*\|\s*(.+?)\s*\|\s*\*\*(agree|FAILED|BLOCKED)\*\*\s*\|", re.M)
    for item, verdict in row.findall(text):
        token = re.match(r"([A-Za-z]{1,4}\d+[A-Za-z0-9\-]*)", item)
        unit = token.group(1) if token else item
        rows.append((unit, item, verdict))
    return rows


def gate_verifier(repo: Repo, source: str, target: str, commits: Sequence[Commit],
                  note: Optional[str]) -> Gate:
    gate = Gate("verifier", "independent verifier reproduced the scorecard deltas")
    root = repo.root
    verdict_file = root / VERDICT_FILE
    findings_file = root / FINDINGS_FILE

    if not verdict_file.exists():
        return gate.fail("verifier_missing", f"{VERDICT_FILE} does not exist; nobody reproduced the deltas")
    verdicts = parse_verdicts(read_text(verdict_file))
    if not verdicts:
        return gate.fail("verifier_unparsable", f"{VERDICT_FILE} has no verdict table")
    agree = [u for u, _, v in verdicts if v == "agree"]
    failed = [u for u, _, v in verdicts if v == "FAILED"]
    blocked = [u for u, _, v in verdicts if v == "BLOCKED"]
    gate.facts.update({"agree": agree, "failed": failed, "blocked": blocked,
                       "verifier": note or ""})
    gate.evidence.append(f"{VERDICT_FILE.name}: {len(agree)} agree, {len(failed)} FAILED, "
                         f"{len(blocked)} BLOCKED")
    gate.evidence.append("reproduced by: " + (note if note else "not recorded (--verifier not given)"))
    if not agree:
        gate.fail("verifier_no_agree", f"{VERDICT_FILE.name} records no agree verdict")

    open_failed: List[Tuple[str, str]] = []
    if findings_file.exists():
        try:
            findings = json.loads(read_text(findings_file))
        except json.JSONDecodeError as exc:
            return gate.fail("verifier_unparsable", f"{FINDINGS_FILE.name}: {exc}")
        for item in findings.get("failed", []):
            open_failed.append((str(item.get("unit", "?")), str(item.get("item", ""))))
        gate.evidence.append(
            f"{FINDINGS_FILE.name}: {len(open_failed)} open FAILED, "
            f"{len(findings.get('blocked', []))} blocked"
        )
    else:
        gate.fail("verifier_findings_missing", f"{FINDINGS_FILE} does not exist; open failures unknown")
    for unit, _ in open_failed:
        if unit not in failed:
            failed.append(unit)

    haystack = [(c.sha, c.subject + "\n" + c.body) for c in commits]
    in_bundle: List[Tuple[str, List[str]]] = []
    for unit in sorted(set(failed)):
        pattern = re.compile(rf"(?<![A-Za-z0-9]){re.escape(unit)}(?![A-Za-z0-9])", re.I)
        hits = [sha for sha, text in haystack if pattern.search(text)]
        if hits:
            in_bundle.append((unit, hits[:5]))

    if in_bundle:
        for unit, hits in in_bundle:
            gate.fail("verifier_failed_unit_in_bundle",
                      f"FAILED unit {unit} is in the bundle "
                      f"(commits: {', '.join(h[:8] for h in hits)})")
        gate.evidence.append("failed units in bundle: "
                             + ", ".join(f"{u} ({len(h)} commit(s))" for u, h in in_bundle))
    else:
        gate.evidence.append("no open FAILED unit is referenced by a bundle commit")

    for unit in sorted(set(blocked)):
        pattern = re.compile(rf"(?<![A-Za-z0-9]){re.escape(unit)}(?![A-Za-z0-9])", re.I)
        hits = [sha for sha, text in haystack if pattern.search(text)]
        if hits:
            gate.evidence.append(
                f"warning: BLOCKED unit {unit} is in the bundle ({len(hits)} commit(s), "
                f"e.g. {', '.join(h[:8] for h in hits[:3])}) — blocked, not failed, so it is "
                "reported not refused"
            )

    gate.ok = not gate.blockers
    return gate


# --------------------------------------------------------------------------- gate 3


def is_creative(path: str) -> bool:
    if not path.startswith("northstar-os-ui/src/"):
        return False
    if path.startswith(CREATIVE_EXEMPT_PREFIXES):
        return False
    if TEST_PATTERN.search(path):
        return False
    return True


def gate_bundle(repo: Repo, source: str, target: str, commits: Sequence[Commit],
                approval: Optional[str]) -> Gate:
    gate = Gate("bundle", "no visual or creative change in the bundle")
    paths = repo.changed_paths(target, source)
    creative = [p for p in paths if is_creative(p)]
    gate.facts.update({"commits": len(commits), "paths": len(paths),
                       "creative_paths": len(creative),
                       "creative_sample": creative[:60],
                       "approval": approval or ""})
    gate.evidence.append(f"bundle {target}..{source}: {len(commits)} commit(s), "
                         f"{len(paths)} changed path(s)")
    gate.evidence.append(f"visual/creative paths: {len(creative)}")
    if creative:
        gate.evidence.extend("  " + p for p in creative[:10])
        if len(creative) > 10:
            gate.evidence.append(f"  ... and {len(creative) - 10} more")
        if approval:
            gate.evidence.append(f"operator visual approval recorded: {approval}")
            gate.ok = True
            gate.facts["approved"] = True
            return gate
        gate.fail("bundle_visual",
                  f"{len(creative)} visual/creative path(s) under northstar-os-ui/src/ "
                  "(e.g. " + ", ".join(creative[:3]) + ") — needs human eyes, not auto-promotion")
        return gate
    gate.ok = True
    return gate


# --------------------------------------------------------------------------- promotion


def evaluate(repo: Repo, source: str, target: str, *, suite: Optional[Path],
             baseline: Path, verifier: Optional[str], approval: Optional[str]) -> Dict[str, Any]:
    commits = repo.commits_between(target, source)
    gates = [
        gate_suite(repo, source, suite, baseline),
        gate_verifier(repo, source, target, commits, verifier),
        gate_bundle(repo, source, target, commits, approval),
    ]
    failed = [g.key for g in gates if not g.ok]
    return {
        "source": source,
        "target": target,
        "source_sha": repo.rev(source),
        "target_sha": repo.rev(target),
        "commits": commits,
        "gates": gates,
        "eligible": not failed,
        "refused_by": failed,
    }


def as_payload(result: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "source": result["source"],
        "target": result["target"],
        "source_sha": result["source_sha"],
        "target_sha": result["target_sha"],
        "eligible": result["eligible"],
        "refused_by": result["refused_by"],
        "gates": [gate.as_dict() for gate in result["gates"]],
        "review": result.get("review", ""),
    }


def render_check(result: Dict[str, Any]) -> str:
    lines = ["=== item 5 -- staging to main eligibility ===",
             f"source {result['source']} @ {result['source_sha'][:8]}  "
             f"target {result['target']} @ {result['target_sha'][:8]}",
             f"bundle: {len(result['commits'])} commit(s)", ""]
    for index, gate in enumerate(result["gates"], 1):
        status = "PASS" if gate.ok else "FAIL"
        lines.append(f"gate {index}/3  {gate.key:9s} {status}  {gate.title}")
        for line in gate.evidence:
            lines.append(f"   - {line}")
        for blocker in gate.blockers:
            lines.append(f"   x {blocker}")
        lines.append("")
    if result["eligible"]:
        lines.append("VERDICT: ELIGIBLE -- all three gates pass")
    else:
        lines.append("VERDICT: REFUSED -- " + ", ".join(f"gate '{k}'" for k in result["refused_by"]))
    return "\n".join(lines)


def _safe_date() -> str:
    return datetime.now().strftime("%Y%m%d")


def write_promotion_record(repo: Repo, result: Dict[str, Any], tag: str,
                           rollback_tag: Optional[str], new_sha: str) -> Path:
    path = repo.root / PROMOTION_RECORD
    path.parent.mkdir(parents=True, exist_ok=True)
    body = [f"# Item 5 promotion — {_safe_date()}", "",
            f"- source `{result['source']}` @ `{result['source_sha']}`",
            f"- target `{result['target']}` @ `{result['target_sha']}` before, `{new_sha}` after",
            f"- promotion tag `{tag}`",
            f"- rollback tag `{rollback_tag}`" if rollback_tag else "- rollback tag: none",
            f"- bundle: {len(result['commits'])} commit(s)", "",
            "## Gates", ""]
    for index, gate in enumerate(result["gates"], 1):
        body.append(f"### {index}. {gate.key} — {'PASS' if gate.ok else 'FAIL'}")
        body.append("")
        body.append(gate.title)
        body.append("")
        for line in gate.evidence:
            body.append(f"- {line}")
        for blocker in gate.blockers:
            body.append(f"- **{blocker}**")
        body.append("")
    path.write_text("\n".join(body) + "\n", encoding="utf-8")
    return path


def _scorecards(repo: Repo, ref: str) -> Optional[Dict[str, Any]]:
    raw = repo.show(ref, SCORECARDS.as_posix())
    if raw is None:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


IMAGE_SUFFIXES = (".png", ".jpg", ".jpeg", ".webp")


def _image_paths(paths: Sequence[str]) -> List[str]:
    return [p for p in paths if p.lower().endswith(IMAGE_SUFFIXES)]


def _last_touch(repo: Repo, target: str, source: str) -> Dict[str, int]:
    """path -> the newest commit time that touched it inside the bundle."""
    raw = repo.git("log", "--format=%x01%ct", "--name-only", f"{target}..{source}")
    touch: Dict[str, int] = {}
    stamp = 0
    for line in raw.splitlines():
        if line.startswith("\x01"):
            try:
                stamp = int(line[1:].strip())
            except ValueError:
                stamp = 0
            continue
        path = line.strip()
        if path:
            touch[path] = max(touch.get(path, 0), stamp)
    return touch


def write_review_pack(repo: Repo, result: Dict[str, Any], out: Optional[Path] = None) -> Path:
    root = repo.root
    source, target = result["source"], result["target"]
    date = _safe_date()
    path = out or (root / "reports" / "ty" / f"staging_review_{date}.md")
    paths = repo.changed_paths(target, source)
    images = _image_paths(paths)
    touch = _last_touch(repo, target, source)

    def rank(path: str) -> int:
        if "digest_composites_" in path:
            return 0
        if re.search(r"dogfood|audit|review", path, re.I):
            return 1
        if "screenshots/" in path:
            return 2
        return 3

    # Test fixtures are not evidence of what the product looks like to a person.
    reviewable = [p for p in images if "/fixtures/" not in p and "\\fixtures\\" not in p]
    ordered = sorted(reviewable, key=lambda p: (rank(p), -touch.get(p, 0)))
    chosen: List[str] = []
    for item in ordered:
        if item not in chosen:
            chosen.append(item)
        if len(chosen) >= 24:
            break

    before_scores = _scorecards(repo, target)
    after_scores = _scorecards(repo, source)

    lines = [f"# Staging review — {date}", "",
             f"`{source}` is {len(result['commits'])} commit(s) ahead of `{target}` and the bundle "
             "contains visual or creative work, so it is refused by name and shown here instead.",
             "",
             f"- source `{source}` @ `{result['source_sha']}`",
             f"- target `{target}` @ `{result['target_sha']}`",
             "", "## Gates", "", "| gate | result | evidence |", "|---|---|---|"]
    for gate in result["gates"]:
        evidence = " ".join(gate.evidence[:2]).replace("|", "/")
        lines.append(f"| {gate.key} | {'PASS' if gate.ok else 'FAIL'} | {evidence} |")
    if result["refused_by"]:
        lines += ["", "Refused by: " + ", ".join(f"`{k}`" for k in result["refused_by"])]

    lines += ["", "## Before / after", "",
              f"{len(images)} image(s) changed in the bundle. Composited digests come first, then "
              f"dogfood/audit shots, then screenshots, newest first ({len(chosen)} of {len(images)}):", "",
              "| after (this bundle) | before (on `main`) |", "|---|---|"]
    if chosen:
        for item in chosen:
            after_link = f"![after](../../{item})"
            before_link = (f"![before](../../{item})" if repo.ok("cat-file", "-e", f"{target}:{item}")
                           else "_absent on main_")
            lines.append(f"| `{item}`<br>{after_link} | {before_link} |")
    else:
        lines.append("| _no image changed_ | _nothing to compare_ |")

    lines += ["", "## Scorecard deltas", ""]
    if before_scores is None and after_scores is None:
        lines.append("`ty/scorecards.json` does not exist on either side.")
    elif before_scores is None:
        lines += [f"`ty/scorecards.json` is **absent on `{target}`** — every score here is new.", "",
                  f"after: {len(after_scores.get('services', []))} services, "
                  f"at_bar **{len(after_scores.get('at_bar', []))}** "
                  f"({', '.join(after_scores.get('at_bar', [])) or 'none'}), "
                  f"test_ids {after_scores.get('test_ids')}", "",
                  "| service | score | at bar |", "|---|---|---|"]
        for service in sorted(after_scores.get("services", []),
                              key=lambda s: s.get("score", 0.0), reverse=True):
            lines.append(f"| {service.get('id')} | {service.get('score', 0.0):g} | "
                         f"{'yes' if service.get('meets_bar') else 'no'} |")
    else:
        before_map = {s["id"]: s for s in before_scores.get("services", [])}
        after_map = {s["id"]: s for s in after_scores.get("services", [])}
        lines += ["| service | before | after | delta | at bar |", "|---|---|---|---|---|"]
        for sid in sorted(set(before_map) | set(after_map)):
            b, a = before_map.get(sid), after_map.get(sid)
            b_score = b.get("score", 0.0) if b else 0.0
            a_score = a.get("score", 0.0) if a else 0.0
            delta = a_score - b_score
            bar = "yes" if (a and a.get("meets_bar")) else "no"
            lines.append(f"| {sid} | {b_score:g} | {a_score:g} | {delta:+g} | {bar} |")
        lines += ["", f"at_bar before **{len(before_scores.get('at_bar', []))}** -> "
                      f"after **{len(after_scores.get('at_bar', []))}**; "
                      f"test_ids {before_scores.get('test_ids')} -> {after_scores.get('test_ids')}"]

    lines += ["", f"## Merged job list ({len(result['commits'])} commits)", "",
              "| sha | date | job |", "|---|---|---|"]
    for commit in result["commits"]:
        subject = commit.subject.replace("|", "/")
        lines.append(f"| `{commit.sha[:8]}` | {commit.date} | {subject} |")

    tag = f"promote/{date}-{result['source_sha'][:8]}"
    lines += ["", "## One command", ""]
    if repo.ok("rev-parse", "--verify", f"refs/tags/{tag}"):
        lines += ["Promotion tag exists; to undo it:", "", "```",
                  f"python tools/promote_staging.py --revert {tag}", "```"]
    else:
        lines += ["Look at the images above, then promote with the recorded approval:",
                  "", "```",
                  f'python tools/promote_staging.py --promote --verifier "<session>" '
                  f'--approve-visual "<what you looked at and accepted>"', "```"]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def do_promote(repo: Repo, result: Dict[str, Any]) -> Tuple[str, Optional[str], str]:
    target, source = result["target"], result["source"]
    date = _safe_date()
    tag = f"promote/{date}-{result['source_sha'][:8]}"
    if repo.ok("rev-parse", "--verify", f"refs/tags/{tag}"):
        raise Refusal("tag_exists", f"{tag} already exists; tags are never moved or deleted")

    rollback_tag = f"rollback/{date}-{result['target_sha'][:8]}"
    if repo.ok("rev-parse", "--verify", f"refs/tags/{rollback_tag}"):
        rollback_tag = f"{rollback_tag}-2"

    worktree = repo.root / ".promote-worktree"
    if worktree.exists():
        raise Refusal("worktree_dirty", f"{worktree} already exists; refusing to touch it")
    lock = None
    try:
        add = subprocess.run(
            ["git", "--no-pager", "worktree", "add", str(worktree), target],
            cwd=str(repo.root), capture_output=True, text=True,
        )
        if add.returncode != 0:
            raise Refusal(
                "target_checked_out",
                f"`{target}` cannot be checked out for the merge ({add.stderr.strip()}). "
                f"Run `git merge --no-ff {source}` in a worktree on `{target}`.",
            )
        lock = worktree
        subprocess.run(["git", "tag", rollback_tag, result["target_sha"]],
                       cwd=str(repo.root), check=True, capture_output=True)
        merge = subprocess.run(
            ["git", "--no-pager", "merge", "--no-ff", "-m",
             f"promote: {source} {result['source_sha'][:12]} -> {target} "
             f"({len(result['commits'])} commits, gates 1-3 green) {tag}",
             source],
            cwd=str(worktree), capture_output=True, text=True,
        )
        if merge.returncode != 0:
            subprocess.run(["git", "merge", "--abort"], cwd=str(worktree), capture_output=True)
            raise Refusal("merge_conflict", (merge.stderr or merge.stdout).strip().splitlines()[0]
                          if (merge.stderr or merge.stdout).strip() else "merge failed")
        new_sha = subprocess.run(["git", "rev-parse", "HEAD"], cwd=str(worktree),
                                 capture_output=True, text=True).stdout.strip()
        subprocess.run(["git", "tag", tag, new_sha], cwd=str(repo.root), check=True,
                       capture_output=True)
    finally:
        if lock is not None:
            subprocess.run(["git", "worktree", "remove", "--force", str(worktree)],
                           cwd=str(repo.root), capture_output=True)
            subprocess.run(["git", "worktree", "prune"], cwd=str(repo.root), capture_output=True)
    return tag, rollback_tag, new_sha


def do_revert(repo: Repo, tag: str, target: str) -> Dict[str, Any]:
    if not repo.ok("rev-parse", "--verify", f"refs/tags/{tag}"):
        return {"reverted": False, "reason": "tag_absent",
                "message": f"no tag {tag}; nothing to revert"}
    if repo.head_ref() != target:
        raise Refusal("wrong_branch",
                      f"--revert must run in a worktree on `{target}` (HEAD is "
                      f"`{repo.head_ref() or 'detached'}`); run `git revert -m 1 --no-edit {tag}` there")
    revert = subprocess.run(["git", "--no-pager", "revert", "-m", "1", "--no-edit", tag],
                            cwd=str(repo.root), capture_output=True, text=True)
    if revert.returncode != 0:
        subprocess.run(["git", "revert", "--abort"], cwd=str(repo.root), capture_output=True)
        raise Refusal("revert_conflict", (revert.stderr or revert.stdout).strip()[:400])
    return {"reverted": True, "reason": "ok", "head": repo.rev("HEAD")}


def main(argv: Optional[Sequence[str]] = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            try:
                reconfigure(encoding="utf-8", errors="replace")
            except (ValueError, OSError):
                pass
    parser = argparse.ArgumentParser(description="Promote staging to main, gated")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true", help="report eligibility, change nothing")
    mode.add_argument("--promote", action="store_true", help="merge source -> target when eligible")
    mode.add_argument("--revert", metavar="TAG", help="revert a promotion; no-op when the tag is absent")
    parser.add_argument("--source", default="staging")
    parser.add_argument("--target", default="main")
    parser.add_argument("--suite", type=Path, help="the full-suite report to read")
    parser.add_argument("--baseline-idlist", type=Path, default=DEFAULT_BASELINE_IDLIST)
    parser.add_argument("--verifier", help="who reproduced the scorecard deltas")
    parser.add_argument("--approve-visual", help="operator approval note covering the visual bundle")
    parser.add_argument("--review", action="store_true", help="write the visual review pack")
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    parser.add_argument("--repo", type=Path, default=ROOT, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)

    repo = Repo(args.repo)
    baseline = args.baseline_idlist if args.baseline_idlist.is_absolute() else repo.root / args.baseline_idlist

    if args.revert:
        try:
            outcome = do_revert(repo, args.revert, args.target)
        except Refusal as refusal:
            print(f"REFUSED {refusal}", file=sys.stderr)
            return 2
        print(json.dumps(outcome) if args.json else outcome["message"])
        return 0

    try:
        result = evaluate(repo, args.source, args.target, suite=args.suite, baseline=baseline,
                          verifier=args.verifier, approval=args.approve_visual)
    except RuntimeError as exc:
        print(f"ERROR {exc}", file=sys.stderr)
        return 1

    if args.review:
        pack = write_review_pack(repo, result)
        result["review"] = str(pack)

    if args.check:
        print(json.dumps(as_payload(result), indent=2) if args.json else render_check(result))
        if args.review:
            print(f"\nreview pack: {result['review']}")
        return 0 if result["eligible"] else 2

    if not result["eligible"]:
        pack = None
        if any(gate.key == "bundle" and not gate.ok for gate in result["gates"]):
            pack = write_review_pack(repo, result)
        print(render_check(result))
        if pack:
            print(f"\nreview pack: {pack}")
        return 2

    try:
        tag, rollback_tag, new_sha = do_promote(repo, result)
    except Refusal as refusal:
        print(f"REFUSED {refusal}", file=sys.stderr)
        return 2
    record = write_promotion_record(repo, result, tag, rollback_tag, new_sha)
    payload = {"promoted": True, "tag": tag, "rollback": rollback_tag,
               "new_target_sha": new_sha, "record": str(record)}
    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        print(render_check(result))
        print(f"\npromoted: tag {tag}, rollback tag {rollback_tag}")
        print(f"new {args.target} sha: {new_sha}")
        print(f"record: {record}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
