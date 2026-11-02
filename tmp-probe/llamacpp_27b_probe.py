"""One bounded measurement of the already-installed llama.cpp build on the local 27B.

No download, no install: the binary at %USERPROFILE%\\.config\\northstar-llm\\bin and the
GGUF at C:\\Users\\T2Hol\\models\\northstar-moe are both already on disk. The server is
started on a free port, measured once, and stopped.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import psutil

SERVER = Path(os.path.expandvars(r"%USERPROFILE%\.config\northstar-llm\bin\llama-server.exe"))
MODEL = Path(r"C:\Users\T2Hol\models\northstar-moe\Qwen3.8-27B-IQ4_XS_4BPW.gguf")
PORT = 8099
LOG = Path("state/evidence/llamacpp_27b_server.log")


def free_gb() -> float:
    return round(psutil.virtual_memory().available / 1024 ** 3, 2)


def get(url, timeout=5):
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return json.loads(r.read().decode())


def post(url, payload, timeout=900):
    req = urllib.request.Request(url, data=json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


def main() -> int:
    for path in (SERVER, MODEL):
        if not path.exists():
            print(json.dumps({"error": f"missing {path}"}))
            return 2
    LOG.parent.mkdir(parents=True, exist_ok=True)
    before = {"host_free_gb": free_gb()}
    log = open(LOG, "w", encoding="utf-8")
    proc = subprocess.Popen(
        [str(SERVER), "-m", str(MODEL), "--alias", "qwen38-27b", "-ngl", "99",
         "-c", "4096", "-fa", "on", "--no-webui", "--host", "127.0.0.1",
         "--port", str(PORT)],
        stdout=log, stderr=subprocess.STDOUT, text=True)
    started = time.time()
    ready = False
    try:
        while time.time() - started < 180:
            if proc.poll() is not None:
                break
            try:
                get(f"http://127.0.0.1:{PORT}/health")
                ready = True
                break
            except Exception:  # noqa: BLE001 - still loading
                time.sleep(2)
        out = {"server_ready": ready, "load_s": round(time.time() - started, 1),
               "host_free_before_gb": before["host_free_gb"],
               "host_free_after_load_gb": free_gb()}
        if not ready:
            out["error"] = f"server exited {proc.returncode}"
            out["log_tail"] = LOG.read_text(encoding="utf-8", errors="replace")[-1500:]
            print(json.dumps(out, indent=2))
            return 1
        res = post(f"http://127.0.0.1:{PORT}/completion",
                   {"prompt": "Write one sentence about coffee.", "n_predict": 64,
                    "temperature": 0.2, "cache_prompt": True})
        t = res.get("timings") or {}
        out.update({"prompt_tokens": t.get("prompt_n"),
                    "predicted_tokens": t.get("predicted_n"),
                    "pp_tok_s": round(float(t.get("prompt_per_second") or 0), 2),
                    "tg_tok_s": round(float(t.get("predicted_per_second") or 0), 2),
                    "host_free_after_gen_gb": free_gb(),
                    "reply_head": str(res.get("content") or "")[:120]})
        print(json.dumps(out, indent=2))
        return 0
    finally:
        try:
            proc.terminate()
            proc.wait(timeout=20)
        except Exception:  # noqa: BLE001
            try:
                proc.kill()
            except Exception:  # noqa: BLE001
                pass
        log.close()
        time.sleep(2)
        print(json.dumps({"cleanup_host_free_gb": free_gb()}))


if __name__ == "__main__":
    raise SystemExit(main())
