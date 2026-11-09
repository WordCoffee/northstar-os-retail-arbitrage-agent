"""Audit composite outputs against the source cutout — independently of the generator.

The generator says it pasted the real product. This checks that it did: for every composite in
`renders/seller_composite/`, cut the product out of the brief's reference, find it in the output
and compare the region. The generator's own claim is not evidence.

    python tools/composite_audit.py --run
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parents[1]
PROOF = ROOT / "state" / "seller" / "composite_proof.json"
OUT = ROOT / "state" / "seller" / "composite_region.json"
BRIEFS = ROOT / "tools" / "seller_tester" / "mogra_briefs.json"
MIN_SIMILARITY = 0.82


def _load(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def brief_index() -> Dict[str, Dict[str, Any]]:
    data = _load(BRIEFS) or {}
    return {str(brief.get("id")): brief for brief in data.get("briefs") or []}


def cutout_for(brief: Dict[str, Any], artefact: Optional[Path] = None) -> Optional[Any]:
    """The cutout the *generator* used, if it saved one.

    Re-deriving a cutout here is a trap: on a lifestyle reference the background is not
    separable by corner distance, so the "cutout" becomes the whole scene and the comparison
    means nothing. The pipeline already runs a real segmenter (BiRefNet), so the audit consumes
    its cutout and refuses when it was not saved — which is what happened first, and is
    recorded rather than papered over.
    """
    candidates = []
    if artefact is not None:
        candidates.append(artefact.with_suffix(".cutout.png"))
    brief_id = str(brief.get("id") or "")
    if brief_id:
        candidates.append(ROOT / "renders" / "seller_composite" / f"{brief_id}.cutout.png")
    for path in candidates:
        if path.is_file():
            from PIL import Image

            with Image.open(path) as opened:
                image = opened.convert("RGBA")
            import numpy as np

            return np.array(image)
    return None


def audit() -> Dict[str, Any]:
    proof = _load(PROOF) or {}
    results = proof.get("results") or []
    briefs = brief_index()
    rows: List[Dict[str, Any]] = []
    for result in results:
        brief_id = str(result.get("brief_id"))
        entry: Dict[str, Any] = {"brief_id": brief_id,
                                 "artefact": result.get("artefact_path"),
                                 "route": result.get("route")}
        brief = briefs.get(brief_id) or {}
        artefact = ROOT / str(result.get("artefact_path") or "")
        cutout = cutout_for(brief, artefact if artefact.is_file() else None)
        if cutout is None:
            entry.update({"ok": False, "cannot_verify": True,
                          "reason": ("the generator did not save the cutout it used, and a "
                                     "re-derived cutout would compare the whole scene; "
                                     "expected <artefact>.cutout.png")})
            rows.append(entry)
            continue
        if not artefact.is_file():
            entry.update({"ok": False, "cannot_verify": True,
                          "reason": "composite artefact is not on disk"})
            rows.append(entry)
            continue
        try:
            from PIL import Image

            from seller_tester.composite_check import check_composite

            with Image.open(artefact) as opened:
                produced = __import__("numpy").array(opened.convert("RGB"))
            verdict = check_composite(produced, cutout, min_similarity=MIN_SIMILARITY)
        except Exception as exc:  # noqa: BLE001
            entry.update({"ok": False, "cannot_verify": True,
                          "reason": f"{type(exc).__name__}: {exc}"})
            rows.append(entry)
            continue
        entry.update({
            "ok": bool(verdict.get("ok")),
            "cannot_verify": bool(verdict.get("cannot_verify")),
            "similarity": verdict.get("similarity"),
            "found_by": verdict.get("found_by"),
            "min_similarity": MIN_SIMILARITY,
            "detail": verdict.get("detail") or verdict.get("reason"),
        })
        rows.append(entry)

    passed = sum(1 for row in rows if row.get("ok"))
    payload = {"at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
               "min_similarity": MIN_SIMILARITY, "rows": rows,
               "passed": passed, "total": len(rows)}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return payload


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Composite product-region audit")
    parser.add_argument("--run", action="store_true")
    ns = parser.parse_args(argv)
    payload = audit()
    print(json.dumps({"passed": payload["passed"], "total": payload["total"],
                      "rows": [{k: row.get(k) for k in ("brief_id", "ok", "similarity",
                                                        "found_by", "detail")}
                               for row in payload["rows"]]}, indent=2))
    return 0 if payload["passed"] == payload["total"] and payload["total"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
