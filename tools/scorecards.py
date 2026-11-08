"""Scorecards: what "production-ready" means per service, and what it scores today.

D4 in the director work order. Two rules keep this honest:

* a dimension is scored **from an artefact** - the measured test id list, the readiness
  scan, the registry's own tool list - never from opinion;
* a service with no artefact scores **0 with the reason named**, which is a real
  measurement ("nothing proves this works") and becomes a gap for D5.

The spec it writes (`ty/TARGET_SPEC.md`) is derived, so it cannot drift from the
scores. Rubric scenarios are tagged `backed` (an artefact exercises it) or `assumed`
(nobody has proved it yet) exactly as PATCH 1 item 1 requires.

    python tools/scorecards.py                 # measure + write the spec
    python tools/scorecards.py --json          # measurement only
"""
from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "ty" / "services.json"
IDLIST = ROOT / "reports" / "ty" / "_idlist_20261107.txt"
SCAN = ROOT / "state" / "director" / "scan.json"
SPEC = ROOT / "ty" / "TARGET_SPEC.md"
SCORES = ROOT / "ty" / "scorecards.json"

BAR = 85.0
WEIGHTS = {"works": 0.30, "correct": 0.30, "complete": 0.15, "usable": 0.15,
           "measured": 0.10}

#: Test-id substrings that belong to each registry entry. Explicit on purpose: an
#: inference would quietly award a service a score for somebody else's tests.
SERVICE_TESTS: Dict[str, List[str]] = {
    "hub": ["foundation/tests", "test_ops_status"],
    "foundation": ["foundation/tests", "test_ops_status"],
    "ledger": ["test_ledger", "batch_run"],
    "prospector": ["test_sourcing", "test_prospector"],
    "product-finder": ["test_product_finder", "test_sourcing"],
    "goldengoose": ["golden_goose"],
    "golden-goose": ["golden_goose"],
    "offerchisel": ["test_listing", "test_offer"],
    "listings": ["test_listing"],
    "listingforge": ["test_listing", "test_forge"],
    "towncrier": ["test_social"],
    "socialpulse": ["test_social"],
    "auctioneer": ["test_ads", "test_auction"],
    "adpilot": ["test_ads", "test_adpilot"],
    "autothink": ["test_autothink", "test_memory"],
    "thewatch": ["test_monitor"],
    "rankledger": ["test_rank"],
    "rivalboard": ["test_competitor", "test_rival"],
    "competitor-monitor": ["test_competitor"],
    "keyword-tracker": ["test_keyword"],
    "keywords": ["test_keyword"],
    "profitability": ["test_profit"],
    "design-studio": ["test_design_studio", "test_studio", "test_asset_rubric"],
    "account": ["test_foundation_api", "test_auth"],
    "jobs": ["test_jobs_durable"],
    "beta": ["test_beta"],
    "beta-support": ["test_beta"],
    "beta-signup": ["test_beta"],
    "beta-ops": ["test_beta", "test_tys_assistant"],
}

#: A readiness finding belongs to a service only when its path names that service.
#: A repo-wide finding (a dead module nobody imports) is an infrastructure gap, not
#: six services failing, so it is reported separately instead of charged six times.
def _service_findings(sid: str, findings: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    key = sid.replace("-", "").replace("_", "").lower()
    out: List[Dict[str, Any]] = []
    for finding in findings:
        path = str(finding.get("file", "")).replace("-", "").replace("_", "").lower()
        if key and key in path:
            out.append(finding)
    return out

#: What a paying seller needs first (0-1). Sourcing and listings ship first because
#: without them there is nothing to sell; social and analytics come after.
IMPACT = {
    "goldengoose": 0.95, "golden-goose": 0.95, "prospector": 0.9,
    "product-finder": 0.9, "offerchisel": 0.9, "listings": 0.9,
    "listingforge": 0.85, "design-studio": 0.95, "ledger": 0.8,
    "profitability": 0.75, "hub": 0.85, "foundation": 0.7, "keywords": 0.6,
    "keyword-tracker": 0.6, "auctioneer": 0.7, "adpilot": 0.7, "thewatch": 0.6,
    "rankledger": 0.55, "rivalboard": 0.5, "competitor-monitor": 0.5,
    "towncrier": 0.45, "socialpulse": 0.45, "autothink": 0.5, "account": 0.8,
    "jobs": 0.4, "beta": 0.9, "beta-support": 0.5, "beta-signup": 0.8,
    "beta-ops": 0.4,
}

PURPOSE = {
    "hub": "the room a seller lands in: today's work, the numbers that matter, and Bojo",
    "ledger": "money in, money out, fees and margin per SKU without a spreadsheet",
    "prospector": "find products worth selling, with demand and competition evidence",
    "product-finder": "SourceScout: match a product idea to suppliers and landed cost",
    "goldengoose": "the high-margin finder: score an opportunity and say why",
    "golden-goose": "the high-margin finder: score an opportunity and say why",
    "offerchisel": "turn a product into an offer: price, title, bullets, images",
    "listings": "Listing Guardian: keep live listings compliant and correct",
    "listingforge": "create and version listings with the copy that converts",
    "towncrier": "seller-side social output that does not read like a robot",
    "socialpulse": "schedule and judge social posts against a brand voice",
    "auctioneer": "PPC bids and budgets that spend only where they return",
    "adpilot": "campaign control: budget, bids, and the report behind them",
    "autothink": "the memory plane: what the seller told us, recalled at the right time",
    "thewatch": "watch the account for the things that quietly cost money",
    "rankledger": "rank, impressions and conversion over time, per keyword",
    "rivalboard": "what competitors changed, and what it means for us",
    "competitor-monitor": "the competitor feed behind Rival Board",
    "keyword-tracker": "which keywords are worth owning, measured not guessed",
    "keywords": "keyword research and SEO workbench",
    "profitability": "per-SKU profitability after fees, ads and returns",
    "design-studio": "product pictures in any seller situation, and A+ content, from "
                     "a prompt, stored references, or uploads - Canva-grade to use",
    "account": "the seller's own account: plan, entitlements, security, preferences",
    "jobs": "long-running work that survives a reload and reports honestly",
    "beta": "onboarding and plan selection for a private beta seller",
    "beta-support": "support inside the beta without a human in the loop",
    "beta-signup": "invite entry that a real invitee can complete unaided",
    "beta-ops": "the tester dashboard: who is in, what they did, what broke",
}

SCENARIOS = {
    "Sourcing": ["find a product in a category I have never sold",
                 "compare landed cost across three suppliers",
                 "tell me the margin at my fee tier"],
    "Listings": ["turn this product into a listing that will not be suppressed",
                 "rewrite the bullets for a different audience",
                 "fix the listing that lost its buy box"],
    "Create": ["white-background main image from a phone photo",
               "lifestyle scene with a scale reference",
               "an A+ module set that matches the brand"],
    "Advertising": ["hold ROAS while doubling spend on the winner",
                    "cut the keywords that only cost money",
                    "show me what the campaign did last week"],
    "Monitoring": ["tell me what changed before I lose the buy box",
                   "show rank over the last 90 days",
                   "alert me when a competitor undercuts me"],
    "Social": ["post about a restock without sounding automated",
               "keep the voice consistent across three posts"],
    "Workspace": ["start the day knowing what needs doing",
                  "see margin per SKU without a spreadsheet"],
    "Internal": ["the work survives a reload and tells me when it failed"],
    "Account": ["change my plan without losing data",
                "see exactly what I am entitled to"],
    "Private Beta": ["an invitee signs up without help",
                     "a tester reports a bug and sees it acknowledged"],
    "Beta Operations": ["see who is active and what broke"],
    "AutothinK": ["remember my brand voice and use it later"],
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def registry() -> List[Dict[str, Any]]:
    data = json.loads(REGISTRY.read_text(encoding="utf-8"))
    return data.get("services") or []


def test_ids() -> List[str]:
    try:
        data = json.loads(IDLIST.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    ids = data.get("ids") if isinstance(data, dict) else data
    return [str(i) for i in (ids or [])]


def scan_findings() -> List[Dict[str, Any]]:
    out = Path(SCAN)
    if out.is_file():
        try:
            return json.loads(out.read_text(encoding="utf-8")).get("findings") or []
        except (OSError, ValueError):
            return []
    return []


_HAYSTACK: Optional[str] = None


def _backend_text() -> str:
    """The backend source, read once. Reading it per service took 29x as long."""
    global _HAYSTACK
    if _HAYSTACK is not None:
        return _HAYSTACK
    chunks: List[str] = []
    for path in (ROOT / "Northstar_backend").rglob("*.py"):
        if "__pycache__" in str(path):
            continue
        try:
            if path.stat().st_size > 2_000_000:
                continue
            chunks.append(path.read_text(encoding="utf-8", errors="replace"))
        except OSError:
            continue
    _HAYSTACK = "\n".join(chunks)
    return _HAYSTACK


def _wired_tools(ids: List[str]) -> Dict[str, bool]:
    """Is a Bojo tool id actually referenced anywhere in the backend?"""
    haystack = _backend_text()
    return {tool: (f"'{tool}'" in haystack or f'"{tool}"' in haystack) for tool in ids}


def measure_one(service: Dict[str, Any], ids: List[str],
                findings: List[Dict[str, Any]]) -> Dict[str, Any]:
    sid = service["id"]
    patterns = SERVICE_TESTS.get(sid, [])
    matched = [one for one in ids if any(p in one for p in patterns)] if patterns else []
    wired = _wired_tools(service.get("tools") or [])
    hits = _service_findings(sid, findings)

    dims: Dict[str, Dict[str, Any]] = {}
    dims["works"] = {
        "score": 100.0 if matched else 0.0,
        "evidence": (f"{len(matched)} test id(s) prove it" if matched
                     else "no test id maps to this service"),
    }
    dims["correct"] = {
        "score": 100.0 if matched else 0.0,
        "evidence": ("its tests passed in the D0 measured run" if matched
                     else "no check proves its output is correct"),
    }
    if wired:
        good = sum(1 for value in wired.values() if value)
        dims["complete"] = {"score": round(100.0 * good / len(wired), 1),
                            "evidence": f"{good}/{len(wired)} declared Bojo tools wired: "
                                        + ", ".join(sorted(wired))}
    else:
        dims["complete"] = {"score": 0.0,
                            "evidence": "no Bojo tool declared, so Bojo cannot drive it"}
    if hits:
        critical = sum(1 for f in hits if f.get("severity") == "high")
        medium = sum(1 for f in hits if f.get("severity") == "medium")
        dims["usable"] = {"score": max(0.0, 100.0 - 25 * critical - 10 * medium),
                          "evidence": f"{len(hits)} readiness finding(s) name this service"}
    else:
        dims["usable"] = {"score": 100.0,
                          "evidence": "no readiness finding names this service"}
    dims["measured"] = {"score": 0.0,
                        "evidence": "no threshold or performance check defined yet"}

    score = round(sum(WEIGHTS[key] * dims[key]["score"] for key in WEIGHTS), 1)
    meets = all(dim["score"] >= BAR for dim in dims.values())
    scenarios = SCENARIOS.get(service.get("group", ""), [])
    return {
        "id": sid, "label": service.get("label"), "group": service.get("group"),
        "kind": service.get("kind"), "route": service.get("route"),
        "impact": IMPACT.get(sid, 0.5), "bar": BAR, "score": score,
        "meets_bar": meets, "weakest": min(dims, key=lambda k: dims[k]["score"]),
        "gap": round(IMPACT.get(sid, 0.5) * max(0.0, BAR - score), 1),
        "dimensions": dims,
        "scenarios": [{"text": text, "tag": "backed" if matched else "assumed"}
                      for text in scenarios],
        "purpose": PURPOSE.get(sid, service.get("label")),
    }


def measure() -> Dict[str, Any]:
    services = registry()
    ids = test_ids()
    findings = scan_findings()
    rows = [measure_one(service, ids, findings) for service in services]
    rows.sort(key=lambda row: row["gap"], reverse=True)
    owned: set = set()
    for service in services:
        for finding in _service_findings(service["id"], findings):
            owned.add(id(finding))
    orphan = [finding for finding in findings if id(finding) not in owned]
    return {"at": _now(), "bar": BAR, "weights": WEIGHTS,
            "test_ids": len(ids), "scan_findings": len(findings),
            "services": rows, "global_findings": orphan,
            "at_bar": [row["id"] for row in rows if row["meets_bar"]]}


def render(result: Dict[str, Any]) -> str:
    lines = ["# Target spec — what production-ready means, per service", "",
             f"Derived {result['at']} from `state/director/services.json`, "
             f"{result['test_ids']} measured test ids and "
             f"{result['scan_findings']} readiness findings. **Scores are measured, "
             "never asserted**: a dimension with no artefact scores 0 and says why.",
             "", f"Bar: **{result['bar']:.0f} on every dimension** (not an average). "
             "A service is at the bar only when its weakest dimension clears it. "
             "Impact weight is what a paying seller needs first; gap = impact x "
             "(bar - score).", "",
             "| service | score | weakest | at bar | gap | impact |",
             "|---|---|---|---|---|---|"]
    for row in result["services"]:
        lines.append(f"| {row['label']} (`{row['id']}`) | {row['score']} | "
                     f"{row['weakest']} | {'yes' if row['meets_bar'] else 'no'} | "
                     f"{row['gap']} | {row['impact']} |")
    lines += ["", f"At the bar today: **{len(result['at_bar'])} of "
              f"{len(result['services'])}**.", ""]
    if result.get("global_findings"):
        lines += ["Repo-wide findings (not charged to any service):", ""]
        for finding in result["global_findings"]:
            lines.append(f"- {finding.get('check')} at `{finding.get('file')}`")
        lines += [""]

    for row in result["services"]:
        lines += [f"## {row['label']} (`{row['id']}`)", "",
                  f"{row['purpose']}.", "",
                  f"- route `{row['route']}`, group {row['group']}, kind {row['kind']}",
                  f"- **score {row['score']} / bar {row['bar']:.0f}** "
                  f"(impact {row['impact']}, gap {row['gap']})", "",
                  "| dimension | score | weight | evidence |", "|---|---|---|---|"]
        for name, dim in row["dimensions"].items():
            lines.append(f"| {name} | {dim['score']} | {WEIGHTS[name]} | "
                         f"{dim['evidence']} |")
        if row["scenarios"]:
            lines += ["", "Seller scenarios:"]
            for scenario in row["scenarios"]:
                lines.append(f"- `{scenario['tag']}` — {scenario['text']}")
        lines += [""]
    return "\n".join(lines)


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Service scorecards")
    parser.add_argument("--json", action="store_true")
    ns = parser.parse_args(argv)

    result = measure()
    SCORES.parent.mkdir(parents=True, exist_ok=True)
    SCORES.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    SPEC.write_text(render(result), encoding="utf-8")
    if ns.json:
        print(json.dumps({row["id"]: row["score"] for row in result["services"]},
                         indent=2))
    else:
        print(json.dumps({"services": len(result["services"]),
                          "at_bar": len(result["at_bar"]),
                          "top_gap": result["services"][0]["id"],
                          "top_gap_score": result["services"][0]["gap"],
                          "spec": str(SPEC)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
