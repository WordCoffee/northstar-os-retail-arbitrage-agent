#!/usr/bin/env python3
"""Generate -> tsc -> repair loop for the MoE coder lane.

Phase 1: 4-round file generation (same protocol as tools/moe_agentic_build.py).
Phase 2: run `npx tsc --noEmit`; on failure send the compiler output back and ask
         for corrected files. Up to --attempts repair rounds. Stops on exit code 0.
Logs every stage to <out>/repair_log.jsonl and writes tsc_attempt_N.txt.
"""
import argparse
import json
import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from moe_agentic_build import FILE_RE, ROUNDS, SYSTEM_SUFFIX, post, safe_path  # noqa: E402

REPAIR_INSTRUCTION = """The TypeScript compiler rejected the workspace. Fix EVERY error listed below.

Return ONLY the files that need changes (do not re-emit unchanged files), each in this exact shape:
=== FILE: relative/path.ts ===
```ts
<complete corrected file>
```

Rules:
- Complete files only; no diffs, no ellipses, no TODOs, no commentary.
- Keep the existing public API unless a signature is itself the error.
- Strict TypeScript must pass: no `any` escapes that hide the error.
- Node built-ins and globals must be imported/used correctly.

tsc --noEmit output:
{errors}
"""


def list_ts_files(root: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for base in ("src", "tests"):
        d = os.path.join(root, base)
        if not os.path.isdir(d):
            continue
        for name in sorted(os.listdir(d)):
            if name.endswith(".ts"):
                p = os.path.join(d, name)
                with open(p, encoding="utf-8") as f:
                    out[f"{base}/{name}"] = f.read()
    return out


def run_tsc(root: str, attempt: int) -> tuple[int, str]:
    proc = subprocess.run(
        "npx tsc --noEmit",
        cwd=root,
        shell=True,
        capture_output=True,
        text=True,
        timeout=600,
    )
    out = (proc.stdout or "") + (proc.stderr or "")
    with open(os.path.join(root, f"tsc_attempt_{attempt}.txt"), "w", encoding="utf-8") as f:
        f.write(out)
    return proc.returncode, out.strip()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--prompt", required=True)
    ap.add_argument("--port", type=int, default=8080)
    ap.add_argument("--attempts", type=int, default=3)
    ap.add_argument("--generate", action="store_true", help="run the 4-round generation first")
    args = ap.parse_args()

    root = os.path.abspath(args.out)
    os.makedirs(root, exist_ok=True)
    log_path = os.path.join(root, "repair_log.jsonl")

    def log(rec: dict) -> None:
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec) + "\n")
        print(json.dumps(rec), flush=True)

    if args.generate:
        brief = open(args.prompt, encoding="utf-8-sig").read().strip()
        messages = [{"role": "system", "content": brief + SYSTEM_SUFFIX}]
        for i, (name, instruction) in enumerate(ROUNDS, start=1):
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
            content = resp["choices"][0]["message"].get("content") or ""
            timings = resp.get("timings", {}) or {}
            files = FILE_RE.findall(content)
            for rel, body in files:
                path = safe_path(root, rel)
                os.makedirs(os.path.dirname(path), exist_ok=True)
                with open(path, "w", encoding="utf-8", newline="\n") as f:
                    f.write(body.strip() + "\n")
            log(
                {
                    "stage": "generate",
                    "round": i,
                    "name": name,
                    "tps": round(float(timings.get("predicted_per_second", 0)), 1),
                    "tokens": timings.get("predicted_n"),
                    "files": [p for p, _ in files],
                    "seconds": round(time.time() - t0, 1),
                }
            )
            messages.append({"role": "assistant", "content": content})

    code, errors = run_tsc(root, 0)
    log({"stage": "tsc", "attempt": 0, "exit": code, "errors": errors[:4000]})
    if code == 0:
        print("GREEN_BUILD attempt=0")
        return 0

    for attempt in range(1, args.attempts + 1):
        files = list_ts_files(root)
        blocks = "\n".join(
            f"=== FILE: {p} ===\n```ts\n{body}```" for p, body in files.items()
        )
        user = REPAIR_INSTRUCTION.format(errors=errors) + "\nCurrent files:\n" + blocks
        t0 = time.time()
        resp = post(
            {
                "messages": [
                    {"role": "system", "content": "You are a senior TypeScript engineer fixing compile errors. Output only corrected files in the required block format."},
                    {"role": "user", "content": user},
                ],
                "n_predict": 8192,
                "temperature": 0.1,
                "cache_prompt": True,
                "chat_template_kwargs": {"enable_thinking": False},
            },
            args.port,
        )
        content = resp["choices"][0]["message"].get("content") or ""
        timings = resp.get("timings", {}) or {}
        changed = FILE_RE.findall(content)
        for rel, body in changed:
            path = safe_path(root, rel)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8", newline="\n") as f:
                f.write(body.strip() + "\n")
        code, errors = run_tsc(root, attempt)
        log(
            {
                "stage": "repair",
                "attempt": attempt,
                "exit": code,
                "tps": round(float(timings.get("predicted_per_second", 0)), 1),
                "tokens": timings.get("predicted_n"),
                "files_changed": [p for p, _ in changed],
                "error_count": 0 if code == 0 else len([l for l in errors.splitlines() if ": error TS" in l]),
                "seconds": round(time.time() - t0, 1),
            }
        )
        if code == 0:
            print(f"GREEN_BUILD attempt={attempt}")
            return 0

    print("ATTEMPT_LIMIT_REACHED")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
