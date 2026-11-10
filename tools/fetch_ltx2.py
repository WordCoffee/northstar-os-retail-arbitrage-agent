"""Discover the LTX-2.3 local set, then fetch it only if it respects the disk floor.

LTX-2 is the one candidate that does length AND audio in a single pass, so it is
worth the ~12 GB - but its weights, text encoder, spatial upscaler and audio
components live in different repos, and a wrong pick either misses a piece or
doubles the footprint. This lists the real files and sizes first, checks the floor,
then downloads exactly what the graph needs.

    python tools/fetch_ltx2.py --list
    python tools/fetch_ltx2.py            # fetch (refuses below the floor)
"""
from __future__ import annotations

import argparse
import csv
import fnmatch
import json
import shutil
import subprocess
import urllib.parse
import urllib.request
from pathlib import Path

INCOMING = Path(r"C:\Users\T2Hol\ComfyUI\models\_incoming")
PROVENANCE = Path(__file__).resolve().parent.parent / "provenance.csv"
FLOOR_GB = 10.0

#: Precise picks: the distilled checkpoint the GPU can actually hold, plus the
#: pieces the ComfyUI LTX-2 graph references by name.
WANT = {
    "Lightricks/LTX-2": ["*distilled*1.1*", "*distilled*"],
    "Comfy-Org/LTX-2_ComfyUI": ["*distilled*", "*spatial*upscaler*"],
}


def sizes(repo: str, patterns: list[str]) -> list[tuple[str, int]]:
    url = f"https://huggingface.co/api/models/{urllib.parse.quote(repo)}?blobs=true"
    try:
        data = json.load(urllib.request.urlopen(url, timeout=30))
    except Exception as exc:
        print(f"  ! {repo}: {exc}")
        return []
    out = []
    for sib in data.get("siblings", []):
        name = sib.get("rfilename", "")
        size = int(sib.get("size") or 0)
        if not size or name.endswith((".md", ".gitattributes")):
            continue
        if any(fnmatch.fnmatch(name.lower(), p.lower()) for p in patterns):
            out.append((name, size))
    return out


def search(term: str, limit: int = 6) -> list[str]:
    url = (f"https://huggingface.co/api/models?search={urllib.parse.quote(term)}"
           f"&limit={limit}&sort=downloads&direction=-1")
    try:
        data = json.load(urllib.request.urlopen(url, timeout=30))
        return [m["id"] for m in data]
    except Exception as exc:
        print(f"search {term}: {exc}")
        return []


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--list", action="store_true")
    args = ap.parse_args(argv)

    print("candidates:")
    for term in ("LTX-2.3", "LTX-2", "LTX-Video"):
        print(f"  {term:10} -> {search(term)}")

    plan: list[tuple[str, str, int]] = []
    for repo, patterns in WANT.items():
        files = sizes(repo, patterns)
        print(f"\n{repo} ({len(files)} matching files)")
        for name, size in sorted(files, key=lambda x: -x[1])[:8]:
            print(f"   {name[:74]:74} {size/1024**3:6.2f} GB")
        plan += [(repo, n, s) for n, s in files]

    total = sum(s for _, _, s in plan)
    free = shutil.disk_usage("C:/").free / 1024**3
    print(f"\nselected: {total/1024**3:.2f} GB | free {free:.1f} GB | "
          f"after {free - total/1024**3:.1f} GB (floor {FLOOR_GB})")
    if args.list:
        return 0
    if not plan:
        print("nothing selected - the repo names need checking before a download")
        return 2
    if free - total / 1024**3 < FLOOR_GB:
        print("REFUSED: this set would cross the free-space floor")
        return 2

    hf = shutil.which("hf")
    if not hf:
        print("the `hf` CLI is not on PATH")
        return 2
    by_repo: dict[str, list[str]] = {}
    for repo, name, _ in plan:
        by_repo.setdefault(repo, []).append(name)
    for repo, names in by_repo.items():
        dest = INCOMING / repo.replace("/", "__")
        cmd = [hf, "download", repo, "--repo-type", "model", "--local-dir", str(dest)]
        for n in names:
            cmd += ["--include", n]
        print(f"[{repo}] {' '.join(cmd[-4:])}", flush=True)
        proc = subprocess.run(cmd, capture_output=True, text=True)
        ok = proc.returncode == 0
        got = sum(f.stat().st_size for f in dest.rglob("*") if f.is_file()) if dest.is_dir() else 0
        print(f"[{repo}] ok={ok} size={got/1024**3:.2f} GB", flush=True)
        if ok:
            new = not PROVENANCE.is_file()
            with open(PROVENANCE, "a", newline="", encoding="utf-8") as fh:
                w = csv.writer(fh)
                if new:
                    w.writerow(["name", "version", "licence", "source", "lane", "purpose", "added"])
                w.writerow([repo.split("/")[-1], "main",
                            "LTX-2 Community (<$10M rev, no-compete, no-training)",
                            f"https://huggingface.co/{repo}", "local-lane",
                            "one-pass long-form video with synchronised audio", "2026-11-04"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
