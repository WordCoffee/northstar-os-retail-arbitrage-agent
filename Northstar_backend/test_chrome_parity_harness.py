"""Tests for the Chrome Connect six-point parity harness (`tools/chrome_parity_harness.py`).

These are offline and hermetic: no browser, no controller, no node. They pin the
two properties that make the harness worth anything:

  * it evaluates exactly the six declared points, in the declared order;
  * it fails closed - a point that cannot be checked is `not_verified`, never a
    pass, and one failed point fails the whole report.

Each evaluator is exercised both ways (a healthy evidence blob and a tampered
one), so a harness that silently rubber-stamps a controller cannot pass these.
"""
from __future__ import annotations

import json
import os
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)
_REPO = os.path.dirname(_HERE)
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)

sys.path.insert(0, os.path.join(_REPO, "tools"))

import chrome_parity_harness as h  # noqa: E402


# ── Synthetic evidence builders ─────────────────────────────────────────────

_POLICY_JS_OK = """
function evaluateUrl(url, options = {}) {
  const host = hostOf(url);
  if (!host) return { allowed: false, reason: 'invalid_url' };
  if (isAmazonHost(host)) {
    return { allowed: false, reason: 'amazon_prohibited' };
  }
  if (HOST_POLICY === 'denylist') {
    return { allowed: true, reason: 'open_web_denylist' };
  }
  if (DOMAIN_ALLOWLIST.includes(host)) {
    return { allowed: true, reason: 'allowlisted' };
  }
  return { allowed: false, reason: 'not_allowlisted' };
}
"""

_POLICY_JS_BAD_ORDER = """
function evaluateUrl(url, options = {}) {
  const host = hostOf(url);
  if (HOST_POLICY === 'denylist') {
    return { allowed: true, reason: 'open_web_denylist' };
  }
  if (DOMAIN_ALLOWLIST.includes(host)) {
    return { allowed: true, reason: 'allowlisted' };
  }
  if (isAmazonHost(host)) {
    return { allowed: false, reason: 'amazon_prohibited' };
  }
  return { allowed: false, reason: 'not_allowlisted' };
}
"""


def _host_evidence(**overrides):
    results = {url: {"allowed": False, "reason": "amazon_prohibited"}
               for url in h._AMAZON_PROBE_URLS}
    results["https://example.org/page"] = {"allowed": True, "reason": "open_web_denylist"}
    evidence = {
        "config": {
            "host_policy": "denylist",
            "prohibited_actions": ["amazon_direct_access", "navigate_amazon"],
            "baseline_fingerprint": "abc123",
        },
        "policy_js": _POLICY_JS_OK,
        "probe": {
            "ok": True,
            "amazon_blocklist": [f"amazon.{i}" for i in range(1, 27)],
            "results": results,
            "guardrails": {"intact": True},
            "fingerprint": "abc123",
        },
    }
    for key, value in overrides.items():
        evidence[key] = value
    return evidence


def _lease_evidence(directory="Profile 6", profile7_pass=False, **overrides):
    evidence = {
        "config": {
            "owner_authorization": {"profile_directory": directory},
            "extension_profile_dir_name": "Profile 6",
        },
        "isolation_js": ("profile_lease_valid selected_directory_exact "
                         "leaseDir === expectedDirectory pin_matches !== false"),
        "probe": {
            "ok": True,
            "owner_authorization": {"present": True, "directory": "Profile 6",
                                    "pin_matches": True},
            "profile6": {"isolated": True, "lease": {"pass": True}},
            "profile7": {"isolated": profile7_pass, "lease": {"pass": profile7_pass}},
        },
    }
    for key, value in overrides.items():
        evidence[key] = value
    return evidence


def _stops_evidence(**overrides):
    evidence = {
        "config": {
            "prohibited_actions": list(h._REQUIRED_PROHIBITED),
            "per_host_action_grants": {
                "account.squarespace.com": {
                    "allow": ["form_submission"],
                    "deny": ["sign_in", "credential_entry", "payment_action"],
                }
            },
        },
        "agent_loop_js": ("blocker code login_wall; captcha detected; "
                          "owner_action_required"),
        "denied_test": {"ran": True, "exit_code": 0},
    }
    for key, value in overrides.items():
        evidence[key] = value
    return evidence


def _journal_records(**overrides):
    records = [
        {"seq": 1, "ts": "2026-11-04T00:00:00Z", "type": "decision",
         "url": "https://example.org/x"},
        {"seq": 2, "ts": "2026-11-04T00:00:01Z", "type": "tool_call",
         "url": "https://example.org/x"},
        {"seq": 3, "ts": "2026-11-04T00:00:02Z", "type": "tool_result", "ok": True},
    ]
    probe = {"ok": True, "dir": "/tmp/j", "file": "run.jsonl", "records": records,
             "decision_seq": 1, "tool_seq": 2, "result_seq": 3, "secret_seq": 4}
    probe.update(overrides)
    return {"probe": probe, "live_files": ["a.jsonl"], "live_dir": "/tmp/j"}


# ── Contract ────────────────────────────────────────────────────────────────

def test_declares_exactly_six_points_in_order():
    ids = [p["id"] for p in h.POINTS]
    assert ids == [
        "host_policy_amazon_first",
        "profile6_lease",
        "credential_captcha_login_stops",
        "redirect_recheck",
        "audit_journal",
        "browser_benchmark",
    ]
    assert len(set(ids)) == 6


def test_summary_passes_only_when_all_six_are_verified():
    points = [h._point(p["id"], h.VERIFIED, {}) for p in h.POINTS]
    assert h.summarise(points)["overall"] == "pass"

    points[3] = h._point(h.POINTS[3]["id"], h.FAILED, {}, "broke")
    summary = h.summarise(points)
    assert summary["overall"] == "failed"
    assert summary["counts"]["failed"] == 1


def test_summary_never_passes_on_an_unverified_point():
    points = [h._point(p["id"], h.VERIFIED, {}) for p in h.POINTS]
    points[0] = h._point(h.POINTS[0]["id"], h.NOT_VERIFIED, {})
    assert h.summarise(points)["overall"] == "not_verified"


def test_summary_rejects_an_incomplete_point_set():
    points = [h._point(p["id"], h.VERIFIED, {}) for p in h.POINTS[:5]]
    assert h.summarise(points)["overall"] == "not_verified"


# ── Point 1: host policy + Amazon first ─────────────────────────────────────

def test_host_policy_verifies_a_denylist_with_amazon_refused_first():
    point = h.check_host_policy(_host_evidence())
    assert point["status"] == h.VERIFIED, point["detail"]


def test_host_policy_fails_when_the_policy_mode_is_allowlist():
    evidence = _host_evidence()
    evidence["config"]["host_policy"] = "allowlist"
    point = h.check_host_policy(evidence)
    assert point["status"] == h.FAILED
    assert "denylist" in point["detail"]


def test_host_policy_fails_when_amazon_is_not_refused():
    evidence = _host_evidence()
    evidence["probe"]["results"]["https://www.amazon.com/dp/B0TEST"] = {
        "allowed": True, "reason": "open_web_denylist"}
    point = h.check_host_policy(evidence)
    assert point["status"] == h.FAILED
    assert "amazon.com" in point["detail"]


def test_host_policy_fails_when_the_denylist_branch_precedes_amazon():
    evidence = _host_evidence(policy_js=_POLICY_JS_BAD_ORDER)
    point = h.check_host_policy(evidence)
    assert point["status"] == h.FAILED
    assert "precedes" in point["detail"]


def test_host_policy_fails_on_a_drifted_fingerprint():
    evidence = _host_evidence()
    evidence["probe"]["fingerprint"] = "deadbeef"
    point = h.check_host_policy(evidence)
    assert point["status"] == h.FAILED
    assert "baseline" in point["detail"]


def test_host_policy_is_not_verified_when_the_probe_could_not_run():
    evidence = _host_evidence(probe={"ok": False, "reason": "node_not_installed"})
    point = h.check_host_policy(evidence)
    assert point["status"] == h.NOT_VERIFIED
    assert "node_not_installed" in point["detail"]


# ── Point 2: Profile 6 lease ────────────────────────────────────────────────

def test_profile_lease_verifies_profile6_and_refuses_profile7():
    point = h.check_profile_lease(_lease_evidence())
    assert point["status"] == h.VERIFIED, point["detail"]
    assert point["evidence"]["config"]["profile7_lease_pass"] is False


def test_profile_lease_fails_when_another_profile_is_authorized():
    point = h.check_profile_lease(_lease_evidence(directory="Profile 7"))
    assert point["status"] == h.FAILED
    assert "Profile 6" in point["detail"]


def test_profile_lease_fails_when_profile7_is_not_refused():
    point = h.check_profile_lease(_lease_evidence(profile7_pass=True))
    assert point["status"] == h.FAILED
    assert "Profile 7" in point["detail"]


def test_profile_lease_is_not_verified_without_the_isolation_probe():
    evidence = _lease_evidence(probe={"ok": False, "reason": "node_probe_timeout"})
    point = h.check_profile_lease(evidence)
    assert point["status"] == h.NOT_VERIFIED


# ── Point 3: credential / CAPTCHA / login stops ─────────────────────────────

def test_action_stops_verifies_the_prohibited_table_and_loop_blockers():
    point = h.check_action_stops(_stops_evidence())
    assert point["status"] == h.VERIFIED, point["detail"]


def test_action_stops_fails_when_captcha_leaves_the_prohibited_list():
    evidence = _stops_evidence()
    evidence["config"]["prohibited_actions"] = [
        a for a in evidence["config"]["prohibited_actions"] if a != "captcha"]
    point = h.check_action_stops(evidence)
    assert point["status"] == h.FAILED
    assert "captcha" in point["detail"]


def test_action_stops_fails_when_the_loop_no_longer_stops_on_a_login_wall():
    evidence = _stops_evidence()
    evidence["agent_loop_js"] = "nothing to see here"
    point = h.check_action_stops(evidence)
    assert point["status"] == h.FAILED


def test_action_stops_is_not_verified_when_the_denied_suite_cannot_run():
    evidence = _stops_evidence(denied_test={"ran": False, "reason": "OSError"})
    point = h.check_action_stops(evidence)
    assert point["status"] == h.NOT_VERIFIED


# ── Point 4: redirect re-check ──────────────────────────────────────────────

def test_redirect_recheck_verifies_both_call_sites():
    evidence = {
        "pw_tool_js": ("// gates on the CURRENT page URL\n"
                       "const verdict = policy.evaluateUrl(url, { allowHosts });"),
        "agent_loop_js": "// Re-evaluate URL policy after every action: a redirect may have moved us.",
        "policy_probe": {"ok": True,
                         "results": {"https://www.amazon.com/dp/B0TEST":
                                     {"reason": "amazon_prohibited"}}},
    }
    assert h.check_redirect_recheck(evidence)["status"] == h.VERIFIED


def test_redirect_recheck_fails_without_the_post_action_recheck():
    evidence = {
        "pw_tool_js": "CURRENT page URL evaluateUrl(url, {})",
        "agent_loop_js": "no recheck here",
        "policy_probe": {"ok": True,
                         "results": {"https://www.amazon.com/dp/B0TEST":
                                     {"reason": "amazon_prohibited"}}},
    }
    point = h.check_redirect_recheck(evidence)
    assert point["status"] == h.FAILED
    assert "re-checks" in point["detail"]


# ── Point 5: audit journal ──────────────────────────────────────────────────

def test_audit_journal_verifies_types_sequence_urls_and_timestamps():
    point = h.check_audit_journal(_journal_records())
    assert point["status"] == h.VERIFIED, point["detail"]


def test_audit_journal_fails_when_a_secret_reaches_the_file():
    evidence = _journal_records()
    evidence["probe"]["records"].append(
        {"seq": 4, "ts": "2026-11-04T00:00:03Z", "type": "note",
         "password": "hunter2-not-a-real-secret"})
    point = h.check_audit_journal(evidence)
    assert point["status"] == h.FAILED
    assert "password" in point["detail"]


def test_audit_journal_fails_on_a_broken_sequence():
    evidence = _journal_records()
    evidence["probe"]["tool_seq"] = 1
    point = h.check_audit_journal(evidence)
    assert point["status"] == h.FAILED
    assert "sequence" in point["detail"]


def test_audit_journal_is_not_verified_when_the_probe_could_not_run():
    evidence = _journal_records(ok=False, reason="node_not_installed")
    point = h.check_audit_journal(evidence)
    assert point["status"] == h.NOT_VERIFIED


# ── Point 6: browser benchmark ──────────────────────────────────────────────

def test_benchmark_verifies_a_replay_plus_a_recorded_artifact():
    point = h.check_browser_benchmark({
        "replay": {"ran": True, "success": True, "steps": 2},
        "live_artifact": {"file": "x.md", "pass_rate": 0.667},
    })
    assert point["status"] == h.VERIFIED


def test_benchmark_fails_without_a_measured_artifact():
    point = h.check_browser_benchmark({
        "replay": {"ran": True, "success": True, "steps": 2},
        "live_artifact": None,
    })
    assert point["status"] == h.FAILED
    assert "artifact" in point["detail"]


def test_benchmark_is_not_verified_when_the_loop_replay_failed():
    point = h.check_browser_benchmark({
        "replay": {"ran": False, "reason": "fixture_missing"},
        "live_artifact": {"file": "x.md", "pass_rate": 0.667},
    })
    assert point["status"] == h.NOT_VERIFIED


# ── Controller discovery + whole-report behaviour ───────────────────────────

def test_resolve_controller_root_returns_none_when_nothing_matches(tmp_path):
    assert h.resolve_controller_root(str(tmp_path), env={}) is None


def test_resolve_controller_root_accepts_a_complete_layout(tmp_path):
    root = tmp_path / "controller"
    (root / "lib" / "chromecontrol").mkdir(parents=True)
    (root / "config").mkdir()
    (root / "lib" / "chromecontrol" / "policy.js").write_text("// policy", encoding="utf-8")
    (root / "config" / "chromecontrol.json").write_text("{}", encoding="utf-8")
    assert h.resolve_controller_root(str(root), env={}) == os.path.abspath(str(root))


def test_run_without_a_controller_reports_six_not_verified_and_never_a_pass():
    report = h.run(str(os.path.join(os.sep, "definitely", "not", "a", "controller")),
                   gather=True)
    assert report["controller_root"] is None
    assert [p["status"] for p in report["points"]] == [h.NOT_VERIFIED] * 6
    assert report["overall"] == h.NOT_VERIFIED
    assert "controller_not_found" in report["points"][0]["detail"]


def test_report_is_json_serialisable():
    report = h.run(None)  # discovers the live controller when present
    assert json.loads(json.dumps(report))["contract"] == "chrome_parity/v1"
    assert len(report["points"]) == 6
    assert report["overall"] in {"pass", h.FAILED, h.NOT_VERIFIED}
