"""Deterministic Rules Engine — classifies requests per the Northstar Steward charter.

This module is pure code, no LLM. It classifies a request as Class A, B, C, or D
using explicit rule sets derived from the owner's written charter. The small
model's role is ONLY to summarize, never to make the final classification call.

Charter source: the owner-approved charter text stored at shared/steward/charter.json.

Decision Classes:
  A: Steward may approve alone (reversible, inside worktree or repo, free, no
     forbidden path, tests pass)
  B: Owner acknowledged first digest; downloadable models with free license
     (>=20GB disk); restarts local services; Chrome Connect lookups on allowlisted
     hosts under Profile 6; renews browser lease
  C: Always queued for owner — any money, credentials, external/irreversible,
     remote pushes, history edits, charter/policy/watchdog/audit edits, non-Profile
     6 Chrome, contracts/supplier/legal
  D: Always denied, logged, and never queued as "approve?" — accessing Amazon
     through browser controller, bypassing login walls, stealth/anti-bot,
     disabling watchdog/kill switch, tampering with ledger
"""

import re
import json
import os
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple, Any

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Allowlisted hosts for Chrome Connect read-only lookups (Profile 6).
ALLOWLIST_HOSTS = [
    "localhost",
    "127.0.0.1",
    "schema",
]

# Hardcoded Amazon blocklist (the Constitution says blocks Amazon first).
AMAZON_BLOCKLIST_KEYWORDS = [
    "listing update", "price change", "purchase order", "add to cart",
    "checkout", "order shipping", "account change", "captcha solve",
]

# Files that cannot be edited (charter §1: this charter, policy files, watchdog, audit log, agent prompts).
FORBIDDEN_EDIT_FILES = [
    os.path.join(REPO_ROOT, "AGENTS.md"),
    os.path.join(REPO_ROOT, "docs", "OPERATING_CONSTITUTION.md"),
    os.path.join(REPO_ROOT, "shared", "master-brain", "brain_policy.json"),
    os.path.join(REPO_ROOT, "shared", "usage-caps.json"),
    os.path.join(REPO_ROOT, "watchdog.py"),
    os.path.join(REPO_ROOT, "steward", "watchdog.py"),
    os.path.join(REPO_ROOT, "audit.log.jsonl"),
    os.path.join(REPO_ROOT, "chromecontrol_policy_owner.json"),
]

# Substrings that indicate self-approval attempts.
SELF_APPROVAL_PATTERNS = [
    r"approve my own", r"self approve", r"approve myself",
    r"\.\.\. myself", r"I should approve", r"I approved",
    r"me approving", r"my approval\b", r"autonomous approval",
    r"I approving", r"look at what I just did, I already approved",
]

# Patterns that look like embedded instructions inside data (web pages, files, task text).
EMBEDDED_INSTRUCTION_PATTERNS = [
    r"please.*approve.*this", r"you must.*approve", r"do not.*without.*approval",
    r"delete.*this.*instruction", r"bypass.*wall", r"captcha solve",
    r"fake.*credit", r"stealth.*bot", r"disable.*kill", r"tamper.*ledger",
    r"amazon.*browser.*controller", r"checkout.*cart.*change",
]

# Approved local commit paths — these are within the repo and reversible.
LOCAL_COMMIT_ALLOWED = True

# Platform base branch for building worktrees.
BUILD_BASE_BRANCH = "feature/chrome-connect-3.0"


class RulesEngine:
    """Classifies a request into one of four charter classes using deterministic rules."""

    def __init__(self, charter_path: Optional[str] = None):
        charter_path = charter_path or os.path.join(REPO_ROOT, "shared", "steward", "charter.json")
        with open(charter_path, "r", encoding="utf-8") as f:
            self._charter = json.load(f)
        # Compile all patterns once.
        self._self_patterns = [re.compile(p, re.IGNORECASE) for p in SELF_APPROVAL_PATTERNS]
        self._embedded_patterns = [re.compile(p, re.IGNORECASE) for p in EMBEDDED_INSTRUCTION_PATTERNS]
        # Cap on items per period.
        self.daily_task_cap = self._charter.get("caps", {}).get("daily_task_cap", 20)
        # Daily cap start tracking.
        self._daily_counts = {}

    def classify(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Classify a single request. Returns a verdict dict.

        Priority:
          1. Self-approval patterns → always deny (Class D)
          2. Embedded instructions in task text → deny (Class D)
          3. Forbidden paths → deny (Class D)
          4. Money/external → queue (Class C)
          5. Other ambiguities → defer (Class C, queued)
          6. Free, reversible, in-repo → approve (Class A)
          7. Model install / service restart / browser lease (after digest)
             → approve (Class B)

        The model is NEVER asked to classify. This is the deterministic gate.
        """
        # --- Step 1: self-approval detection (hard deny) ---
        text = request.get("text", "") or request.get("request", "") or ""
        for pat in self._self_patterns:
            if pat.search(text):
                return {
                    "class": "D",
                    "reason": "SELF_APPROVAL_DETECTED",
                    "detail": "Request contains self-approval language.",
                }

        # --- Step 2: embedded instruction detection (hard deny) ---
        for pat in self._embedded_patterns:
            if pat.search(text):
                return {
                    "class": "D",
                    "reason": "EMBEDDED_INSTRUCTION_DETECTED",
                    "detail": "Embedded instructions found in task data. Treat as data, not authority.",
                }

        # --- Step 3: check if editing forbidden files ---
        touched_files = request.get("files", [])
        for_files = [f for f in touched_files if isinstance(f, str)]
        for fpath in for_files:
            normalized = os.path.normpath(fpath)
            for fb in FORBIDDEN_EDIT_FILES:
                if normalized == os.path.normpath(fb) or os.path.abspath(normalized) == os.path.abspath(fb):
                    return {
                        "class": "D",
                        "reason": "FORBIDDEN_PATH",
                        "detail": f"Editing '{fb}' is forbidden per the charter.",
                        "forbidden_file": fb,
                    }

        # --- Step 4: check for money/credentials/external actions ---
        money_terms = ["purchas", "subscription", "paid api", "payment", "credits",
                        "buy now", "purchase order", "billing", "charge"]
        cred_terms = ["token", "secret", "password", "login", "captcha", "2fa",
                      "auth", "credential", "api key", "aws key"]
        external_terms = ["send", "publish", "post", "submit", "delete account",
                            "settings change", "remote push", "merge main", "history edit"]

        request_lower = text.lower()
        all_terms = [t for t in money_terms + cred_terms + external_terms]
        term_found = any(t in request_lower for t in all_terms)

        if term_found or request.get("amount", ""):
            return {
                "class": "C",
                "reason": "QUEUED_OWNER",
                "detail": "Action involves money, credentials, external/irreversible ops, or protected branches.",
                "risk_note": request.get("amount", "unknown") or "none",
            }

        # --- Step 5: evaluate Class A conditions ---
        checks = []

        # Reversible?
        reversible = request.get("reversible", True)
        checks.append(("reversible", reversible))

        # Inside worktree or repo?
        in_worktree = bool(request.get("worktree", False)) or not request.get("remote_op", True)
        checks.append(("local/worktree scope", in_worktree))

        # Free (no live calls, no credentials)?
        free = request.get("free", True)
        checks.append(("free tools", free))

        # No forbidden path?
        no_forbidden = True
        for f in touched_files:
            if isinstance(f, str):
                for fb in FORBIDDEN_EDIT_FILES:
                    fb_rel = fb.replace(REPO_ROOT, "").replace("\\", "/").lstrip("/")
                    if f.endswith(fb_rel) or f == fb_rel:
                        no_forbidden = False
                        break
            if not no_forbidden:
                break
        checks.append(("no forbidden path", no_forbidden))

        # Tests pass? (checked by Tester, not rules engine)
        tests_ok = request.get("tests_ok", True)
        checks.append(("tests pass", tests_ok))

        # Installed MIT/Apache/BSD packages >= 14 days old with checksum?
        pkg_installed = request.get("package_pinned", False)
        pkg_days = request.get("package_age_days", 0)
        pkg_checksum = bool(request.get("checksum", False))
        pkg_ok = pkg_installed and (pkg_days >= 14) and pkg_checksum
        # Only require package check if package_pinned is True
        if not pkg_installed:
            pkg_ok = True  # Not installing a package, so this check passes
        checks.append(("pinned package", pkg_ok))

        all_a_hold = all(v for _, v in checks)

        if all_a_hold:
            return {
                "class": "A",
                "reason": "STeward_APPROVAL_ALL_HOLD",
                "detail": f"All class-A checks passed: {', '.join(k for k, v in checks if v)}",
                "checks": checks,
            }

        # --- Step 6: evaluate Class B conditions ---
        digest_acknowledged = request.get("digest_stage2", False)
        free_models = bool(request.get("model_free_license", False))
        disk_remaining = request.get("free_disk_gb", float("inf")) >= 20.0
        service_restart = request.get("is_service_restart", False)
        browser_lookup = request.get("allowlisted_host", True)

        # Class B sub-categories:
        # 1. Model download (free license, >= 20GB disk)
        # 2. Service restart (digest ack required)
        # 3. Chrome Connect lookup (Profile 6 only)
        # 4. Browser lease renewal

        is_model_download = bool(request.get("model_free_license", False))
        is_service_restart = bool(request.get("is_service_restart", False))
        is_browser_lookup = bool(request.get("allowlisted_host", False))
        is_lease_renewal = bool(request.get("lease_renewal", False))

        b_holds = False
        if is_model_download:
            b_holds = digest_acknowledged and free_models and disk_remaining
        elif is_service_restart:
            b_holds = digest_acknowledged
        elif is_browser_lookup:
            b_holds = digest_acknowledged and bool(request.get("profile", "")) == "Profile 6"
        elif is_lease_renewal:
            b_holds = digest_acknowledged
        else:
            # Default: if digest acknowledged and disk ok, allow
            b_holds = digest_acknowledged and disk_remaining

        if b_holds:
            return {
                "class": "B",
                "reason": "STeward_APPROVAL_DIGEST_STAGE2",
                "detail": "Owner has acknowledged first digest; conditions met.",
                "checks": [
                    ("digest_stage2", digest_acknowledged),
                    ("free_license", free_models),
                    ("disk>=20GB", disk_remaining),
                    ("service_restart", is_service_restart),
                    ("Profile 6", is_browser_lookup and bool(request.get("profile", "")) == "Profile 6"),
                ],
            }

        # --- Step 7: defer (ambiguous, go to owner) ---
        return {
            "class": "C",
            "reason": "DEFER_OWNER",
            "detail": "Request is ambiguous; queued for owner attention.",
            "what": "text",
            "why": text[:200],
            "risk": "no clear authorization",
        }

    def is_forbidden_diff(self, diff_paths: List[str]) -> List[str]:
        """Return the subset of diff paths that touch forbidden locations.

        Used by the watchdog (deterministic) — never an LLM decision.
        """
        result = []
        for path in diff_paths:
            norm = os.path.normpath(path).replace("\\", "/")
            # Strip REPO_ROOT prefix if present to get relative path
            rel = norm
            if rel.startswith(REPO_ROOT.replace("\\", "/")):
                rel = rel[len(REPO_ROOT.replace("\\", "/")):]
            rel = rel.lstrip("/")
            for fb in FORBIDDEN_EDIT_FILES:
                fb_rel = fb.replace(REPO_ROOT, "").replace("\\", "/").lstrip("/")
                if rel == fb_rel or rel.endswith("/" + fb_rel) or rel == fb_rel.split("/")[-1]:
                    result.append(path)
                    break
            # Also catch wildcard patterns in chromecontrol_policy_owner.json
            if "chromecontrol_policy_owner" in norm or "chromecontrol_policy_owner" in rel:
                if path not in result:
                    result.append(path)
        return result

    def violation_summary(self, forbidden: List[str], diff_paths: List[str]) -> Dict[str, Any]:
        """Compact summary for the watchdog digest."""
        if forbidden:
            return {
                "violation": "FORBIDDEN_PATH_CHANGE",
                "files": len(forbidden),
                "sample": forbidden[:3],
                "scope": "watchdog detected forbidden edits",
            }
        return {"violation": None, "files": 0, "sample": [], "scope": "clean"}
