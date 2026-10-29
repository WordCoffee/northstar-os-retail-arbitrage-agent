"""Content validators for NS-PROJ-20 artifacts.

These are machine checks built from instruments already in the repo:
  * labels: PNG magic + text_fidelity OCR + package_readiness prepress
  * ads: ffprobe container/streams/duration/resolution
  * A+: specRegistry module ids (the file is read, not executed)
  * text/patch/json/social: schema, required terms, length

They do not judge prose quality. A pass means the artifact is the right kind and
carries the required evidence.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "Northstar_backend"))
from agent_kernel.artifacts import parse_json_text, strip_markdown_fence  # noqa: E402

BRIEFS = ROOT / "eval/projects/ns_proj_20.json"
SPEC_REGISTRY = ROOT / "northstar-os-ui/src/studio/engine/specRegistry.js"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace") if path.is_file() else ""


def _norm(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", text.lower())


def validate_label(path: Path, terms: List[str]) -> Dict[str, Any]:
    raw = path.read_bytes() if path.is_file() else b""
    checks: Dict[str, Any] = {"png_magic": raw.startswith(b"\x89PNG\r\n\x1a\n")}
    if not checks["png_magic"]:
        return {"kind": "label", "valid": False, "checks": checks,
                "detail": "not a PNG"}
    try:
        import text_fidelity as tf
        import package_readiness as pr
    except Exception as exc:  # noqa: BLE001
        return {"kind": "label", "valid": False, "checks": checks,
                "detail": f"instruments unavailable: {exc}"}
    ocr = tf.check_text_in_image(raw)
    words = " ".join(ocr.get("words") or [])
    checks["ocr_status"] = ocr.get("status")
    checks["ocr_terms"] = {t: (_norm(t) in _norm(words)) for t in terms}
    prepress = pr.assess_prepress(raw)
    checks["prepress_assessed"] = bool(prepress.get("assessed"))
    checks["prepress_verdict"] = prepress.get("verdict")
    checks["printable"] = prepress.get("verdict") == "printable"
    valid = (checks["ocr_status"] == "ok"
             and all(checks["ocr_terms"].values())
             and checks["prepress_assessed"] and checks["printable"])
    return {"kind": "label", "valid": valid, "checks": checks,
            "detail": "OCR terms + prepress"}


def validate_ad(path: Path) -> Dict[str, Any]:
    if not path.is_file():
        return {"kind": "ad", "valid": False, "checks": {}, "detail": "missing"}
    try:
        r = subprocess.run(["ffprobe", "-v", "error", "-print_format", "json",
                            "-show_format", "-show_streams", str(path)],
                           capture_output=True, text=True, timeout=60)
    except Exception as exc:  # noqa: BLE001
        return {"kind": "ad", "valid": False, "checks": {},
                "detail": f"ffprobe unavailable: {exc}"}
    if r.returncode != 0:
        return {"kind": "ad", "valid": False, "checks": {},
                "detail": (r.stderr or "")[:200]}
    data = json.loads(r.stdout)
    streams = data.get("streams") or []
    video = next((s for s in streams if s.get("codec_type") == "video"), None)
    audio = next((s for s in streams if s.get("codec_type") == "audio"), None)
    duration = float((data.get("format") or {}).get("duration") or 0)
    checks = {
        "video_stream": video is not None,
        "audio_stream": audio is not None,
        "duration_s": round(duration, 2),
        "duration_12_15": 12.0 <= duration <= 15.0,
        "width": (video or {}).get("width"),
        "height": (video or {}).get("height"),
        "vertical_1080x1920": ((video or {}).get("width") == 1080
                               and (video or {}).get("height") == 1920),
    }
    valid = all(checks[k] for k in ("video_stream", "audio_stream",
                                    "duration_12_15", "vertical_1080x1920"))
    return {"kind": "ad", "valid": valid, "checks": checks, "detail": "ffprobe"}


def validate_patch(path: Path) -> Dict[str, Any]:
    text, _ = strip_markdown_fence(_read(path))
    checks = {"has_minus_file": "---" in text, "has_plus_file": "+++" in text,
              "has_hunk": bool(re.search(r"^@@", text, re.M))}
    return {"kind": "patch", "valid": all(checks.values()), "checks": checks,
            "detail": "unified diff shape"}


def validate_json(path: Path) -> Dict[str, Any]:
    text, _ = strip_markdown_fence(_read(path))
    try:
        data = parse_json_text(text)
        valid = True
        detail = f"parsed {type(data).__name__}"
    except Exception as exc:  # noqa: BLE001
        valid = False
        detail = f"json error: {str(exc)[:120]}"
    return {"kind": "json", "valid": valid, "checks": {}, "detail": detail}


def validate_text(path: Path, terms: List[str], min_chars: int = 120) -> Dict[str, Any]:
    text, fenced = strip_markdown_fence(_read(path))
    low = text.lower()
    checks = {"chars": len(text), "min_chars": min_chars,
              "long_enough": len(text) >= min_chars,
              "terms": {t: t.lower() in low for t in terms}}
    valid = checks["long_enough"] and all(checks["terms"].values())
    return {"kind": "text", "valid": valid, "checks": checks,
            "detail": "length + required terms"}


def validate_social(path: Path) -> Dict[str, Any]:
    """Social canvas JSON: every entry names a format and a documented size."""
    text, _ = strip_markdown_fence(_read(path))
    try:
        data = parse_json_text(text)
    except Exception as exc:  # noqa: BLE001
        return {"kind": "social", "valid": False, "checks": {},
                "detail": f"json error: {str(exc)[:120]}"}
    expected = {"ig-post": (1440, 1800), "meta-story": (1440, 2560),
                "x-post": (1200, 628), "linkedin": (628, 628),
                "yt-thumb": (3840, 2160)}
    rows = data if isinstance(data, list) else data.get("canvases") or []
    checks = {"entries": len(rows), "formats": {}}
    ok = len(rows) >= 3
    for row in rows[:20]:
        fmt = str(row.get("format") or row.get("id") or "")
        size = expected.get(fmt)
        good = bool(size and int(row.get("width") or 0) == size[0]
                    and int(row.get("height") or 0) == size[1])
        checks["formats"][fmt] = good
        ok = ok and good
    return {"kind": "social", "valid": bool(ok), "checks": checks,
            "detail": "format + documented size"}


def validate_aplus(path: Path) -> Dict[str, Any]:
    """A+ markdown must name at least three module ids that exist in the registry."""
    text = _read(path)
    registry = _read(SPEC_REGISTRY)
    ids = set(re.findall(r"id:\s*['\"]([a-z0-9-]+)['\"]", registry))
    named = [i for i in ids if i in text.lower()]
    checks = {"registry_ids": len(ids), "named": named,
              "at_least_three": len(named) >= 3}
    return {"kind": "aplus", "valid": bool(ids) and len(named) >= 3,
            "checks": checks, "detail": "specRegistry ids named"}


def validate_brief(folder: Path, brief: Dict[str, Any]) -> Dict[str, Any]:
    path = folder / brief["id"] / brief["artifact"]
    kind = str(brief.get("validator") or "text")
    terms = list(brief.get("terms") or [])
    if kind == "label":
        return validate_label(path, terms or ["ORGANIC LION'S MANE",
                                              "MUSHROOM POWDER", "6 oz"])
    if kind == "ad":
        return validate_ad(path)
    if kind == "patch":
        return validate_patch(path)
    if kind == "json":
        return validate_json(path)
    if kind == "social":
        return validate_social(path)
    if kind == "aplus":
        return validate_aplus(path)
    return validate_text(path, terms, int(brief.get("min_chars") or 120))


def run(folder: Path) -> Dict[str, Any]:
    briefs = json.loads(BRIEFS.read_text(encoding="utf-8"))["briefs"]
    rows = []
    for b in briefs:
        r = validate_brief(folder, b)
        rows.append({"id": b["id"], "artifact": b["artifact"], **r})
    passed = sum(1 for r in rows if r["valid"])
    return {"folder": str(folder), "valid": passed, "total": len(rows),
            "rate": round(passed / max(1, len(rows)), 3),
            "rows": rows}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--folder", required=True)
    ap.add_argument("--out", default="")
    args = ap.parse_args()
    folder = Path(args.folder)
    out = run(folder)
    target = Path(args.out) if args.out else folder / "content_audit.json"
    target.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(json.dumps({"valid": out["valid"], "total": out["total"],
                      "rate": out["rate"],
                      "failed": [r["id"] for r in out["rows"] if not r["valid"]]},
                     indent=2))
    return 0 if out["valid"] == out["total"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
