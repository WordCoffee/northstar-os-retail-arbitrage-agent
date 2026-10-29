"""Content validators shared by the kernel and the benchmark CLI.

These are machine checks built from instruments already in the repo:
labels (text_fidelity + package_readiness), ads (ffprobe), A+ (specRegistry),
and schema/length checks for text, patch, JSON and social canvases.

A pass means the artifact is the right kind and carries the required evidence;
it is not a judgement of prose or design.
"""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

from .artifacts import parse_json_text, strip_markdown_fence

ROOT = Path(__file__).resolve().parents[2]
BRIEFS = ROOT / "eval/projects/ns_proj_20.json"
SPEC_REGISTRY = ROOT / "northstar-os-ui/src/studio/engine/specRegistry.js"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace") if path.is_file() else ""


def _norm(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", text.lower())


# ── semantic helpers ────────────────────────────────────────────────────────
# A keyword match proves the artifact mentions a thing. These checks prove it is
# the *kind* of document it claims to be: it says something, it is not still the
# stub it started from, its diff arithmetic holds, and its JSON carries the keys
# the brief actually requires.

# A placeholder is a *marker*, not a word: line-leading TODO/TBD/FIXME/XXX, a
# bullet or checkbox form of the same, or an inline "TODO:" / "FIXME:".
# Prose that merely says the word "todo" is not a placeholder.
PLACEHOLDER_RE = re.compile(
    r"(?im)^\s*(?:[-*>]\s*)?(?:\[[ xX]\]\s*)?(TODO|TBD|FIXME|XXX)\b"
    r"|\b(TODO|FIXME):")

_HUNK_RE = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")
_SENTENCE_RE = re.compile(r"[.!?](?:\s|$)")


def _sentence_count(text: str) -> int:
    return len(_SENTENCE_RE.findall(text))


def _heading_count(text: str) -> int:
    return len(re.findall(r"^#{1,6}\s+\S", text, re.M))


def _semantic_text(text: str, brief: Dict[str, Any]) -> Dict[str, Any]:
    """Structure, not prose quality: does this read as finished work?"""
    sem = dict(brief.get("semantics") or {})
    placeholders = sorted({next(g for g in m.groups() if g)
                           for m in PLACEHOLDER_RE.finditer(text)})
    checks: Dict[str, Any] = {
        "placeholders": placeholders,
        "no_placeholders": not placeholders,
        "sentences": _sentence_count(text),
        "headings": _heading_count(text),
    }
    floor = int(sem.get("min_sentences") or 3)
    checks["min_sentences"] = floor
    checks["enough_sentences"] = checks["sentences"] >= floor
    required_headings = list(sem.get("required_headings") or [])
    if required_headings:
        checks["required_headings"] = {
            h: bool(re.search(r"^#{1,6}\s*%s" % re.escape(h), text, re.I | re.M))
            for h in required_headings}
        checks["has_headings"] = all(checks["required_headings"].values())
    ok = checks["no_placeholders"] and checks["enough_sentences"] and checks.get(
        "has_headings", True)
    return {"ok": ok, "checks": checks}


def _semantic_patch(text: str) -> Dict[str, Any]:
    """Hunk arithmetic: the declared line counts must match the hunk body.

    A patch can carry `---`, `+++` and `@@` and still be unusable. This is the
    check `git apply` would make, minus the filesystem: if the counts disagree,
    the patch is wrong no matter how plausible it looks.
    """
    checks: Dict[str, Any] = {"hunks": 0, "bad_hunks": []}
    old_expected = new_expected = None
    old_seen = new_seen = 0
    hunk_line = 0

    def close_hunk() -> None:
        nonlocal old_expected, new_expected, old_seen, new_seen
        if old_expected is not None and (old_seen != old_expected
                                         or new_seen != new_expected):
            checks["bad_hunks"].append(
                {"line": hunk_line, "old": [old_seen, old_expected],
                 "new": [new_seen, new_expected]})
        old_expected = new_expected = None
        old_seen = new_seen = 0

    for number, line in enumerate(text.splitlines(), 1):
        if line.startswith("--- "):
            close_hunk()
            continue
        if line.startswith("+++ "):
            continue
        match = _HUNK_RE.match(line)
        if match:
            close_hunk()
            checks["hunks"] += 1
            hunk_line = number
            old_expected = int(match.group(2) or 1)
            new_expected = int(match.group(4) or 1)
            continue
        if old_expected is None:
            continue
        tag = line[:1]
        if tag in (" ", ""):
            old_seen += 1
            new_seen += 1
        elif tag == "-":
            old_seen += 1
        elif tag == "+":
            new_seen += 1
    close_hunk()
    checks["arithmetic_ok"] = checks["hunks"] > 0 and not checks["bad_hunks"]
    return {"ok": bool(checks["arithmetic_ok"]), "checks": checks}


def _semantic_json(data: Any, brief: Dict[str, Any]) -> Dict[str, Any]:
    """The keys the brief requires, present and carrying a real value."""
    sem = dict(brief.get("semantics") or {})
    required = list(sem.get("required_keys") or [])
    if isinstance(data, list):
        keys = set()
        for row in data[:20]:
            if isinstance(row, dict):
                keys |= set(row)
        present = {k: k in keys for k in required}
    elif isinstance(data, dict):
        present = {k: k in data for k in required}
    else:
        present = {k: False for k in required}
        keys = set()
    empty = []
    if isinstance(data, dict):
        for k in required:
            if k in data and data[k] in (None, "", [], {}):
                empty.append(k)
    checks = {"required_keys": required, "present": present,
              "empty_values": empty,
              "no_empty_values": not empty}
    ok = all(present.values()) and not empty
    return {"ok": ok, "checks": checks}



def validate_label(path: Path, terms: List[str]) -> Dict[str, Any]:
    raw = path.read_bytes() if path.is_file() else b""
    checks: Dict[str, Any] = {"png_magic": raw.startswith(b"\x89PNG\r\n\x1a\n")}
    if not checks["png_magic"]:
        return {"kind": "label", "valid": False, "checks": checks,
                "detail": "not a PNG"}
    import package_readiness as pr
    import text_fidelity as tf

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
    checks = {"video_stream": video is not None,
              "audio_stream": audio is not None,
              "duration_s": round(duration, 2),
              "duration_12_15": 12.0 <= duration <= 15.0,
              "width": (video or {}).get("width"),
              "height": (video or {}).get("height"),
              "vertical_1080x1920": ((video or {}).get("width") == 1080
                                     and (video or {}).get("height") == 1920)}
    valid = all(checks[k] for k in ("video_stream", "audio_stream",
                                    "duration_12_15", "vertical_1080x1920"))
    return {"kind": "ad", "valid": valid, "checks": checks, "detail": "ffprobe"}


def validate_patch(path: Path) -> Dict[str, Any]:
    text, _ = strip_markdown_fence(_read(path))
    checks = {"has_minus_file": "---" in text, "has_plus_file": "+++" in text,
              "has_hunk": bool(re.search(r"^@@", text, re.M))}
    semantic = _semantic_patch(text)
    valid = all(checks.values()) and semantic["ok"]
    return {"kind": "patch", "valid": valid,
            "checks": {**checks, "semantics": semantic["checks"]},
            "detail": "unified diff shape + hunk arithmetic"}


def validate_json(path: Path, brief: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    text, _ = strip_markdown_fence(_read(path))
    try:
        data = parse_json_text(text)
    except Exception as exc:  # noqa: BLE001
        return {"kind": "json", "valid": False, "checks": {},
                "detail": f"json error: {str(exc)[:120]}"}
    semantic = _semantic_json(data, brief or {})
    return {"kind": "json", "valid": semantic["ok"],
            "checks": {"parsed": True, "semantics": semantic["checks"]},
            "detail": ("parsed" if semantic["ok"]
                       else "parsed but the required structure is missing")}


def validate_text(path: Path, terms: List[str], min_chars: int = 120,
                  brief: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    text, _ = strip_markdown_fence(_read(path))
    low = text.lower()
    checks = {"chars": len(text), "min_chars": min_chars,
              "long_enough": len(text) >= min_chars,
              "terms": {t: t.lower() in low for t in terms}}
    semantic = _semantic_text(text, brief or {})
    valid = (checks["long_enough"] and all(checks["terms"].values())
             and semantic["ok"])
    return {"kind": "text", "valid": valid,
            "checks": {**checks, "semantics": semantic["checks"]},
            "detail": "length + required terms + structure"}



def validate_social(path: Path) -> Dict[str, Any]:
    text, _ = strip_markdown_fence(_read(path))
    try:
        data = parse_json_text(text)
    except Exception as exc:  # noqa: BLE001
        return {"kind": "social", "valid": False, "checks": {},
                "detail": f"json error: {str(exc)[:120]}"}
    expected = {"ig-post": (1440, 1800), "meta-story": (1440, 2560),
                "x-post": (1200, 628), "linkedin": (1200, 628),
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
    text = _read(path)
    registry = _read(SPEC_REGISTRY)
    ids = set(re.findall(r"id:\s*['\"]([a-z0-9-]+)['\"]", registry))
    named = [i for i in ids if i in text.lower()]
    checks = {"registry_ids": len(ids), "named": named,
              "at_least_three": len(named) >= 3}
    return {"kind": "aplus", "valid": bool(ids) and len(named) >= 3,
            "checks": checks, "detail": "specRegistry ids named"}


def validate_brief(folder: Path, brief: Dict[str, Any],
                   seed_dir: Optional[Path] = None) -> Dict[str, Any]:
    """Validate one brief's artifact.

    ``seed_dir`` is the untouched workspace for the same brief. When supplied,
    an artifact byte-identical to its seed is rejected: several briefs hand the
    model a stub to finish, and a faithful copy of the stub is not the finished
    work however many keywords it contains.
    """
    path = folder / brief["id"] / brief["artifact"]
    kind = str(brief.get("validator") or "text")
    terms = list(brief.get("terms") or [])
    if kind == "label":
        result = validate_label(path, terms or ["ORGANIC LION'S MANE",
                                                "MUSHROOM POWDER", "6 oz"])
    elif kind == "ad":
        result = validate_ad(path)
    elif kind == "patch":
        result = validate_patch(path)
    elif kind == "json":
        result = validate_json(path, brief)
    elif kind == "social":
        result = validate_social(path)
    elif kind == "aplus":
        result = validate_aplus(path)
    else:
        result = validate_text(path, terms, int(brief.get("min_chars") or 120),
                               brief)
    if seed_dir is not None and result.get("valid"):
        source = Path(seed_dir) / brief["id"] / brief["artifact"]
        if source.is_file() and path.is_file() and source.read_bytes() == path.read_bytes():
            checks = dict(result.get("checks") or {})
            checks["unchanged_from_seed"] = False
            result = {**result, "valid": False, "checks": checks,
                      "detail": "artifact is byte-identical to the seed stub"}
    return result


def run(folder: Path) -> Dict[str, Any]:
    briefs = json.loads(BRIEFS.read_text(encoding="utf-8"))["briefs"]
    rows = []
    for b in briefs:
        r = validate_brief(folder, b)
        rows.append({"id": b["id"], "artifact": b["artifact"], **r})
    passed = sum(1 for r in rows if r["valid"])
    return {"folder": str(folder), "valid": passed, "total": len(rows),
            "rate": round(passed / max(1, len(rows)), 3), "rows": rows}
