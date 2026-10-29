"""
REA scoring harness — rerun the baseline instruments and fail on regression.

Every metric is compared against reports/rea_baseline_20261028.json (the recorded
"before"). A metric that was measured in the baseline and cannot be measured now
counts as a regression: losing a measurement is worse than a bad number.

Usage
  python tools/rea_regress.py                # full: all probes + parses
  python tools/rea_regress.py --quick        # skip the slow probes (warp, video)
  python tools/rea_regress.py --with-tests   # add the focused pytest subset
  python tools/rea_regress.py --with-build   # add `npm run build`
  python tools/rea_regress.py --update-baseline   # rewrite the baseline (only with a decision)

Exit code: 0 = no regression, 1 = regression or lost metric.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "reports" / "rea_baseline_20261028.json"
PROBE = ROOT / "reports" / "rea_probe"

LOWER = "lower_better"
HIGHER = "higher_better"

# What the harness refuses to let slide. Each entry says which direction is
# better and how much drift is tolerated before it counts as a regression.
SPEC = [
    {"id": "label_warp_homography_mean_px", "direction": LOWER, "tol": 0.05,
     "why": "1.1: the geometry the shipped compositor uses"},
    {"id": "label_warp_mesh_5x7_mean_px", "direction": LOWER, "tol": 0.05,
     "why": "1.1: L1's acceptance number"},
    {"id": "label_edge_bleed_lum", "direction": LOWER, "tol": 0.05,
     "why": "1.1: halo is geometric, not the feather"},
    {"id": "ocr_legibility_floor_px", "direction": LOWER, "tol": 0.0,
     "why": "1.1: smallest readable cap height on clean art"},
    {"id": "sqlite_errors_at_5s", "direction": LOWER, "tol": 0.0,
     "why": "1.5: concurrent writers must lose nothing"},
    {"id": "lane_create_p95_s", "direction": LOWER, "tol": 0.25,
     "why": "1.5: the tail the operator actually feels"},
    {"id": "label_intent_tool_ratio", "direction": HIGHER, "tol": 0.0,
     "why": "1.6: turns reaching the label tool"},
    {"id": "ink_faint_contrast", "direction": HIGHER, "tol": 0.0,
     "why": "1.6: WCAG 2.2 AA needs 4.5:1"},
    {"id": "social_canvases_without_source", "direction": LOWER, "tol": 0.0,
     "why": "1.4: provenance coverage"},
    {"id": "social_canvases_missing", "direction": LOWER, "tol": 0.0,
     "why": "1.4: documented placements with no canvas"},
    {"id": "video_clip_seconds", "direction": HIGHER, "tol": 0.0,
     "why": "1.3: a real assembled clip exists"},
    {"id": "feather_policy_ok", "direction": HIGHER, "tol": 0.0,
     "why": "L3: feather must follow the residual, clamped 1-12 px"},
    {"id": "logo_tool_present", "direction": HIGHER, "tol": 0.0,
     "why": "U3: the logo gap had no tool at all"},
    {"id": "social_validator_ok", "direction": HIGHER, "tol": 0.0,
     "why": "S4: a correct asset passes, a wrong ratio blocks"},
]


# ── extractors ──────────────────────────────────────────────────────────────

def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _run(cmd: list[str]) -> tuple[int, str]:
    r = subprocess.run(cmd, capture_output=True, text=True, cwd=str(ROOT))
    return r.returncode, (r.stdout + r.stderr)


def m_warp() -> dict:
    code, out = _run([sys.executable, "tools/rea_warp_probe.py"])
    data = json.loads(_read(PROBE / "warp_probe.json")) if (PROBE / "warp_probe.json").is_file() else {}
    rows = {r["method"]: r for r in data.get("warp_error", [])}
    halo = [h["bleed_outside_true_edge_lum"] for h in data.get("halo", [])
            if h["quad_overshoot_px"] == 1 and h["feather_sigma_px"] == 0]
    return {
        "label_warp_homography_mean_px": rows.get("4-point homography (today)", {}).get("mean_px"),
        "label_warp_mesh_5x7_mean_px": rows.get("quad mesh 5x7", {}).get("mean_px"),
        "label_edge_bleed_lum": halo[0] if halo else None,
        "ocr_legibility_floor_px": (data.get("ocr_floor") or {}).get("first_detected_font_px"),
        "_probe_exit": code,
    }


def m_video() -> dict:
    code, _ = _run([sys.executable, "tools/rea_video_probe.py"])
    path = PROBE / "video" / "video_probe.json"
    data = json.loads(_read(path)) if path.is_file() else {}
    return {
        "video_clip_seconds": (data.get("output") or {}).get("duration_s"),
        "_probe_exit": code,
    }


def m_bojo() -> dict:
    code, _ = _run([sys.executable, "tools/rea_bojo_probe.py"])
    path = PROBE / "bojo_probe.json"
    data = json.loads(_read(path)) if path.is_file() else {}
    sqlite = {s["busy_timeout_ms"]: s for s in data.get("sqlite", [])}
    lanes = data.get("lane_latency", {}).get("by_lane", {})
    create = lanes.get("chat:default|create", {})
    return {
        "sqlite_errors_at_5s": sqlite.get(5000, {}).get("errors"),
        "lane_create_p95_s": create.get("p95_s"),
        "_probe_exit": code,
    }


def m_smui() -> dict:
    code, _ = _run([sys.executable, "tools/rea_smui_intents.py"])
    path = PROBE / "smui_intents.json"
    data = json.loads(_read(path)) if path.is_file() else {}
    intents = dict(data.get("intent_counts", []))
    calls = {t["tool"]: t["calls"] for t in data.get("tool_usage", [])}
    label_turns = intents.get("label / pouch composite") or 0
    label_calls = calls.get("apply_label", 0)
    return {
        "label_intent_tool_ratio": round(label_calls / label_turns, 4) if label_turns else None,
        "_label_turns": label_turns,
        "_label_calls": label_calls,
        "_probe_exit": code,
    }


def _contrast(hex_fg: str, hex_bg: str) -> float:
    def lum(h: str) -> float:
        h = h.lstrip("#")
        r, g, b = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
        f = lambda c: c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
        return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b)
    a, b = sorted([lum(hex_fg), lum(hex_bg)])
    return round((b + 0.05) / (a + 0.05), 2)


def m_css() -> dict:
    css = _read(ROOT / "northstar-os-ui" / "src" / "styles" / "simple.css")
    ink_faint = re.search(r"--ink-faint:\s*(#[0-9a-fA-F]{6})", css)
    surface = re.search(r"background:\s*(#1a2435)", css)
    bg = surface.group(1) if surface else "#1a2435"
    return {
        "ink_faint_contrast": _contrast(ink_faint.group(1), bg) if ink_faint else None,
        "_surface": bg,
    }


SOCIAL_REQUIRED = [
    "ig-post", "ig-carousel", "pin", "x-post", "linkedin", "yt-thumb",
    "meta-story", "tiktok", "pin-video", "pin-idea", "x-carousel",
    "x-vertical", "yt-shorts-thumb",
]


def m_social() -> dict:
    """Every social canvas must carry a source reference; every required canvas
    must exist. This is the S1/S2 gate.

    Parsed line-by-line on purpose: the format objects are single-line, while a
    brace-matching regex swallows the first entry inside each group object.
    """
    js = _read(ROOT / "northstar-os-ui" / "src" / "studio" / "engine" / "presets.js")
    found = {}
    for line in js.splitlines():
        m = re.search(r"id:\s*'([\w-]+)'", line)
        if not m or " w:" not in line or " h:" not in line:
            continue
        found[m.group(1)] = line
    present = [i for i in SOCIAL_REQUIRED if i in found]
    without_source = [i for i in present if "source:" not in found[i]]
    missing = [i for i in SOCIAL_REQUIRED if i not in found]
    return {
        "social_canvases_without_source": len(without_source),
        "social_canvases_missing": len(missing),
        "_detail": {"present": len(present), "without_source": without_source, "missing": missing},
    }


def m_tests() -> dict:
    code, out = _run([sys.executable, "-m", "pytest",
                      "test_mockup_compositor.py", "test_compositor_realism.py",
                      "test_pouch_label_placement.py", "-q"])
    m = re.search(r"(\d+) passed(?:, (\d+) failed)?", out)
    return {
        "focused_tests_passed": int(m.group(1)) if m else None,
        "focused_tests_failed": int(m.group(2) or 0) if m else None,
        "_exit": code,
    }


def m_build() -> dict:
    code, out = _run(["npm", "run", "build"])
    return {
        "npm_build_ok": 1 if code == 0 else 0,
        "_errors": re.findall(r"error[^\n]*", out, re.I)[:3],
    }


def m_guards() -> dict:
    """Cheap capability gates added after wave 2/3. 1 = the guard holds."""
    out: dict = {}
    sys.path.insert(0, str(ROOT / "Northstar_backend"))
    try:
        import mockup_compositor as mc
        out["feather_policy_ok"] = 1 if (
            abs(mc.feather_sigma(1.0) - 2.5) < 1e-6
            and mc.feather_sigma(0.1) == 1.0
            and mc.feather_sigma(10.0) == 12.0
        ) else 0
    except Exception as exc:  # noqa: BLE001
        out["feather_policy_ok"] = 0
        out["_feather_error"] = type(exc).__name__
    try:
        import chat_tools
        out["logo_tool_present"] = 1 if "place_logo" in chat_tools.tool_names() else 0
    except Exception as exc:  # noqa: BLE001
        out["logo_tool_present"] = 0
        out["_logo_error"] = type(exc).__name__
    try:
        import io
        from PIL import Image
        import social_validate as sv
        good = io.BytesIO()
        Image.new("RGB", (1000, 1500)).save(good, format="PNG")
        bad = io.BytesIO()
        Image.new("RGB", (1080, 1080)).save(bad, format="PNG")
        ok_good = sv.validate(good.getvalue(), "pin")["ok"] is True
        ok_bad = sv.validate(bad.getvalue(), "ig-post")["ok"] is False
        out["social_validator_ok"] = 1 if (ok_good and ok_bad) else 0
    except Exception as exc:  # noqa: BLE001
        out["social_validator_ok"] = 0
        out["_social_error"] = type(exc).__name__
    return out


# ── baseline mapping ────────────────────────────────────────────────────────

def baseline_values() -> dict:
    if not BASE.is_file():
        return {}
    b = json.loads(_read(BASE))["metrics"]

    def g(*path):
        cur = b
        for p in path:
            if isinstance(cur, dict):
                cur = cur.get(p)
            else:
                return None
        return cur if isinstance(cur, (int, float)) else None

    return {
        "label_warp_homography_mean_px": g("label_warp_reprojection_error_px", "homography_mean_px"),
        "label_warp_mesh_5x7_mean_px": g("label_warp_reprojection_error_px", "mesh_5x7_mean_px"),
        "label_edge_bleed_lum": g("label_edge_bleed_lum", "quad_overshoot_1px_feather_0"),
        "ocr_legibility_floor_px": g("ocr_legibility_floor_clean_art_px", "first_detected_font_px"),
        "sqlite_errors_at_5s": g("sqlite_writer_contention", "busy_timeout_5000ms", "errors"),
        "lane_create_p95_s": g("lane_latency_s", "create", "p95"),
        "label_intent_tool_ratio": None,  # derived below from the raw counts
        "ink_faint_contrast": g("smui_contrast_wcag", "ink_faint"),
        "social_canvases_without_source": g("social_spec_staleness", "canvases_without_source"),
        "social_canvases_missing": g("social_spec_staleness", "missing_canvases"),
        "video_clip_seconds": g("video_assembly", "duration_s"),
        "feather_policy_ok": g("guards", "feather_policy_ok"),
        "logo_tool_present": g("guards", "logo_tool_present"),
        "social_validator_ok": g("guards", "social_validator_ok"),
    }


def baseline_label_ratio() -> float | None:
    b = json.loads(_read(BASE))["metrics"]
    turns = b.get("smui_turns_to_tool", {}).get("by_intent", {}).get("label_composite", {})
    t, c = turns.get("turns"), turns.get("tool_calls")
    return round(c / t, 4) if t and c is not None else None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true", help="skip the warp and video probes")
    ap.add_argument("--with-tests", action="store_true")
    ap.add_argument("--with-build", action="store_true")
    ap.add_argument("--update-baseline", action="store_true")
    args = ap.parse_args()

    current: dict = {}
    current.update(m_css())
    current.update(m_social())
    current.update(m_guards())
    current.update(m_smui())
    current.update(m_bojo())
    skipped: set[str] = set()
    if not args.quick:
        current.update(m_warp())
        current.update(m_video())
    else:
        skipped = {"label_warp_homography_mean_px", "label_warp_mesh_5x7_mean_px",
                   "label_edge_bleed_lum", "ocr_legibility_floor_px", "video_clip_seconds"}
    if args.with_tests:
        current.update(m_tests())
    if args.with_build:
        current.update(m_build())

    base = baseline_values()
    base["label_intent_tool_ratio"] = baseline_label_ratio()

    rows, failures, unmeasured = [], [], []
    for spec in SPEC:
        mid, direction, tol = spec["id"], spec["direction"], spec["tol"]
        before = base.get(mid)
        after = current.get(mid)
        if mid in skipped:
            verdict = "skipped"
        elif before is None:
            verdict = "no baseline"
        elif after is None:
            verdict = "LOST"
        elif direction == LOWER:
            limit = before * (1 + tol) + 1e-9
            verdict = "ok" if after <= limit else "REGRESSED"
        else:
            limit = before * (1 - tol) - 1e-9
            verdict = "ok" if after >= limit else "REGRESSED"
        if verdict in ("REGRESSED", "LOST"):
            failures.append((mid, before, after, verdict))
        if before is not None and after is None and mid not in skipped:
            unmeasured.append(mid)
        rows.append((mid, before, after, direction, verdict, spec["why"]))

    # informational probes: reported, never gating
    info = [(k, v) for k, v in current.items() if k.startswith("_")]

    def fmt(v):
        if v is None:
            return "  n/a  "
        if isinstance(v, float):
            return f"{v:8.3f}"
        return f"{v:8}"

    print("\nREA REGRESSION REPORT".center(96, "="))
    print(f"{'metric':38} {'before':>10} {'after':>10}  {'dir':6} verdict")
    print("-" * 96)
    for mid, before, after, direction, verdict, why in rows:
        print(f"{mid:38} {fmt(before):>10} {fmt(after):>10}  "
              f"{'lower' if direction == LOWER else 'higher':6} {verdict}")
        if verdict != "ok":
            print(f"{'':38} ^ {why}")
    print("-" * 96)
    if info:
        print("probe detail:", {k: v for k, v in info})
    if failures:
        print(f"\nFAIL: {len(failures)} metric(s) regressed or lost:")
        for mid, before, after, verdict in failures:
            print(f"  - {mid}: {before} -> {after} ({verdict})")
        return 1
    print("\nPASS: every measured metric is at or better than baseline.")
    if unmeasured:
        print("note: no current value for", unmeasured)
    return 0


if __name__ == "__main__":
    sys.exit(main())
