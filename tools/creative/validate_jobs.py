"""End-to-end validation of the shared creative pipeline.

Runs *complete* jobs (not isolated stages), verifies the saved outputs (existence,
decode, dimensions), provenance sidecars, cancellation, and failure recovery.
Writes a JSON + markdown report to reports/creative_validation/.

Usage: python tools/creative/validate_jobs.py
"""
from __future__ import annotations

import json
import time
import urllib.request
from pathlib import Path

from PIL import Image

REPO = Path(__file__).resolve().parents[2]
OUT = REPO / "reports" / "creative_validation"
OUT.mkdir(parents=True, exist_ok=True)
BASE = "http://127.0.0.1:8000"
SRC = str(REPO / "generated_images" / "mogra_mockups" / "live_scene_turmeric.png")


def _req(path, method="GET", body=None):
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(BASE + path, data=data, method=method,
                               headers={"Content-Type": "application/json"} if data else {})
    with urllib.request.urlopen(r, timeout=30) as resp:
        return json.loads(resp.read())


def run(task, payload, *, timeout=1800):
    jid = _req("/api/creative/pipeline", "POST", {"task": task, "payload": payload})["job_id"]
    t0 = time.time()
    while time.time() - t0 < timeout:
        time.sleep(2)
        j = _req(f"/api/creative/jobs/{jid}")
        if j["status"] in ("done", "error", "cancelled"):
            j["elapsed_s"] = round(time.time() - t0, 2)
            return j
    return {"id": jid, "status": "timeout"}


def verify_output(path):
    if not path or not Path(path).exists():
        return {"exists": False}
    try:
        with Image.open(path) as im:
            res = {"exists": True, "size": list(im.size), "mode": im.mode}
        side = Path(path + ".json")
        res["provenance"] = side.exists()
        if side.exists():
            rec = json.loads(side.read_text(encoding="utf-8"))
            res["provenance_lane"] = rec.get("lane")
            res["commercial_use"] = rec.get("commercial_use")
            res["output_sha256"] = (rec.get("output_sha256") or "")[:16]
        return res
    except Exception as e:
        return {"exists": True, "decode_error": str(e)}


def main():
    results = []

    # 0) routing policy
    lanes = _req("/api/creative/lanes")
    gen = lanes["capabilities"]["generate"]
    routing = {
        "draft": (gen["draft"].get("primary") or {}).get("lane"),
        "standard": (gen["standard"].get("primary") or {}).get("lane"),
        "high": (gen["high"].get("primary") or {}).get("lane"),
        "explicit_lanes": [e["lane"] for e in gen["standard"].get("explicit_lanes", [])],
        "inpaint": (lanes["capabilities"].get("inpaint", {}).get("standard", {}).get("primary") or {}).get("lane"),
    }
    results.append({"check": "routing", "routing": routing})

    # 1) faithful product-photo ad (mask + exact compose)
    presets = _req("/api/creative/presets")
    spec = {"brand": "Mogra Organics", "tagline": "Fuel Your Focus.",
            "product_name": "Organic Turmeric Powder",
            "descriptor": "Ground · 100% Pure", "net_weight": "5 lb (80 oz)"}
    j = run("product_ad", {"source": SRC, "cutout": True,
                           "compose": {"spec": spec,
                                       "surface": presets["surfaces"]["front_label_panel"]}})
    results.append({"check": "product_ad", "status": j["status"], "elapsed_s": j.get("elapsed_s"),
                    "output": verify_output(j.get("output")), "error": j.get("error")})

    # 2) packaging concept with exact labels (generate + compose)
    j = run("packaging_concept", {"prompt": "premium glass jar of turmeric powder on a "
                                            "neutral studio background, blank label panel, "
                                            "no text",
                                  "mode": "draft", "seed": 7,
                                  "compose": {"spec": spec,
                                              "surface": presets["surfaces"]["front_label_panel"]}})
    results.append({"check": "packaging_concept", "status": j["status"], "elapsed_s": j.get("elapsed_s"),
                    "concept": (j.get("result") or {}).get("concept"),
                    "disclaimer": bool((j.get("result") or {}).get("disclaimer")),
                    "composited": verify_output((j.get("result") or {}).get("composited")),
                    "error": j.get("error")})

    # 3) finished ad layout / export
    j = run("ad_layout", {"product": SRC,
                          "background": None, "spec": spec,
                          "export": [1080, 1080]})
    results.append({"check": "ad_layout", "status": j["status"], "elapsed_s": j.get("elapsed_s"),
                    "output": verify_output(j.get("output")), "cutout": verify_output(j.get("result", {}).get("cutout")),
                    "error": j.get("error")})

    # 4) masked edit (inpaint)
    # build a mask covering the lower half (red channel == 1)
    mask = REPO / "generated_images" / "creative" / "validate_mask.png"
    from PIL import ImageDraw
    with Image.open(SRC) as im:
        w, h = im.size
    m = Image.new("RGB", (w, h), (0, 0, 0))
    ImageDraw.Draw(m).rectangle([0, h // 2, w, h], fill=(255, 255, 255))
    mask.parent.mkdir(parents=True, exist_ok=True)
    m.save(mask)
    j = run("inpaint", {"source": SRC, "mask": str(mask),
                        "prompt": "warm walnut wood table surface, soft studio light",
                        "denoise": 0.75, "seed": 11, "steps": 20})
    results.append({"check": "inpaint", "status": j["status"], "elapsed_s": j.get("elapsed_s"),
                    "output": verify_output(j.get("output")), "error": j.get("error")})

    # 5) failure recovery (bad source path -> error, not a crash)
    j = run("upscale", {"source": str(REPO / "does_not_exist.png")})
    results.append({"check": "failure_recovery", "status": j["status"],
                    "error_present": bool(j.get("error")), "error": j.get("error")})

    # 6) cancellation (interrupt a running render)
    jid = _req("/api/creative/pipeline", "POST",
               {"task": "generate", "payload": {"prompt": "a long render",
                                                "mode": "high", "lane": "qwen-t2i",
                                                "width": 1024, "height": 1024}})["job_id"]
    for _ in range(60):  # wait until the worker is actually running
        time.sleep(0.5)
        if _req(f"/api/creative/jobs/{jid}")["status"] == "running":
            break
    time.sleep(12)  # let ComfyUI start sampling so /interrupt has an effect
    _req(f"/api/creative/jobs/{jid}/cancel", "POST")
    j = {"status": "running"}
    for _ in range(60):
        time.sleep(1)
        j = _req(f"/api/creative/jobs/{jid}")
        if j["status"] in ("done", "error", "cancelled"):
            break
    results.append({"check": "cancellation", "status": j["status"]})

    (OUT / "validation_report.json").write_text(json.dumps(results, indent=2), encoding="utf-8")

    # markdown
    lines = ["# Shared Creative — End-to-End Job Validation", "",
             f"Run: {time.strftime('%Y-%m-%dT%H:%M:%S')}", ""]
    for r in results:
        lines.append(f"## {r['check']}")
        lines.append("```json")
        lines.append(json.dumps(r, indent=2))
        lines.append("```")
        lines.append("")
    (OUT / "validation_report.md").write_text("\n".join(lines), encoding="utf-8")

    for r in results:
        print(f"{r['check']}: {r.get('status', 'info')} "
              f"{r.get('error') or ''} {r.get('output') or r.get('routing') or ''}")
    print(f"report -> {OUT / 'validation_report.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
