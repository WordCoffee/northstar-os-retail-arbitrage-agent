#!/usr/bin/env python3
"""End-to-end creative flow run: author -> free GPU -> plate -> gate -> compose -> hero.

Two lanes cannot hold the GPU at once: the 27B prompt author needs ~12 GB and
FLUX 3 needs ~6 GB. So the run is serialised, deliberately:

    1. author the plate prompt with the LOCAL 27B (venv-crew, no spend)
    2. stop the 27B lane and wait for VRAM
    3. ensure the FLUX 3 gateway is up
    4. CreativeFlow: plate -> gate -> compose -> hero -> aplus -> report
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "Northstar_backend"))

os.environ.setdefault("MEDIA_GEN_LIVE", "1")

import creative_flow  # noqa: E402
import pouch_label  # noqa: E402
import studio_generation as sg  # noqa: E402

CREW_PY = ROOT / "venv-crew" / "Scripts" / "python.exe"
BRIEF = {
    "product_id": "lions-mane-6oz",
    "material_tier": "premium",
    "substrate": "matte kraft with soft-touch lamination",
    "finish": "unfinished matte fibre",
    "environment": "studio-white",
}
COPY = {"title": "LION'S MANE", "subtitle": "Organic Mushroom Powder",
        "weight": "6 oz (170 g)",
        "bullets": ["Fruiting body only", "Third-party tested", "60 servings"]}


def http_json(url: str, timeout: float = 5.0):
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def author_prompt() -> dict:
    env = dict(os.environ)
    env.setdefault("CREW_BASE_URL", "http://127.0.0.1:8080/v1")
    env.setdefault("CREW_MODEL_NAME", "openai/northstaros-27b-coder")
    env.setdefault("OPENAI_API_KEY", "not-needed-local")
    proc = subprocess.run([str(CREW_PY), "-m", "Northstar_backend.creative_crew",
                           "--author", json.dumps(BRIEF)],
                          cwd=str(ROOT), capture_output=True, text=True,
                          timeout=600, env=env, check=False)
    text = (proc.stdout or "").strip()
    start = text.find("{")
    if start >= 0:
        try:
            return json.loads(text[start:])
        except json.JSONDecodeError:
            pass
    return {"ok": False, "prompt": "", "error": (proc.stderr or text)[-400:]}


def stop_lane() -> None:
    subprocess.run(["powershell", "-NoProfile", "-Command",
                    "Get-Process llama-server -ErrorAction SilentlyContinue | Stop-Process -Force"],
                   capture_output=True, text=True, timeout=60, check=False)
    for _ in range(20):
        try:
            http_json("http://127.0.0.1:8080/health", timeout=1.0)
            time.sleep(1)
        except Exception:
            break


def ensure_gateway() -> bool:
    try:
        http_json("http://127.0.0.1:8190/health", timeout=3.0)
        return True
    except Exception:
        pass
    flags = subprocess.CREATE_NEW_PROCESS_GROUP | getattr(subprocess, "DETACHED_PROCESS", 0)
    subprocess.Popen([sys.executable, str(ROOT / "tools" / "flux3_gateway.py"),
                      "--port", "8190"], cwd=str(ROOT),
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                     creationflags=flags)
    for _ in range(30):
        time.sleep(1)
        try:
            http_json("http://127.0.0.1:8190/health", timeout=2.0)
            return True
        except Exception:
            continue
    return False


def main() -> int:
    out = {"started_at": time.strftime("%Y-%m-%dT%H:%M:%S")}

    authored = author_prompt()
    out["author"] = authored
    prompt = authored.get("prompt") or (
        "Pristine plain kraft stand-up pouch, unprinted uniform texture, flat continuous matte "
        "material, standing upright, soft diffused studio lighting, seamless studio-white "
        "background, photorealistic")

    stop_lane()
    out["gateway_up"] = ensure_gateway()
    if not out["gateway_up"]:
        out["status"] = "gateway_unavailable"
        print(json.dumps(out, indent=2)[:2000])
        return 2

    job = creative_flow.CreativeJob(
        job_id="e2e1027",
        product={"id": "lions-mane-6oz", "target_price": 34.0, "unit_cost": 11.5,
                 "brand": {"colors": ["#1d4a1d"], "fonts": {"heading": "Playfair Display"}}},
        pricing={"target_price": 34.0, "unit_cost": 11.5},
        keywords=["lion's mane powder", "fruiting body mushroom"],
        copy=COPY,
        out_dir=str(ROOT / "exports" / "flow_e2e1027"),
    )
    flow = creative_flow.CreativeFlow(
        job, root=ROOT,
        render=lambda p, w, h: sg.generate_image(p, w, h, tier="draft", seed=4242)["bytes"],
        cutout=lambda b: sg.generate_cutout(b)["bytes"],
        compose=lambda path, **kw: pouch_label.compose(path, **kw),
        prompt_author=lambda _brief: prompt,
    )
    state = flow.run()
    out["flow"] = state
    out["prompt_used"] = prompt
    out["status"] = state["status"]
    print(json.dumps(out, indent=2)[:6000])
    return 0 if state["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
