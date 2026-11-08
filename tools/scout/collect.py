"""Discovery orchestrator + CLI (D11 / A18–A21).

    python -m tools.scout.collect --dry-run           # fixtures only, writes nothing
    python -m tools.scout.collect --live              # real APIs, writes ty/intel_gaps.json
    python -m tools.scout.collect --record-fixtures   # refresh tools/scout/fixtures/

Live run order: plan -> search -> normalise -> dedupe -> vet -> evidence ->
rank -> status -> verify URLs -> atomic write.  A source that fails is recorded
in the run health and the rest continue; a failure is never an empty success.

The tracked file is ``ty/intel_gaps.json`` because ``state/`` is gitignored in
this repo; ``state/intel/gaps.json`` is written as the runtime mirror.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from . import config, connectors, evidence, normalize, rank, vet, verify
from .http import Refused, ScoutTransport
from .licence import classify

SCHEMA = "northstar.intel_gaps/1"
_SLUG = re.compile(r"[^a-z0-9]+")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _slug(text: str) -> str:
    return _SLUG.sub("-", str(text).lower()).strip("-")[:60]


# ------------------------------------------------------------------- refusals
def log_refusal(rule_id: str, *, source: str = "", url: str = "",
                detail: str = "", path: Optional[Path] = None) -> Dict[str, Any]:
    """Append one refusal.  The rule id vocabulary is closed (A18 decision 1)."""
    if rule_id not in config.REFUSAL_RULES:
        raise ValueError(f"unknown_rule_id: {rule_id!r}")
    row = {"at": _now(), "rule_id": rule_id, "source": source, "url": url,
           "detail": str(detail)[:300],
           "rule": config.REFUSAL_RULES[rule_id]}
    target = Path(path or config.REFUSALS_PATH)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    return row


# ---------------------------------------------------------------------- write
def write_atomic(path: Path, payload: Dict[str, Any]) -> Path:
    """Write JSON via a sibling temp file + ``os.replace``.  No partial file."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temp_name = tempfile.mkstemp(dir=str(path.parent),
                                        prefix=path.name + ".", suffix=".tmp")
    try:
        with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as stream:
            json.dump(payload, stream, indent=2, ensure_ascii=False)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp_name, path)
    finally:
        if os.path.exists(temp_name):
            try:
                os.unlink(temp_name)
            except OSError:
                pass
    return path


# -------------------------------------------------------------------- fixtures
def fixtures_dir() -> Path:
    return config.FIXTURES


def load_fixtures(directory: Optional[Path] = None) -> List[Dict[str, Any]]:
    folder = Path(directory or fixtures_dir())
    if not folder.is_dir():
        return []
    out = []
    for path in sorted(folder.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if data.get("source") and "payload" in data:
            data["_fixture"] = path.name
            out.append(data)
    return out


def record_fixtures(*, limit: int = 3, directory: Optional[Path] = None,
                    plan: Optional[List[Dict[str, str]]] = None) -> Dict[str, Any]:
    """Record real payloads (trimmed) so tests can replay them offline."""
    folder = Path(directory or fixtures_dir())
    folder.mkdir(parents=True, exist_ok=True)
    recorded: List[str] = []
    failed: List[Dict[str, str]] = []
    for row in plan or config.QUERY_PLAN:
        name = str(row["source"])
        if not config.SOURCES.get(name, {}).get("enabled", False):
            continue
        try:
            payload = connectors.get(name).record(str(row["query"]), limit)
        except (ScoutTransport, Refused) as exc:
            failed.append({"source": name, "query": str(row["query"]), "error": str(exc)})
            continue
        target = folder / f"{name}_{_slug(str(row['query']))}.json"
        target.write_text(json.dumps(payload, indent=1, ensure_ascii=False) + "\n",
                          encoding="utf-8")
        recorded.append(target.name)
        time.sleep(0.2)
    return {"recorded": recorded, "failed": failed}


# ------------------------------------------------------------------------ run
def _apply_vet(finding: Dict[str, Any], *, do_vet: bool, dry_run: bool) -> Dict[str, Any]:
    if dry_run:
        finding["vet"] = ({"checked": False, "verdict": "not_checked"}
                          if finding.get("ecosystem") else
                          {"checked": False, "verdict": "not_applicable"})
        return finding
    if not do_vet:
        finding["vet"] = {"checked": False, "verdict": "not_checked"}
        return finding
    finding["vet"] = vet.vet_hit(finding)
    return finding


def _finding_out(finding: Dict[str, Any]) -> Dict[str, Any]:
    description = evidence.excerpt(finding.get("description"), 140)
    what = str(finding.get("title") or "")
    if description:
        what = f"{what} — {description}"
    out = {
        "id": finding.get("id"),
        "what": what,
        "where": finding.get("url"),
        "title": finding.get("title"),
        "licence": finding.get("licence"),
        "licence_class": finding.get("licence_class"),
        "service": finding.get("service"),
        "service_label": finding.get("service_label"),
        "estimated_lift": finding.get("estimated_lift"),
        "lift_basis": finding.get("lift_basis"),
        "evidence": finding.get("evidence"),
        "source": finding.get("source"),
        "fetched_at": finding.get("fetched_at"),
        "status": finding.get("status"),
        "adopt_eligible": finding.get("adopt_eligible"),
        "relevance": finding.get("relevance"),
        "score": finding.get("score"),
        "rank": finding.get("rank"),
        "stars": finding.get("stars"),
        "downloads": finding.get("downloads"),
        "version": finding.get("version"),
        "kind": finding.get("kind"),
        "vet": finding.get("vet"),
        "url_status": finding.get("url_status"),
        "url_ok": finding.get("url_ok"),
        "verified_via": finding.get("verified_via"),
        "verified_via_url": finding.get("verified_via_url"),
        "verified_via_status": finding.get("verified_via_status"),
        "verified_at": finding.get("verified_at"),
        "identity": finding.get("identity"),
        "content_sha256": finding.get("content_sha256"),
        "revisions": finding.get("revisions"),
        "matched_terms": finding.get("matched_terms"),
    }
    return out


def run(*, dry_run: bool = True, limit: int = 5, max_findings: int = 60,
        do_vet: bool = True, do_verify: bool = True,
        out_path: Optional[Path] = None, mirror_path: Optional[Path] = None,
        services_path: Optional[Path] = None,
        fixtures: Optional[Path] = None,
        plan: Optional[List[Dict[str, str]]] = None,
        sleep: float = 0.0) -> Dict[str, Any]:
    """One discovery run.  Returns the document it wrote (or would have)."""
    started = time.time()
    services = config.load_services(services_path)
    gaps = config.load_gaps()
    plan_rows = list(plan or config.QUERY_PLAN)
    hints_by_query = {str(row["query"]): str(row.get("service_hint") or "")
                      for row in plan_rows}
    health: Dict[str, Dict[str, Any]] = {
        name: {"queries": 0, "failed_queries": 0, "raw_hits": 0, "ok": True,
               "error": None, "quota_remaining": None, "duration_s": 0.0}
        for name in config.SOURCES
    }
    raw: List[Dict[str, Any]] = []
    queries_run = 0

    if dry_run:
        fixtures_used: List[str] = []
        for fixture in load_fixtures(fixtures):
            source = str(fixture.get("source"))
            if source not in config.SOURCES or not config.SOURCES[source]["enabled"]:
                log_refusal("source_disabled", source=source,
                            detail=str(fixture.get("_fixture")))
                continue
            query = str(fixture.get("query") or "")
            try:
                hits = connectors.get(source).parse(fixture.get("payload"), query=query)
            except (ScoutTransport, Refused, ValueError) as exc:
                health[source]["ok"] = False
                health[source]["error"] = str(exc)
                continue
            health[source]["queries"] += 1
            health[source]["raw_hits"] += len(hits)
            queries_run += 1
            fixtures_used.append(str(fixture.get("_fixture")))
            for hit in hits:
                hit["_service_hint"] = hints_by_query.get(query, "")
            raw.extend(hits)
        fixtures_used = sorted(set(fixtures_used))
    else:
        fixtures_used = []
        stopped: Dict[str, str] = {}
        for row in plan_rows:
            source = str(row["source"])
            meta = config.SOURCES.get(source)
            if not meta or not meta.get("enabled"):
                log_refusal("source_disabled", source=source, detail=str(row["query"]))
                continue
            if source in stopped:
                continue
            query = str(row["query"])
            began = time.time()
            health[source]["queries"] += 1
            try:
                hits = connectors.get(source).search(query, limit)
            except (ScoutTransport, Refused) as exc:
                health[source]["ok"] = False
                health[source]["failed_queries"] = health[source].get("failed_queries", 0) + 1
                health[source]["error"] = health[source].get("error") or f"{type(exc).__name__}: {exc}"
                status = getattr(exc, "status", None)
                if isinstance(exc, Refused):
                    log_refusal("amazon_host_blocked" if "amazon" in str(exc).lower()
                                else "not_absolute_url", source=source, detail=str(exc))
                if status in (401, 403, 429) or isinstance(exc, Refused):
                    # Quota/abuse refusal: stop asking this source this run.  The
                    # failure is recorded; it is never converted into an empty success.
                    stopped[source] = str(exc)
                health[source]["duration_s"] = round(
                    health[source]["duration_s"] + time.time() - began, 2)
                continue
            health[source]["raw_hits"] += len(hits)
            health[source]["duration_s"] = round(
                health[source]["duration_s"] + time.time() - began, 2)
            payload = getattr(connectors.get(source), "last_payload", None) or {}
            quota = payload.get("quota_remaining") if isinstance(payload, dict) else None
            if quota is not None:
                health[source]["quota_remaining"] = quota
            queries_run += 1
            for hit in hits:
                hit["_service_hint"] = str(row.get("service_hint") or "")
            raw.extend(hits)
            time.sleep(max(float(sleep or 0.0), config.PACE.get(source, 0.3)))

    unique, dedupe_report = normalize.dedupe(raw)
    for finding in unique:
        _apply_vet(finding, do_vet=do_vet, dry_run=dry_run)
        finding["evidence"] = evidence.build(finding)

    ranked, dropped = rank.rank(
        unique, services, gaps=gaps,
        hints={},
    )
    for finding in ranked:
        finding["status"] = vet.decide_status(
            licence=str(finding.get("licence")),
            licence_class=str(finding.get("licence_class")),
            vet=finding.get("vet"),
            relevance=float(finding.get("relevance") or 0.0),
            kind=str(finding.get("kind") or "item"))
        finding["adopt_eligible"] = vet.adopt_eligible(finding["status"])
        finding.pop("_service_hint", None)

    selected = ranked[:max(1, int(max_findings))]
    verified = 0
    verified_ok = 0
    verified_direct = 0
    verified_via_api = 0
    if not dry_run and do_verify:
        memo: Dict[str, Dict[str, Any]] = {}
        for finding in selected:
            result = verify.verify_finding(finding, memo=memo)
            finding["url_status"] = result.get("status")
            finding["url_ok"] = bool(result.get("ok"))
            finding["verified_at"] = _now()
            finding["verified_via"] = result.get("via")
            finding["verified_via_url"] = result.get("via_url")
            finding["verified_via_status"] = result.get("via_status")
            verified += 1
            verified_direct += 1 if result.get("direct_ok") else 0
            verified_via_api += 1 if result.get("via") == "api" else 0
            if result.get("ok"):
                verified_ok += 1
            else:
                log_refusal("url_unverified", source=str(finding.get("source")),
                            url=str(finding.get("url")),
                            detail=str(result.get("direct_error")
                                       or result.get("via_status")
                                       or result.get("status")))
            time.sleep(0.15)
    else:
        for finding in selected:
            finding["url_status"] = None
            finding["url_ok"] = None
            finding["verified_at"] = None
            finding["verified_via"] = None

    findings_out = [_finding_out(finding) for finding in selected]
    gap_rows = rank.gaps_from(selected, services)
    off_domain_dropped = sum(1 for finding in dropped
                             if str(finding.get("drop_reason") or "").startswith("off_domain"))
    doc = {
        "schema": SCHEMA,
        "generated_at": _now(),
        "run": {
            "dry_run": bool(dry_run),
            "queries": queries_run,
            "raw_hits": len(raw),
            "unique": len(unique),
            "findings": len(findings_out),
            "dropped_offtopic": len(dropped) - off_domain_dropped,
            "dropped_off_domain": off_domain_dropped,
            "duplicates": dedupe_report["duplicates"],
            "revisions": dedupe_report["revisions"],
            "verified": verified,
            "verified_ok": verified_ok,
            "verified_direct": verified_direct,
            "verified_via_api": verified_via_api,
            "duration_s": round(time.time() - started, 2),
            "fixtures": fixtures_used,
        },
        "sources": health,
        "findings": findings_out,
        "gaps": gap_rows,
    }
    written: List[str] = []
    if not dry_run:
        written.append(str(write_atomic(Path(out_path or config.GAPS_PATH), doc)))
        mirror = Path(mirror_path or config.MIRROR_PATH)
        if str(mirror) != str(Path(out_path or config.GAPS_PATH)):
            written.append(str(write_atomic(mirror, doc)))
    doc["run"]["written"] = written
    return doc


# ------------------------------------------------------------------------ CLI
def _print_human(doc: Dict[str, Any], top: int) -> None:
    run_info = doc.get("run") or {}
    mode = "DRY RUN (fixtures)" if run_info.get("dry_run") else "LIVE"
    print(f"scout intel — {mode}")
    print(f"  queries={run_info.get('queries')} raw={run_info.get('raw_hits')} "
          f"unique={run_info.get('unique')} findings={run_info.get('findings')} "
          f"duplicates={run_info.get('duplicates')} revisions={run_info.get('revisions')} "
          f"offtopic={run_info.get('dropped_offtopic')} "
          f"off_domain={run_info.get('dropped_off_domain')}")
    print(f"  urls verified={run_info.get('verified')} ok={run_info.get('verified_ok')} "
          f"direct={run_info.get('verified_direct')} "
          f"via_api={run_info.get('verified_via_api')} "
          f"duration={run_info.get('duration_s')}s")
    for name, row in (doc.get("sources") or {}).items():
        state = "ok" if row.get("ok") else "FAILED"
        print(f"  source {name}: {state} queries={row.get('queries')} "
              f"hits={row.get('raw_hits')} quota={row.get('quota_remaining')}"
              + (f" error={row.get('error')}" if row.get("error") else ""))
    print(f"\n  top {top}:")
    for finding in (doc.get("findings") or [])[:top]:
        title = str(finding.get("title") or "")[:58]
        safe = title.encode("ascii", "replace").decode("ascii")
        print(f"   {str(finding.get('rank')):>3}. {finding.get('service'):<18} "
              f"lift={finding.get('estimated_lift'):>5} "
              f"lic={str(finding.get('licence'))[:14]:<14} "
              f"{finding.get('source'):<11} {finding.get('status'):<13} {safe}")
    if run_info.get("written"):
        print("\n  written: " + ", ".join(run_info["written"]))


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Northstar discovery lane (D11).")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true",
                      help="replay recorded fixtures; writes nothing (default)")
    mode.add_argument("--live", action="store_true", help="call the public APIs")
    mode.add_argument("--record-fixtures", action="store_true",
                      help="refresh tools/scout/fixtures/ from live APIs")
    parser.add_argument("--limit", type=int, default=5, help="hits per query")
    parser.add_argument("--max-findings", type=int, default=60)
    parser.add_argument("--no-vet", action="store_true", help="skip OSV (not recommended)")
    parser.add_argument("--no-verify", action="store_true", help="skip URL resolution checks")
    parser.add_argument("--top", type=int, default=10)
    parser.add_argument("--json", action="store_true", help="print the whole document")
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--mirror", type=Path, default=None)
    parser.add_argument("--fixtures", type=Path, default=None)
    parser.add_argument("--fixture-limit", type=int, default=3)
    args = parser.parse_args(argv)

    try:
        if args.record_fixtures:
            result = record_fixtures(limit=args.fixture_limit, directory=args.fixtures)
            print(json.dumps(result, indent=2, ensure_ascii=True))
            return 0 if result["recorded"] else 2
        live = bool(args.live)
        doc = run(dry_run=not live, limit=args.limit,
                  max_findings=args.max_findings, do_vet=not args.no_vet,
                  do_verify=not args.no_verify, out_path=args.out,
                  mirror_path=args.mirror, fixtures=args.fixtures)
    except Refused as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        return 1
    except ScoutTransport as exc:
        print(f"TRANSPORT FAILURE (not a result): {exc}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(doc, indent=2, ensure_ascii=True))
    else:
        _print_human(doc, args.top)
    return 0 if doc["run"]["findings"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
