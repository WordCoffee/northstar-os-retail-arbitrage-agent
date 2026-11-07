#!/usr/bin/env python3
"""Multi-turn agentic build driver for the MoE coder lane (llama-server on :8080).

Sends a fixed system brief, then one round per file group. Parses strict
"=== FILE: path ===" blocks, writes them under --out, and records per-round timings.
"""
import argparse
import json
import os
import re
import sys
import time
import urllib.request

FILE_RE = re.compile(r"=== FILE:\s*(.+?)\s*===\s*\n```[a-zA-Z0-9_-]*\n(.*?)\n```", re.DOTALL)

ROUNDS = [
    (
        "core",
        "Round 1 of 4. Deliver the complete core engine files now, compilable under strict TypeScript "
        "with @types/node. Files required: src/types.ts, src/queue.ts (lock-free bounded MPMC ring over "
        "SharedArrayBuffer + Atomics with backpressure signals), src/backoff.ts (exponential backoff with "
        "full jitter), src/circuit-breaker.ts (closed/open/half-open state machine), src/telemetry.ts "
        "(structured logging hooks + metrics counters). No placeholders, no TODOs, no ellipses.",
    ),
    (
        "runtime",
        "Round 2 of 4. Deliver the runtime files, complete and compilable, importing the round-1 modules "
        "exactly as written. Files required: src/worker.ts (worker_threads entry point with message protocol), "
        "src/pool.ts (dynamic load balancing across workers, starvation guards), src/pipeline.ts "
        "(submit/await with async backpressure), src/index.ts (public exports). No placeholders, no TODOs.",
    ),
    (
        "tests",
        "Round 3 of 4. Deliver a real Jest suite (ts-jest, node environment) for the code from rounds 1-2. "
        "Files required: tests/queue.test.ts, tests/backoff.test.ts, tests/circuit-breaker.test.ts, "
        "tests/pipeline.test.ts, tests/pool.test.ts. Cover concurrency, backpressure overflow, race conditions, "
        "thread starvation, and recovery paths. Every test must import the real modules, no mocks of the queue. "
        "No placeholders, no skipped tests.",
    ),
    (
        "docs",
        "Round 4 of 4. Deliver docs/ARCHITECTURE.md: architectural decisions, trade-offs, O-notation complexity "
        "for each queueing operation, worker lifecycle, backpressure model, failure/recovery semantics, and a "
        "step-by-step migration path from a legacy single-threaded queue. Reference the actual file and symbol "
        "names from rounds 1-3. No placeholders.",
    ),
]

SYSTEM_SUFFIX = """

You are working in a real repository. Output files ONLY as blocks in this exact shape:
=== FILE: relative/path.ts ===
```ts
<complete file content>
```
Write every file in full. Do not abbreviate, do not use ellipses, do not emit prose between files.
"""


def post(payload: dict, port: int, timeout: int = 1800) -> dict:
    req = urllib.request.Request(
        f"http://127.0.0.1:{port}/v1/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def safe_path(root: str, rel: str) -> str:
    rel = rel.strip().replace("\\", "/").lstrip("/")
    if ".." in rel.split("/"):
        raise ValueError(f"unsafe path: {rel}")
    return os.path.join(root, *rel.split("/"))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--port", type=int, default=8080)
    ap.add_argument("--prompt", required=True)
    ap.add_argument("--rounds", type=int, default=4)
    args = ap.parse_args()

    brief = open(args.prompt, encoding="utf-8-sig").read().strip()
    system = brief + SYSTEM_SUFFIX
    os.makedirs(args.out, exist_ok=True)

    messages = [{"role": "system", "content": system}]
    log_path = os.path.join(args.out, "agentic_log.jsonl")
    ok = True

    for i, (name, instruction) in enumerate(ROUNDS[: args.rounds], start=1):
        messages.append({"role": "user", "content": instruction})
        t0 = time.time()
        resp = post(
            {
                "messages": messages,
                "n_predict": 8192,
                "temperature": 0.2,
                "cache_prompt": True,
                "chat_template_kwargs": {"enable_thinking": False},
            },
            args.port,
        )
        dt = time.time() - t0
        msg = resp["choices"][0]["message"]
        content = msg.get("content") or ""
        reasoning = msg.get("reasoning_content") or ""
        timings = resp.get("timings", {}) or {}
        files = FILE_RE.findall(content)
        written = []
        for rel, body in files:
            try:
                path = safe_path(args.out, rel)
            except ValueError as e:
                print(f"  !! {e}", file=sys.stderr)
                continue
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8", newline="\n") as f:
                f.write(body.strip() + "\n")
            written.append((rel, len(body)))
        if not files:
            ok = False
        rec = {
            "round": i,
            "name": name,
            "decoded_tps": round(float(timings.get("predicted_per_second", 0)), 1),
            "prompt_tps": round(float(timings.get("prompt_per_second", 0)), 1),
            "tokens": timings.get("predicted_n"),
            "reasoning_chars": len(reasoning),
            "content_chars": len(content),
            "files": [{"path": p, "chars": n} for p, n in written],
            "seconds": round(dt, 1),
        }
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec) + "\n")
        print(json.dumps(rec))
        messages.append({"role": "assistant", "content": content})

    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
