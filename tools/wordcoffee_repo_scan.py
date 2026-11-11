"""Counts-only scan of the other public WordCoffee GitHub repos.

Never prints a value. For each repo it records: visibility, size, Pages hosting, the
number of tracked files, and how many *shapes* of sensitive string appear (credential
assignment, credential URL, private-key header, tokens, email, phone). A count is the
only thing that leaves this script; the matching text is discarded with the buffer.

It clones each repo shallow (no API rate limit, no authentication, nothing written back)
and reads only text files under 400 KB. GitHub Pages is detected from the API when the
budget allows and from the presence of a Pages-shaped branch/folder + CNAME when it does
not, and the report says which method produced the answer.

    python tools/wordcoffee_repo_scan.py            # scan + write report
    python tools/wordcoffee_repo_scan.py --json     # machine-readable only

No authentication, no writes to GitHub, no Amazon host anywhere.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

API = "https://api.github.com"
OWNER = "WordCoffee"
SKIP = {"northstar-os-retail-arbitrage-agent"}  # this repo; scanned separately

#: Shapes only. Each entry is (class, compiled pattern). No value is ever captured.
PATTERNS = [
    ("private_key_header", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----")),
    ("github_token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b")),
    ("aws_key_id", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("slack_token", re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}\b")),
    ("stripe_key", re.compile(r"\b[sr]k_(?:live|test)_[A-Za-z0-9]{10,}\b")),
    ("generic_secret", re.compile(
        r"(?i)\b(?:api[_-]?key|secret|token|passwd|password)\b\s*[:=]\s*['\"]?[A-Za-z0-9_\-]{12,}")),
    ("credential_url", re.compile(r"[a-z][a-z0-9+.-]*://[^/\s:@]{1,40}:[^/\s@]{1,40}@[^\s]+", re.I)),
    ("email", re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")),
    ("phone", re.compile(r"(?<!\d)(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]\d{3}[-.\s]\d{4}(?!\d)")),
]

SECRET_CLASSES = ("private_key_header", "github_token", "aws_key_id", "slack_token",
                  "stripe_key", "generic_secret", "credential_url")

TEXT_SUFFIXES = {
    ".md", ".txt", ".json", ".js", ".jsx", ".ts", ".tsx", ".py", ".html", ".htm",
    ".css", ".scss", ".yml", ".yaml", ".toml", ".ini", ".cfg", ".conf", ".env",
    ".example", ".sh", ".ps1", ".bat", ".sql", ".csv", ".xml", ".svg", ".php", ".rb",
}
MAX_BYTES = 400_000


def api(url: str):
    request = urllib.request.Request(url, headers={"User-Agent": "northstar-ty-scan",
                                                   "Accept": "application/vnd.github+json"})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8", "replace"))
    except urllib.error.HTTPError as exc:
        if exc.code in (403, 404, 409, 451):
            return None
        raise


def clone(name: str, branch: str, dest: Path) -> bool:
    remote = f"https://github.com/{OWNER}/{name}.git"
    proc = subprocess.run(
        ["git", "clone", "--depth", "1", "--branch", branch, "--quiet", remote, str(dest)],
        capture_output=True, text=True, timeout=300)
    return proc.returncode == 0


def scan_tree(root: Path) -> tuple[int, int, dict, str]:
    counts = {label: 0 for label, _ in PATTERNS}
    files_total = 0
    files_scanned = 0
    for path in root.rglob("*"):
        if ".git" in path.parts or not path.is_file():
            continue
        files_total += 1
        if path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        try:
            if path.stat().st_size > MAX_BYTES:
                continue
            content = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        files_scanned += 1
        for label, pattern in PATTERNS:
            counts[label] += len(pattern.findall(content))
        content = ""  # discard, never retained
    cname_file = root / "CNAME"
    cname = cname_file.read_text(encoding="utf-8", errors="replace").strip() if cname_file.exists() else ""
    return files_total, files_scanned, counts, cname


def scan_repo(repo: dict, workdir: Path) -> dict:
    name = repo["name"]
    branch = repo.get("default_branch") or "main"
    pages_api = api(f"{API}/repos/{OWNER}/{name}/pages")
    dest = workdir / name
    cloned = clone(name, branch, dest)
    if cloned:
        files_total, files_scanned, counts, cname = scan_tree(dest)
        shutil.rmtree(dest, ignore_errors=True)
    else:
        files_total = files_scanned = 0
        counts = {label: 0 for label, _ in PATTERNS}
        cname = ""

    if pages_api is not None:
        pages = {"hosted": True, "url": pages_api.get("html_url"), "cname": pages_api.get("cname"),
                 "source": "api"}
    elif cname or (dest / "docs").exists():
        pages = {"hosted": True, "url": f"https://{OWNER.lower()}.github.io/{name}/",
                 "cname": cname or None, "source": "CNAME/folder (api budget spent)"}
    elif repo.get("has_pages"):
        pages = {"hosted": True, "url": f"https://{OWNER.lower()}.github.io/{name}/",
                 "cname": None, "source": "repo metadata has_pages"}
    else:
        pages = {"hosted": False, "url": None, "cname": None, "source": "repo metadata has_pages"}

    return {
        "name": name,
        "private": bool(repo.get("private")),
        "size_kb": repo.get("size"),
        "pushed_at": repo.get("pushed_at"),
        "default_branch": branch,
        "cloned": cloned,
        "files_total": files_total,
        "files_scanned": files_scanned,
        "github_pages": pages,
        "counts": counts,
    }


def recommend(row: dict) -> str:
    risk = sum(row["counts"][k] for k in SECRET_CLASSES)
    if risk:
        return f"Make private now: {risk} sensitive-string shape(s) in tracked text on a public remote."
    if row["github_pages"]["hosted"] and (row["size_kb"] or 0) > 2000:
        return "Candidate for private: a large public site; business content, no credential shapes found."
    if row["github_pages"]["hosted"]:
        return "Can stay public: Pages site, no credential shapes found in tracked text."
    if row["files_total"] == 0:
        return "Near-empty public repo: make private or delete; nothing is served."
    return "Can stay public: no Pages site, no credential shapes found in tracked text."


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true")
    ns = parser.parse_args(argv)

    repos = api(f"{API}/users/{OWNER}/repos?per_page=100&type=public")
    if not repos:  # budget spent: fall back to the known list from the last reads
        repos = [{"name": n, "private": False, "default_branch": "main"}
                 for n in ("word-coffee", "Word-coffee.co", "Word-coffee-website", "house-finder",
                           "WordCoffee.co", "Amazon-Ads-Bid-Adjustment-Calc", "WordCoffee",
                           "wordcoffee.github.io", "Wordcoffee-website")]
    targets = [r for r in repos if r["name"] not in SKIP]

    rows = []
    with tempfile.TemporaryDirectory(prefix="wc_scan_") as tmp:
        workdir = Path(tmp)
        for repo in sorted(targets, key=lambda r: -(r.get("size") or 0)):
            sys.stderr.write(f"scanning {repo['name']}\n")
            row = scan_repo(repo, workdir)
            row["recommendation"] = recommend(row)
            rows.append(row)

    stamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    result = {"scanned_at": stamp, "owner": OWNER, "repos": rows,
              "note": "counts only; no value, line or filename is recorded"}
    out = Path("reports/ty/wordcoffee_repos_scan.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")

    if ns.json:
        print(json.dumps(result, indent=2))
        return 0

    lines = ["# The other public WordCoffee repos — counts only", "",
             f"Scanned {stamp}. Owner `{OWNER}`; this repo excluded (scanned separately).",
             "No value, line or filename is printed. A count is the whole finding.", "",
             "| repo | size KB | Pages | files | text scanned | secret shapes | emails | phones | recommendation |",
             "|---|---|---|---|---|---|---|---|---|"]
    for row in rows:
        c = row["counts"]
        secret = sum(c[k] for k in SECRET_CLASSES)
        pages = row["github_pages"]
        pages_cell = f"[{pages['url']}]({pages['url']})" if pages.get("hosted") else "no"
        lines.append(
            f"| `{row['name']}` | {row['size_kb']} | {pages_cell} | {row['files_total']} | "
            f"{row['files_scanned']} | {secret} | {c['email']} | {c['phone']} | {row['recommendation']} |")
    lines += ["", "## Pages detail", "",
              "| repo | hosted | url | cname | source of the answer |",
              "|---|---|---|---|---|"]
    for row in rows:
        p = row["github_pages"]
        lines.append(f"| `{row['name']}` | {p['hosted']} | {p['url'] or '—'} | {p['cname'] or '—'} | {p['source']} |")
    lines += ["", "## Per-class counts", "",
              "| repo | private key | github token | aws key | slack | stripe | generic secret | credential URL |",
              "|---|---|---|---|---|---|---|---|"]
    for row in rows:
        c = row["counts"]
        lines.append(f"| `{row['name']}` | {c['private_key_header']} | {c['github_token']} | "
                     f"{c['aws_key_id']} | {c['slack_token']} | {c['stripe_key']} | "
                     f"{c['generic_secret']} | {c['credential_url']} |")
    Path("reports/ty/wordcoffee_repos_scan.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
