"""A+ deliverable packages: the page, its measured QA, and an OCR read-back.

The renderer already measures contrast, container overflow and file weight at
draw time (`aplus_render._qa`). That proves the *layout model* is sound; it does
not prove the pixels contain the words. A missing font, a clipped glyph run or a
wrong text colour can pass a geometric check and still ship a blank panel.

So an A+ package carries three kinds of evidence, in one manifest:

    requested  the module kinds that were asked for
    drawn      the strings the renderer records as drawn
    read back  what OCR finds in the finished PNG

The verdict is built from those, reusing `quality_gate.verdict` so A+ and the
ad/packaging lane speak the same language:

    typography       OCR must read back the drawn copy
    layout           the renderer's QA must be clean (contrast, fit, container)
    design_alignment every requested module must exist in the page
    form, material   not applicable to a composited module

Pure local work: Pillow output, OCR on the operator's machine, no network.
"""
from __future__ import annotations

import json
import re
import shutil
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

import quality_gate as qg
import text_fidelity as tf

ROOT = Path(__file__).resolve().parents[1]
DELIVERABLES = ROOT / "state" / "deliverables"

#: Share of the drawn strings OCR must find. Calibrated by measurement, not taste:
#: composited Playfair/Inter at >= 14 px reads back at 1.0 in practice, so the
#: threshold is set where a real failure (a dropped glyph run) sits well below it
#: while ordinary OCR noise on a long paragraph still passes.
COVERAGE_PASS = 0.8


def _safe(run_id: str) -> str:
    base = re.sub(r"[^A-Za-z0-9._-]+", "_", str(run_id or "")).strip("._")
    return base[:80] or f"aplus_{int(time.time())}"


def _module_evidence(entry: Dict[str, Any], folder: Optional[Path]) -> Dict[str, Any]:
    src = Path(entry["path"])
    data = src.read_bytes()
    ocr = tf.check_text_in_image(data)
    texts = [t for t in (entry.get("copy_texts") or []) if str(t).strip()]
    coverage = qg.term_coverage(texts, ocr.get("words") or [])
    qa = entry.get("qa") or {}
    evidence: Dict[str, Any] = {
        "index": entry.get("index"),
        "kind": entry.get("kind"),
        "size": list(entry.get("size") or []),
        "bytes": len(data),
        "copy_mode": entry.get("copy_mode"),
        "qa": {"ok": bool(qa.get("ok")),
               "problems": list(qa.get("problems") or []),
               "warnings": list(qa.get("warnings") or [])},
        "texts": texts,
    }
    ocr_block = {k: v for k, v in ocr.items() if v is not None and k != "words"}
    if ocr.get("words"):
        ocr_block["words"] = [w for w in ocr["words"] if w][:12]
    if ocr_block:
        evidence["ocr"] = ocr_block
    if coverage.get("applicable"):
        evidence["coverage"] = coverage
    if folder is not None:
        dest = folder / f"aplus_{int(entry.get('index') or 0):02d}_{entry.get('kind')}{src.suffix}"
        shutil.copyfile(src, dest)
        evidence["file"] = dest.name
    return evidence


def _page_axes(evidence: Sequence[Dict[str, Any]], *, requested_kinds: Sequence[str],
               kinds_rendered: Sequence[str]) -> Dict[str, Dict[str, Any]]:
    typed = [m for m in evidence if m.get("texts")]
    typography: Dict[str, Any]
    if not typed:
        typography = {"status": "not_applicable", "reason": "no_copy_drawn"}
    else:
        unread = []
        for module in typed:
            coverage = module.get("coverage") or {}
            ocr = module.get("ocr") or {}
            if ocr.get("contains_text") is None:
                unread.append(f"{module['kind']}: OCR unavailable")
            elif float(coverage.get("coverage") or 0.0) < COVERAGE_PASS:
                unread.append(f"{module['kind']}: {float(coverage.get('coverage') or 0.0):.0%} "
                              f"of copy read back")
        if unread:
            typography = {"status": "fail", "reason": "typography_unreadable",
                          "detail": "; ".join(unread)[:300]}
        else:
            worst = min(float((m.get("coverage") or {}).get("coverage") or 0.0) for m in typed)
            typography = {"status": "pass", "coverage": round(worst, 2),
                          "modules_read": len(typed)}

    problems = [f"{m['kind']}: {p}" for m in evidence for p in m["qa"]["problems"]]
    layout = ({"status": "fail", "reason": "layout_qa", "detail": "; ".join(problems)[:300]}
              if problems else {"status": "pass", "modules_measured": len(evidence)})

    missing = [k for k in requested_kinds if k not in kinds_rendered]
    alignment = ({"status": "fail", "reason": "module_missing",
                  "detail": f"requested but not rendered: {missing}"[:300]}
                 if missing else
                 {"status": "pass", "modules": len(list(kinds_rendered))})

    return {
        "form": {"status": "not_applicable", "reason": "aplus_module"},
        "design_alignment": alignment,
        "layout": layout,
        "typography": typography,
        "material": {"status": "not_applicable", "reason": "composited_module"},
    }


def package(page: Dict[str, Any], *, requested_kinds: Sequence[str],
            out_root: Optional[Path] = None,
            write: Optional[bool] = None) -> Dict[str, Any]:
    """Write one A+ deliverable folder and return its manifest.

    A failing page is not left on disk as if it had shipped: the manifest comes
    back for the caller to read, and the folder is removed. `write` overrides the
    default (write only when the verdict passes).
    """
    root = Path(out_root) if out_root else DELIVERABLES
    run_id = _safe(page.get("id") or f"aplus_{int(time.time())}")
    folder = root / run_id
    folder.mkdir(parents=True, exist_ok=True)

    evidence = [_module_evidence(entry, folder) for entry in page.get("modules") or []]
    kinds_rendered = [m["kind"] for m in evidence]
    axes = _page_axes(evidence, requested_kinds=list(requested_kinds),
                      kinds_rendered=kinds_rendered)
    verdict = qg.verdict({"axes": axes, "available": True, "model": None})
    verdict["model"] = "deterministic:pillow+rapidocr"
    verdict["available"] = True

    manifest: Dict[str, Any] = {
        "run_id": run_id,
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "kind": "aplus",
        "requested_kinds": list(requested_kinds),
        "modules": evidence,
        "quality": {
            "axes": axes,
            "verdict": {k: verdict[k] for k in
                        ("ok", "passed", "failed", "not_applicable", "score", "reasons")},
            "model": verdict["model"],
            "available": True,
            "coverage_threshold": COVERAGE_PASS,
        },
        "dieline": {"built": False,
                    "reason": "A+ module; canvas is fixed by the module, not a die"},
        "color_profile": {"working": "RGB", "target": "sRGB",
                          "converted": False,
                          "note": "A+ modules ship as sRGB PNG/JPG; no print conversion"},
    }
    manifest["files"] = sorted([m["file"] for m in evidence if m.get("file")] + ["manifest.json"])
    should_write = verdict["ok"] if write is None else bool(write)
    if should_write:
        (folder / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        return {"folder": str(folder), "manifest": manifest,
                "verdict": manifest["quality"]["verdict"]}
    shutil.rmtree(folder, ignore_errors=True)
    return {"folder": None, "manifest": manifest, "verdict": manifest["quality"]["verdict"],
            "reason": "verdict failed; nothing was written"}


__all__ = ["COVERAGE_PASS", "package"]
