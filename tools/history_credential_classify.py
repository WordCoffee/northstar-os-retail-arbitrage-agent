"""Classify the credential-shaped history findings: localhost/fixture vs real host.

Counts only. No user, password, token, address or line ever leaves this script — the report
carries integers and, for credential URLs only, the **hostname**, because a rotation action
that does not name the host is not actionable. No path, no query, no user info.

What it reads: every line added on any ref (`git log --all -p --unified=0`), the same stream
`tools/history_sensitive_scan.py` uses, so the two reports are comparable.

Classes:

* `dev_credential_url` → the authority's host is `localhost`, a reserved/example host, or a real host.
* `dev_credential_assignment` → the line also names a real host / a local host / neither, and the
  value is a code reference (`os.environ`, `getenv`, an f-string) or a literal.
* `email` → owner / business / third-party personal, by domain and by the owner's own handles.
* `phone` → US/CA vs international, plus `business` when the same line names a vendor, `owner` when
  it names the owner's brand. Anything else is `unattributed`, because digits alone cannot say whose
  number it is and this report will not pretend otherwise.

    python tools/history_credential_classify.py --write
    python tools/history_credential_classify.py --json
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
from collections import Counter
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "reports" / "ty" / "history_credential_classes.json"
REPORT = ROOT / "reports" / "ty" / "history_credential_classes.md"

BASIC_AUTH_URL = re.compile(r"[a-zA-Z][a-zA-Z0-9+.\-]*://[^/\s:@]{1,64}:[^/\s@]{1,64}@[^\s'\"]*")
DEV_SECRET = re.compile(r"(?i)\b(password|passwd|pwd|secret|token)\s*[:=]\s*([^\s'\"]{4,})")
EMAIL = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
MACHINE_EMAIL = re.compile(r"(?i)(noreply|no-reply|example\.(com|org)|users\.noreply\.github\.com|"
                           r"localhost|@example)")
PHONE_E164 = re.compile(r"(?<![\d+])\+[1-9]\d{8,14}(?!\d)")
PHONE_US = re.compile(r"(\(\d{3}\)\s*\d{3}[-. ]\d{4}|(?<!\d)\d{3}-\d{3}-\d{4}(?!\d))")

HOST_IN_LINE = re.compile(r"https?://([A-Za-z0-9.\-]+\.[A-Za-z]{2,}|localhost|127\.0\.0\.1)")

LOCAL_HOSTS = {"localhost", "127.0.0.1", "0.0.0.0", "::1", "host.docker.internal"}
#: Hosts that appear in documentation and connection-string examples. They are not endpoints;
#: counting them as "real" would manufacture a rotation task for a placeholder.
DOC_PLACEHOLDER_HOSTS = {
    "host", "host.com", "dbhost", "postgres", "mysql", "redis", "mongo", "bar.com", "foo.com",
    "proxy-host", "myhost", "yourhost", "server", "db", "database", "internal", "prod-db.internal",
    "smtp", "mail", "api", "www",
}
FIXTURE_HOSTS = {
    "example.com", "example.org", "example.net", "test.com", "test.local", "dummy.com",
    "fake.com", "mock.com", "placeholder.com", "your-domain.com", "yourdomain.com",
}
FIXTURE_VALUES = re.compile(r"(?i)^(?:changeme|change-me|your[_-]?|xxx+|\*+|redacted|placeholder|"
                            r"<[^>]+>|dummy|test|secret|token|password|none|null|todo)")
CODE_VALUE = re.compile(r"(?i)(os\.environ|getenv|settings\.|config\.|secrets\.|env\[|\$\{|%s|\{[a-z_]+\}|"
                        r"process\.env|localStorage|sessionStorage|getItem|\(|\[|=>|\.get\(|"
                        r"import\.meta|self\.|this\.|Boolean|str\(|int\(|float\()")

OWNER_HANDLES = ("wordcoffee", "word-coffee", "northstar", "t2holdings", "t2-holdings", "mogra",
                 "tyrone", "lionsmane", "lions-mane", "necknirvana", "neck-nirvana")
BUSINESS_DOMAINS = {
    "costco.com", "brightdata.com", "brightdata.io", "scavio.com", "unwrangle.com", "chocodata.com",
    "easyparser.com", "canopy.co", "keepa.com", "faire.com", "packify.ai", "pacdora.com",
    "openwebninja.com", "rapidapi.com", "dataforseo.com", "ultralytics.com", "openai.com",
    "anthropic.com", "comfyui.com", "amazon.com", "shopify.com", "stripe.com", "github.com",
}
FREE_MAIL = {"gmail.com", "yahoo.com", "hotmail.com", "outlook.com", "aol.com", "icloud.com",
             "proton.me", "protonmail.com", "live.com", "msn.com", "me.com", "gmx.com"}
VENDOR_NAMES = ("costco", "amazon", "brightdata", "bright data", "scavio", "unwrangle", "chocodata",
                "easyparser", "canopy", "keepa", "faire", "packify", "pacdora", "openwebninja",
                "rapidapi", "dataforseo", "ultralytics", "openai", "anthropic", "comfyui",
                "wordcoffee", "word coffee", "northstar", "mogra")


def host_class(host: str) -> str:
    host = (host or "").lower().strip(".")
    if not host:
        return "unparsed"
    if host in LOCAL_HOSTS:
        return "localhost"
    if host in FIXTURE_HOSTS or host.endswith((".test", ".local", ".example")) or host.endswith("example.com"):
        return "fixture"
    if host in DOC_PLACEHOLDER_HOSTS or "." not in host:
        return "doc_placeholder"
    return "real_host"


def classify_url(url: str) -> tuple[str, str]:
    try:
        parts = urlsplit(url)
        host = parts.hostname or ""
    except ValueError:
        return "unparsed", ""
    return host_class(host), (host or "").lower()


def classify_assignment_line(line: str) -> tuple[str, str]:
    host_match = HOST_IN_LINE.search(line)
    if host_match:
        kind = host_class(host_match.group(1))
        return "with_" + kind, host_match.group(1).lower()
    match = DEV_SECRET.search(line)
    if not match:
        return "unparsed", ""
    value = match.group(2).strip().strip("'\"")
    if CODE_VALUE.search(value):
        return "no_host_code_reference", ""
    if FIXTURE_VALUES.match(value):
        return "no_host_placeholder", ""
    return "no_host_literal", ""


def classify_email(address: str) -> str:
    low = address.lower()
    _, _, domain = low.partition("@")
    if MACHINE_EMAIL.search(low):
        return "machine"
    if any(handle in low for handle in OWNER_HANDLES):
        return "owner"
    if domain in BUSINESS_DOMAINS or domain.endswith(tuple("." + d for d in BUSINESS_DOMAINS)):
        return "business"
    if domain in FREE_MAIL:
        return "third_party_personal"
    return "business_or_vendor"


def classify_phone(line: str) -> str:
    low = line.lower()
    if any(name in low for name in OWNER_HANDLES):
        return "owner"
    if any(name in low for name in VENDOR_NAMES):
        return "business"
    if PHONE_E164.search(line):
        return "international_unattributed"
    return "us_ca_unattributed"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--json", action="store_true")
    ns = parser.parse_args(argv)

    command = ["git", "log", "--all", "-p", "--unified=0", "--no-color", "--no-textconv"]
    commits = subprocess.run(["git", "rev-list", "--all"], cwd=str(ROOT),
                             capture_output=True, text=True, encoding="utf-8",
                             errors="replace").stdout.split()
    refs = subprocess.run(["git", "for-each-ref", "--format=%(refname)"], cwd=str(ROOT),
                          capture_output=True, text=True, encoding="utf-8",
                          errors="replace").stdout.split()

    url_classes: Counter = Counter()
    url_hosts: Counter = Counter()
    assignment_classes: Counter = Counter()
    email_classes: Counter = Counter()
    phone_classes: Counter = Counter()
    commit_hits: Counter = Counter()

    process = subprocess.Popen(command, cwd=str(ROOT), stdout=subprocess.PIPE,
                               stderr=subprocess.DEVNULL, text=True, encoding="utf-8",
                               errors="replace")
    assert process.stdout
    seen: set = set()
    for raw in process.stdout:
        if raw.startswith("commit "):
            sha = raw.split()[1] if len(raw.split()) > 1 else ""
            seen = set()
            current = sha
            continue
        if not raw.startswith("+") or raw.startswith("+++"):
            continue
        line = raw[1:]

        hits: list[tuple[str, str]] = []
        for match in BASIC_AUTH_URL.findall(line):
            kind, host = classify_url(match)
            hits.append(("url", kind))
            url_classes[kind] += 1
            if kind == "real_host" and host:
                url_hosts[host] += 1
        for _ in DEV_SECRET.findall(line):
            kind, host = classify_assignment_line(line)
            hits.append(("assignment", kind))
            assignment_classes[kind] += 1
            if kind == "with_real_host" and host:
                url_hosts[f"assignment-line:{host}"] += 1
        for address in EMAIL.findall(line):
            kind = classify_email(address)
            hits.append(("email", kind))
            email_classes[kind] += 1
        for _ in PHONE_E164.findall(line) + PHONE_US.findall(line):
            kind = classify_phone(line)
            hits.append(("phone", kind))
            phone_classes[kind] += 1

        for category, kind in hits:
            key = f"{category}:{kind}"
            if key not in seen:
                seen.add(key)
                commit_hits[key] += 1
    process.stdout.close()
    process.wait()

    result = {
        "refs": len(refs), "commits": len(commits),
        "credential_url": dict(sorted(url_classes.items())),
        "credential_url_real_hosts": dict(sorted(url_hosts.items())),
        "credential_assignment": dict(sorted(assignment_classes.items())),
        "email": dict(sorted(email_classes.items())),
        "phone": dict(sorted(phone_classes.items())),
        "commits_containing": dict(sorted(commit_hits.items())),
        "note": "counts only; the only strings recorded are hostnames for real-host credential URLs",
    }

    if ns.write:
        OUT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        lines = ["# Credential-shaped history: localhost/fixture vs real host", "",
                 f"{len(commits):,} commits across {len(refs)} refs, every added line read.",
                 "Counts only. No user, password, token, address or line is printed. The only strings "
                 "recorded are hostnames, and only for a credential URL that reaches a real host — "
                 "a rotation action that does not name the host is not actionable.", "",
                 "## Credential URLs (88 expected)", "",
                 "| class | occurrences |", "|---|---|"]
        for key, value in result["credential_url"].items():
            lines.append(f"| `{key}` | {value} |")
        lines += ["", "### Real hosts carrying a user:pass URL", "",
                  "| host | occurrences |", "|---|---|"]
        if result["credential_url_real_hosts"]:
            for host, value in result["credential_url_real_hosts"].items():
                lines.append(f"| `{host}` | {value} |")
        else:
            lines.append("| — | 0 |")
        lines += ["", "## Credential assignments (535 expected)", "",
                  "| class | occurrences |", "|---|---|"]
        for key, value in result["credential_assignment"].items():
            lines.append(f"| `{key}` | {value} |")
        lines += ["", "## Non-machine emails (674 expected)", "", "| class | occurrences |", "|---|---|"]
        for key, value in result["email"].items():
            lines.append(f"| `{key}` | {value} |")
        lines += ["", "## Phones (319 expected)", "", "| class | occurrences |", "|---|---|"]
        for key, value in result["phone"].items():
            lines.append(f"| `{key}` | {value} |")
        lines += ["", "`unattributed` is deliberate: a phone number carries no owner. It is only "
                  "attributed when the same line names a brand (`business`) or the owner's own handle "
                  "(`owner`). Anything else stays unattributed rather than guessed.", ""]
        REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")

    if ns.json or not ns.write:
        print(json.dumps(result, indent=2))
    else:
        print(json.dumps({k: v for k, v in result.items() if k != "commits_containing"}, indent=2))
        print("report:", REPORT.relative_to(ROOT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
