#!/usr/bin/env python3
"""Per-file isolated repair loop.

Each attempt targets ONE file (the one with the most remaining errors) and sends only
that file plus its compiler errors. Up to --attempts rounds. Stops on tsc exit 0.
"""
import argparse
import json
import os
import re
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from moe_agentic_build import FILE_RE, post, safe_path  # noqa: E402

ERR_RE = re.compile(r"^(.+?)\((\d+),(\d+)\): error (TS\d+): (.*)$")


def run_tsc(root: str, tag: str) -> tuple[int, str]:
    proc = subprocess.run("npx tsc --noEmit", cwd=root, shell=True, capture_output=True, text=True, timeout=600)
    out = ((proc.stdout or "") + (proc.stderr or "")).strip()
    with open(os.path.join(root, f"tsc_{tag}.txt"), "w", encoding="utf-8") as f:
        f.write(out)
    return proc.returncode, out


def parse_errors(text: str) -> dict[str, list[str]]:
    groups: dict[str, list[str]] = {}
    current_file = None
    for line in text.splitlines():
        m = ERR_RE.match(line)
        if m:
            current_file = m.group(1)
            groups.setdefault(current_file, []).append(line)
        elif current_file and (line.startswith("  ") or line.startswith("\t")):
            groups[current_file].append(line)
    return groups


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--port", type=int, default=8080)
    ap.add_argument("--attempts", type=int, default=6)
    args = ap.parse_args()

    root = os.path.abspath(args.out)
    log_path = os.path.join(root, "repair_perfile_log.jsonl")

    def log(rec: dict) -> None:
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec) + "\n")
        print(json.dumps(rec), flush=True)

    code, errors = run_tsc(root, "perfile_0")
    log({"stage": "tsc", "attempt": 0, "exit": code, "error_lines": len([l for l in errors.splitlines() if ERR_RE.match(l)])})
    if code == 0:
        print("GREEN_BUILD attempt=0")
        return 0

    for attempt in range(1, args.attempts + 1):
        groups = parse_errors(errors)
        if not groups:
            break
        target = max(groups.items(), key=lambda kv: len(kv[1]))[0]
        tpath = os.path.join(root, *target.replace("\\", "/").split("/"))
        try:
            with open(tpath, encoding="utf-8") as f:
                body = f.read()
        except FileNotFoundError:
            print(f"missing file {target}")
            return 3

        user = (
            f"File: {target}\n\n"
            "The TypeScript compiler reports the errors below in this file only. Fix all of them in this file.\n"
            "Return ONLY this file, complete, in this exact shape:\n"
            f"=== FILE: {target} ===\n```ts\n<complete corrected file>\n```\n\n"
            "Errors:\n" + "\n".join(groups[target]) + "\n\n"
            "Current content:\n```ts\n" + body + "\n```\n"
        )
        t0 = time.time()
        resp = post(
            {
                "messages": [
                    {"role": "system", "content": "You are a senior TypeScript engineer. Repair exactly one file. Output only that file in the required block format."},
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
        with open(os.path.join(root, f"raw_attempt_{attempt}.txt"), "w", encoding="utf-8") as f:
            f.write(content)
        blocks = {rel: b for rel, b in FILE_RE.findall(content)}
        if target not in blocks:
            fences = re.findall(r"```[a-zA-Z0-9_-]*\n(.*?)```", content, re.DOTALL)
            if fences:
                blocks[target] = max(fences, key=len)
        changed = []
        if target in blocks:
            with open(tpath, "w", encoding="utf-8", newline="\n") as f:
                f.write(blocks[target].strip() + "\n")
            changed.append(target)
        code, errors = run_tsc(root, f"perfile_{attempt}")
        n_err = len([l for l in errors.splitlines() if ERR_RE.match(l)])
        log(
            {
                "stage": "repair",
                "attempt": attempt,
                "target": target,
                "exit": code,
                "errors_left": n_err,
                "changed": changed,
                "content_chars": len(content),
                "block_paths": list(blocks.keys()),
                "tps": round(float(timings.get("predicted_per_second", 0)), 1),
                "tokens": timings.get("predicted_n"),
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
