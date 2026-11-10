"""Run-to-run spread for the live NS-PROJ-20 text-lane baseline."""
from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "Northstar_backend"))
import content_validators as cv  # noqa: E402

BRIEFS = ROOT / "eval/projects/ns_proj_20.json"


def format_audit(folder: Path, briefs) -> dict:
    rows = []
    for b in briefs:
        p = folder / b["id"] / b["artifact"]
        raw = p.read_bytes() if p.is_file() else b""
        text = raw.decode("utf-8", errors="replace")
        suffix = p.suffix.lower()
        if suffix == ".png":
            ok = raw.startswith(b"\x89PNG\r\n\x1a\n")
        elif suffix == ".mp4":
            ok = len(raw) > 12 and raw[4:8] == b"ftyp"
        elif suffix == ".json":
            body = text.strip()
            if body.startswith("```"):
                body = body.split("\n", 1)[1].rsplit("```", 1)[0]
            try:
                json.loads(body)
                ok = True
            except Exception:
                ok = False
        elif suffix == ".patch":
            ok = "---" in text and "+++" in text
        else:
            ok = len(raw) >= 40
        rows.append({"id": b["id"], "format_valid": bool(ok),
                     "markdown_fence": text.lstrip().startswith("```")})
    valid = sum(1 for r in rows if r["format_valid"])
    return {"valid": valid, "total": len(rows),
            "rate": round(valid / max(1, len(rows)), 3),
            "markdown_fenced": sum(1 for r in rows if r["markdown_fence"]),
            "rows": rows}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--folders", nargs="+", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    briefs = json.loads(BRIEFS.read_text(encoding="utf-8"))["briefs"]
    runs = []
    for f in args.folders:
        folder = Path(f)
        summary = json.loads((folder / "summary.json").read_text(encoding="utf-8"))
        fmt = format_audit(folder, briefs)
        quality = cv.run(folder)
        summary["label"] = "live text-lane baseline"
        summary["pinned_settings"] = {
            "mtp": False, "context": 8192, "kv_cache": "q8_0",
            "reason": "MTP runs aborted at 46 and 49 calls; no-MTP completed 60",
        }
        summary["format_audit"] = fmt
        summary["quality_audit"] = quality
        (folder / "summary.json").write_text(json.dumps(summary, indent=2),
                                             encoding="utf-8")
        runs.append({
            "folder": folder.name,
            "complete": summary["complete"],
            "p50": summary["node_seconds_p50"],
            "p95": summary["node_seconds_p95"],
            "format_rate": fmt["rate"],
            "quality_rate": quality["rate"],
            "fence_stripped": summary.get("fence_stripped", 0),
        })

    def spread(key):
        vals = [r[key] for r in runs if r[key] is not None]
        return {"values": vals, "min": min(vals), "max": max(vals),
                "median": round(statistics.median(vals), 2),
                "mean": round(statistics.mean(vals), 2)}

    sp = {k: spread(k) for k in ("complete", "p50", "p95",
                                  "format_rate", "quality_rate")}
    thresholds = {
        "completion_rate_min": 1.0,
        "evidence_coverage_min": 1.0,
        "node_seconds_p50_max": round(sp["p50"]["max"] * 1.2, 1),
        "node_seconds_p95_max": round(sp["p95"]["max"] * 1.2, 1),
        "format_validity_min": sp["format_rate"]["min"],
        "quality_min": sp["quality_rate"]["min"],
        "quality_note": ("Set only after content validators ran on all three "
                         "baseline runs; p11/p13/p14 are the stable text-lane "
                         "failures."),
    }
    out = {"label": "live text-lane baseline",
           "runs": runs, "spread": sp, "thresholds": thresholds,
           "note": "Thresholds use max + 20% for latency and the observed minimum "
                   "for rates; they are not quality claims."}
    Path(args.out).write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
