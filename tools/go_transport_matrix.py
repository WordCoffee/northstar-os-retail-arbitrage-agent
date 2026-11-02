"""Transport matrix: does `opencode run` complete at 1/8/16/24/32 KB of stdin?

Each probe asks for a fixed short answer and pads the prompt to the target size.
A call that exceeds the budget is recorded as a hang, not retried.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODEL = "opencode-go/deepseek-v4.1-flash"
SIZES = [1024, 8192, 16384, 24576, 32768]
BUDGET_S = 90


def cmd() -> list:
    found = shutil.which("opencode")
    if found and Path(found).suffix.lower() == ".ps1":
        alt = Path(found).with_suffix(".cmd")
        if alt.is_file():
            return [str(alt)]
    return [found or "opencode"]


def probe(size: int) -> dict:
    head = "Answer with the single word: pong\n\n"
    pad = ("filler line for transport sizing\n" * ((size // 32) + 1))[: max(0, size - len(head))]
    prompt = head + pad
    started = time.time()
    try:
        proc = subprocess.run(cmd() + ["run", "--model", MODEL, "--format", "json",
                                       "--title", f"ty-size-{size}"],
                              cwd=str(ROOT), capture_output=True, text=True,
                              timeout=BUDGET_S, input=prompt)
    except subprocess.TimeoutExpired:
        return {"bytes": len(prompt), "hang": True, "elapsed_s": round(time.time() - started, 1)}
    text = ""
    cost = 0.0
    for line in (proc.stdout or "").splitlines():
        if not line.startswith("{"):
            continue
        try:
            ev = json.loads(line)
        except ValueError:
            continue
        if ev.get("type") == "text":
            text += str((ev.get("part") or {}).get("text") or "")
        elif ev.get("type") == "step_finish":
            cost += float((ev.get("part") or {}).get("cost") or 0.0)
    return {"bytes": len(prompt), "hang": False,
            "elapsed_s": round(time.time() - started, 1), "rc": proc.returncode,
            "answer": text.strip()[:40], "cost_usd": round(cost, 6),
            "stderr": (proc.stderr or "")[:120]}


if __name__ == "__main__":
    rows = [probe(s) for s in SIZES]
    out = ROOT / "state" / "evidence" / "go_transport_matrix.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rows, indent=2), encoding="utf-8")
    print(json.dumps(rows, indent=2))
    raise SystemExit(0)
