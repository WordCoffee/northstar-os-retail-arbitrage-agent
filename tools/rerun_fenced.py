"""Re-run only the fenced artifact nodes from a live baseline, stripping fences."""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "Northstar_backend"))
from agent_kernel.artifacts import strip_markdown_fence  # noqa: E402

BRIEFS = ROOT / "eval/projects/ns_proj_20.json"
LLM = "http://127.0.0.1:8080/v1/chat/completions"
MODEL = "northstaros-qwen3.8:27b"


def call(prompt: str) -> str:
    body = json.dumps({
        "model": MODEL, "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 700, "temperature": 0.2, "stream": False,
        "chat_template_kwargs": {"enable_thinking": False},
    }).encode()
    req = urllib.request.Request(LLM, data=body,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=300) as r:
        out = json.load(r)
    return str((out.get("choices") or [{}])[0].get("message", {}).get("content") or "")


def audit(folder: Path, briefs) -> dict:
    rows = []
    for b in briefs:
        p = folder / b["id"] / b["artifact"]
        raw = p.read_bytes() if p.is_file() else b""
        text = raw.decode("utf-8", errors="replace")
        suffix = p.suffix.lower()
        fenced = text.lstrip().startswith("```")
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
        rows.append({"id": b["id"], "bytes": len(raw), "format_valid": bool(ok),
                     "markdown_fence": fenced})
    valid = sum(1 for r in rows if r["format_valid"])
    return {"valid": valid, "total": len(rows),
            "rate": round(valid / max(1, len(rows)), 3),
            "markdown_fenced": sum(1 for r in rows if r["markdown_fence"]),
            "rows": rows}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--folder", required=True)
    args = ap.parse_args()
    folder = Path(args.folder)
    summary_path = folder / "summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    briefs = {b["id"]: b for b in json.loads(
        BRIEFS.read_text(encoding="utf-8"))["briefs"]}
    fenced = [r["id"] for r in summary.get("format_audit", {}).get("rows", [])
              if r.get("markdown_fence")]
    repaired = []
    for bid in fenced:
        b = briefs[bid]
        prompt = ("Produce the content of the artifact "
                  f"`{b['artifact']}` for this project. Goal: {b['goal']}. "
                  f"Checks: {'; '.join(b.get('checks') or [])}. "
                  "Return only the artifact content. If a patch is requested, return "
                  "a unified diff. No commentary.")
        before = (folder / bid / b["artifact"])
        old = before.stat().st_size if before.is_file() else 0
        text = call(prompt)
        clean, stripped = strip_markdown_fence(text)
        before.write_text(clean + ("\n" if clean and not clean.endswith("\n") else ""),
                          encoding="utf-8")
        repaired.append({"id": bid, "artifact": b["artifact"], "before_bytes": old,
                         "after_bytes": before.stat().st_size,
                         "fence_stripped": stripped})
        print(f"  {bid}: {old} -> {before.stat().st_size} bytes, fence={stripped}",
              flush=True)
    summary["format_audit"] = audit(folder, list(briefs.values()))
    summary["fence_rerun"] = {
        "policy": "strip Markdown fences at persistence; record the event",
        "nodes": len(repaired), "repaired": repaired,
    }
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps({"repaired": len(repaired),
                      "format_valid": summary["format_audit"]["valid"],
                      "rate": summary["format_audit"]["rate"],
                      "fenced_now": summary["format_audit"]["markdown_fenced"]},
                     indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
