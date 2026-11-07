#!/usr/bin/env python3
"""Repair v2: deterministic fix table for known-wrong patterns, then per-file model repair
with anti-repetition (identical previous output -> demand a different fix) and temperature escalation.
"""
import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from moe_agentic_build import FILE_RE, post  # noqa: E402

ERR_RE = re.compile(r"^(.+?)\((\d+),(\d+)\): error (TS\d+): (.*)$")

FIXES = [
    ("src/types.ts",
     "  backpressureThreshold?: number;\n}",
     "  backpressureThreshold?: number;\n  /** Optional existing shared buffer to reconstruct a queue over. */\n  sharedBuffer?: SharedArrayBuffer;\n}"),
    ("src/queue.ts",
     "import {\n  Atomics,\n} from 'node:worker_threads';\n\n",
     ""),
    ("src/queue.ts",
     "Number.isPow2(capacity)",
     "(capacity & (capacity - 1)) === 0"),
    ("src/queue.ts",
     "this.sharedBuffer = new SharedArrayBuffer(capacity * (this.slotSize + 16));",
     "this.sharedBuffer = options.sharedBuffer ?? new SharedArrayBuffer(capacity * (this.slotSize + 16));"),
    ("src/queue.ts",
     "    out.writeUInt32LE(bytes.length, 0);",
     "    new DataView(out.buffer).setUint32(0, bytes.length, true);"),
    ("src/worker.ts",
     "      consumers: message.options.consumers ?? 1,\n    });\n    // Reconstruct the queue over the shared buffer.\n    queue['sharedBuffer'] = message.queue as SharedArrayBuffer;",
     "      consumers: message.options.consumers ?? 1,\n      sharedBuffer: message.queue as SharedArrayBuffer,\n    });"),
    ("src/pool.ts",
     "    const __dirname = fileURLToPath(new URL('.', import.meta.url));\n    return join(__dirname, 'worker.js');",
     "    return join(__dirname, 'worker.js');"),
]


def run_tsc(root: str, tag: str) -> tuple[int, str]:
    proc = subprocess.run("npx tsc --noEmit", cwd=root, shell=True, capture_output=True, text=True, timeout=600)
    out = ((proc.stdout or "") + (proc.stderr or "")).strip()
    with open(os.path.join(root, f"tsc_{tag}.txt"), "w", encoding="utf-8") as f:
        f.write(out)
    return proc.returncode, out


def parse_errors(text: str) -> dict[str, list[str]]:
    groups: dict[str, list[str]] = {}
    cur = None
    for line in text.splitlines():
        m = ERR_RE.match(line)
        if m:
            cur = m.group(1)
            groups.setdefault(cur, []).append(line)
        elif cur and (line.startswith("  ") or line.startswith("\t")):
            groups[cur].append(line)
    return groups


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--port", type=int, default=8080)
    ap.add_argument("--attempts", type=int, default=6)
    args = ap.parse_args()
    root = os.path.abspath(args.out)
    log_path = os.path.join(root, "repair_v2_log.jsonl")

    def log(rec: dict) -> None:
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec) + "\n")
        print(json.dumps(rec), flush=True)

    # Phase A: deterministic fix table
    applied = []
    for rel, old, new in FIXES:
        p = os.path.join(root, *rel.split("/"))
        with open(p, encoding="utf-8") as f:
            src = f.read()
        if old in src:
            with open(p, "w", encoding="utf-8", newline="\n") as f:
                f.write(src.replace(old, new, 1))
            applied.append(f"{rel}: {old.splitlines()[0][:60]}")
    log({"stage": "deterministic", "applied": applied})

    code, errors = run_tsc(root, "v2_0")
    log({"stage": "tsc", "attempt": 0, "exit": code, "errors": len([l for l in errors.splitlines() if ERR_RE.match(l)])})
    if code == 0:
        print("GREEN_BUILD attempt=0")
        return 0

    last_output: dict[str, str] = {}
    for attempt in range(1, args.attempts + 1):
        groups = parse_errors(errors)
        if not groups:
            break
        target = max(groups.items(), key=lambda kv: len(kv[1]))[0]
        tpath = os.path.join(root, *target.split("/"))
        with open(tpath, encoding="utf-8") as f:
            body = f.read()

        repeat_note = ""
        if last_output.get(target) == hashlib.sha1(body.encode()).hexdigest():
            repeat_note = ("Your previous output for this file was applied and did NOT reduce the errors. "
                           "You must produce a DIFFERENT implementation this time.\n\n")
        temp = 0.1 if attempt <= 2 else 0.4

        user = (
            f"File: {target}\n\n" + repeat_note +
            "Fix all compiler errors below in this file only. Return ONLY this file, complete, in this shape:\n"
            f"=== FILE: {target} ===\n```ts\n<complete corrected file>\n```\n\n"
            "Errors:\n" + "\n".join(groups[target]) + "\n\nCurrent content:\n```ts\n" + body + "\n```\n"
        )
        t0 = time.time()
        resp = post(
            {
                "messages": [
                    {"role": "system", "content": "You are a senior TypeScript engineer repairing exactly one file."},
                    {"role": "user", "content": user},
                ],
                "n_predict": 8192,
                "temperature": temp,
                "cache_prompt": True,
                "chat_template_kwargs": {"enable_thinking": False},
            },
            args.port,
        )
        content = resp["choices"][0]["message"].get("content") or ""
        timings = resp.get("timings", {}) or {}
        blocks = {rel: b for rel, b in FILE_RE.findall(content)}
        if target not in blocks:
            fences = re.findall(r"```[a-zA-Z0-9_-]*\n(.*?)```", content, re.DOTALL)
            if fences:
                blocks[target] = max(fences, key=len)
        changed = False
        if target in blocks:
            with open(tpath, "w", encoding="utf-8", newline="\n") as f:
                f.write(blocks[target].strip() + "\n")
            changed = True
        code, errors = run_tsc(root, f"v2_{attempt}")
        with open(tpath, encoding="utf-8") as f:
            last_output[target] = hashlib.sha1(f.read().encode()).hexdigest()
        n_err = len([l for l in errors.splitlines() if ERR_RE.match(l)])
        log({
            "stage": "repair", "attempt": attempt, "target": target, "exit": code,
            "errors_left": n_err, "changed": changed, "temp": temp,
            "tps": round(float(timings.get("predicted_per_second", 0)), 1),
            "tokens": timings.get("predicted_n"), "seconds": round(time.time() - t0, 1),
        })
        if code == 0:
            print(f"GREEN_BUILD attempt={attempt}")
            return 0

    print("ATTEMPT_LIMIT_REACHED")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
