import hashlib
import json
import os
import subprocess
from pathlib import Path

WS = Path(r"C:\Users\T2Hol\Desktop\Northstar External\rea-study")
TARGETS = ["product-shots", "ecommerce-image-skills", "amazon-product-studio"]

LICENSE_KEYS = ("MIT", "Apache", "GPL", "AGPL", "BSD", "MPL", "Unlicense",
                "CC BY", "proprietary", "All rights reserved")


def detect_license(repo: Path) -> tuple[str, str]:
    for name in ("LICENSE", "LICENSE.md", "LICENSE.txt", "COPYING", "license"):
        p = repo / name
        if p.is_file():
            text = p.read_text(encoding="utf-8", errors="replace")[:4000]
            head = " ".join(text.splitlines()[:6])[:220]
            for key in LICENSE_KEYS:
                if key.lower() in text.lower():
                    return key, head
            return "UNRECOGNISED", head
    return "NONE FOUND", "no LICENSE file at the repository root"


def git(repo: Path, *args) -> str:
    try:
        return subprocess.run(["git", *args], cwd=repo, capture_output=True,
                              text=True, timeout=30).stdout.strip()
    except Exception:
        return ""


def skill_docs(repo: Path) -> list[str]:
    out = []
    for p in sorted(repo.rglob("*.md")):
        if ".git" in p.parts:
            continue
        try:
            head = p.read_text(encoding="utf-8", errors="replace")[:1200]
        except OSError:
            continue
        if "name:" in head[:400] and ("description:" in head[:900] or "skill" in head.lower()):
            out.append(str(p.relative_to(repo)))
    return out


rows = []
for name in TARGETS:
    repo = WS / name
    if not repo.is_dir():
        rows.append({"repo": name, "status": "NOT CLONED"})
        continue
    lic, head = detect_license(repo)
    files = [p for p in repo.rglob("*") if p.is_file() and ".git" not in p.parts]
    size = sum(p.stat().st_size for p in files)
    rows.append({
        "repo": name,
        "commit": git(repo, "rev-parse", "--short", "HEAD"),
        "commit_date": git(repo, "log", "-1", "--format=%ci"),
        "license": lic,
        "license_head": head,
        "files": len(files),
        "bytes": size,
        "top_level": sorted(p.name for p in repo.iterdir() if p.name != ".git")[:14],
        "skill_docs": skill_docs(repo)[:12],
        "readme_head": (repo / "README.md").read_text(encoding="utf-8", errors="replace")[:600]
        if (repo / "README.md").is_file() else "",
    })

out = Path(r"C:\Users\T2Hol\Desktop\Northstar OS Retail Arbitrage Agent\research\tier-a-inventory.json")
out.write_text(json.dumps(rows, indent=2), encoding="utf-8")
for r in rows:
    print(f"{r['repo']:26s} {r.get('license','?'):12s} files={r.get('files','?'):4} "
          f"skills={len(r.get('skill_docs') or [])} commit={r.get('commit','?')}")
    print(f"   top: {', '.join(r.get('top_level') or [])[:150]}")
print("wrote", out)
