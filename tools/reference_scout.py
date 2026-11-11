"""Reference-library scout: public, openly licensed product designs.

The seller rubric cannot be built from the owner's examples (work order, PATCH
2026-11-07 item 1) and must never touch an Amazon endpoint. Openverse indexes
hundreds of millions of openly licensed images and needs no key; PATCH 2 adds it
as a reference source **for the rubric only, never as a product asset**, and says
each work's licence must be verified before use.

So every row this writes carries: query, title, creator, licence + version,
licence URL, the creator's page (``foreign_landing_url``) and the file we saved.
Only licences that permit commercial reuse *and* modification are kept — ``cc0``,
``by``, ``by-sa`` — because a rubric that cannot be shown to a future user is not
a rubric. ``by-nc`` and ``by-nd`` are refused and counted, not silently dropped.

The download is a **reference**, not an asset: nothing here may be composited into
a product picture. `usage` says so on every row.

    python tools/reference_scout.py --out renders/references/public \
        --manifest reports/ty/reference_library.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence

ROOT = Path(__file__).resolve().parents[1]
API = "https://api.openverse.org/v1/images/"
USER_AGENT = "northstar-ty/1.0 (local research; reference library for a seller rubric)"

#: Licences that allow commercial reuse and modification. NC forbids the first,
#: ND the second; both are refused by name.
ALLOWED_LICENCES = {"cc0", "by", "by-sa"}

#: One query per packaging family the seller rubric needs, so the library is not
#: five photographs of the same bag.
QUERIES = (
    "stand up pouch packaging",
    "coffee bag packaging",
    "gift box packaging",
    "supplement bottle label",
    "cosmetic jar packaging",
    "product packaging mockup",
    "tea tin packaging",
    "soap box packaging",
    "spice jar label",
    "skincare bottle packaging",
)


def _now() -> str:
    import datetime

    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")


#: The question the local vision model is asked about every kept row. Keyword
#: relevance is not enough on its own: a 1960s airline flyer passed it because its
#: tags said "bag". The model is asked one thing — is this a package — and its
#: verdict is recorded either way.
VISION_RUBRIC = {
    "constraint": (
        "The image shows a physical product package — a pouch, bag, box, bottle, "
        "jar, tin, tube, sachet or canister — shown as a product. Answer yes only "
        "if a package is the subject of the picture."),
}


def _default_json(url: str) -> Dict[str, Any]:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def _default_bytes(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=45) as response:
        return response.read()


def search_url(query: str, *, page_size: int = 8, size: str = "") -> str:
    params = {
        "q": query,
        "license": ",".join(sorted(ALLOWED_LICENCES)),
        "page_size": str(max(1, min(20, page_size))),
        "mature": "false",
    }
    if size:
        params["size"] = size
    return API + "?" + urllib.parse.urlencode(params)


#: A reference must look like packaging, not merely match the words. Openverse's
#: relevance is loose ("stand up pouch packaging" returned a 1960s airline
#: flyer), so a row is kept only when its own title, tags or description names a
#: packaging object.
PACKAGING_TERMS = (
    "pouch", "bag", "box", "bottle", "jar", "tin", "tube", "sachet", "carton",
    "label", "packaging", "package", "mockup", "canister", "container", "sleeve",
    "wrapper", "flask", "vial",
)


def _text_of(item: Dict[str, Any]) -> str:
    tags = item.get("tags") or []
    names = []
    for tag in tags:
        if isinstance(tag, dict):
            names.append(str(tag.get("name") or ""))
        else:
            names.append(str(tag))
    return " ".join([str(item.get("title") or ""), str(item.get("description") or ""),
                     " ".join(names)]).lower()


def keep(item: Dict[str, Any], *, min_side: int = 800,
         require_packaging: bool = True) -> Optional[str]:
    """Why this row is usable, or the reason it is refused."""
    licence = str(item.get("license") or "").lower()
    if licence not in ALLOWED_LICENCES:
        return f"licence_refused: {licence or 'none'}"
    if not str(item.get("url") or "").strip():
        return "no image url"
    width = int(item.get("width") or 0)
    height = int(item.get("height") or 0)
    if width and height and min(width, height) < min_side:
        return f"too small: {width}x{height}"
    if not str(item.get("foreign_landing_url") or "").strip():
        return "no landing url: the licence cannot be verified at source"
    if require_packaging:
        text = _text_of(item)
        if not any(term in text for term in PACKAGING_TERMS):
            return "off_topic: no packaging object in the title, tags or description"
    return None


def row_for(item: Dict[str, Any], *, query: str, path: Optional[Path] = None) -> Dict[str, Any]:
    return {
        "id": str(item.get("id") or ""),
        "query": query,
        "title": str(item.get("title") or "")[:120],
        "creator": str(item.get("creator") or "")[:80],
        "licence": str(item.get("license") or ""),
        "licence_version": str(item.get("license_version") or ""),
        "licence_url": str(item.get("license_url") or ""),
        "source_url": str(item.get("foreign_landing_url") or ""),
        "image_url": str(item.get("url") or ""),
        "width": int(item.get("width") or 0),
        "height": int(item.get("height") or 0),
        "file": str(path) if path else None,
        "sha256": None,
        "usage": ("rubric reference only - never a product asset, never composited "
                  "into a seller picture"),
        "checked_at": _now(),
    }


def run(*, queries: Sequence[str] = QUERIES, out_dir: str | Path,
        manifest: str | Path, per_query: int = 2, min_side: int = 800,
        fetch_json: Optional[Callable[[str], Dict[str, Any]]] = None,
        fetch_bytes: Optional[Callable[[str], bytes]] = None,
        judge: Optional[Callable[[bytes, Dict[str, Any]], Dict[str, Any]]] = None,
        ) -> Dict[str, Any]:
    """Search, filter, download and record. Deterministic given the API's answers."""
    get_json = fetch_json or _default_json
    get_bytes = fetch_bytes or _default_bytes
    target = Path(out_dir)
    target.mkdir(parents=True, exist_ok=True)

    rows: List[Dict[str, Any]] = []
    refused: List[Dict[str, Any]] = []
    seen: set = set()
    for query in queries:
        try:
            payload = get_json(search_url(query, page_size=max(per_query * 3, 6)))
        except Exception as exc:  # noqa: BLE001 - a network failure is a recorded fact
            refused.append({"query": query, "reason": f"{type(exc).__name__}: {exc}"[:200]})
            continue
        kept = 0
        for item in payload.get("results") or []:
            if kept >= per_query:
                break
            identifier = str(item.get("id") or "")
            if identifier and identifier in seen:
                continue
            why = keep(item, min_side=min_side)
            if why:
                refused.append({"query": query, "id": identifier, "reason": why})
                continue
            try:
                blob = get_bytes(str(item["url"]))
            except Exception as exc:  # noqa: BLE001
                refused.append({"query": query, "id": identifier,
                                "reason": f"download failed: {type(exc).__name__}"})
                continue
            if len(blob) < 8_000:
                refused.append({"query": query, "id": identifier,
                                "reason": f"file too small: {len(blob)} bytes"})
                continue
            suffix = Path(urllib.parse.urlparse(str(item["url"])).path).suffix or ".jpg"
            if suffix.lower() not in (".jpg", ".jpeg", ".png", ".webp"):
                suffix = ".jpg"
            path = target / f"{identifier}{suffix}"
            path.write_bytes(blob)
            row = row_for(item, query=query, path=path)
            row["sha256"] = hashlib.sha256(blob).hexdigest()[:16]
            # A file that does not open is not a reference. Measure what landed
            # instead of trusting the API's dimensions.
            try:
                from PIL import Image

                with Image.open(path) as check:
                    row["file_size"] = list(check.size)
                    check.verify()
            except Exception as exc:  # noqa: BLE001
                path.unlink(missing_ok=True)
                refused.append({"query": query, "id": identifier,
                                "reason": f"not an image: {type(exc).__name__}"})
                continue
            rows.append(row)
            seen.add(identifier)
            kept += 1

    if judge is not None:
        for row in rows:
            path = Path(row["file"]) if row.get("file") else None
            if path is None or not path.is_file():
                row["vision"] = {"pass": None, "available": False,
                                 "reasons": ["no file"]}
                continue
            try:
                row["vision"] = judge(path.read_bytes(), VISION_RUBRIC)
            except Exception as exc:  # noqa: BLE001 - unavailable is a skip
                row["vision"] = {"pass": None, "available": False,
                                 "reasons": [f"{type(exc).__name__}: {exc}"[:200]]}

    confirmed = sum(1 for row in rows if (row.get("vision") or {}).get("pass") is True)

    result = {
        "at": _now(),
        "source": "Openverse (openverse.org), API v1, no key",
        "policy": {
            "allowed_licences": sorted(ALLOWED_LICENCES),
            "refused_licences": ["by-nc", "by-nc-sa", "by-nd", "by-nc-nd", "unknown"],
            "usage": "rubric references only; never product assets",
            "amazon": "never contacted",
        },
        "rows": rows,
        "refused": refused,
        "counts": {
            "kept": len(rows),
            "refused": len(refused),
            "distinct_queries_with_a_row": len({row["query"] for row in rows}),
            "vision_confirmed_packages": confirmed if judge is not None else None,
        },
    }
    path = Path(manifest)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return result


def main(argv: Optional[list] = None) -> int:
    parser = argparse.ArgumentParser(description="Openverse reference-library scout")
    parser.add_argument("--out", default=str(ROOT / "renders" / "references" / "public"))
    parser.add_argument("--manifest", default=str(ROOT / "reports" / "ty" / "reference_library.json"))
    parser.add_argument("--per-query", type=int, default=2)
    parser.add_argument("--min-side", type=int, default=800)
    parser.add_argument("--markdown", default=str(ROOT / "reports" / "ty" / "reference_library.md"))
    parser.add_argument("--vision", action="store_true",
                        help="ask the local vision model whether each kept row is a package")
    ns = parser.parse_args(argv)
    judge = None
    if ns.vision:
        sys.path.insert(0, str(ROOT))
        from tools.seller_tester.judge import local_judge  # noqa: PLC0415

        judge = local_judge
    result = run(out_dir=ns.out, manifest=ns.manifest, per_query=ns.per_query,
                 min_side=ns.min_side, judge=judge)
    lines = ["# Reference library (Openverse, openly licensed, rubric only)", "",
             f"Built {result['at']}. Licences allowed: {', '.join(sorted(ALLOWED_LICENCES))}. "
             "**These are rubric references, never product assets.**", ""]
    counts = result["counts"]
    lines.append(f"Kept **{counts['kept']}** of {counts['kept'] + counts['refused']} candidates "
                 f"across {counts['distinct_queries_with_a_row']} packaging families; "
                 f"vision-confirmed packages: **{counts.get('vision_confirmed_packages')}**."
                 if counts.get("vision_confirmed_packages") is not None else
                 f"Kept **{counts['kept']}** of {counts['kept'] + counts['refused']} candidates "
                 f"across {counts['distinct_queries_with_a_row']} packaging families.")
    lines += ["", "| query | title | creator | licence | source | package? |",
              "|---|---|---|---|---|---|"]
    for row in result["rows"]:
        verdict = (row.get("vision") or {}).get("pass")
        mark = "yes" if verdict is True else ("no" if verdict is False else "unjudged")
        lines.append(f"| {row['query']} | {row['title'][:44]} | {row['creator'][:22]} | "
                     f"{row['licence']} {row['licence_version']} | {row['source_url']} | {mark} |")
    Path(ns.markdown).write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"counts": result["counts"], "manifest": ns.manifest,
                      "markdown": ns.markdown}, indent=2))
    return 0 if result["rows"] else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
