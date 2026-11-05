"""The standing improvement backlog: list it, check it, promote it into the loop.

The continuous loop executes task contracts and never invents scope. That is
correct, and it means a drained queue is a stopped loop. This tool keeps the
queue fed from a curated file instead of from whatever a model felt like doing:

    python tools/improvement_backlog.py --list
        grouped by theme and priority, with counts

    python tools/improvement_backlog.py --check
        read-only. Validates the schema, the statuses, unique ids, and - for every
        'ready' item - that write_paths are inside the loop's commit allowlist and
        that a verification is named. Exits 1 on any problem.

    python tools/improvement_backlog.py --promote <id>
        turns one 'ready' item into a task card in config/continuous_loop_tasks.json.
        The card is validated with continuous_loop.validate_task BEFORE the file is
        written, so a promotion cannot create a task the supervisor would refuse.

    python tools/improvement_backlog.py --done <id> --commit <sha>
        marks an item done and records the commit that shipped it.

Nothing here dispatches work. Promotion only makes an item eligible; the
supervisor still takes the baseline, audits the scope and commits.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple

ROOT = Path(__file__).resolve().parents[1]
BACKLOG = ROOT / "state" / "backlog" / "improvements.json"
TASKS = ROOT / "config" / "continuous_loop_tasks.json"

STATUSES = ("ready", "promoted", "needs-author", "blocked", "done")
THEMES = ("creative", "ui", "backend", "tooling", "reliability")
PRIORITIES = ("P1", "P2", "P3")

sys.path.insert(0, str(ROOT / "scripts"))


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def load(path: Path | None = None) -> Dict[str, Any]:
    path = BACKLOG if path is None else Path(path)
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not isinstance(data.get("items"), list):
        raise ValueError(f"{path} is not an improvement backlog")
    return data


def save(data: Dict[str, Any], path: Path | None = None) -> None:
    path = BACKLOG if path is None else Path(path)
    data["updated_at"] = _now()
    data["counts"] = counts(data)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n",
                    encoding="utf-8", newline="")


def counts(data: Dict[str, Any]) -> Dict[str, int]:
    out = {"total": len(data["items"])}
    for status in STATUSES:
        out[status] = sum(1 for i in data["items"] if i.get("status") == status)
    return out


def check(data: Dict[str, Any]) -> List[str]:
    """Every reason the backlog is not trustworthy. Empty list means it is."""
    import continuous_loop as cl

    problems: List[str] = []
    seen = set()
    for index, item in enumerate(data["items"]):
        label = item.get("id") or f"items[{index}]"
        if not item.get("id"):
            problems.append(f"{label}: missing id")
        elif item["id"] in seen:
            problems.append(f"{label}: duplicate id")
        seen.add(item.get("id"))
        if item.get("status") not in STATUSES:
            problems.append(f"{label}: status {item.get('status')!r} is not one of {STATUSES}")
        if item.get("theme") not in THEMES:
            problems.append(f"{label}: theme {item.get('theme')!r} is not one of {THEMES}")
        if item.get("priority") not in PRIORITIES:
            problems.append(f"{label}: priority {item.get('priority')!r} is not one of {PRIORITIES}")
        if not item.get("problem"):
            problems.append(f"{label}: no problem statement")
        if not item.get("evidence"):
            problems.append(f"{label}: no evidence - an unevidenced item is an opinion")
        if item.get("status") == "ready":
            paths = item.get("write_paths") or []
            if not paths:
                problems.append(f"{label}: ready but has no write_paths")
            else:
                _, refused = cl.validate_commit_paths(paths)
                for reason in refused:
                    problems.append(f"{label}: ready but {reason}")
            if not item.get("verification"):
                problems.append(f"{label}: ready but names no verification")
        if item.get("status") in ("needs-author", "blocked") and not item.get("blocked"):
            problems.append(f"{label}: {item.get('status')} but no blocked reason")
    return problems


def _card(item: Dict[str, Any]) -> Dict[str, Any]:
    """The loop task contract for a ready backlog item."""
    paths = list(item["write_paths"])
    checks = item.get("checks") or []
    if not checks:
        raise ValueError(f"{item['id']}: a ready item must name checks; "
                         "a verification sentence is not a command")
    card = {
        "id": item["id"],
        "name": item["title"],
        "schema_version": 2,
        "authorized": True,
        "authorization_note": (
            "Promoted from state/backlog/improvements.json by "
            f"tools/improvement_backlog.py. Evidence: {'; '.join(item['evidence'][:3])}"),
        "risk": item.get("risk", "low"),
        "risk_class": item.get("risk", "low"),
        "execution": "ty",
        "contract_version": 1,
        "objective": f"{item['problem']}\n\nCHANGE: {item['proposed_change']}\n\n"
                     f"VERIFICATION: {item['verification']}",
        "dependencies": [],
        "write_paths": paths,
        "read_paths": [],
        "apply_commands": [],
        "precheck_commands": [],
        "checks": checks,
        "acceptance_commands": [c["cmd"] for c in checks],
        "commit_paths": paths,
        "commit_message": f"{item.get('commit_prefix', 'feat')}: {item['title'][:60]}",
        "required_artifact": paths[0],
        "timeout_seconds": 900,
        "max_repairs": 1,
        "max_steps": 16,
        "model": "qwen3.5:4b",
        "provider": "ollama",
        "num_ctx": 8192,
        "native_tools": True,
        "allowed_tools": ["read", "ast_edit", "run", "finish"],
        "author_lane": "opencode-go/deepseek-v4.1-flash (unattended CLI)",
    }
    # A new module must name the consumer the supervisor can verify (see
    # continuous_loop.wiring_errors); pass the item's declaration straight through.
    if item.get("wiring"):
        card["wiring"] = item["wiring"]
    return card


def promote(item_id: str) -> Dict[str, Any]:
    import continuous_loop as cl

    data = load()
    item = next((i for i in data["items"] if i.get("id") == item_id), None)
    if item is None:
        raise ValueError(f"unknown backlog item {item_id!r}")
    if item.get("status") != "ready":
        raise ValueError(f"{item_id} is {item.get('status')!r}; only 'ready' items may be promoted")
    problems = [p for p in check(data) if p.startswith(item_id)]
    if problems:
        raise ValueError("item is not promotable: " + "; ".join(problems))

    card = _card(item)
    tasks = json.loads(TASKS.read_text(encoding="utf-8"))
    if any(t.get("id") == card["id"] for t in tasks.get("tasks") or []):
        raise ValueError(f"a task {card['id']} already exists in {TASKS.name}")
    errors = cl.validate_task(card)
    if errors:
        raise ValueError("the supervisor would refuse this card: " + "; ".join(errors))

    tasks.setdefault("tasks", []).append(card)
    TASKS.write_text(json.dumps(tasks, indent=2, ensure_ascii=False) + "\n",
                     encoding="utf-8", newline="")
    item["status"] = "promoted"
    item["promoted_at"] = _now()
    item["task_id"] = card["id"]
    save(data)
    return {"promoted": item_id, "task": card["id"], "write_paths": card["write_paths"]}


def mark_done(item_id: str, commit: str) -> Dict[str, Any]:
    data = load()
    item = next((i for i in data["items"] if i.get("id") == item_id), None)
    if item is None:
        raise ValueError(f"unknown backlog item {item_id!r}")
    item["status"] = "done"
    item["done_at"] = _now()
    item["commit"] = commit
    save(data)
    return {"done": item_id, "commit": commit}


def render(data: Dict[str, Any]) -> str:
    counts_ = counts(data)
    lines = [f"IMPROVEMENT BACKLOG  ({counts_['total']} items: "
             f"{counts_['ready']} ready, {counts_.get('promoted', 0)} promoted, "
             f"{counts_['needs-author']} needs-author, "
             f"{counts_['blocked']} blocked, {counts_['done']} done)"]
    for theme in THEMES:
        items = [i for i in data["items"] if i.get("theme") == theme]
        if not items:
            continue
        lines.append("")
        lines.append(f"  {theme.upper()}")
        for priority in PRIORITIES:
            for item in sorted((i for i in items if i.get("priority") == priority),
                               key=lambda i: i["id"]):
                flag = item.get("status", "?")
                lines.append(f"    [{priority}] {flag:<12} {item['id']}")
                lines.append(f"           {item['title']}")
                if flag == "blocked" and item.get("blocked"):
                    lines.append(f"           blocked: {item['blocked'][:100]}")
    return "\n".join(lines)


def scan_report(check: str = "") -> Dict[str, Any]:
    """Run the production-readiness scan. The scanner's real consumer.

    A scanner nothing calls is the same defect it exists to find, so the backlog
    tool is its entry point: `--scan` prints the findings next to the queue, which
    is where a finding has to land to become work.
    """
    sys.path.insert(0, str(ROOT / "tools"))
    import production_readiness_scan as prs  # noqa: PLC0415 - deliberate late import
    selected = [c.strip() for c in str(check or "").split(",") if c.strip()] or None
    return prs.scan(selected)


def vet_report(name: str, ecosystem: str, version: str = "") -> Dict[str, Any]:
    """Vet a package against OSV. The supply-chain check the adoption gate lacks.

    provider_suite answers "may this lane use it" (licence, lane, arming). It
    cannot answer "is it malicious". Before an item that installs something is
    promoted, this is the check that runs.
    """
    sys.path.insert(0, str(ROOT / "tools"))
    import vet_package as vp  # noqa: PLC0415 - deliberate late import
    return vp.vet(name, ecosystem, version or None)


def render_scan(report: Dict[str, Any]) -> str:
    lines = [f"READINESS SCAN  ({report['total']} finding(s))"]
    for name, count in sorted(report["by_check"].items(), key=lambda kv: -kv[1]):
        lines.append(f"  {name:<20} {count}")
    if report.get("waivers"):
        lines.append(f"  waived: {len(report['waivers'])} declared in-file")
    lines.append("")
    lines.append("  top hotspots")
    for path, count in report["hotspots"][:8]:
        lines.append(f"    {count:>3}  {path}")
    lines.append("")
    lines.append("  each finding is a candidate item; --promote needs write_paths and checks")
    return "\n".join(lines)


def main(argv: List[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    group = ap.add_mutually_exclusive_group(required=True)
    group.add_argument("--list", action="store_true")
    group.add_argument("--check", action="store_true")
    group.add_argument("--scan", nargs="?", const="", metavar="CHECKS",
                       help="run the production-readiness scan (optionally a comma-separated subset)")
    group.add_argument("--vet", metavar="NAME",
                       help="vet a package against OSV before promoting an install item")
    group.add_argument("--promote", metavar="ID")
    group.add_argument("--done", metavar="ID")
    ap.add_argument("--commit", default="", help="commit sha for --done")
    ap.add_argument("--ecosystem", default="PyPI", help="ecosystem for --vet")
    ap.add_argument("--version", default="", help="version for --vet")
    args = ap.parse_args(argv)

    if args.vet:
        try:
            print(json.dumps(vet_report(args.vet, args.ecosystem, args.version), indent=2))
        except (OSError, ValueError) as exc:
            print(f"REFUSED (check incomplete, never a pass): {exc}")
            return 1
        return 0

    if args.scan is not None:
        try:
            report = scan_report(args.scan)
        except (OSError, ValueError) as exc:
            print(f"FAIL: {exc}")
            return 1
        print(json.dumps(report, indent=2) if args.scan else render_scan(report))
        return 0

    try:
        data = load()
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"FAIL: {exc}")
        return 1

    if args.list:
        print(render(data))
        return 0
    if args.check:
        problems = check(data)
        if problems:
            for problem in problems:
                print("FAIL  " + problem)
            print(f"\n{len(problems)} problem(s)")
            return 1
        print(json.dumps({"status": "OK", "counts": counts(data)}, indent=2))
        return 0
    if args.promote:
        try:
            print(json.dumps(promote(args.promote), indent=2))
        except (OSError, ValueError, KeyError) as exc:
            print(f"FAIL: {exc}")
            return 1
        return 0
    try:
        print(json.dumps(mark_done(args.done, args.commit), indent=2))
    except (OSError, ValueError) as exc:
        print(f"FAIL: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
