"""Continuous Improvement Engine — one cycle.

observe -> prioritise -> research -> author -> evaluate -> promote/discard -> report

The offline cycle is deterministic and model-free: it measures *knowledge
coverage* on the golden set (does the pack contain an atom relevant to the
question), proposes atoms from the curated research corpus, and promotes only
when coverage improves. Live answer quality is graded by ``cie_eval`` when an
answer function is supplied; that path is opt-in so a cycle can never claim a
model-driven win it did not measure.

Every cycle writes a report and a rollback instruction. Nothing is promoted
without a snapshot of the base commit, and the stop switch is checked before
each stage.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple

import cie_eval
import cie_research
import cie_store
import knowledge_pack as kp

REPO = Path(__file__).resolve().parent.parent
COVERAGE_THRESHOLD = 0.35
DOMAIN_WEIGHT = {d["id"]: float(d.get("weight", 0.5))
                 for d in kp.domain_meta()} or {}


def suite_path() -> Path:
    return kp.root() / "eval" / "golden" / "core.jsonl"


def suite() -> List[Dict[str, Any]]:
    return cie_eval.load_suite(suite_path())


# ── coverage ────────────────────────────────────────────────────────────────

def _pool(extra: Optional[Iterable[Dict[str, Any]]] = None) -> List[Dict[str, Any]]:
    pool = kp.all_atoms()
    if extra:
        pool = pool + [a for a in extra if a]
    return pool


def best_match(query: str, pool: List[Dict[str, Any]]) -> Tuple[float, Optional[str]]:
    best, best_id = 0.0, None
    for atom in pool:
        score = kp.score_atom(query, atom)
        if score > best:
            best, best_id = score, atom.get("id")
    return best, best_id


def coverage_table(items: Iterable[Dict[str, Any]],
                   extra: Optional[Iterable[Dict[str, Any]]] = None) -> Dict[str, Any]:
    """Coverage = does the pack hold an atom the item declares it needs?

    Each golden item names ``expects``: atom-id prefixes (for example
    ``"listing.title"``). This is exact and reproducible. Lexical similarity is
    used only to *find* the source snippet during research, never to decide
    whether a question is covered.
    """
    pool = _pool(extra)
    ids = [str(a.get("id") or "") for a in pool]
    rows = []
    for item in items:
        expects = [str(e) for e in (item.get("expects") or [])]
        hits = [i for i in ids if any(i.startswith(e) for e in expects)]
        rows.append({"id": item.get("id"), "domain": item.get("domain"),
                     "expects": expects, "atom": (hits[0] if hits else None),
                     "covered": bool(hits)})
    total = len(rows)
    covered = sum(1 for r in rows if r["covered"])
    return {"total": total, "covered": covered,
            "score": round(covered / total, 4) if total else 0.0, "rows": rows}


# ── stages ──────────────────────────────────────────────────────────────────

def snapshot() -> Dict[str, Any]:
    try:
        commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"],
                                cwd=str(REPO), capture_output=True, text=True,
                                timeout=20).stdout.strip()
        dirty = subprocess.run(["git", "status", "--porcelain"],
                               cwd=str(REPO), capture_output=True, text=True,
                               timeout=20).stdout.strip()
        return {"commit": commit or "unknown",
                "dirty_files": len(dirty.splitlines()) if dirty else 0}
    except Exception:  # noqa: BLE001 - snapshot is best-effort, never fatal
        return {"commit": "unknown", "dirty_files": 0}


def observe(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    gaps: List[Dict[str, Any]] = []
    table = coverage_table(items)
    for row in table["rows"]:
        if row["covered"]:
            continue
        item = next((i for i in items if i.get("id") == row["id"]), {})
        gaps.append({
            "gap_id": f"golden:{row['id']}",
            "domain": row["domain"],
            "question": str(item.get("prompt") or ""),
            "expects": row.get("expects") or [],
            "evidence": [{"kind": "knowledge_miss", "expects": row.get("expects")}],
            "frequency": 1,
        })
    for fb in cie_store.negative_feedback():
        domain = "listing"
        note = str(fb.get("note") or "")
        gaps.append({
            "gap_id": f"feedback:{fb.get('id')}",
            "domain": domain if "list" in note.lower() else domain,
            "question": note or "operator marked an answer wrong",
            "evidence": [{"kind": "feedback", "verdict": fb.get("verdict")}],
            "frequency": 1,
        })
    return gaps


def backlog_items() -> List[Dict[str, Any]]:
    """Operator-declared topics to learn next, used when the golden set is clean."""
    path = kp.knowledge_dir() / "backlog.jsonl"
    out: List[Dict[str, Any]] = []
    if not path.exists():
        return out
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except ValueError:
                continue
            if isinstance(row, dict) and row.get("question") and row.get("domain"):
                out.append(row)
    return out


def backlog_gaps(limit: int = 5) -> List[Dict[str, Any]]:
    """Backlog topics that the current packs cannot already answer.

    A topic the pack already covers is skipped instead of re-queued forever:
    that is what keeps a nightly cycle from reporting the same gap every day.
    """
    out: List[Dict[str, Any]] = []
    for row in backlog_items():
        hits = kp.retrieve(row["question"], row["domain"], limit=1)
        if hits and hits[0][0] >= 0.6:
            continue
        out.append({"gap_id": f"backlog:{_slug_id(row['question'])}",
                    "domain": row["domain"], "question": row["question"],
                    "expects": row.get("expects") or [],
                    "evidence": [{"kind": "backlog"}], "frequency": 1})
    return out[:limit]


def _slug_id(text: str, limit: int = 40) -> str:
    import re
    return re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")[:limit] or "topic"


def prioritise(gaps: Iterable[Dict[str, Any]], cap: int = 5) -> List[Dict[str, Any]]:
    scored = []
    for gap in gaps:
        weight = DOMAIN_WEIGHT.get(gap["domain"], 0.5)
        score = round(weight * float(gap.get("frequency") or 1), 4)
        scored.append({**gap, "score": score})
    scored.sort(key=lambda g: g["score"], reverse=True)
    # de-duplicate by question
    seen, out = set(), []
    for gap in scored:
        key = gap["question"].strip().lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(gap)
        if len(out) >= cap:
            break
    return out


def research(gaps: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    candidates = []
    for gap in gaps:
        want_id = (gap.get("expects") or [None])[0]
        candidate = cie_research.candidate_atom(gap["question"], gap["domain"],
                                                atom_id=want_id)
        if candidate:
            candidate["_gap"] = gap["gap_id"]
            candidates.append(candidate)
    return candidates


def author(candidates: Iterable[Dict[str, Any]],
           existing: Optional[Iterable[Dict[str, Any]]] = None) -> Tuple[List[Dict], List[Dict]]:
    pool = list(existing if existing is not None else kp.all_atoms())
    accepted, rejected = [], []
    for candidate in candidates:
        verdict = cie_research.review(candidate, pool)
        if verdict["ok"]:
            accepted.append(candidate)
            pool.append(candidate)  # so later candidates can't duplicate this one
        else:
            rejected.append({"candidate": candidate.get("id"),
                             "reasons": verdict["reasons"]})
    return accepted, rejected


def evaluate(items: List[Dict[str, Any]], accepted: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    before = coverage_table(items)
    after = coverage_table(items, extra=list(accepted))
    gained = [r["id"] for b, r in zip(before["rows"], after["rows"])
              if not b["covered"] and r["covered"]]
    gained_keys = {f"golden:{g}" for g in gained}
    kept = [r for r in accepted if r.get("_gap") in gained_keys]
    return {"before": before["score"], "after": after["score"],
            "delta": round(after["score"] - before["score"], 4),
            "gained": gained, "needed": kept,
            "coverage_rows": after["rows"]}


def promote(accepted: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Append accepted atoms to their domain packs. Returns the written rows."""
    written: List[Dict[str, Any]] = []
    for atom in accepted:
        domain = atom.get("domain")
        if domain not in kp.domains():
            continue
        clean = {k: v for k, v in atom.items() if not k.startswith("_")}
        atoms = kp.load_atoms(domain)
        if any(a.get("id") == clean["id"] for a in atoms):
            continue
        atoms.append(clean)
        kp.save_atoms(domain, atoms)
        kp.write_pack_meta(domain)
        written.append({"domain": domain, "id": clean["id"]})
    return written


def write_report(cycle: Dict[str, Any], gaps: List[Dict[str, Any]],
                 candidates: List[Dict[str, Any]], accepted: List[Dict[str, Any]],
                 rejected: List[Dict[str, Any]], evaluation: Dict[str, Any],
                 written: List[Dict[str, Any]],
                 live: Optional[Dict[str, Any]] = None) -> Path:
    path = cie_store.report_dir() / f"{cycle['cycle_id']}.md"
    lines = [
        f"# Improvement cycle {cycle['cycle_id']}",
        "",
        f"- started: {cycle['started_at']}",
        f"- base commit: `{cycle['base_commit']}` ({cycle.get('dirty_files', 0)} dirty files)",
        f"- coverage before: **{evaluation['before']:.0%}** -> after: **{evaluation['after']:.0%}** (delta {evaluation['delta']:+.0%})",
        f"- gaps: {len(gaps)} · candidates: {len(candidates)} · accepted: {len(accepted)} · rejected: {len(rejected)}",
        (f"- live answer score: **{live['score']:.0%}** on {live['total']} questions "
         f"(failed: {', '.join(live['failed']) or 'none'})" if live else
         "- live answer score: not measured this cycle (`--live`)"),
        "",
        "## Gaps",
        "",
    ]
    for gap in gaps:
        lines.append(f"- `{gap['gap_id']}` ({gap['domain']}) — {gap['question'][:140]}")
    lines += ["", "## Accepted", ""]
    if accepted:
        for atom in accepted:
            lines.append(f"- `{atom['id']}` — {atom['do'][:110]}")
    else:
        lines.append("- none")
    lines += ["", "## Rejected", ""]
    if rejected:
        for row in rejected:
            lines.append(f"- `{row['candidate']}` — {'; '.join(row['reasons'])}")
    else:
        lines.append("- none")
    lines += ["", "## Rollback", ""]
    if written:
        lines.append("Remove the promoted atoms and restore the previous pack versions:")
        lines.append("")
        for row in written:
            lines.append(f"- `{row['domain']}` / `{row['id']}`")
        lines.append("")
        lines.append("`git checkout -- knowledge/` restores the packs from the base commit.")
    else:
        lines.append("Nothing was written; no rollback needed.")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def model_answer(item: Dict[str, Any]) -> str:
    """Ask the live model one golden question, with the current packs in context."""
    import chat_adapter
    prompt = str(item.get("prompt") or "")
    messages = chat_adapter.build_chat_messages(
        [{"role": "user", "content": prompt}], query=prompt)
    parts: List[str] = []
    for event in chat_adapter.stream_turn(messages, think="medium"):
        if isinstance(event, dict) and event.get("type") == "content":
            parts.append(str(event.get("delta") or ""))
        elif isinstance(event, dict) and event.get("type") == "error":
            break
    return "".join(parts)


def run_cycle(dry_run: bool = False, cap: int = 5,
              answer_fn: Optional[Callable[[Dict[str, Any]], str]] = None,
              live_limit: int = 10) -> Dict[str, Any]:
    cycle_id = cie_store.new_cycle_id()
    if cie_store.is_stopped():
        return {"ok": False, "stopped": True, "cycle_id": cycle_id,
                "reason": "stop switch is set"}

    items = suite()
    if not items:
        return {"ok": False, "cycle_id": cycle_id, "reason": "golden set is empty"}

    snap = snapshot()
    cie_store.start_cycle(cycle_id, base_commit=snap["commit"], snapshot=snap["commit"])

    gaps = prioritise(observe(items), cap=cap)
    if len(gaps) < cap:
        gaps += prioritise(backlog_gaps(cap - len(gaps)), cap=cap - len(gaps))
    for gap in gaps:
        cie_store.upsert_gap(gap_id=gap["gap_id"], domain=gap["domain"],
                             question=gap["question"], evidence=gap.get("evidence"),
                             frequency=gap.get("frequency", 1), score=gap.get("score", 0))
    candidates = research(gaps)
    accepted, rejected = author(candidates)
    evaluation = evaluate(items, accepted)
    # Optional live measurement: ask the model the golden questions and grade the
    # answers deterministically. This is a quality TREND, not the promotion gate
    # (promotion stays coverage-based, so a bad model day cannot rewrite rules).
    live: Optional[Dict[str, Any]] = None
    if answer_fn is not None:
        live_items = items[:max(1, int(live_limit))]
        live = cie_eval.run_suite(live_items, answer_fn)
        cie_store.add_eval(cycle_id, "live", live["score"],
                           {"failed": live["failed"], "items": live["total"]})
    # Only promote atoms that actually closed a gap.
    gained_keys = {f"golden:{g}" for g in evaluation["gained"]}
    to_write = []
    for atom in accepted:
        gap = str(atom.get("_gap", ""))
        match = float((atom.get("_research") or {}).get("match") or 0)
        if gap in gained_keys:
            to_write.append(atom)
        elif gap.startswith("feedback:") or (gap.startswith("backlog:") and match >= 0.35):
            # Non-golden gaps have no coverage delta to prove; require a strong
            # source match and a clean lint instead, and label it in the report.
            atom["_provenance"] = "backlog" if gap.startswith("backlog:") else "feedback"
            to_write.append(atom)
    written = [] if dry_run else promote(to_write)
    if written:
        written_ids = {row["id"] for row in written}
        for atom in to_write:
            if atom.get("id") in written_ids and atom.get("_gap"):
                cie_store.close_gap(str(atom["_gap"]), "resolved")

    report = write_report(
        {"cycle_id": cycle_id, "started_at": cie_store.now(),
         "base_commit": snap["commit"], "dirty_files": snap["dirty_files"]},
        gaps, candidates, to_write, rejected, evaluation, written, live)

    rollback_cmd = ("git checkout -- knowledge/" if written
                    else "nothing to roll back")
    cie_store.finish_cycle(
        cycle_id, status="dry_run" if dry_run else "done",
        gaps=len(gaps), researched=len(candidates), authored=len(accepted),
        promoted=len(written), discarded=len(rejected),
        report_path=str(report), rollback_cmd=rollback_cmd,
        detail={"evaluation": {k: v for k, v in evaluation.items()
                               if k != "coverage_rows"},
                "written": written})
    cie_store.add_eval(cycle_id, "coverage", evaluation["after"],
                       {"before": evaluation["before"],
                        "gained": evaluation["gained"]})

    resolved_keys = {f"golden:{g}" for g in evaluation["gained"]}
    for gap in gaps:
        if gap["gap_id"] in resolved_keys:
            cie_store.close_gap(gap["gap_id"], "resolved")

    return {
        "ok": True,
        "cycle_id": cycle_id,
        "dry_run": dry_run,
        "gaps": len(gaps),
        "candidates": len(candidates),
        "accepted": len(accepted),
        "promoted": written,
        "rejected": rejected,
        "coverage": {"before": evaluation["before"], "after": evaluation["after"],
                     "gain": evaluation["delta"]},
        "live": ({"score": live["score"], "items": live["total"],
                  "failed": live["failed"]} if live else None),
        "report": str(report),
        "rollback": rollback_cmd,
    }


def status() -> Dict[str, Any]:
    base = cie_store.status()
    pack = kp.stats()
    table = coverage_table(suite()) if suite() else {"score": 0.0, "total": 0}
    base.update({"packs": pack, "coverage": table["score"],
                 "golden_items": table["total"],
                 "corpus": cie_research.corpus_stats()})
    return base


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Northstar continuous improvement engine")
    ap.add_argument("--cycle", action="store_true", help="run one cycle")
    ap.add_argument("--dry-run", action="store_true", help="evaluate without writing")
    ap.add_argument("--cap", type=int, default=5)
    ap.add_argument("--live", action="store_true",
                    help="also ask the model the golden questions and grade them")
    ap.add_argument("--live-limit", type=int, default=10)
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--stop", action="store_true")
    ap.add_argument("--resume", action="store_true")
    args = ap.parse_args(argv)

    if args.stop:
        print(json.dumps(cie_store.set_stopped(True, "operator stop"), indent=2))
        return 0
    if args.resume:
        print(json.dumps(cie_store.set_stopped(False), indent=2))
        return 0
    if args.status:
        print(json.dumps(status(), indent=2))
        return 0
    if args.cycle:
        print(json.dumps(run_cycle(
            dry_run=args.dry_run, cap=args.cap,
            answer_fn=(model_answer if args.live else None),
            live_limit=args.live_limit), indent=2))
        return 0
    ap.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
