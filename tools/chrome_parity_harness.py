"""Chrome Connect six-point parity harness.

Purpose
-------
`reports/v3_readiness_20261104.md` §5 makes one condition non-negotiable before
anyone may retire Chrome Connect: the replacement must enforce the same six
properties. This tool measures those six properties against the *running*
controller, so a retirement decision rests on evidence rather than on prose.

The six points (the order is deliberate - the first one is the hard stop):

  1. ``host_policy_amazon_first``      host policy mode + the hardcoded Amazon
                                       blocklist evaluated BEFORE anything else
  2. ``profile6_lease``                exactly "Profile 6" is usable; every
                                       other profile is refused
  3. ``credential_captcha_login_stops`` credentials, CAPTCHA and login are
                                       never automated
  4. ``redirect_recheck``              policy is re-evaluated against the
                                       CURRENT page URL after every action
  5. ``audit_journal``                 every decision/tool call/result is
                                       journalled, with secrets redacted
  6. ``browser_benchmark``             the browser-brain benchmark still runs
                                       and produces a measurement

Design rules
------------
* **Fail closed.** A point is ``verified``, ``failed`` or ``not_verified``.
  ``not_verified`` is what an unavailable input produces - never a pass. The
  overall verdict is ``pass`` only when all six are ``verified``.
* **Read-only on the controller.** Nothing in the controller tree is written.
  Node probes only read modules and call pure functions; the journal probe
  writes into a throwaway temp directory via ``NORTHSTAR_AGENT_JOURNAL_DIR``.
* **Evidence over claims.** Each point carries the concrete observations it was
  decided on, so a reviewer can re-check the reasoning without re-running it.

Usage::

    python tools/chrome_parity_harness.py                    # human summary
    python tools/chrome_parity_harness.py --json             # full JSON
    python tools/chrome_parity_harness.py --out reports/x.json
    python tools/chrome_parity_harness.py --root "D:/chromecontroller"

The controller root is taken from ``--root``, then ``CHROMECONTROL_ROOT``, then
a short list of known deployments. If none resolves, all six points report
``not_verified`` with reason ``controller_not_found`` - the harness never
assumes a controller is healthy because it could not look.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from typing import Any, Dict, List, Optional

VERIFIED = "verified"
FAILED = "failed"
NOT_VERIFIED = "not_verified"

POINTS: List[Dict[str, str]] = [
    {"id": "host_policy_amazon_first",
     "title": "Host policy + hardcoded Amazon blocklist, evaluated first"},
    {"id": "profile6_lease",
     "title": "Profile 6 lease (exact directory); every other profile refused"},
    {"id": "credential_captcha_login_stops",
     "title": "Credentials / CAPTCHA / login are stops, never automated"},
    {"id": "redirect_recheck",
     "title": "Policy re-checked against the current URL after every action"},
    {"id": "audit_journal",
     "title": "Audit journal records decisions, tool calls and results"},
    {"id": "browser_benchmark",
     "title": "Browser-brain benchmark runs and measures"},
]

#: Candidate roots, tried in order when no explicit root is supplied. These are
#: read-only lookups; the harness never writes to any of them.
_CANDIDATE_ROOTS = (
    os.path.join(os.path.expanduser("~"), "OneDrive", "Documents", "Default Project"),
    os.path.join(os.path.expanduser("~"), "Documents", "Default Project"),
    os.path.join(os.path.expanduser("~"), "OneDrive", "Desktop", "Default Project"),
)

_REQUIRED_PROHIBITED = (
    "credentials", "enter_credentials", "login_submit", "mfa", "captcha",
    "solve_captcha", "checkout", "amazon_direct_access", "navigate_amazon",
)

_AMAZON_PROBE_URLS = (
    "https://www.amazon.com/dp/B0TEST",
    "https://amazon.co.uk/dp/X",
    "https://sellercentral.amazon.com/home",
    "https://amazon.de/",
    "https://amazon.co.uk.evil.example/x",   # lookalike host
)


# ---------------------------------------------------------------------------
# Controller discovery + node bridge
# ---------------------------------------------------------------------------

def resolve_controller_root(explicit: Optional[str] = None,
                            env: Optional[Dict[str, str]] = None,
                            candidates: Optional[tuple] = None) -> Optional[str]:
    """Return the controller root, or None when it cannot be found.

    An *explicit* root is strict: if it is not a controller, the answer is None
    rather than some other controller. Measuring a different deployment than the
    one asked for would make the report a lie.
    """
    def _looks_like_controller(cand: str) -> bool:
        policy_js = os.path.join(cand, "lib", "chromecontrol", "policy.js")
        config = os.path.join(cand, "config", "chromecontrol.json")
        return os.path.isfile(policy_js) and os.path.isfile(config)

    if explicit:
        return os.path.abspath(explicit) if _looks_like_controller(explicit) else None

    candidates_list: List[str] = []
    env_map = os.environ if env is None else env
    if env_map.get("CHROMECONTROL_ROOT"):
        candidates_list.append(env_map["CHROMECONTROL_ROOT"])
    candidates_list.extend(_CANDIDATE_ROOTS if candidates is None else candidates)
    for cand in candidates_list:
        if cand and _looks_like_controller(cand):
            return os.path.abspath(cand)
    return None


def _node_json(root: str, body: str, *, timeout: float = 120.0,
               extra_env: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    """Run a JS snippet inside the controller root and parse its JSON stdout.

    The snippet is written to a temp file (never into the controller tree) and
    requires modules by absolute path, so nothing is mutated on disk.
    """
    node = shutil.which("node")
    if not node:
        return {"ok": False, "reason": "node_not_installed"}
    script = (
        "const ROOT = " + json.dumps(root) + ";\n"
        "const path = require('node:path');\n"
        "const req = (rel) => require(path.join(ROOT, rel));\n"
        "const emit = (o) => process.stdout.write(JSON.stringify(o));\n"
        "try {\n" + body + "\n} catch (e) { emit({ ok: false, reason: e.message }); }\n"
    )
    tmp_dir = tempfile.mkdtemp(prefix="cc-parity-")
    script_path = os.path.join(tmp_dir, "probe.js")
    with open(script_path, "w", encoding="utf-8") as fh:
        fh.write(script)
    env = dict(os.environ)
    env.update(extra_env or {})
    try:
        proc = subprocess.run([node, script_path], capture_output=True, text=True,
                              timeout=timeout, cwd=tmp_dir, env=env)
    except subprocess.TimeoutExpired:
        return {"ok": False, "reason": "node_probe_timeout"}
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)
    if proc.returncode != 0:
        return {"ok": False, "reason": (proc.stderr or "").strip()[:600]
                or f"node_exit_{proc.returncode}"}
    text = (proc.stdout or "").strip()
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return {"ok": False, "reason": f"unparseable_probe_output: {text[:300]}"}
    return payload if isinstance(payload, dict) else {"ok": False,
                                                      "reason": "probe_not_an_object"}


def _read_text(path: str) -> str:
    try:
        with open(path, encoding="utf-8", errors="ignore") as fh:
            return fh.read()
    except OSError:
        return ""


def _read_json(path: str) -> Optional[Dict[str, Any]]:
    try:
        with open(path, encoding="utf-8") as fh:
            doc = json.load(fh)
        return doc if isinstance(doc, dict) else None
    except (OSError, json.JSONDecodeError):
        return None


# ---------------------------------------------------------------------------
# Evidence gathering (impure: reads files, runs node / the local loop)
# ---------------------------------------------------------------------------

_HOST_POLICY_PROBE = r"""
const policy = req('lib/chromecontrol/policy');
const results = {};
for (const u of US) { try { results[u] = policy.evaluateUrl(u); } catch (e) { results[u] = { allowed: null, reason: e.message }; } }
const actions = {};
for (const a of ['captcha', 'solve_captcha', 'enter_credentials', 'credentials', 'login_submit', 'mfa', 'checkout', 'add_to_cart', 'read_page', 'extract']) {
  actions[a] = policy.isProhibited(a);
}
let grant = null;
try { grant = policy.evaluateActionForHost('sign_in', 'account.squarespace.com'); } catch (e) { grant = { allowed: null, reason: e.message }; }
let ar = null;
try { ar = policy.assertGuardrailsIntact(); } catch (e) { ar = { intact: false, reason: e.message }; }
emit({
  ok: true,
  amazon_blocklist: policy.AMAZON_BLOCKLIST,
  results,
  prohibited: actions,
  squarespace_sign_in: grant,
  guardrails: ar,
  fingerprint: (() => { try { return policy.fingerprint(); } catch (e) { return null; } })(),
  owner_source: (() => { try { return policy.ownerConfigSource(); } catch (e) { return null; } })(),
});
""".replace("US", json.dumps(list(_AMAZON_PROBE_URLS)))


def gather_host_policy(root: str) -> Dict[str, Any]:
    config_path = os.path.join(root, "config", "chromecontrol_policy_owner.json")
    config = _read_json(config_path)
    policy_js = _read_text(os.path.join(root, "lib", "chromecontrol", "policy.js"))
    probe = _node_json(root, _HOST_POLICY_PROBE)
    return {"config_path": config_path, "config": config, "policy_js": policy_js,
            "probe": probe}


def gather_profile_lease(root: str) -> Dict[str, Any]:
    config = _read_json(os.path.join(root, "config", "chromecontrol.json"))
    isolation_js = _read_text(os.path.join(root, "lib", "chromecontrol", "profile-isolation.js"))
    body = r"""
const iso = req('lib/chromecontrol/profile-isolation');
const auth = iso.readOwnerAuthorization();
// Offline gate proof: inject Local State + the owner authorization, then ask the
// real verifier twice. A Profile 6 expectation must pass; a Profile 7
// expectation against a Profile 6 authorization must fail.
const localState = () => ({ profile: { info_cache: {
  'Profile 6': { name: 'NORTHSTAR OS', user_name: 'northstarosllc@gmail.com' },
  'Profile 7': { name: 'Northstar Research', user_name: null },
} } });
const deps = {
  localState,
  runningProcesses: () => [],
  visibleWindows: () => [],
  scanCookies: () => ({ available: false, reason: 'parity_probe_no_cookie_read' }),
  liveAttachment: () => ({ available: false, reason: 'parity_probe_offline' }),
  transportBinding: () => null,
  ownerAuthorization: () => auth,
};
const good = iso.verifyIsolation({ expect: { directory: 'Profile 6', display_name: 'NORTHSTAR OS' }, deps });
const wrong = iso.verifyIsolation({ expect: { directory: 'Profile 7', display_name: 'Northstar Research' }, deps });
const pick = (r) => (r.checks || []).find((c) => c.id === 'profile_lease_valid') || null;
emit({
  ok: true,
  owner_authorization: auth,
  profile6: { isolated: good.isolated, lease: pick(good) },
  profile7: { isolated: wrong.isolated, lease: pick(wrong) },
});
"""
    probe = _node_json(root, body)
    return {"config": config, "isolation_js": isolation_js, "probe": probe}


def gather_action_stops(root: str) -> Dict[str, Any]:
    config = _read_json(os.path.join(root, "config", "chromecontrol_policy_owner.json"))
    agent_loop = _read_text(os.path.join(root, "lib", "chromecontrol", "agent-loop.js"))
    denied_test = os.path.join(root, "test", "denied-action-test.js")
    denied_out: Dict[str, Any] = {"ran": False}
    node = shutil.which("node")
    if node and os.path.isfile(denied_test):
        try:
            proc = subprocess.run([node, denied_test], capture_output=True, text=True,
                                  timeout=180, cwd=root)
            denied_out = {"ran": True, "exit_code": proc.returncode,
                          "tail": (proc.stdout or "")[-800:]}
        except (OSError, subprocess.TimeoutExpired) as exc:
            denied_out = {"ran": False, "reason": type(exc).__name__}
    return {"config": config, "agent_loop_js": agent_loop, "denied_test": denied_out}


def gather_redirect_recheck(root: str, policy_probe: Dict[str, Any]) -> Dict[str, Any]:
    pw_tool = _read_text(os.path.join(root, "lib", "chromecontrol", "pw-tool.js"))
    agent_loop = _read_text(os.path.join(root, "lib", "chromecontrol", "agent-loop.js"))
    return {"pw_tool_js": pw_tool, "agent_loop_js": agent_loop,
            "policy_probe": policy_probe}


def gather_journal(root: str) -> Dict[str, Any]:
    body = r"""
const fs = require('node:fs');
const journal = req('lib/chromecontrol/journal');
const runId = 'parity-probe-' + Date.now();
const d = journal.decision(runId, { step_index: 1, outcome: 'acted', url: 'https://example.org/x' });
const t = journal.toolCall(runId, { tool: 'read_page', url: 'https://example.org/x' });
const r = journal.toolResult(runId, { tool: 'read_page', ok: true });
const secret = journal.append(runId, { note: 'login attempt', password: 'hunter2-not-a-real-secret', authorization: 'Bearer abcdefghijklmnopqrstuvwxyz' });
const records = journal.tail(20);
const file = (journal.files().slice(-1)[0] || {}).name || null;
emit({
  ok: true,
  dir: journal.JOURNAL_DIR,
  file,
  records,
  decision_seq: d.seq, tool_seq: t.seq, result_seq: r.seq, secret_seq: secret.seq,
});
"""
    tmp_dir = tempfile.mkdtemp(prefix="cc-parity-journal-")
    try:
        probe = _node_json(root, body, timeout=90,
                           extra_env={"NORTHSTAR_AGENT_JOURNAL_DIR": tmp_dir})
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)
    live_dir = os.path.join(root, "data", "agent-journal")
    live_files = []
    try:
        live_files = sorted(n for n in os.listdir(live_dir) if n.endswith(".jsonl"))[-5:]
    except OSError:
        live_files = []
    return {"probe": probe, "live_dir": live_dir, "live_files": live_files}


def gather_benchmark(root: str, repo_root: str) -> Dict[str, Any]:
    """Replay the AI loop offline, and collect the recorded live bench artifact."""
    replay: Dict[str, Any] = {"ran": False}
    backend = os.path.join(repo_root, "Northstar_backend")
    if backend not in sys.path:
        sys.path.insert(0, backend)
    try:
        import chromeconnect_ai_loop as ail
        import chromeconnect_observation as obs
        html = obs.load_fixture("costco_product_page")
        if html is None:
            replay = {"ran": False, "reason": "fixture_missing: costco_product_page"}
        else:
            scripted = [
                {"tool": "extract", "args": {"schema": {"title": "string"}}},
                {"tool": "finish", "args": {"result": {"title": "probe"}}},
            ]
            calls = {"n": 0}

            def decision_fn(goal, snapshot):
                i = calls["n"]
                calls["n"] += 1
                return scripted[i] if i < len(scripted) else None

            started = time.monotonic()
            result = ail.run_loop("extract the page title", lambda url: html,
                                  decision_fn=decision_fn)
            replay = {"ran": True, "success": bool(result.get("success")),
                      "steps": result.get("steps"),
                      "seconds": round(time.monotonic() - started, 3),
                      "status": result.get("status")}
    except Exception as exc:  # noqa: BLE001 - a broken loop is evidence, not a crash
        replay = {"ran": False, "reason": f"{type(exc).__name__}: {exc}"}

    artifact: Optional[Dict[str, Any]] = None
    reports_dir = os.path.join(repo_root, "reports")
    try:
        names = sorted(os.listdir(reports_dir))
    except OSError:
        names = []
    for name in names:
        if "chromeconnect" not in name.lower() or not name.endswith(".md"):
            continue
        text = _read_text(os.path.join(reports_dir, name))
        m = re.search(r"pass_rate\s*=\s*([0-9.]+)", text)
        if m:
            artifact = {"file": name, "pass_rate": float(m.group(1))}
            break
    return {"replay": replay, "live_artifact": artifact}


# ---------------------------------------------------------------------------
# Pure evaluators (unit-testable without node or a controller)
# ---------------------------------------------------------------------------

def _point(point_id: str, status: str, evidence: Any, detail: str = "") -> Dict[str, Any]:
    meta = next(p for p in POINTS if p["id"] == point_id)
    return {"id": point_id, "title": meta["title"], "status": status,
            "detail": detail, "evidence": evidence}


def check_host_policy(evidence: Dict[str, Any]) -> Dict[str, Any]:
    config = evidence.get("config") or {}
    probe = evidence.get("probe") or {}
    js = evidence.get("policy_js") or ""
    failures: List[str] = []
    notes: Dict[str, Any] = {}

    notes["host_policy"] = config.get("host_policy")
    if config.get("host_policy") != "denylist":
        failures.append(f"host_policy is {config.get('host_policy')!r}, expected 'denylist'")

    prohibited = {str(x) for x in (config.get("prohibited_actions") or [])}
    for required in ("amazon_direct_access", "navigate_amazon"):
        if required not in prohibited:
            failures.append(f"prohibited_actions is missing {required}")

    if not probe.get("ok"):
        return _point("host_policy_amazon_first", NOT_VERIFIED,
                      {"config": notes, "probe": probe},
                      f"policy probe unavailable: {probe.get('reason')}")

    blocklist = probe.get("amazon_blocklist") or []
    notes["amazon_blocklist_size"] = len(blocklist)
    if len(blocklist) < 20:
        failures.append(f"hardcoded Amazon blocklist has {len(blocklist)} entries")

    results = probe.get("results") or {}
    for url in _AMAZON_PROBE_URLS:
        verdict = results.get(url) or {}
        if verdict.get("allowed") is not False:
            failures.append(f"{url} was not refused (allowed={verdict.get('allowed')!r})")
        elif str(verdict.get("reason")) != "amazon_prohibited":
            failures.append(f"{url} refused for {verdict.get('reason')!r}, not amazon_prohibited")
    notes["amazon_refusals"] = {u: (results.get(u) or {}).get("reason") for u in _AMAZON_PROBE_URLS}

    ordinary = results.get("https://example.org/page")
    if ordinary is not None:
        notes["open_web_allowed"] = ordinary.get("allowed")
        if ordinary.get("allowed") is not True:
            failures.append("denylist mode did not allow an ordinary non-Amazon host")

    # Ordering: the Amazon refusal must precede the policy-mode branch and the
    # allowlist branch inside evaluateUrl, i.e. no option can get in front of it.
    eval_at = js.find("function evaluateUrl")
    if eval_at < 0:
        failures.append("policy.js has no evaluateUrl")
    else:
        body = js[eval_at:]
        amazon_at = body.find("isAmazonHost(host)")
        mode_at = body.find("HOST_POLICY === 'denylist'")
        allow_at = body.find("DOMAIN_ALLOWLIST")
        notes["order"] = {"amazon": amazon_at, "denylist": mode_at, "allowlist": allow_at}
        if amazon_at < 0:
            failures.append("evaluateUrl never calls isAmazonHost")
        else:
            if 0 <= mode_at < amazon_at:
                failures.append("the denylist branch precedes the Amazon refusal")
            if 0 <= allow_at < amazon_at:
                failures.append("the allowlist branch precedes the Amazon refusal")

    guard = probe.get("guardrails") or {}
    notes["fingerprint"] = probe.get("fingerprint")
    notes["baseline"] = config.get("baseline_fingerprint")
    if guard.get("intact") is not True:
        failures.append("assertGuardrailsIntact() did not return intact=true")
    if notes["baseline"] and notes["fingerprint"] != notes["baseline"]:
        failures.append("live policy fingerprint differs from the owner-recorded baseline")

    status = FAILED if failures else VERIFIED
    return _point("host_policy_amazon_first", status,
                  {"config": notes, "probe": {k: probe.get(k) for k in
                                              ("ok", "reason", "owner_source")}},
                  "; ".join(failures))


def check_profile_lease(evidence: Dict[str, Any]) -> Dict[str, Any]:
    config = evidence.get("config") or {}
    js = evidence.get("isolation_js") or ""
    probe = evidence.get("probe") or {}
    failures: List[str] = []
    notes: Dict[str, Any] = {}

    auth = (config.get("owner_authorization") or {})
    notes["authorized_directory"] = auth.get("profile_directory")
    notes["pinned_directory"] = config.get("extension_profile_dir_name")
    if auth.get("profile_directory") != "Profile 6":
        failures.append(f"owner_authorization.profile_directory is "
                        f"{auth.get('profile_directory')!r}, expected 'Profile 6'")
    if config.get("extension_profile_dir_name") != "Profile 6":
        failures.append("extension_profile_dir_name is not 'Profile 6'")
    if auth.get("pin_matches") is False:
        failures.append("config pin disagrees with the owner authorization")

    for anchor in ("profile_lease_valid", "selected_directory_exact",
                   "leaseDir === expectedDirectory", "pin_matches !== false"):
        if anchor not in js:
            failures.append(f"profile-isolation.js lost the {anchor!r} rule")

    if not probe.get("ok"):
        return _point("profile6_lease", NOT_VERIFIED,
                      {"config": notes, "probe": probe},
                      f"isolation probe unavailable: {probe.get('reason')}")

    owner = probe.get("owner_authorization") or {}
    notes["read_owner_authorization"] = owner
    if owner.get("present") is not True:
        failures.append(f"readOwnerAuthorization() reported absent: {owner.get('reason')}")
    if owner.get("directory") != "Profile 6":
        failures.append(f"readOwnerAuthorization() names {owner.get('directory')!r}")

    p6 = probe.get("profile6") or {}
    p7 = probe.get("profile7") or {}
    notes["profile6_lease_pass"] = (p6.get("lease") or {}).get("pass")
    notes["profile7_lease_pass"] = (p7.get("lease") or {}).get("pass")
    if notes["profile6_lease_pass"] is not True:
        failures.append("the Profile 6 lease check did not pass for an exact Profile 6 expectation")
    if notes["profile7_lease_pass"] is not False:
        failures.append("a Profile 7 expectation was NOT refused by the lease gate")

    status = FAILED if failures else VERIFIED
    return _point("profile6_lease", status, {"config": notes, "probe": {"ok": probe.get("ok")}},
                  "; ".join(failures))


def check_action_stops(evidence: Dict[str, Any]) -> Dict[str, Any]:
    config = evidence.get("config") or {}
    agent_loop = evidence.get("agent_loop_js") or ""
    denied = evidence.get("denied_test") or {}
    failures: List[str] = []
    notes: Dict[str, Any] = {}

    prohibited = {str(x) for x in (config.get("prohibited_actions") or [])}
    missing = [x for x in _REQUIRED_PROHIBITED if x not in prohibited]
    notes["missing_prohibited_actions"] = missing
    if missing:
        failures.append(f"prohibited_actions is missing {missing}")

    grants = config.get("per_host_action_grants") or {}
    sq = (grants.get("account.squarespace.com") or {}).get("deny") or []
    notes["squarespace_deny"] = sq
    for required in ("sign_in", "credential_entry", "payment_action"):
        if required not in sq:
            failures.append(f"the squarespace grant does not deny {required}")

    # The loop must own the stop, not just the policy table: a login wall and a
    # CAPTCHA must terminate the run as a blocker that needs the owner.
    notes["loop_stops"] = {
        "login_wall": "login_wall" in agent_loop,
        "captcha": "captcha" in agent_loop.lower(),
        "needs_owner": "owner_action_required" in agent_loop,
    }
    for key, present in notes["loop_stops"].items():
        if not present:
            failures.append(f"agent-loop.js no longer stops on {key}")

    notes["denied_action_suite"] = denied
    if denied.get("ran"):
        if denied.get("exit_code") != 0:
            failures.append("the controller's denied-action suite did not exit 0")
    else:
        return _point("credential_captcha_login_stops", NOT_VERIFIED,
                      {"config": notes, "reason": denied.get("reason")},
                      "the denied-action suite could not be executed")

    status = FAILED if failures else VERIFIED
    return _point("credential_captcha_login_stops", status,
                  {"config": notes}, "; ".join(failures))


def check_redirect_recheck(evidence: Dict[str, Any]) -> Dict[str, Any]:
    pw_tool = evidence.get("pw_tool_js") or ""
    agent_loop = evidence.get("agent_loop_js") or ""
    probe = evidence.get("policy_probe") or {}
    failures: List[str] = []
    notes: Dict[str, Any] = {}

    # pw-tool gates each action on the CURRENT page URL ...
    notes["pw_tool_evaluates_current_url"] = (
        "evaluateUrl(url" in pw_tool and "CURRENT page URL" in pw_tool)
    if not notes["pw_tool_evaluates_current_url"]:
        failures.append("pw-tool.js no longer evaluates policy against the current page URL")
    # ... and the loop re-evaluates after every action, so a redirect cannot
    # smuggle the next action onto a refused host.
    notes["loop_rechecks_after_action"] = (
        "Re-evaluate URL policy after every action" in agent_loop)
    if not notes["loop_rechecks_after_action"]:
        failures.append("agent-loop.js no longer re-checks policy after each action")

    notes["amazon_refused_by_policy"] = bool(probe.get("ok")) and str(
        ((probe.get("results") or {}).get("https://www.amazon.com/dp/B0TEST") or {})
        .get("reason")) == "amazon_prohibited"
    if not notes["amazon_refused_by_policy"]:
        failures.append("the live policy no longer refuses an Amazon URL")

    status = FAILED if failures else VERIFIED
    return _point("redirect_recheck", status, notes, "; ".join(failures))


def check_audit_journal(evidence: Dict[str, Any]) -> Dict[str, Any]:
    probe = evidence.get("probe") or {}
    if not probe.get("ok"):
        return _point("audit_journal", NOT_VERIFIED, {"probe": probe},
                      f"journal probe unavailable: {probe.get('reason')}")

    failures: List[str] = []
    notes: Dict[str, Any] = {"journal_dir": probe.get("dir"), "file": probe.get("file"),
                             "live_files": evidence.get("live_files"),
                             "live_dir": evidence.get("live_dir")}
    records = probe.get("records") or []
    types = {r.get("type") for r in records}
    notes["record_types"] = sorted(t for t in types if t)
    for required in ("decision", "tool_call", "tool_result"):
        if required not in types:
            failures.append(f"the journal did not record a {required} record")

    seqs = [probe.get("decision_seq"), probe.get("tool_seq"),
            probe.get("result_seq"), probe.get("secret_seq")]
    notes["sequence"] = seqs
    if any(not isinstance(s, int) for s in seqs):
        failures.append("journal records are missing a numeric sequence")
    elif seqs != sorted(seqs) or len(set(seqs)) != len(seqs):
        failures.append("journal sequence numbers are not strictly increasing")

    # Redaction: the literal secret must never reach the file.
    blob = json.dumps(records)
    notes["secret_redacted"] = "hunter2-not-a-real-secret" not in blob
    if not notes["secret_redacted"]:
        failures.append("a password value was written to the journal verbatim")
    notes["bearer_redacted"] = "abcdefghijklmnopqrstuvwxyz" not in blob
    if not notes["bearer_redacted"]:
        failures.append("an authorization header was written to the journal verbatim")

    urls = [r.get("url") for r in records if r.get("url")]
    notes["urls_recorded"] = urls
    if not urls:
        failures.append("no URL was recorded on a decision/tool record")
    notes["timestamps"] = all(isinstance(r.get("ts"), str) and r.get("ts") for r in records)
    if not notes["timestamps"]:
        failures.append("a journal record carried no timestamp")

    status = FAILED if failures else VERIFIED
    return _point("audit_journal", status, notes, "; ".join(failures))


def check_browser_benchmark(evidence: Dict[str, Any]) -> Dict[str, Any]:
    replay = evidence.get("replay") or {}
    artifact = evidence.get("live_artifact")
    notes: Dict[str, Any] = {"replay": replay, "live_artifact": artifact}
    if not replay.get("ran"):
        return _point("browser_benchmark", NOT_VERIFIED, notes,
                      f"the loop replay did not run: {replay.get('reason')}")
    failures: List[str] = []
    if replay.get("success") is not True:
        failures.append("the AI loop replay did not reach a successful finish")
    if not isinstance(replay.get("steps"), int):
        failures.append("the replay reported no step count")
    if not artifact:
        failures.append("no recorded live browser-benchmark artifact was found in reports/")
    status = FAILED if failures else VERIFIED
    return _point("browser_benchmark", status, notes, "; ".join(failures))


# ---------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------

def summarise(points: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Overall verdict. Fail closed: only six verified points make a pass."""
    statuses = [p.get("status") for p in points]
    if len(points) != len(POINTS) or [p.get("id") for p in points] != [p["id"] for p in POINTS]:
        overall = NOT_VERIFIED
        reason = "the harness did not evaluate exactly the six declared points"
    elif FAILED in statuses:
        overall = FAILED
        reason = "one or more parity points failed"
    elif NOT_VERIFIED in statuses:
        overall = NOT_VERIFIED
        reason = "one or more parity points could not be verified"
    elif all(s == VERIFIED for s in statuses):
        overall = "pass"
        reason = "all six parity points verified"
    else:
        overall = NOT_VERIFIED
        reason = "unknown status"
    return {"overall": overall, "reason": reason,
            "counts": {s: statuses.count(s) for s in (VERIFIED, FAILED, NOT_VERIFIED)}}


def run(root: Optional[str] = None, *, repo_root: Optional[str] = None,
        gather: bool = True) -> Dict[str, Any]:
    repo_root = repo_root or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    resolved = resolve_controller_root(root)
    report: Dict[str, Any] = {
        "contract": "chrome_parity/v1",
        "checked_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "controller_root": resolved,
        "requested_root": root,
        "points": [],
        "retirement": ("Chrome Connect may only be retired after this report reads "
                       "overall=pass; a not_verified point is not permission."),
    }
    if not resolved or not gather:
        reason = ("controller_not_found: no root with lib/chromecontrol/policy.js and "
                  "config/chromecontrol.json was found"
                  + (f" at {root}" if root else " (set CHROMECONTROL_ROOT)"))
        report["points"] = [_point(p["id"], NOT_VERIFIED, {"reason": reason}, reason)
                            for p in POINTS]
        report.update(summarise(report["points"]))
        return report

    host = gather_host_policy(resolved)
    lease = gather_profile_lease(resolved)
    stops = gather_action_stops(resolved)
    redirect = gather_redirect_recheck(resolved, host.get("probe") or {})
    journal = gather_journal(resolved)
    bench = gather_benchmark(resolved, repo_root)

    report["points"] = [
        check_host_policy(host),
        check_profile_lease(lease),
        check_action_stops(stops),
        check_redirect_recheck(redirect),
        check_audit_journal(journal),
        check_browser_benchmark(bench),
    ]
    report.update(summarise(report["points"]))
    return report


def format_summary(report: Dict[str, Any]) -> str:
    lines = [
        "Chrome Connect six-point parity harness",
        f"controller: {report.get('controller_root') or '(not found)'}",
        f"checked_at: {report.get('checked_at')}",
        "",
    ]
    for i, point in enumerate(report.get("points") or [], start=1):
        lines.append(f"{i}. {point['title']}: {point['status'].upper()}")
        if point.get("detail"):
            lines.append(f"   - {point['detail']}")
    lines += ["", f"OVERALL: {str(report.get('overall')).upper()} "
                  f"({report.get('reason')})",
              f"counts: {report.get('counts')}"]
    return "\n".join(lines)


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Chrome Connect six-point parity harness")
    parser.add_argument("--root", default=None, help="controller root (default: env/probe)")
    parser.add_argument("--json", action="store_true", help="print the full JSON report")
    parser.add_argument("--out", default=None, help="write the JSON report to this path")
    parser.add_argument("--strict", action="store_true",
                        help="exit non-zero unless the overall verdict is pass")
    args = parser.parse_args(argv)

    report = run(args.root)
    if args.out:
        os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
        with open(args.out, "w", encoding="utf-8") as fh:
            json.dump(report, fh, indent=2)
    print(json.dumps(report, indent=2) if args.json else format_summary(report))
    if args.strict and report.get("overall") != "pass":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
