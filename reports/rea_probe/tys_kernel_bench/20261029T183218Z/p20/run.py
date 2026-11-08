"""Run the three-node project end to end and leave a run log behind."""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
NODES = ["nodes/collect.py", "nodes/summarise.py", "nodes/verify.py"]


def main():
    log = []
    for rel in NODES:
        run = subprocess.run([sys.executable, rel], cwd=str(ROOT),
                             capture_output=True, text=True)
        log.append({"node": rel, "returncode": run.returncode,
                    "stdout": (run.stdout or "").strip()[-400:],
                    "stderr": (run.stderr or "").strip()[-400:]})
        if run.returncode != 0:
            break
    (ROOT / "run_log.json").write_text(
        json.dumps({"nodes": log}, indent=2) + "\n", encoding="utf-8")
    ok = len(log) == len(NODES) and all(e["returncode"] == 0 for e in log)
    print("run ok" if ok else "run failed at %s" % log[-1]["node"])
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
