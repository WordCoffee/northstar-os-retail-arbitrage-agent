"""Fetch the creative stack the plan calls for, with provenance, into a staging area.

Nothing is moved into ComfyUI's model tree by this script: it downloads to
`ComfyUI/models/_incoming/<repo>` so the file names can be verified before they are
placed, and records one provenance row per repo (licence included).

    python tools/fetch_creative_stack.py --list      # show what would be fetched
    python tools/fetch_creative_stack.py             # fetch the phase 1+2 set
    python tools/fetch_creative_stack.py --only seedvr2

Every item is commercially licensed (Apache-2.0 / MIT). The non-commercial
candidates the research rejected (FLUX.1 Kontext dev, FLUX.2 dev, Redux dev, SUPIR,
MMAudio, CLIP-IQA) are deliberately absent from this list.
"""
from __future__ import annotations

import argparse
import csv
import json
import shutil
import subprocess
import sys
from pathlib import Path

INCOMING = Path(r"C:\Users\T2Hol\ComfyUI\models\_incoming")
PROVENANCE = Path(__file__).resolve().parent.parent / "provenance.csv"

STACK = [
    {
        "key": "seedvr2",
        "repo": "Comfy-Org/SeedVR2",
        # ONE variant. The first pass used *fp8* and pulled five (17.9 GB).
        "include": ["diffusion_models/seedvr2_3b_fp8_e4m3fn.safetensors"],
        "licence": "Apache-2.0",
        "why": "one-step detail restoration: 1024 -> 2000px packshots and video upscale",
        "comfy_dir": "seedvr2",
    },
    {
        "key": "wan22",
        "repo": "QuantStack/Wan2.2-I2V-A14B-GGUF",
        # Q4_K_M only: both experts. Q5 would add 2.1 GB for no graded gain.
        "include": ["HighNoise/Wan2.2-I2V-A14B-HighNoise-Q4_K_M.gguf",
                    "LowNoise/Wan2.2-I2V-A14B-LowNoise-Q4_K_M.gguf"],
        "licence": "Apache-2.0",
        "why": "image-to-video A14B high+low experts, start/end frame control",
        "comfy_dir": "diffusion_models",
    },
    {
        "key": "pickscore",
        "repo": "yuvalkirstain/PickScore_v1",
        # safetensors only: the repo ships the same weights again as .bin (3.7 GB).
        "include": ["model.safetensors", "config.json", "preprocessor_config.json",
                    "special_tokens_map.json", "tokenizer_config.json",
                    "tokenizer.json", "vocab.json", "merges.txt"],
        "licence": "MIT",
        "why": "prompt-adherence scoring for best-of-N and the ship gate",
        "comfy_dir": None,
    },
    {
        "key": "hpsv2",
        "repo": "xswu/HPSv2",
        # One checkpoint, not three (11.2 GB if all).
        "include": ["HPS_v2.1_compressed.pt"],
        "licence": "Apache-2.0",
        "why": "human-preference floor for the ship gate",
        "comfy_dir": None,
    },
]


def _hf() -> str:
    exe = shutil.which("hf")
    if not exe:
        raise SystemExit("the `hf` CLI is not on PATH (pip install huggingface_hub)")
    return exe


def fetch(item: dict, *, dry_run: bool = False) -> dict:
    dest = INCOMING / item["repo"].replace("/", "__")
    cmd = [_hf(), "download", item["repo"], "--repo-type", "model",
           "--local-dir", str(dest)]
    for pattern in item["include"] or []:
        cmd += ["--include", pattern]
    print(f"[{item['key']}] {' '.join(cmd)}", flush=True)
    if dry_run:
        return {"key": item["key"], "ok": None, "dry_run": True, "dest": str(dest)}
    proc = subprocess.run(cmd, capture_output=True, text=True)
    ok = proc.returncode == 0
    files = sorted(p for p in dest.rglob("*") if p.is_file()) if dest.is_dir() else []
    total = sum(p.stat().st_size for p in files)
    if not files:
        ok = False
    out = {"key": item["key"], "ok": ok, "dest": str(dest), "files": len(files),
           "gb": round(total / (1024 ** 3), 2),
           "error": (proc.stderr or "")[-400:] if not ok else ""}
    print(f"[{item['key']}] ok={ok} files={len(files)} size={out['gb']} GB", flush=True)
    return out


def record(results: list[dict]) -> None:
    by_key = {i["key"]: i for i in STACK}
    new = not PROVENANCE.is_file()
    with open(PROVENANCE, "a", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        if new:
            w.writerow(["name", "version", "licence", "source", "lane", "purpose", "added"])
        for row in results:
            if not row.get("ok"):
                continue
            item = by_key[row["key"]]
            w.writerow([item["repo"].split("/")[-1], "main", item["licence"],
                        f"https://huggingface.co/{item['repo']}", "local-lane",
                        item["why"], "2026-11-03"])


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--only", action="append", default=[])
    ap.add_argument("--list", action="store_true")
    args = ap.parse_args(argv)
    items = [i for i in STACK if not args.only or i["key"] in args.only]
    if args.list:
        for i in items:
            print(f"{i['key']:10} {i['repo']:38} {i['licence']:12} {i['why']}")
        return 0
    INCOMING.mkdir(parents=True, exist_ok=True)
    results = [fetch(i) for i in items]
    record(results)
    (INCOMING / "fetch_report.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    bad = [r for r in results if not r.get("ok")]
    print(json.dumps({"fetched": len(results) - len(bad), "failed": [r["key"] for r in bad],
                      "gb": round(sum(r.get("gb") or 0 for r in results), 2)}, indent=2))
    return 0 if not bad else 1


if __name__ == "__main__":
    raise SystemExit(main())
