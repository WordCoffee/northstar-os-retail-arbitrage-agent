"""The daily digest, and the disk floor that gates work before it starts.

Folded fix (WORK ORDER 3 items 5): *no downloads or new worktrees below 5 GB free; report
free space in every digest.* The floor lives here so every caller asks the same question,
and the digest always prints the answer.

    python tools/ty_digest.py --write
"""
from __future__ import annotations

import argparse
import json
import shutil
import sqlite3
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parents[1]
TY = ROOT / "reports" / "ty"
QUEUE = TY / "director_queue.json"
SCORES = ROOT / "ty" / "scorecards.json"
TY_DIR = ROOT / "ty"
DB = ROOT / "state" / "director" / "queue.sqlite"

FLOOR_GB = 5.0


def free_gb(path: Optional[Path] = None) -> float:
    try:
        usage = shutil.disk_usage(str(path or ROOT))
        return round(usage.free / (1024 ** 3), 2)
    except OSError:
        return 0.0


def allow_download(*, path: Optional[Path] = None, free: Optional[float] = None) -> Dict[str, Any]:
    """May work that consumes disk start? The floor is 5 GB and it is not negotiable."""
    space = free_gb(path) if free is None else float(free)
    ok = space >= FLOOR_GB
    return {"allow": ok, "free_gb": space, "floor_gb": FLOOR_GB,
            "reason": "" if ok else f"free disk {space} GB is below the {FLOOR_GB} GB floor"}


def allow_worktree(*, path: Optional[Path] = None,
                   free: Optional[float] = None) -> Dict[str, Any]:
    """A worktree is cheap but it is still new disk; the same floor applies."""
    return allow_download(path=path, free=free)


def _read_json(path: Path) -> Dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _jobs() -> Dict[str, Any]:
    if not DB.exists():
        return {}
    try:
        conn = sqlite3.connect(str(DB), timeout=5)
        conn.row_factory = sqlite3.Row
        rows = [dict(row) for row in
                conn.execute("SELECT id, unit, title, status, owner FROM jobs").fetchall()]
        conn.close()
    except sqlite3.Error:
        return {}
    counts: Dict[str, int] = {}
    for row in rows:
        counts[row["status"]] = counts.get(row["status"], 0) + 1
    return {"total": len(rows), "by_status": counts,
            "open": [row for row in rows if row["status"] in
                     ("queued", "claimed", "running", "ready")][:10]}


def _composites() -> List[Dict[str, Any]]:
    """Composite outputs with the source they were made from, newest first.

    A composite is only reviewable next to its source, so the digest pairs them. Metadata comes
    from the proof run and the brief catalogue; a pair without a source is listed as unpaired
    rather than guessed at.
    """
    proof = _read_json(ROOT / "state" / "seller" / "composite_proof.json") or {}
    briefs = _read_json(ROOT / "tools" / "seller_tester" / "mogra_briefs.json") or {}
    by_id = {str(brief.get("id")): brief for brief in briefs.get("briefs") or []}
    region = _read_json(ROOT / "state" / "seller" / "composite_region.json") or {}
    region_by_id = {str(row.get("brief_id")): row for row in region.get("rows") or []}

    rows: List[Dict[str, Any]] = []
    for result in proof.get("results") or []:
        brief_id = str(result.get("brief_id"))
        output = str(result.get("artefact_path") or "")
        brief = by_id.get(brief_id) or {}
        source = str(((brief.get("reference") or {}).get("path")) or "")
        audit = region_by_id.get(brief_id) or {}
        rows.append({
            "brief_id": brief_id,
            "output": output,
            "output_ok": bool(output) and (ROOT / output).is_file(),
            "source": source,
            "source_ok": bool(source) and (ROOT / source).is_file(),
            "fidelity": str(result.get("fidelity") or brief.get("fidelity") or "exact"),
            "route": str(result.get("route") or ""),
            "score": result.get("score"),
            "passed": result.get("passed"),
            "provisional": bool(result.get("provisional")),
            "provisional_score": result.get("provisional_score"),
            "similarity": audit.get("similarity"),
            "region_state": ("verified" if audit.get("ok")
                             else "cannot verify" if audit.get("cannot_verify")
                             else "not audited" if not audit else "failed"),
        })
    return rows


def _contact_sheet(rows: List[Dict[str, Any]], limit: int = 3) -> Optional[str]:
    """One side-by-side image per pair, source on the left and output on the right."""
    if not rows:
        return None
    try:
        from PIL import Image, ImageDraw, ImageFont

        pairs = [row for row in rows if row["source_ok"] and row["output_ok"]][:limit]
        if not pairs:
            return None
        tile = 380
        sheet = Image.new("RGB", (tile * 2, tile * len(pairs) + 26), "#f6f3ec")
        draw = ImageDraw.Draw(sheet)
        try:
            font = ImageFont.truetype("segoeui.ttf", 16)
        except OSError:
            font = ImageFont.load_default()
        draw.text((8, 4), "source", fill="#1b2a22", font=font)
        draw.text((tile + 8, 4), "composite", fill="#1b2a22", font=font)
        for index, row in enumerate(pairs):
            top = 26 + index * tile
            for column, path in enumerate((row["source"], row["output"])):
                with Image.open(ROOT / path) as image:
                    thumb = image.convert("RGB")
                    thumb.thumbnail((tile - 8, tile - 8))
                sheet.paste(thumb, (column * tile + 4, top + 4))
        target = TY / "digest_composites_2026-11-08.png"
        sheet.save(target)
        return str(target.relative_to(ROOT))
    except Exception:  # noqa: BLE001 - a missing sheet must not break the digest
        return None


def _parity() -> Dict[str, Any]:
    flag = ROOT / "config" / "chromeconnect_quarantine.json"
    runs = sorted(TY.glob("d8_parity_run*.json"))
    passes = 0
    for path in runs:
        try:
            if (json.loads(path.read_text(encoding="utf-8")).get("comparison") or {}).get("ok"):
                passes += 1
        except ValueError:
            continue
    return {"runs": len(runs), "passes": passes,
            "quarantined": flag.exists(),
            "six_point": [p.name for p in sorted(TY.glob("d8_sixpoint_run*.json"))]}


def _count(data: Any, key: str) -> int:
    """Count a list of records whether it is a bare list or wrapped in a key.

    `ty/seller_gaps.json` is a bare list; `ty/intel_gaps.json` is `{"findings": [...]}`.
    Reading only the wrapped shape reported 0 for a 29-item list (found by the D15 verifier).
    """
    if isinstance(data, list):
        return len(data)
    if isinstance(data, dict):
        value = data.get(key)
        if isinstance(value, list):
            return len(value)
    return 0


def _registry() -> Dict[str, Any]:
    """What the service registry says, in one block: coverage, controls, tools, layouts."""
    data = _read_json(TY_DIR / "service_registry.json")
    rows = data.get("services") if isinstance(data, dict) else None
    if not rows:
        return {}
    tools = _read_json(TY_DIR / "bojo_tool_list.json") or {}
    workspaces = _read_json(TY_DIR / "northstar_workspaces.json") or {}
    gaps = _read_json(TY_DIR / "registry_gaps.json") or {}
    vision: Dict[str, int] = {}
    confidence: Dict[str, int] = {}
    for row in rows:
        evidence = row.get("evidence") or {}
        kind = str(evidence.get("vision") or "unknown")
        vision[kind] = vision.get(kind, 0) + 1
        level = str(evidence.get("confidence") or "unknown")
        confidence[level] = confidence.get(level, 0) + 1
    specs = workspaces.get("workspaces") if isinstance(workspaces, dict) else None
    if isinstance(specs, dict):
        specs = list(specs.values())
    layouts: Dict[str, int] = {}
    for spec in specs or []:
        layout = str((spec or {}).get("layout") or "?")
        layouts[layout] = layouts.get(layout, 0) + 1
    gap_rows = gaps.get("gaps") if isinstance(gaps, dict) else gaps
    owned = tools.get("tools") if isinstance(tools, dict) else None
    return {"services": len(rows),
            "with_controls": sum(1 for row in rows if row.get("has_controls")),
            "vision": vision,
            "confidence": confidence,
            "tools": {"owned": len(owned or []),
                      "wired": (tools.get("wired") if isinstance(tools, dict) else None)},
            "layouts": layouts,
            "gaps": len(gap_rows or [])}


def collect(*, path: Optional[Path] = None) -> Dict[str, Any]:
    """Everything the digest needs, as data. Missing files are reported, not invented."""
    queue = _read_json(QUEUE)
    scores = _read_json(SCORES)
    rows = [row for row in scores.get("services") or [] if isinstance(row, dict)]
    below = [row for row in rows if not row.get("meets_bar")]
    below.sort(key=lambda row: -float(row.get("gap") or 0))
    gaps = _read_json(TY_DIR / "seller_gaps.json")
    intel = _read_json(TY_DIR / "intel_gaps.json")
    models = _read_json(TY_DIR / "model_leaderboard.json")
    verifier = _read_json(TY / "verifier_findings.json")
    needs = (TY / "needs_you.md")
    return {
        "date": date.today().isoformat(),
        "disk": allow_download(path=path),
        "units": {name: (row.get("status") if isinstance(row, dict) else row)
                  for name, row in (queue.get("units") or {}).items()},
        "in_flight": queue.get("unit_in_flight", ""),
        "services": {"total": len(rows), "below_bar": len(below), "at_bar": len(rows) - len(below),
                     "top_gaps": [{"id": row.get("id"), "gap": row.get("gap"),
                                   "weakest": row.get("weakest")} for row in below[:5]]},
        "jobs": _jobs(),
        "parity": _parity(),
        "seller_gaps": _count(gaps, "gaps"),
        "intel_findings": _count(intel, "findings"),
        "model_roles": len((models.get("roles") or {})) if isinstance(models, dict) else 0,
        "composites": _composites(),
        "composite_sheet": _contact_sheet(_composites()),
        "registry": _registry(),
        "verifier_failed": (verifier.get("failed") or [])[:10] if isinstance(verifier, dict) else [],
        "verifier_blocked": (verifier.get("blocked") or [])[:10] if isinstance(verifier, dict) else [],
        "needs_you_open": (len([line for line in needs.read_text(encoding="utf-8").splitlines()
                                if line.startswith("## ")])
                           if needs.exists() else 0),
    }


def render(data: Dict[str, Any]) -> str:
    disk = data["disk"]
    lines: List[str] = [
        f"# Ty digest — {data['date']}", "",
        f"**Disk free:** {disk['free_gb']} GB (floor {disk['floor_gb']} GB — "
        f"{'ok' if disk['allow'] else 'BELOW FLOOR, work that consumes disk is refused'})", "",
        f"**Unit in flight:** {data['in_flight'] or '(none)'}", "",
        "| unit | status |", "|---|---|",
    ]
    for name, status in sorted(data["units"].items()):
        lines.append(f"| {name} | {status} |")
    services = data["services"]
    lines += ["", "## Services", "",
              f"{services['total']} scored, {services['below_bar']} below the bar, "
              f"{services['at_bar']} at it.", ""]
    if services["top_gaps"]:
        lines += ["| service | gap | weakest |", "|---|---|---|"]
        for row in services["top_gaps"]:
            lines.append(f"| {row['id']} | {row['gap']} | {row['weakest']} |")
    parity = data["parity"]
    lines += ["", "## Chrome Connect parity", "",
              f"{parity['runs']} suite run(s), {parity['passes']} passing; "
              f"quarantined: {parity['quarantined']}; "
              f"six-point evidence files: {len(parity['six_point'])}", ""]
    failed = data.get("verifier_failed") or []
    blocked = data.get("verifier_blocked") or []
    registry = data.get("registry") or {}
    if registry:
        lines += ["## Service registry (single source of truth)", ""]
        lines.append(f"{registry['services']} services, {registry['with_controls']} with controls, "
                     f"{registry.get('gaps', 0)} gaps recorded.")
        lines.append("")
        vision = registry.get("vision") or {}
        if vision:
            lines.append("- evidence: " + ", ".join(f"{k} {v}" for k, v in sorted(vision.items())))
        confidence = registry.get("confidence") or {}
        if confidence:
            lines.append("- confidence: " + ", ".join(
                f"{k} {v}" for k, v in sorted(confidence.items(), key=lambda kv: -kv[1])))
        layouts = registry.get("layouts") or {}
        if layouts:
            lines.append("- default-view layouts: " + ", ".join(
                f"{k} {v}" for k, v in sorted(layouts.items(), key=lambda kv: -kv[1])))
        tools = registry.get("tools") or {}
        if tools:
            lines.append(f"- Bojo tools owned by a service: {tools.get('owned')}")
        lines.append("")

    lines += ["## Mogra composites — source next to output", ""]
    composites = data.get("composites") or []
    if composites:
        lines += ["| brief | source | output | route | fidelity | score | product region |",
                  "|---|---|---|---|---|---|---|"]
        for row in composites:
            lines.append(
                f"| {row['brief_id']} | `{row['source']}` | `{row['output']}` | "
                f"{row.get('route', '')} | {row['fidelity']} | "
                f"{row.get('score', '—')}"
                + (f" (provisional {row.get('provisional_score')})"
                   if row.get("provisional") else "")
                + " | " + str(row.get("region_state", "not audited")) + " |")
        if data.get("composite_sheet"):
            lines += ["", f"Side by side (source left, composite right): "
                          f"`{data['composite_sheet']}`"]
    else:
        lines.append("None produced yet: no composite outputs on disk. `sel-01b` is the job "
                     "that produces them.")
    lines += [""]

    lines += ["## Verifier FAILED items", ""]
    if failed:
        lines += ["| unit | item | why | state now |", "|---|---|---|---|"]
        for row in failed:
            lines.append(f"| {row.get('unit', '?')} | {row.get('item', '')} | "
                         f"{row.get('why', '')} | {row.get('state_now', '')} |")
    else:
        lines.append("None recorded.")
    if blocked:
        lines += ["", "### Blocked, not failed", ""]
        for row in blocked:
            lines.append(f"- **{row.get('unit', '?')}** {row.get('item', '')} — "
                         f"{row.get('why', '')} ({row.get('state_now', '')})")
    lines += [""]
    lines += ["## Lanes", "",
              f"- Seller-Tester gaps filed: {data['seller_gaps']}",
              f"- Intel findings: {data['intel_findings']}",
              f"- Model roles on the leaderboard: {data['model_roles']}",
              f"- Open `needs_you` sections: {data['needs_you_open']}", ""]
    jobs = data["jobs"]
    if jobs:
        lines += ["## Jobs", "",
                  f"{jobs.get('total', 0)} total: "
                  + ", ".join(f"{key}={value}" for key, value in
                              sorted((jobs.get("by_status") or {}).items())), ""]
    return "\n".join(lines) + "\n"


def write(*, path: Optional[Path] = None, out: Optional[Path] = None) -> Dict[str, Any]:
    data = collect(path=path)
    target = Path(out) if out else TY / f"digest_{data['date']}.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(render(data), encoding="utf-8")
    return {"ok": True, "path": str(target), "disk_free_gb": data["disk"]["free_gb"]}


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Ty digest and disk floor")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--json", action="store_true")
    ns = parser.parse_args(argv)
    if ns.write:
        print(json.dumps(write(), indent=2))
        return 0
    print(json.dumps(collect(), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
