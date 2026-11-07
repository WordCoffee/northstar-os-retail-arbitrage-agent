#!/usr/bin/env python3
"""Pass@3 — run the 9-file concurrency spec 3x on the coder lane.

Faithful to pass 1 (exports/pass1_coder_17k_v2_20261029):
- same OBJECTIVE.md, verbatim
- same acceptance: `npx tsc --noEmit` exit 0 + the 9 required files
- same build profile: builder + scaffold
- max_steps=24, max_repairs=1 (pass 1's run-3 config; the rewrite gate and
  the no-op verify_stall gate are built into coding_agent.py)

Each run gets a fresh workspace. node_modules is pre-installed before the
agent starts because `npm install` is not in the agent's run allowlist —
pass 1's workspace was set up the same way.

Output: exports/pass3_coder_17k_20261029/run{1..3}.json + pass3_summary.json
"""
import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

OBJECTIVE_PATH = os.path.join(ROOT, "exports", "pass1_coder_17k_v2_20261029", "OBJECTIVE.md")
OUT_DIR = os.path.join(ROOT, "exports", "pass3_coder_17k_20261029")

REQUIRED = [
    "src/types.ts", "src/queue.ts", "src/worker.ts", "src/pool.ts",
    "src/backoff.ts", "src/circuit-breaker.ts", "src/pipeline.ts",
    "src/telemetry.ts", "src/index.ts",
]

RUNS = 3
MAX_STEPS = 24
MAX_REPAIRS = 1

# Same scaffold the harness writes (coding_runner.TS_SCAFFOLD), duplicated so
# npm install can run before the agent starts.
PACKAGE_JSON = {
    "name": "agent-ws", "private": True, "version": "1.0.0",
    "devDependencies": {"typescript": "^5.7.2", "@types/node": "^22.10.2"},
}
TSCONFIG = {
    "compilerOptions": {
        "target": "ES2022", "module": "commonjs", "strict": True,
        "esModuleInterop": True, "skipLibCheck": True, "noEmit": True,
        "types": ["node"],
    },
    "include": ["src/**/*.ts"],
}


def prep_workspace(ws: str) -> None:
    os.makedirs(os.path.join(ws, "src"), exist_ok=True)
    for name, payload in (("package.json", PACKAGE_JSON), ("tsconfig.json", TSCONFIG)):
        p = os.path.join(ws, name)
        if not os.path.exists(p):
            with open(p, "w", encoding="utf-8") as f:
                f.write(json.dumps(payload, indent=2) + "\n")
    # shell=True: on Windows npm is a .cmd shim, not directly executable.
    proc = subprocess.run(
        "npm install --no-audit --no-fund",
        cwd=ws, capture_output=True, text=True, shell=True,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"npm install failed in {ws}: {proc.stderr[-500:]}")


def parse_harness_json(stdout: str):
    s = (stdout or "").strip()
    if not s:
        return None
    try:
        return json.loads(s)
    except Exception:
        pass
    idx = s.rfind("\n{")
    if idx >= 0:
        try:
            return json.loads(s[idx + 1:])
        except Exception:
            return None
    return None


def main() -> int:
    with open(OBJECTIVE_PATH, "r", encoding="utf-8") as f:
        objective = f.read().strip()

    os.makedirs(OUT_DIR, exist_ok=True)
    results = []
    for i in range(1, RUNS + 1):
        ws = os.path.join(OUT_DIR, f"run{i}")
        prep_workspace(ws)
        cmd = [
            sys.executable, os.path.join(HERE, "run_coding_agent.py"),
            "--workspace", ws,
            "--objective", objective,
            "--command", "npx tsc --noEmit",
            "--max-steps", str(MAX_STEPS),
            "--max-repairs", str(MAX_REPAIRS),
            "--builder", "--scaffold",
        ]
        for rf in REQUIRED:
            cmd += ["--required-file", rf]
        t0 = time.time()
        proc = subprocess.run(cmd, capture_output=True, text=True, cwd=ROOT)
        elapsed = round(time.time() - t0, 1)
        harness = parse_harness_json(proc.stdout)
        entry = {"run": i, "exit": proc.returncode, "elapsed_s": elapsed}
        if harness is not None:
            entry["harness"] = {
                k: harness.get(k) for k in
                ("ok", "summary", "steps", "files", "error", "acceptance_recovered")
            }
        else:
            entry["harness_parse_error"] = True
            entry["stdout_tail"] = (proc.stdout or "")[-800:]
        results.append(entry)
        with open(os.path.join(OUT_DIR, f"run{i}.json"), "w", encoding="utf-8") as f:
            json.dump(entry, f, indent=2)
        h = entry.get("harness") or {}
        print(f"run{i}: ok={h.get('ok')} steps={h.get('steps')} "
              f"exit={proc.returncode} elapsed={elapsed}s", flush=True)

    passed = sum(1 for r in results if (r.get("harness") or {}).get("ok") is True)
    summary = {
        "pass_at_3": f"{passed}/{RUNS}",
        "config": {
            "objective": "exports/pass1_coder_17k_v2_20261029/OBJECTIVE.md (verbatim)",
            "acceptance": "npx tsc --noEmit exit 0 + 9 required files",
            "max_steps": MAX_STEPS, "max_repairs": MAX_REPAIRS,
            "builder": True, "scaffold": True,
            "gates": "rewrite gate + no-op verify_stall gate (built into coding_agent.py)",
        },
        "runs": results,
    }
    with open(os.path.join(OUT_DIR, "pass3_summary.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
    print(f"PASS@3 = {passed}/{RUNS}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
