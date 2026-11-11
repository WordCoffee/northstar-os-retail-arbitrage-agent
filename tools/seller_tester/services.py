"""Seller-Tester beyond images: the four non-image service paths, exercised and scored.

A seller does not only buy pictures. Four of the services produce artefacts of a
different kind, and each has one path a seller actually walks:

* **listing** — product facts in, a listing revision proposal out, through
  `bojo_tools.publishing.compose_listing` -> `reasoning_tasks.listing_proposal`,
  the same function behind `POST /api/v1/reasoning/listing-proposal`. The model
  answer is a recorded fixture (a paid/cloud call is a gated action); every
  deterministic step the app applies — the 200 / 500 / 2000 character limits, the
  prohibited-phrase list, the copy audit, the provenance record — is the app's own,
  and is what a seller's listing is judged on.
* **ppc** — the bulksheet path end to end through the API: upload -> propose ->
  approve -> write a change file -> download. This is the route
  `Northstar_backend/test_amazon_files_primary_action.py` proves; the shape here is
  the same and the assertions are not weakened. Everything is local: the sheet is
  built in memory and the store is a sqlite file in this run's own directory. No
  Amazon host is contacted at any point.
* **golden_goose** — a product-discovery scan through `bojo_tools.sourcing.
  golden_goose_scan`, which runs the real fee stack (`calculate_breakdown_economics`)
  and the real scorer (`score_batch`). Candidates are fixture rows, not a crawl.
* **research** — a research query through `research_graph.research`: deconstruct ->
  traverse -> cross-validate -> synthesise, against a local corpus. The searcher is
  injected with the fixture corpus, so the graph's own counting (corroboration,
  single-source claims, numeric conflicts) is exercised with no network and no
  embedding model.

Each path returns a list of named checks, exactly like `packaging.py`: a check that
is skipped is reported as skipped and is not counted as a pass, a refusal is
recorded with the engine's own words, and the path score is the share of graded
checks that passed (0-100). Nothing is averaged across paths.

**Who owns which path.** A path is measured, not attributed: the fixture file's
`service_attribution` block names the one service whose declared code path
produces each artefact, and names *none* where no service does.
`tools/seller_scores.py` reads that block when it buckets the pass per service, so
a path cannot quietly lend its sample to a service that does not produce it.

    python -m tools.seller_tester services
    python -m tools.seller_tester services --only ppc,golden_goose
"""
from __future__ import annotations

import base64
import hashlib
import io
import json
import re
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_FIXTURES = Path(__file__).resolve().parent / "service_briefs.json"
DEFAULT_OUT = ROOT / "state" / "seller" / "services_proof.json"
DEFAULT_WORK_DIR = ROOT / "state" / "seller" / "services"

PATHS = ("listing", "ppc", "golden_goose", "research")

RECORDED_PROVIDER_NOTE = (
    "the model answer is a recorded fixture: a live reasoning call is a gated, paid "
    "action. Every deterministic step applied to it (length limits, prohibited "
    "phrases, copy audit, provenance) is the app's own code.")

#: A number with a unit or a count word is a factual claim about the product.
_NUMBER = re.compile(r"\b\d+(?:\.\d+)?\s*(?:mg|g|oz|ml|l|mm|cm|in|servings?|capsules?|"
                     r"cards?|count|pack|%)\b", re.IGNORECASE)


class ServiceRefused(RuntimeError):
    """The path refused by name. Recorded, never swapped for a different run."""


# ── plumbing ─────────────────────────────────────────────────────────────────

def _backend() -> Path:
    backend = ROOT / "Northstar_backend"
    if str(backend) not in sys.path:
        sys.path.insert(0, str(backend))
    return backend


def load_fixtures(path: str | Path | None = None) -> Dict[str, Any]:
    payload = json.loads(Path(path or DEFAULT_FIXTURES).read_text(encoding="utf-8"))
    for name in PATHS:
        payload.setdefault(name, [])
    return payload


def load_attribution(path: str | Path | None = None) -> Dict[str, Dict[str, Any]]:
    """Which service each path belongs to, as the fixture declares it.

    An entry with ``"service": null`` is a path that no service owns; it is kept
    so the absence is a recorded statement rather than a missing key.
    """
    payload = load_fixtures(path)
    block = payload.get("service_attribution") or {}
    out: Dict[str, Dict[str, Any]] = {}
    for name, entry in block.items():
        if isinstance(entry, dict):
            out[str(name)] = dict(entry)
        elif isinstance(entry, str):
            out[str(name)] = {"service": entry}
        else:
            out[str(name)] = {"service": None}
    return out



def _ok(check: str, **kw: Any) -> Dict[str, Any]:
    return {"ok": True, "check": check, **kw}


def _bad(check: str, detail: str, **kw: Any) -> Dict[str, Any]:
    return {"ok": False, "check": check, "detail": detail, **kw}


def _skip(check: str, detail: str, **kw: Any) -> Dict[str, Any]:
    return {"ok": False, "check": check, "skipped": True, "detail": detail, **kw}


def score_checks(checks: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    """Share of graded checks that passed. A skip is not a pass and not a failure."""
    graded = [name for name, check in checks.items() if not check.get("skipped")]
    failed = [name for name in graded if not checks[name].get("ok")]
    skipped = [name for name, check in checks.items() if check.get("skipped")]
    score = round(100.0 * (len(graded) - len(failed)) / len(graded), 1) if graded else 0.0
    return {"score": score, "passed": not failed and bool(graded),
            "graded": len(graded), "failed_checks": failed, "skipped_checks": skipped}


# ── listing ──────────────────────────────────────────────────────────────────

class _RecordedProvider:
    """A reasoning provider that replays one recorded answer. No network."""

    def __init__(self, proposed: Dict[str, Any], sku: str) -> None:
        self.proposed = proposed
        self.sku = sku
        self.requests: List[Any] = []

    def complete(self, request: Any) -> Any:
        from adapters.base import ProviderResponse, ProviderStatus  # noqa: PLC0415

        self.requests.append(request)
        content = json.dumps({
            "sku": self.sku,
            "original": {},
            "proposed": self.proposed,
            "reasons": self.proposed.get("reasons") or [],
            "missing_evidence": self.proposed.get("missing_evidence") or [],
            "warnings": self.proposed.get("warnings") or [],
        })
        return ProviderResponse(success=True, status=ProviderStatus.OK,
                                provider="recorded-fixture",
                                data={"content": content, "model": "recorded-fixture"},
                                latency_ms=0.0)


def _numbers(text: str) -> List[str]:
    return sorted({match.group(0).strip().lower() for match in _NUMBER.finditer(text)})


def run_listing(brief: Dict[str, Any], *, work_dir: Path) -> Dict[str, Any]:
    """Compose a listing proposal through the app's own path and check it like a seller."""
    _backend()
    from bojo_tools.publishing import compose_listing  # noqa: PLC0415

    proposed = dict(brief.get("recorded_proposal") or {})
    if not proposed:
        raise ServiceRefused(f"{brief.get('id')}: the fixture records no model answer")
    provider = _RecordedProvider(proposed, str(brief.get("sku") or ""))
    result = compose_listing(
        sku=str(brief.get("sku") or ""), title=str(brief.get("title") or ""),
        bullets=list(brief.get("bullets") or []),
        description=str(brief.get("description") or ""),
        attributes=dict(brief.get("attributes") or {}),
        keywords=list(brief.get("keywords") or []), brand=brief.get("brand"),
        provider=provider)
    if not result.get("ok"):
        raise ServiceRefused(f"{brief.get('id')}: the composer refused: {result.get('reason')}")
    checks: Dict[str, Dict[str, Any]] = {}
    data = result["data"]
    copy = data["proposed"]
    title = str(copy.get("title") or "")
    bullets = [str(b) for b in (copy.get("bullets") or [])]
    description = str(copy.get("description") or "")
    everything = " ".join([title, *bullets, description])

    checks["sku_preserved"] = (_ok("sku_preserved", sku=data.get("sku"))
                               if str(data.get("sku")) == str(brief.get("sku"))
                               else _bad("sku_preserved",
                                         f"proposal sku {data.get('sku')!r} is not "
                                         f"{brief.get('sku')!r}"))
    checks["title_within_limit"] = (
        _ok("title_within_limit", chars=len(title))
        if 20 <= len(title) <= 200 else
        _bad("title_within_limit", f"title is {len(title)} chars (limit 200, floor 20)"))
    long_bullets = [b for b in bullets if len(b) > 500]
    checks["bullets_within_limit"] = (
        _ok("bullets_within_limit", count=len(bullets))
        if 3 <= len(bullets) <= 5 and not long_bullets else
        _bad("bullets_within_limit",
             f"{len(bullets)} bullets, {len(long_bullets)} over 500 chars"))
    checks["description_within_limit"] = (
        _ok("description_within_limit", chars=len(description))
        if 0 < len(description) <= 2000 else
        _bad("description_within_limit",
             f"description is {len(description)} chars (limit 2000)"))
    warnings = [str(w) for w in (data.get("warnings") or [])]
    prohibited = [w for w in warnings if "prohibited phrase" in w.lower()]
    checks["no_prohibited_phrase"] = (
        _ok("no_prohibited_phrase", warnings=len(warnings))
        if not prohibited else _bad("no_prohibited_phrase", "; ".join(prohibited)[:300]))
    audit = data.get("copy_audit") or {}
    if audit.get("abstained"):
        checks["copy_audit_clear"] = _skip(
            "copy_audit_clear", "the copy audit backend is unavailable; nothing measured")
    else:
        blocked = str(audit.get("value") or "") == "block"
        checks["copy_audit_clear"] = (
            _bad("copy_audit_clear", f"copy audit blocked the text: {audit.get('flags')}")
            if blocked else
            _ok("copy_audit_clear", value=audit.get("value"), flags=audit.get("flags") or []))
    facts = [str(fact).lower() for fact in (brief.get("facts") or [])]
    invented = [token for token in _numbers(everything)
                if not any(token in fact or fact in token for fact in facts)]
    checks["no_invented_numbers"] = (
        _ok("no_invented_numbers", numbers=_numbers(everything))
        if not invented else
        _bad("no_invented_numbers",
             f"numbers with no source in the brief's facts: {invented}"))
    # A draft that carries a claim the seller cannot support must come out clean.
    # The brief names the phrases (`must_not_keep`); a phrase it names but its own
    # draft does not carry is a stale brief and fails rather than passing vacuously.
    must_not_keep = [str(p) for p in (brief.get("must_not_keep") or []) if str(p).strip()]
    if not must_not_keep:
        checks["draft_claims_removed"] = _skip(
            "draft_claims_removed",
            "this brief declares no claim in the seller's draft to remove")
    else:
        draft_text = " ".join([str(brief.get("title") or ""),
                               *[str(b) for b in (brief.get("bullets") or [])],
                               str(brief.get("description") or "")]).lower()
        absent = [p for p in must_not_keep if p.lower() not in draft_text]
        kept = [p for p in must_not_keep if p.lower() in everything.lower()]
        if absent:
            checks["draft_claims_removed"] = _bad(
                "draft_claims_removed",
                f"the brief declares {absent} but its own draft does not carry it")
        elif kept:
            checks["draft_claims_removed"] = _bad(
                "draft_claims_removed",
                f"the proposal repeats claim(s) the seller's draft carried: {kept}")
        else:
            checks["draft_claims_removed"] = _ok("draft_claims_removed",
                                                removed=must_not_keep)

    reasons = [str(r) for r in (data.get("reasons") or [])]
    checks["reasons_recorded"] = (
        _ok("reasons_recorded", count=len(reasons)) if reasons else
        _bad("reasons_recorded", "the proposal records no reason for its changes"))
    checks["provenance_recorded"] = (
        _ok("provenance_recorded", **(data.get("provenance") or {}))
        if data.get("provenance") else
        _bad("provenance_recorded", "the proposal carries no provenance record"))
    checks["not_applied"] = (
        _ok("not_applied") if data.get("applied") is False else
        _bad("not_applied", "a proposal must never be applied automatically"))

    work_dir.mkdir(parents=True, exist_ok=True)
    target = work_dir / f"{brief.get('id')}.json"
    target.write_text(json.dumps({"brief": brief.get("id"),
                                  "request_provider": "recorded-fixture", "result": result},
                                 indent=2, ensure_ascii=False), encoding="utf-8")
    scored = score_checks(checks)
    return {"path": "listing", "brief_id": brief.get("id"), "artefact": str(target),
            "provider": "recorded-fixture", "checks": checks, **scored}


# ── ppc ──────────────────────────────────────────────────────────────────────

def _xlsx(rows: Sequence[Sequence[Any]], sheet_title: str) -> bytes:
    try:
        import openpyxl  # noqa: PLC0415
    except ImportError as exc:  # pragma: no cover - environment guard
        raise ServiceRefused(f"openpyxl is required to build the bulksheet: {exc}") from exc
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = sheet_title
    for row in rows:
        ws.append(list(row))
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def run_ppc(brief: Dict[str, Any], *, work_dir: Path) -> Dict[str, Any]:
    """Upload -> propose -> approve -> write -> download, through the real API."""
    _backend()
    import data_layer  # noqa: PLC0415

    work_dir.mkdir(parents=True, exist_ok=True)
    previous_path = getattr(data_layer, "_SQLITE_PATH", None)
    data_layer._SQLITE_PATH = work_dir / "northstar.db"
    checks: Dict[str, Dict[str, Any]] = {}
    try:
        db = data_layer.NorthstarDB()
        import design_studio_api  # noqa: PLC0415
        from fastapi.testclient import TestClient  # noqa: PLC0415
        from main import app  # noqa: PLC0415

        previous_get_db = getattr(design_studio_api, "get_northstar_db", None)
        design_studio_api.get_northstar_db = lambda: db
        account = "org-seller-tester"
        app.dependency_overrides[design_studio_api.studio_account] = lambda: account
        client = TestClient(app)
        try:
            return _ppc_steps(client, brief, work_dir, checks)
        finally:
            app.dependency_overrides = {}
            if previous_get_db is not None:
                design_studio_api.get_northstar_db = previous_get_db
    finally:
        data_layer._SQLITE_PATH = previous_path


def _ppc_steps(client: Any, brief: Dict[str, Any], work_dir: Path,
               checks: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    expect = brief.get("expect") or {}
    content = _xlsx(brief.get("rows") or [], str(brief.get("sheet_title") or "Sheet1"))
    up = client.post("/api/design-studio/amazon-files/upload",
                     json={"filename": brief.get("filename") or "bulk.xlsx",
                           "content_b64": base64.b64encode(content).decode("ascii")})
    if up.status_code != 200:
        raise ServiceRefused(f"{brief.get('id')}: upload refused {up.status_code}: "
                             f"{up.text[:300]}")
    upload = up.json()["upload"]
    uid = upload["id"]
    checks["upload_parsed"] = (
        _ok("upload_parsed", kind=upload["kind"], rows=upload["row_count"])
        if upload.get("kind") == "ads_bulksheet" and int(upload.get("row_count") or 0) >= 4 else
        _bad("upload_parsed", f"kind={upload.get('kind')} rows={upload.get('row_count')}"))
    sheets = upload.get("sheets") or []
    if not sheets:
        detail = client.get(f"/api/design-studio/amazon-files/{uid}").json()["upload"]
        sheets = detail.get("sheets") or []
    checks["sheet_detected"] = (
        _ok("sheet_detected", sheet=sheets[0]["name"]) if sheets else
        _bad("sheet_detected", "the upload reports no sheets"))
    if not sheets:
        raise ServiceRefused(f"{brief.get('id')}: no sheet to propose against")
    sheet = sheets[0]["name"]

    prop = client.post(f"/api/design-studio/amazon-files/{uid}/proposals",
                       json={"changes": [{"sheet": sheet,
                                          "row_index": int(expect["row_index"]),
                                          "op": "Update",
                                          "fields": {"bid": expect["after_bid"]},
                                          "reason": expect.get("reason")}]})
    if prop.status_code != 200:
        raise ServiceRefused(f"{brief.get('id')}: proposal refused {prop.status_code}: "
                             f"{prop.text[:300]}")
    proposal = prop.json()["proposals"][0]
    checks["proposal_before_after"] = (
        _ok("proposal_before_after", before=proposal["before"], after=proposal["after"])
        if proposal["before"].get("bid") == expect["before_bid"]
        and proposal["after"].get("bid") == expect["after_bid"] else
        _bad("proposal_before_after",
             f"before={proposal['before']} after={proposal['after']}"))
    checks["proposal_unblocked"] = (
        _ok("proposal_unblocked") if not proposal.get("blocks") else
        _bad("proposal_unblocked", "; ".join(proposal["blocks"])))

    approved = client.post(f"/api/design-studio/amazon-files/proposals/{proposal['id']}/approve",
                           json={})
    checks["approved"] = (
        _ok("approved") if approved.status_code == 200
        and approved.json()["proposal"]["status"] == "approved" else
        _bad("approved", f"{approved.status_code}: {approved.text[:200]}"))

    first = client.post(f"/api/design-studio/amazon-files/{uid}/write", json={})
    if first.status_code != 200:
        raise ServiceRefused(f"{brief.get('id')}: write refused {first.status_code}: "
                             f"{first.text[:300]}")
    f1 = first.json()["change_file"]
    checks["write_is_version_one"] = (
        _ok("write_is_version_one", rows=f1["row_count"]) if f1["version"] == 1
        and int(f1["row_count"]) >= 1 else
        _bad("write_is_version_one", f"version={f1['version']} rows={f1['row_count']}"))
    checks["roundtrip_ok"] = (
        _ok("roundtrip_ok", rows=first.json()["roundtrip"].get("rows_written"))
        if first.json()["roundtrip"].get("ok") is True else
        _bad("roundtrip_ok", json.dumps(first.json()["roundtrip"])[:300]))

    second = client.post(f"/api/design-studio/amazon-files/{uid}/write", json={})
    f2 = second.json().get("change_file", {}) if second.status_code == 200 else {}
    checks["second_write_is_a_new_file"] = (
        _ok("second_write_is_a_new_file", version=f2.get("version"), id=f2.get("id"))
        if f2.get("version") == 2 and f2.get("id") != f1["id"]
        and str(f2.get("filename", "")).endswith("-v2." + str(f2.get("format"))) else
        _bad("second_write_is_a_new_file", f"{second.status_code}: {second.text[:200]}"))

    dl = client.get(f"/api/design-studio/amazon-files/change/{f1['id']}/download")
    digest = hashlib.sha256(dl.content).hexdigest() if dl.status_code == 200 else ""
    checks["download_is_the_written_bytes"] = (
        _ok("download_is_the_written_bytes", bytes=len(dl.content), sha256=digest[:16])
        if dl.status_code == 200 and digest == f1["checksum"] and len(dl.content) > 1000
        and (f1["format"] != "xlsx" or dl.content[:2] == b"PK") else
        _bad("download_is_the_written_bytes",
             f"status={dl.status_code} sha={digest[:16]} expected={str(f1['checksum'])[:16]}"))

    after = client.get(f"/api/design-studio/amazon-files/{uid}").json()["upload"]
    checks["original_untouched"] = (
        _ok("original_untouched", checksum=str(upload["checksum"])[:16])
        if after.get("checksum") == upload["checksum"] else
        _bad("original_untouched",
             f"the upload checksum changed: {upload['checksum']} -> {after.get('checksum')}"))

    bulk = work_dir / str(f1["filename"])
    bulk.write_bytes(dl.content)
    checks["bulk_file_on_disk"] = (
        _ok("bulk_file_on_disk", bytes=len(dl.content), path=str(bulk))
        if bulk.is_file() and hashlib.sha256(bulk.read_bytes()).hexdigest() == f1["checksum"]
        else _bad("bulk_file_on_disk", "the downloaded change file is not on disk intact"))

    scored = score_checks(checks)
    return {"path": "ppc", "brief_id": brief.get("id"), "artefact": str(bulk),
            "upload_id": uid, "change_file": f1["filename"],
            "checks": checks, **scored}


# ── golden goose ─────────────────────────────────────────────────────────────

def run_golden_goose(brief: Dict[str, Any], *, work_dir: Path) -> Dict[str, Any]:
    """Score a wholesale->individual candidate set through the real Golden Goose path."""
    _backend()
    from bojo_tools.sourcing import golden_goose_scan  # noqa: PLC0415

    expect = brief.get("expect") or {}
    result = golden_goose_scan(
        list(brief.get("candidates") or []),
        roi_floor=float(brief.get("roi_floor", 10.0)),
        min_monthly_sales=int(brief.get("min_monthly_sales", 1000)))
    checks: Dict[str, Dict[str, Any]] = {}
    if not result.get("ok"):
        raise ServiceRefused(f"{brief.get('id')}: the scan refused: {result.get('reason')}")
    data = result["data"]
    rows = data.get("opportunities") or []
    asins = [row.get("asin") for row in rows]
    checks["scan_evaluated_every_candidate"] = (
        _ok("scan_evaluated_every_candidate", evaluated=data["evaluated"])
        if int(data["evaluated"]) == len(brief.get("candidates") or []) else
        _bad("scan_evaluated_every_candidate",
             f"evaluated {data['evaluated']} of {len(brief.get('candidates') or [])}"))
    checks["results_returned"] = (
        _ok("results_returned", returned=len(rows)) if rows else
        _bad("results_returned", "no candidate survived selection"))
    rejected = expect.get("rejected_asin")
    checks["reject_tier_dropped"] = (
        _ok("reject_tier_dropped", rejected=rejected)
        if rejected and rejected not in asins else
        _bad("reject_tier_dropped", f"{rejected} is in the returned rows"))
    scores = [float(row.get("composite_score") or 0.0) for row in rows]
    checks["ranked_descending"] = (
        _ok("ranked_descending", scores=scores)
        if scores == sorted(scores, reverse=True) else
        _bad("ranked_descending", f"order is {scores}"))
    first = expect.get("first_asin")
    checks["best_row_is_first"] = (
        _ok("best_row_is_first", asin=asins[0] if asins else None)
        if first and asins and asins[0] == first
        and data["summary"].get("best_asin") == first
        else _bad("best_row_is_first",
                  f"first row {asins[0] if asins else None}, best reported "
                  f"{data['summary'].get('best_asin')}"))
    filters_ok = all(set(row.get("filters") or {}) >=
                     {"profit_floor", "demand_floor", "competition_ceiling",
                      "listing_health", "seller_identity", "size", "all"} for row in rows)
    checks["filters_reported"] = (
        _ok("filters_reported", rows=len(rows)) if rows and filters_ok else
        _bad("filters_reported", "a row carries no complete filter verdict"))
    economics_ok = all(
        isinstance((row.get("economics") or {}).get(key), (int, float))
        for row in rows
        for key in ("unit_cogs", "net_profit_per_unit", "roi_per_unit", "profit_margin_pct"))
    checks["economics_present"] = (
        _ok("economics_present") if rows and economics_ok else
        _bad("economics_present", "a row is missing a measured economics figure"))
    tags = sorted({tag for row in rows for tag in (row.get("tags") or [])})
    checks["why_recorded"] = (
        _ok("why_recorded", tags=tags) if rows and tags else
        _bad("why_recorded", "a row says nothing about why it scored"))
    checks["thresholds_recorded"] = (
        _ok("thresholds_recorded", roi_floor=data["roi_floor"],
            min_monthly_sales=data["min_monthly_sales"])
        if float(data["roi_floor"]) == float(brief.get("roi_floor", 10.0))
        and int(data["min_monthly_sales"]) == int(brief.get("min_monthly_sales", 1000)) else
        _bad("thresholds_recorded", f"{data['roi_floor']} / {data['min_monthly_sales']}"))

    work_dir.mkdir(parents=True, exist_ok=True)
    target = work_dir / f"{brief.get('id')}.json"
    target.write_text(json.dumps({"brief": brief.get("id"), "result": result},
                                 indent=2, ensure_ascii=False), encoding="utf-8")
    scored = score_checks(checks)
    return {"path": "golden_goose", "brief_id": brief.get("id"), "artefact": str(target),
            "row_count": len(rows), "checks": checks, **scored}


# ── research ─────────────────────────────────────────────────────────────────

def run_research(brief: Dict[str, Any], *, work_dir: Path) -> Dict[str, Any]:
    """Run one research query through the local corpus graph and check its honesty."""
    _backend()
    import research_graph  # noqa: PLC0415

    corpus = list(brief.get("corpus") or [])
    calls: List[str] = []

    def search(text: str, limit: int) -> List[Dict[str, Any]]:
        """Deterministic local corpus: a hit is a document sharing a query term."""
        calls.append(text)
        terms = [term.lower() for term in re.findall(r"[A-Za-z]+", text)]
        hits = []
        for doc in corpus:
            body = str(doc.get("text") or "")
            low = body.lower()
            if any(len(term) > 3 and term in low for term in terms):
                hits.append({"source_id": doc.get("source_id"), "source": doc.get("source"),
                             "text": body, "score": 1.0})
        return hits[:limit]

    result = research_graph.research(str(brief.get("query") or ""), search=search)
    checks: Dict[str, Dict[str, Any]] = {}
    nodes = result.get("nodes") or []
    hits = sum(len(node.get("results") or []) for node in nodes)
    axes = [str(node.get("id")) for node in nodes]
    checks["query_matrix_decomposed"] = (
        _ok("query_matrix_decomposed", axes=axes)
        if axes == ["concept", "edge_case", "history"] else
        _bad("query_matrix_decomposed", f"axes are {axes}"))
    checks["evidence_returned"] = (
        _ok("evidence_returned", hits=hits, nodes=len(nodes))
        if hits > 0 else
        _bad("evidence_returned", "no passage was retrieved for any node"))
    want_sources = int((brief.get("expect") or {}).get("min_sources") or 2)
    sources = result.get("sources") or []
    checks["sources_are_distinct"] = (
        _ok("sources_are_distinct", sources=sources) if len(sources) >= want_sources else
        _bad("sources_are_distinct", f"{len(sources)} source(s), {want_sources} needed"))
    validation = result.get("validation") or {}
    checks["corroboration_counted"] = (
        _ok("corroboration_counted", multi_source=validation.get("multi_source_count"))
        if int(validation.get("multi_source_count") or 0) >= 1 else
        _bad("corroboration_counted", "no claim was found in more than one source"))
    single = validation.get("single_source") or []
    checks["single_source_labelled"] = (
        _ok("single_source_labelled", count=len(single))
        if single and all(item.get("source") for item in single) else
        _bad("single_source_labelled",
             "no single-source claim was labelled, or a label names no source"))
    conflicts = validation.get("conflicts") or []
    declared = (brief.get("expect") or {}).get("conflict_values")
    want_values = [str(v) for v in (declared or [])]
    if declared is None:
        checks["numeric_conflict_surfaced"] = _skip(
            "numeric_conflict_surfaced",
            "the brief does not say whether its sources agree or disagree")
    elif not want_values:
        # The corpus was declared to agree: surfacing a conflict here is the bug.
        checks["numeric_conflict_surfaced"] = (
            _ok("numeric_conflict_surfaced", conflicts=[], declared="sources agree")
            if not conflicts else
            _bad("numeric_conflict_surfaced",
                 f"the brief's sources were declared to agree, but the graph surfaced "
                 f"{len(conflicts)} conflict(s): {conflicts}"))
    else:
        surfaced = [conflict for conflict in conflicts
                    if all(any(value in str(key)
                               for key in (conflict.get("values") or {}))
                           for value in want_values)]
        checks["numeric_conflict_surfaced"] = (
            _ok("numeric_conflict_surfaced", conflicts=surfaced)
            if surfaced else
            _bad("numeric_conflict_surfaced",
                 f"the disagreeing figures {want_values} were not surfaced as one conflict: "
                 f"{conflicts}"))

    summary = str(result.get("summary") or "")
    checks["headline_is_a_measurement"] = (
        _ok("headline_is_a_measurement", summary=summary)
        if summary.startswith(f"{hits} passage") else
        _bad("headline_is_a_measurement", f"headline does not lead with the count: {summary}"))
    checks["no_web_crawl_claimed"] = (
        _ok("no_web_crawl_claimed", method=str(result.get("method"))[:120])
        if "no web crawl" in str(result.get("method") or "").lower()
        and len(calls) == len(nodes) else
        _bad("no_web_crawl_claimed",
             f"method/call count do not match a local corpus run: {len(calls)} call(s)"))

    work_dir.mkdir(parents=True, exist_ok=True)
    target = work_dir / f"{brief.get('id')}.json"
    target.write_text(json.dumps({"brief": brief.get("id"),
                                  "search": "fixture local corpus",
                                  "queries": calls, "result": result},
                                 indent=2, ensure_ascii=False), encoding="utf-8")
    scored = score_checks(checks)
    return {"path": "research", "brief_id": brief.get("id"), "artefact": str(target),
            "summary": summary, "checks": checks, **scored}


# ── the pass ─────────────────────────────────────────────────────────────────

RUNNERS = {"listing": run_listing, "ppc": run_ppc,
           "golden_goose": run_golden_goose, "research": run_research}


def parse_only(value: Optional[str]) -> List[str]:
    if not value or not str(value).strip():
        return list(PATHS)
    wanted = [part.strip() for part in str(value).split(",") if part.strip()]
    unknown = [name for name in wanted if name not in PATHS]
    if unknown:
        raise ValueError(f"unknown path(s) {unknown}; choose from {list(PATHS)}")
    return [name for name in PATHS if name in wanted]


def run_pass(*, fixtures: Optional[str | Path] = None, only: Optional[str] = None,
             out_path: str | Path = DEFAULT_OUT,
             work_dir: str | Path = DEFAULT_WORK_DIR,
             now: Optional[str] = None) -> Dict[str, Any]:
    """Run each selected path over every fixture of its kind. A refusal is recorded."""
    payload = load_fixtures(fixtures)
    attribution = load_attribution(fixtures)
    selected = parse_only(only)
    started = time.time()
    results: List[Dict[str, Any]] = []
    refusals: List[Dict[str, Any]] = []
    for name in selected:
        runner = RUNNERS[name]
        briefs = payload.get(name) or []
        if not briefs:
            reason = "the fixture file carries no brief for this path"
            refusals.append({"path": name, "brief_id": None, "reason": reason})
            results.append({"path": name, "brief_id": None, "status": "refused",
                            "score": 0.0, "passed": False, "failed_checks": ["fixture"],
                            "reason": reason})
            continue
        for brief in briefs:
            try:
                row = runner(brief, work_dir=Path(work_dir) / name)
                row["status"] = "scored"
            except ServiceRefused as exc:
                refusals.append({"path": name, "brief_id": brief.get("id"),
                                 "reason": str(exc)})
                row = {"path": name, "brief_id": brief.get("id"), "status": "refused",
                       "score": 0.0, "passed": False, "failed_checks": ["run"],
                       "reason": str(exc)}
            results.append(row)

    by_path: Dict[str, Dict[str, Any]] = {}
    for name in PATHS:
        rows = [row for row in results if row["path"] == name]
        scored = [row for row in rows if row.get("status") == "scored"]
        owner = attribution.get(name) or {}
        by_path[name] = {
            "selected": len(rows) if name in selected else 0,
            "scored": len(scored),
            "passed": sum(1 for row in scored if row.get("passed")),
            "refused": sum(1 for row in rows if row.get("status") == "refused"),
            "mean_score": (round(sum(float(row["score"]) for row in scored) / len(scored), 1)
                           if scored else None),
            "measured": name in selected,
            "service": owner.get("service"),
            "service_aliases": owner.get("aliases") or [],
        }
    summary = {
        "generated_at": now or time.strftime("%Y-%m-%dT%H:%M:%S"),
        "command": "python -m tools.seller_tester services"
                   + (f" --only {only}" if only else ""),
        "fixtures": str(Path(fixtures or DEFAULT_FIXTURES)),
        "only": selected,
        "seconds": round(time.time() - started, 2),
        "network": "none: every path runs against local fixtures and local code",
        "recorded_provider_note": RECORDED_PROVIDER_NOTE,
        "paths": by_path,
        "scored": sum(1 for row in results if row.get("status") == "scored"),
        "passed": sum(1 for row in results if row.get("passed")),
        "refused": len(refusals),
        "refusals": refusals,
        "results": results,
    }
    target = Path(out_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    summary["summary_path"] = str(target)
    return summary


__all__ = ["DEFAULT_FIXTURES", "DEFAULT_OUT", "DEFAULT_WORK_DIR", "PATHS",
           "RECORDED_PROVIDER_NOTE", "RUNNERS", "ServiceRefused", "load_attribution",
           "load_fixtures", "parse_only", "run_golden_goose", "run_listing", "run_pass",
           "run_ppc", "run_research", "score_checks"]




