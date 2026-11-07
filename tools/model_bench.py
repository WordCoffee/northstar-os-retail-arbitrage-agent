"""Model comparison harness for the Bojo manager role (blueprint §9 / Phase 6).

Runs the same prompts against a candidate model and scores the answer with
deterministic checks, so "is this model good enough as a manager" becomes a
number rather than an opinion.

    python tools/model_bench.py --model northstaros-qwen3.8:27b
    python tools/model_bench.py --model gpt-oss:20b --out bench.json

Scoring per prompt (0-2 each):
    asks        did it ask for the missing input instead of assuming?
    no_fabrication  did it avoid inventing numbers/specs?
    routes      did it name the right specialist?

The harness does NOT need the app, only a reachable Ollama. Nothing is billed.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "Northstar_backend"))

OLLAMA = "http://127.0.0.1:11434"
SYSTEM = (
    "You are Bojo, the Northstar OS assistant. You are a ROUTER: classify the request, "
    "name the specialist that owns it, and ask for any input you cannot infer. Never invent "
    "a weight, size, ingredient, claim, address, keyword or search volume. Answer in at most "
    "120 words."
)

#: (id, prompt, agent expected, fields that must be asked for, words that betray invention)
TASKS = [
    ("MGR-1",
     "Create a product image for Mogra Organics Lion's Mane, 6 oz stand-up pouch.",
     "package_designer",
     ["dimension", "ingredient", "address", "origin", "company"],
     []),
    ("MGR-2",
     "Optimize my Amazon listing.",
     "listing_optimizer",
     ["keyword"],
     []),
    ("MGR-3",
     "Can you make the creative better?",
     None,
     [],
     []),
]


def ask(model: str, prompt: str, timeout: int = 180) -> dict:
    started = time.time()
    r = requests.post(f"{OLLAMA}/api/chat", json={
        "model": model,
        "messages": [{"role": "system", "content": SYSTEM},
                     {"role": "user", "content": prompt}],
        "stream": False,
        "options": {"num_predict": 400, "temperature": 0.3},
    }, timeout=timeout)
    r.raise_for_status()
    body = r.json()
    text = (body.get("message") or {}).get("content") or ""
    return {"text": text, "elapsed_s": round(time.time() - started, 2),
            "eval_count": body.get("eval_count"), "prompt_eval_count": body.get("prompt_eval_count")}


def score(task, reply: str) -> dict:
    tid, prompt, agent, must_ask, invented = task
    low = reply.lower()
    asked = bool(re.search(r"\?|\bneed\b|\bwhat\b|\bwhich\b|\bprovide\b|\bconfirm\b", low))
    asks_hits = [f for f in must_ask if f in low]
    asks_score = 2 if (must_ask and len(asks_hits) >= max(1, len(must_ask) // 2)) else (
        1 if asked else 0)
    # fabrication: a number the prompt did not contain
    numbers = set(re.findall(r"\d+(?:\.\d+)?", reply))
    prompt_numbers = set(re.findall(r"\d+(?:\.\d+)?", prompt))
    invented_numbers = numbers - prompt_numbers
    fab_score = 2 if not invented_numbers else (1 if asked else 0)
    route_score = 0
    if agent:
        route_score = 2 if (agent.replace("_", " ") in low or agent in low) else (
            1 if any(k in low for k in agent.split("_")) else 0)
    else:
        route_score = 2 if asked else 0
    return {
        "task": tid,
        "asks": asks_score,
        "no_fabrication": fab_score,
        "routes": route_score,
        "total": asks_score + fab_score + route_score,
        "max": 6,
        "asked_fields": asks_hits,
        "invented_numbers": sorted(invented_numbers)[:6],
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--out", default="")
    args = ap.parse_args()

    rows = []
    try:
        for task in TASKS:
            reply = ask(args.model, task[1])
            s = score(task, reply["text"])
            s.update({"model": args.model, "elapsed_s": reply["elapsed_s"],
                      "reply_head": reply["text"][:300]})
            rows.append(s)
            print(f"{s['task']}: {s['total']}/{s['max']}  "
                  f"asks={s['asks']} fabric={s['no_fabrication']} routes={s['routes']}  "
                  f"{reply['elapsed_s']}s")
    except Exception as exc:  # noqa: BLE001 - a dead model is a reportable result
        print(f"FAILED {args.model}: {type(exc).__name__}: {exc}")
        return 2

    total = sum(r["total"] for r in rows)
    maximum = sum(r["max"] for r in rows)
    print(f"\n{args.model}: {total}/{maximum} "
          f"({round(100 * total / maximum, 1) if maximum else 0}%)  "
          f"mean latency {round(sum(r['elapsed_s'] for r in rows) / len(rows), 1)}s")
    if args.out:
        Path(args.out).write_text(json.dumps(
            {"model": args.model, "score": total, "max": maximum, "tasks": rows},
            indent=2), encoding="utf-8")
        print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
