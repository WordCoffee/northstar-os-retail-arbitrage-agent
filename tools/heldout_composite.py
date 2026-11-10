"""The held-out composite pass, resumable.

A 21-brief render on this box is not atomic: FLUX 3 has failed mid-sampler before, and a crash in
brief 15 would take the first fourteen with it. So the pass runs in chunks of briefs that have no
result yet, and each chunk's proof is merged into one accumulating file. Re-running the command
after a crash continues where it stopped instead of starting over.

    python tools/heldout_composite.py --run                # as many chunks as needed
    python tools/heldout_composite.py --run --chunk 5      # smaller chunks on a tight machine
    python tools/heldout_composite.py --status             # what is done, what is left

It never writes `state/seller/composite_proof.json` — that file is the tuned three-brief proof, and
a held-out run must not be able to overwrite the number the catalogue publishes.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[1]
BRIEFS = ROOT / "ty" / "seller_briefs_heldout.json"
PROOF = ROOT / "state" / "seller" / "heldout_composite_proof.json"
GAPS = ROOT / "state" / "seller" / "heldout_gaps.json"
OUT_DIR = ROOT / "renders" / "seller_composite_heldout"
WORK = ROOT / "state" / "seller" / "_heldout_chunk"


def _briefs() -> List[Dict[str, Any]]:
    return json.loads(BRIEFS.read_text(encoding="utf-8"))["briefs"]


def _proof() -> Dict[str, Any]:
    if not PROOF.exists():
        return {"generated_at": None, "results": []}
    try:
        data = json.loads(PROOF.read_text(encoding="utf-8"))
    except ValueError:
        return {"generated_at": None, "results": []}
    data.setdefault("results", [])
    return data


def done_ids(proof: Dict[str, Any]) -> set:
    """A brief counts as done only when it produced a row with a verdict, pass or fail."""
    return {str(row.get("brief_id")) for row in proof.get("results") or []
            if row.get("score") is not None or row.get("cannot_verify")}


def status() -> Dict[str, Any]:
    briefs = _briefs()
    proof = _proof()
    done = done_ids(proof)
    remaining = [b["id"] for b in briefs if b["id"] not in done]
    rows = [row for row in proof.get("results") or [] if row.get("brief_id") in done]
    passed = sum(1 for row in rows if row.get("passed"))
    return {"total": len(briefs), "done": len(rows), "remaining": remaining,
            "passed": passed,
            "mean": round(sum(float(row.get("score") or 0.0) for row in rows) / len(rows), 1)
            if rows else None}


def run_chunk(chunk: int, renderer: str, model: str, scene_size: int, steps: int,
              briefs: List[Dict[str, Any]]) -> Dict[str, Any]:
    WORK.mkdir(parents=True, exist_ok=True)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    GAPS.parent.mkdir(parents=True, exist_ok=True)
    payload = json.loads(BRIEFS.read_text(encoding="utf-8"))
    payload["briefs"] = briefs
    chunk_path = WORK / "chunk.json"
    chunk_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    chunk_proof = WORK / "chunk_proof.json"
    if chunk_proof.exists():
        chunk_proof.unlink()
    command = [sys.executable, "-m", "tools.seller_tester", "composite",
               "--catalog", str(chunk_path), "--limit", str(len(briefs)),
               "--renderer", renderer, "--model", model,
               "--scene-size", str(scene_size), "--steps", str(steps),
               "--out-dir", str(OUT_DIR), "--summary-out", str(chunk_proof),
               "--gaps", str(GAPS), "--root", str(ROOT)]
    print("running:", " ".join(command), flush=True)
    result = subprocess.run(command, cwd=str(ROOT), capture_output=True, text=True)
    if result.returncode != 0:
        print(result.stdout[-2000:], file=sys.stderr)
        print(result.stderr[-2000:], file=sys.stderr)
    if not chunk_proof.exists():
        return {"ok": False, "returncode": result.returncode,
                "error": (result.stderr or result.stdout or "")[-800:]}
    produced = json.loads(chunk_proof.read_text(encoding="utf-8"))
    merge(produced)
    return {"ok": result.returncode == 0, "returncode": result.returncode,
            "rows": len(produced.get("results") or [])}


def merge(produced: Dict[str, Any]) -> Dict[str, Any]:
    proof = _proof()
    index = {str(row.get("brief_id")): row for row in proof.get("results") or []}
    for row in produced.get("results") or []:
        index[str(row.get("brief_id"))] = row
    rows = list(index.values())
    rows.sort(key=lambda row: str(row.get("brief_id")))
    passed = sum(1 for row in rows if row.get("passed"))
    scored = [row for row in rows if row.get("score") is not None]
    proof.update({
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "generator": "composite (held-out, chunked)",
        "catalog_briefs": len(_briefs()),
        "scored": len(scored),
        "passed": passed,
        "mean_score": round(sum(float(r["score"]) for r in scored) / len(scored), 1)
        if scored else None,
        "results": rows,
    })
    PROOF.parent.mkdir(parents=True, exist_ok=True)
    PROOF.write_text(json.dumps(proof, indent=2) + "\n", encoding="utf-8")
    return proof


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Held-out composite pass, resumable")
    parser.add_argument("--run", action="store_true")
    parser.add_argument("--status", action="store_true")
    parser.add_argument("--chunk", type=int, default=7)
    parser.add_argument("--renderer", default="comfy", choices=["comfy", "synthetic"])
    parser.add_argument("--model", default="sdxl", choices=["sdxl", "flux3"])
    parser.add_argument("--scene-size", type=int, default=768)
    parser.add_argument("--steps", type=int, default=20)
    ns = parser.parse_args(argv)
    if ns.status or not ns.run:
        print(json.dumps(status(), indent=2))
        return 0
    briefs = _briefs()
    done = done_ids(_proof())
    remaining = [b for b in briefs if b["id"] not in done]
    if not remaining:
        print(json.dumps({"ok": True, "message": "every held-out brief already has a verdict",
                          **status()}, indent=2))
        return 0
    runs = 0
    while remaining:
        batch, remaining = remaining[:ns.chunk], remaining[ns.chunk:]
        outcome = run_chunk(ns.chunk, ns.renderer, ns.model, ns.scene_size, ns.steps, batch)
        runs += 1
        print(json.dumps({"chunk": runs, "briefs": [b["id"] for b in batch], **outcome},
                         indent=2), flush=True)
        if not outcome.get("ok"):
            print(json.dumps({"stopped_after": runs, "reason": outcome.get("error"),
                              **status()}, indent=2))
            return 2
    print(json.dumps({"chunks": runs, **status()}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
