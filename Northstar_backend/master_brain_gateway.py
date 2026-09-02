"""Master Brain Gateway — deterministic task classifier and append-only audit log.

Offline, additive-only. No LLM calls, no network calls. Pure rules-based
classification and JSONL audit logging.
"""

import json
import os
import re
from datetime import datetime, timezone
from typing import Dict, List, Optional

# Track taxonomy (mirrors shared/master-brain/constitution.json)
TRACKS = (
    "AUTOTHINK_RESEARCH",
    "AUTOTHINK_CODE",
    "AUTOTHINK_COMPUTER",
    "NORTHSTAR_OS_COMMERCE",
    "NORTHSTAR_OS_PROVIDER",
    "T2_OPERATIONS",
    "PLATFORM_ADMIN",
)

# Action-verb patterns (always win when matched — define the *what*)
ACTION_PATTERNS: Dict[str, List[re.Pattern]] = {
    "AUTOTHINK_CODE": [
        re.compile(r"\b(refactor|implement|fix|debug|patch|rewrite|reimplement|rework|harden)\b", re.I),
        re.compile(r"\bwrite\s+(a\s+)?(code|function|test|fixture|module|class)\b", re.I),
        re.compile(r"\badd\s+(a\s+)?(test|feature|method|function|class)\b", re.I),
        re.compile(r"\b(syntax|compilation|typing|code review)\b", re.I),
    ],
    "AUTOTHINK_COMPUTER": [
        # Explicit run/execute followed by a direct object (script/cli/tool/etc.)
        re.compile(r"\b(run|execute|launch|invoke|call)\s+(the|a|this|an)?\s*(script|cli|tool|command|process|tests?|pytest|unittest|backup|job)\b", re.I),
        # Run/execute at the start of a command (Run the X, Execute the X, Run X)
        re.compile(r"^(run|execute|launch)\s+(the|a|this|an)?\s*\w+", re.I),
        # File/directory operations
        re.compile(r"\b(copy|move|delete|rm|mkdir|ls|cat|grep|find|chmod|chown|reboot|shutdown|restart)\b", re.I),
    ],
    "AUTOTHINK_RESEARCH": [
        re.compile(r"\b(research|investigate|look\s+up|look\s+into|compare|benchmark|survey|study)\b", re.I),
        re.compile(r"\b(how\s+(to|does)|what\s+is|why\s+does|explain|describe|document|documentation)\b", re.I),
        re.compile(r"\b(analyz|analyse|review|assess|evaluate|examine|explore)\b", re.I),
        re.compile(r"\b(handle|process|manage)\b", re.I),
        re.compile(r"\b(check|verify|validate)\b", re.I),
    ],
}

# Domain-keyword patterns (define the *domain context*)
DOMAIN_PATTERNS: Dict[str, List[re.Pattern]] = {
    "PLATFORM_ADMIN": [
        re.compile(r"\b(deploy|wrangler|cloudflare|kv\s+binding|kv\s+namespace|secrets?\s+management|rotate\s+credentials?|monitor|alerts?|audit\s+log|retention)\b", re.I),
        re.compile(r"\b(infrastructure|access\s+control|permissions?|authn|authz|compliance\s+audit)\b", re.I),
    ],
    "NORTHSTAR_OS_PROVIDER": [
        re.compile(r"\b(bright\s*data|web\s+unlocker|rapidapi|easyparser|chocodata|unwrangle|dataforseo|scavio)\b", re.I),
        re.compile(r"\b(merchant\s+standard|amazon\s+(api|enrichment)|seller\s+(api|roster)|buy\s+box|provider\s+(api|integration|config|ttl|retention))\b", re.I),
        re.compile(r"\b(provider|providers|provider\s+enrichment|enrichment\s+cache)\b", re.I),
    ],
    "T2_OPERATIONS": [
        re.compile(r"\b(task\s+scheduler|scheduled\s+(task|run|job)|sunday\s+03:00|weekly\s+run|windows\s+task)\b", re.I),
        re.compile(r"\b(business\s+center\s+invoice|vendor\s+(management|compliance)|t2\s+holdings|costco\s+refresh)\b", re.I),
        re.compile(r"\b(billing|rate\s+limit|rate-limited|429|block|blocked|retry)\b", re.I),
    ],
    "NORTHSTAR_OS_COMMERCE": [
        re.compile(r"\b(pricing|margin|roi|profit|fee|economics|opportunity|replenish|tier|verdict)\b", re.I),
        re.compile(r"\b(costco\s+cost|cost\s+basis|pack\s+match|variant|product\s+fingerprint|bsr|demand\s+estimator|competition\s+analytics|portfolio\s+analytics|portfolio\s+readiness|profit\s+tier|economics\s+confidence)\b", re.I),
        re.compile(r"\b(portfolio|catalog|scanner)\b", re.I),
    ],
}

# Default audit log path (project-root relative)
_DEFAULT_AUDIT_LOG = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "shared", "master-brain", "audit.log.jsonl"
)


def classify_task(task_string: str) -> str:
    """Classify a task string into one of the seven tracks.

    Pure rules-based: action verb (what to do) takes priority; if no action
    verb matches, falls back to domain keyword (what area). No LLM, no network.

    Priority:
    1. Action-verb match: AUTOTHINK_CODE > AUTOTHINK_COMPUTER > AUTOTHINK_RESEARCH
    2. Domain match: PLATFORM_ADMIN > NORTHSTAR_OS_PROVIDER > T2_OPERATIONS > NORTHSTAR_OS_COMMERCE
    3. Fallback: AUTOTHINK_RESEARCH
    """
    if not isinstance(task_string, str) or not task_string.strip():
        return "AUTOTHINK_RESEARCH"  # safe default

    text = task_string.strip()

    # Phase 1: action verb (what to do)
    action_order = ["AUTOTHINK_CODE", "AUTOTHINK_COMPUTER", "AUTOTHINK_RESEARCH"]
    for track in action_order:
        for pattern in ACTION_PATTERNS.get(track, []):
            if pattern.search(text):
                return track

    # Phase 2: domain keyword (what area)
    domain_order = ["PLATFORM_ADMIN", "NORTHSTAR_OS_PROVIDER", "T2_OPERATIONS", "NORTHSTAR_OS_COMMERCE"]
    for track in domain_order:
        for pattern in DOMAIN_PATTERNS.get(track, []):
            if pattern.search(text):
                return track

    return "AUTOTHINK_RESEARCH"  # fallback


def write_audit_entry(
    track: str,
    files_touched: Optional[List[str]] = None,
    live_action_requested: bool = False,
    approval_status: str = "not_requested",
    metadata: Optional[Dict] = None,
    log_path: Optional[str] = None,
) -> str:
    """Append a single audit entry to the JSONL audit log.

    Returns the path written to. Never overwrites — always appends.
    Creates parent directories if needed.
    """
    if track not in TRACKS:
        raise ValueError(f"Invalid track: {track}. Must be one of {TRACKS}")

    log_path = log_path or _DEFAULT_AUDIT_LOG
    parent = os.path.dirname(log_path)
    if parent and not os.path.isdir(parent):
        os.makedirs(parent, exist_ok=True)

    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "track": track,
        "files_touched": files_touched or [],
        "live_action_requested": bool(live_action_requested),
        "approval_status": approval_status,  # not_requested | pending | approved | denied
        "metadata": metadata or {},
    }

    # Append directly to the log file. This preserves all prior entries
    # and never overwrites (open mode "a" creates if missing, appends otherwise).
    line = json.dumps(entry, ensure_ascii=False) + "\n"
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(line)

    return log_path


def read_audit_log(log_path: Optional[str] = None) -> List[Dict]:
    """Read all audit entries (newest last). Returns empty list if file missing.
    Skips individual corrupt lines."""
    log_path = log_path or _DEFAULT_AUDIT_LOG
    if not os.path.exists(log_path):
        return []
    entries = []
    try:
        with open(log_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    continue  # skip corrupt line
    except OSError:
        return []
    return entries


if __name__ == "__main__":
    # Quick self-test
    test_cases = [
        ("Research how BSR affects sales estimates", "AUTOTHINK_RESEARCH"),
        ("Fix the fee_engine.py bug in FBA calculation", "AUTOTHINK_CODE"),
        ("Run the costco catalog refresh script", "AUTOTHINK_COMPUTER"),
        ("Calculate ROI for ASIN B000000001 with costco cost 15.99", "NORTHSTAR_OS_COMMERCE"),
        ("Configure Bright Data Web Unlocker zone northstaros", "NORTHSTAR_OS_PROVIDER"),
        ("Schedule Sunday 03:00 Costco catalog refresh", "T2_OPERATIONS"),
        ("Deploy to Cloudflare Workers via wrangler", "PLATFORM_ADMIN"),
    ]
    print("=== Task Classifier Self-Test ===")
    for task, expected in test_cases:
        result = classify_task(task)
        status = "PASS" if result == expected else "FAIL"
        print(f"  {status}: '{task}' -> {result} (expected {expected})")

    # Audit log test
    print("\n=== Audit Log Self-Test ===")
    test_log = os.path.join(os.path.dirname(__file__), "test_audit.log.jsonl")
    try:
        if os.path.exists(test_log):
            os.remove(test_log)
        write_audit_entry("AUTOTHINK_CODE", files_touched=["test.py"], live_action_requested=False, approval_status="not_requested", log_path=test_log)
        write_audit_entry("NORTHSTAR_OS_COMMERCE", files_touched=["fee_engine.py"], live_action_requested=True, approval_status="pending", log_path=test_log)
        entries = read_audit_log(test_log)
        assert len(entries) == 2, f"Expected 2 entries, got {len(entries)}"
        assert entries[0]["track"] == "AUTOTHINK_CODE"
        assert entries[1]["track"] == "NORTHSTAR_OS_COMMERCE"
        assert entries[1]["live_action_requested"] is True
        print("  PASS: audit log writes and reads correctly (append-only)")
    finally:
        if os.path.exists(test_log):
            os.remove(test_log)