"""Reference coverage for the seller briefs: 12 of 56 -> at least 40 of 56, with a held-out split.

Three sources, and the report keeps them apart because they are not the same kind of evidence:

* **brand_asset** — a real brand photograph already on this machine, admitted only through a
  hash-reviewed roster (the D-003 lesson: a folder called "pictures for seller umbrella" held quote
  cards and a wordmark, and only the pixels said so). Same bytes twice is one asset, not two.
* **public_licensed** — an openly licensed photograph of *some other seller's* product, from
  Openverse (no key, no Amazon), with licence, licence URL and the creator's landing page recorded on
  every row. These matter because the rubric has to generalise past our own three brands.
* **synthetic** — pipeline-made. Tagged, and **excluded from every pass-rate claim** by the coverage
  arithmetic below, because scoring the pipeline against its own output is circular.

Held-out split: 30 % of briefs, chosen by a hash of the brief id (so the split cannot drift when the
catalogue is reordered), are assigned references from a **disjoint** 30 % of the images. Tuning sees
only the other 70 %.

    python tools/reference_coverage.py --fetch          # download public references (network)
    python tools/reference_coverage.py --report         # assign + write the tables (offline)
    python tools/reference_coverage.py --report --json
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parents[1]
API = "https://api.openverse.org/v1/images/"
UA = "northstar-ty/1.0 (local research; seller reference library)"

LIBRARY = ROOT / "ty" / "reference_library.json"
REVIEW = ROOT / "ty" / "reference_review.json"
BRIEFS = ROOT / "ty" / "seller_briefs.json"
OUT_DIR = ROOT / "renders" / "references" / "categories"
REPORT = ROOT / "reports" / "ty" / "reference_coverage.md"

ALLOWED = {"cc0", "by", "by-sa"}
HELD_OUT_PCT = 30

#: One entry per category the owner named, with the words that must appear in the row's own text.
#: Openverse relevance is loose, so the title/description/tags have to name the object.
CATEGORIES: Dict[str, Dict[str, Any]] = {
    "supplement_pouch": {
        "queries": ["supplement pouch packaging", "vitamin pouch product"],
        "terms": ("pouch", "sachet", "bag", "supplement", "vitamin", "powder"),
    },
    "apparel": {
        "queries": ["folded t-shirt product", "apparel product photography"],
        "terms": ("shirt", "t-shirt", "tee", "apparel", "clothing", "hoodie", "jacket"),
    },
    "ceramic_mug": {
        "queries": ["ceramic mug product", "coffee mug product photography"],
        "terms": ("mug", "cup", "ceramic", "stoneware"),
    },
    "pet_product": {
        "queries": ["pet toy product", "dog product photography"],
        "terms": ("pet", "dog", "cat", "chew", "leash", "collar", "toy"),
    },
    "skincare_bottle": {
        "queries": ["skincare bottle product", "cosmetic bottle product photography"],
        "terms": ("skincare", "lotion", "serum", "cosmetic", "bottle", "cream", "beauty"),
    },
    "toy": {
        "queries": ["wooden toy product", "children toy product photography"],
        "terms": ("toy", "block", "puzzle", "play", "children", "kids"),
    },
    "home": {
        "queries": ["home decor product", "candle product photography"],
        "terms": ("home", "decor", "candle", "vase", "lamp", "vessel"),
    },
    "electronics_accessories": {
        "queries": ["usb cable product", "phone accessory product photography"],
        "terms": ("cable", "charger", "usb", "accessory", "headphone", "adapter", "electronic"),
    },
    "food_jar": {
        "queries": ["glass food jar product", "honey jar product photography",
                    "jam jar label", "spice jar product"],
        "terms": ("jar", "honey", "jam", "preserve", "food", "spice"),
    },
    "tool": {
        "queries": ["hand tool product", "screwdriver product photography"],
        "terms": ("tool", "screwdriver", "wrench", "pliers", "hammer", "drill"),
    },
    "small_appliance": {
        "queries": ["kitchen appliance product", "small appliance product photography"],
        "terms": ("appliance", "blender", "kettle", "toaster", "mixer", "machine"),
    },
}

#: Reviewed brand assets: the roster after D-003. Every path here was opened and confirmed to show
#: the product. A path outside this list is not admitted by the brand-asset source.
BRAND_ROSTER = {
    "supplement_pouch": [
        "renders/references/mogra/mogra_pair_main.png",
        "renders/references/mogra/mogra_pair_lifestyle.png",
        "renders/references/mogra/mogra_forest_dusk.png",
        "renders/references/word-coffee/word_coffee_moms_front.jpg",
        "renders/references/word-coffee/word_coffee_women_front.jpg",
        "renders/references/word-coffee/wc_women_pic_box.jpg",
        "renders/references/word-coffee/wc_women_easter_table.png",
        "renders/references/word-coffee/wc_women_in_purse.png",
    ],
}


def _sha16(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()[:16]


def _brief_split(brief_id: str) -> str:
    """Deterministic 30 % held-out split by brief id."""
    bucket = int(hashlib.sha256(brief_id.encode()).hexdigest()[:8], 16) % 100
    return "held_out" if bucket < HELD_OUT_PCT else "tuning"


def _image_split(sha: str) -> str:
    bucket = int(hashlib.sha256(sha.encode()).hexdigest()[:8], 16) % 100
    return "held_out" if bucket < HELD_OUT_PCT else "tuning"


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


def _get_json(url: str) -> Dict[str, Any]:
    request = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(request, timeout=40) as response:
        return json.load(response)


def _get_bytes(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(request, timeout=60) as response:
        return response.read()


def fetch(category: str, *, per_query: int = 3, min_side: int = 800,
          get_json=_get_json, get_bytes=_get_bytes) -> Dict[str, Any]:
    spec = CATEGORIES[category]
    rows: List[Dict[str, Any]] = []
    refused: List[Dict[str, Any]] = []
    target = OUT_DIR / category
    target.mkdir(parents=True, exist_ok=True)
    seen: set = set()
    for query in spec["queries"]:
        params = {
            "q": query,
            "license": ",".join(sorted(ALLOWED)),
            "page_size": str(max(per_query * 4, 12)),
            "mature": "false",
        }
        try:
            payload = get_json(API + "?" + urllib.parse.urlencode(params))
        except Exception as exc:  # noqa: BLE001 - a network failure is a recorded fact
            refused.append({"query": query, "reason": f"{type(exc).__name__}: {exc}"[:160]})
            continue
        kept = 0
        for item in payload.get("results") or []:
            if kept >= per_query:
                break
            identifier = str(item.get("id") or "")
            if not identifier or identifier in seen:
                continue
            licence = str(item.get("license") or "").lower()
            if licence not in ALLOWED:
                refused.append({"query": query, "id": identifier, "reason": f"licence {licence}"})
                continue
            width, height = int(item.get("width") or 0), int(item.get("height") or 0)
            if width and height and min(width, height) < min_side:
                refused.append({"query": query, "id": identifier,
                                "reason": f"small {width}x{height}"})
                continue
            if not str(item.get("foreign_landing_url") or "").strip():
                refused.append({"query": query, "id": identifier, "reason": "no landing url"})
                continue
            text = _text_of(item)
            if not any(term in text for term in spec["terms"]):
                refused.append({"query": query, "id": identifier,
                                "reason": "off_topic: no category term in title/tags/description"})
                continue
            try:
                blob = get_bytes(str(item.get("url") or ""))
            except Exception as exc:  # noqa: BLE001
                refused.append({"query": query, "id": identifier,
                                "reason": f"download {type(exc).__name__}"})
                continue
            if len(blob) < 8_000:
                refused.append({"query": query, "id": identifier, "reason": "file too small"})
                continue
            suffix = Path(urllib.parse.urlparse(str(item.get("url") or "")).path).suffix or ".jpg"
            if suffix.lower() not in (".jpg", ".jpeg", ".png", ".webp"):
                suffix = ".jpg"
            path = target / f"{identifier}{suffix}"
            path.write_bytes(blob)
            try:
                from PIL import Image

                with Image.open(path) as check:
                    size = list(check.size)
                    check.verify()
            except Exception:  # noqa: BLE001
                path.unlink(missing_ok=True)
                refused.append({"query": query, "id": identifier, "reason": "not an image"})
                continue
            rows.append({
                "category": category,
                "source_type": "public_licensed",
                "id": identifier,
                "query": query,
                "title": str(item.get("title") or "")[:120],
                "creator": str(item.get("creator") or "")[:80],
                "licence": licence,
                "licence_version": str(item.get("license_version") or ""),
                "licence_url": str(item.get("license_url") or ""),
                "source_url": str(item.get("foreign_landing_url") or ""),
                "image_url": str(item.get("url") or ""),
                "file": str(path.relative_to(ROOT)).replace("\\", "/"),
                "sha256": _sha16(blob),
                "pixels": size,
                "usage": ("rubric reference only - never a product asset, never composited into "
                          "a seller picture"),
            })
            seen.add(identifier)
            kept += 1
    return {"category": category, "rows": rows, "refused": refused}


def brand_assets() -> List[Dict[str, Any]]:
    rows = []
    for category, paths in BRAND_ROSTER.items():
        for rel in paths:
            path = ROOT / rel
            if not path.is_file():
                continue
            blob = path.read_bytes()
            rows.append({
                "category": category,
                "source_type": "brand_asset",
                "id": f"brand-{_sha16(blob)}",
                "file": rel,
                "sha256": _sha16(blob),
                "licence": "owner-owned",
                "licence_url": None,
                "source_url": None,
                "usage": "owner's own product photograph; usable as a seller reference",
            })
    return rows


def synthetic_assets() -> List[Dict[str, Any]]:
    """Pipeline-made images, tagged so they can never be counted as a pass-rate population."""
    rows = []
    for path in sorted((ROOT / "Northstar_backend" / "data" / "studio_generated").glob("*")):
        if path.suffix.lower() not in (".png", ".jpg", ".jpeg"):
            continue
        blob = path.read_bytes()
        rows.append({
            "category": None,
            "source_type": "synthetic",
            "id": f"synthetic-{_sha16(blob)}",
            "file": str(path.relative_to(ROOT)).replace("\\", "/"),
            "sha256": _sha16(blob),
            "usage": "pipeline-made; excluded from every pass-rate claim",
        })
    return rows


def load_library() -> Dict[str, Any]:
    if LIBRARY.is_file():
        return json.loads(LIBRARY.read_text(encoding="utf-8"))
    return {"rows": [], "refused": []}


def assign(briefs: List[Dict[str, Any]], images: List[Dict[str, Any]]) -> Dict[str, Any]:
    review = {}
    if REVIEW.is_file():
        review = (json.loads(REVIEW.read_text(encoding="utf-8")).get("by_sha") or {})

    usable = []
    rejected = 0
    for row in images:
        if row["source_type"] not in ("brand_asset", "public_licensed"):
            continue
        verdict = review.get(row.get("sha256") or "")
        if verdict:
            if verdict["verdict"] == "reject":
                rejected += 1
                continue
            if verdict["verdict"] == "reclassify" and verdict.get("reclassify_to"):
                row = dict(row)
                row["category"] = verdict["reclassify_to"]
        usable.append(row)

    by_category: Dict[str, List[Dict[str, Any]]] = {}
    for row in usable:
        by_category.setdefault(row["category"], []).append(row)
    for rows in by_category.values():
        rows.sort(key=lambda r: r["sha256"])

    assigned = []
    uncovered = []
    for brief in briefs:
        category = brief.get("category")
        pool = by_category.get(category) or []
        split = _brief_split(brief["id"])
        side = [r for r in pool if _image_split(r["sha256"]) == split]
        if not side:
            side = pool
        if not side:
            uncovered.append(brief["id"])
            continue
        pick = side[int(hashlib.sha256(brief["id"].encode()).hexdigest(), 16) % len(side)]
        assigned.append({"brief": brief["id"], "category": category, "split": split,
                         "reference": pick["file"], "source_type": pick["source_type"],
                         "licence": pick.get("licence")})
    depth = {category: len([r for r in rows if r["source_type"] != "synthetic"])
             for category, rows in by_category.items()}
    return {"assigned": assigned, "uncovered": uncovered,
            "rejected_by_review": rejected, "depth": depth,
            "usable_images": len(usable)}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fetch", action="store_true", help="download public references")
    parser.add_argument("--categories", default="", help="comma list; default all")
    parser.add_argument("--per-query", type=int, default=3)
    parser.add_argument("--report", action="store_true")
    parser.add_argument("--min-side", type=int, default=800)
    parser.add_argument("--json", action="store_true")
    ns = parser.parse_args(argv)

    library = load_library()

    if ns.fetch:
        names = [n.strip() for n in ns.categories.split(",") if n.strip()] or list(CATEGORIES)
        by_key = {(r.get("category"), r.get("id")): r for r in library["rows"]}
        for name in names:
            result = fetch(name, per_query=ns.per_query, min_side=ns.min_side)
            for row in result["rows"]:
                by_key[(row["category"], row["id"])] = row
            library.setdefault("refused", []).extend(result["refused"])
            print(f"{name}: +{len(result['rows'])} kept, {len(result['refused'])} refused")
        rows = [r for r in by_key.values()]
        # brand assets are re-measured each time so a changed file changes its hash
        rows = [r for r in rows if r["source_type"] != "brand_asset"] + brand_assets()
        library["rows"] = rows
        library["at"] = "2026-11-11"
        library["policy"] = {
            "allowed_licences": sorted(ALLOWED),
            "usage": "rubric references only; never product assets; Amazon never contacted",
            "synthetic": "tagged and excluded from every pass-rate claim",
        }
        LIBRARY.write_text(json.dumps(library, indent=2, ensure_ascii=False) + "\n",
                           encoding="utf-8")
        print(f"library: {len(rows)} rows -> {LIBRARY.relative_to(ROOT)}")

    if ns.report or ns.json or not ns.fetch:
        briefs = json.loads(BRIEFS.read_text(encoding="utf-8"))["briefs"]
        rows = library.get("rows") or []
        rows = [r for r in rows if r["source_type"] != "synthetic"] + synthetic_assets()
        result = assign(briefs, rows)
        counts: Dict[str, int] = {}
        for row in result["assigned"]:
            counts[row["source_type"]] = counts.get(row["source_type"], 0) + 1
        coverage = len(result["assigned"])
        payload = {
            "briefs": len(briefs),
            "covered": coverage,
            "coverage_pct": round(100.0 * coverage / len(briefs), 1) if briefs else 0.0,
            "by_source": counts,
            "held_out_briefs": sum(1 for a in result["assigned"] if a["split"] == "held_out"),
            "tuning_briefs": sum(1 for a in result["assigned"] if a["split"] == "tuning"),
            "uncovered": result["uncovered"],
            "images": {"brand_asset": sum(1 for r in rows if r["source_type"] == "brand_asset"),
                       "public_licensed": sum(1 for r in rows
                                              if r["source_type"] == "public_licensed"),
                       "synthetic_excluded": sum(1 for r in rows
                                                 if r["source_type"] == "synthetic")},
            "categories_covered": sorted({a["category"] for a in result["assigned"]}),
            "rejected_by_review": result.get("rejected_by_review", 0),
            "reviewed_depth": result.get("depth", {}),
            "usable_images": result.get("usable_images", 0),
            "assigned": result["assigned"],
        }
        (ROOT / "ty" / "reference_assignment.json").write_text(
            json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        if ns.json:
            print(json.dumps(payload, indent=2))
            return 0
        lines = ["# Reference coverage", "",
                 f"**{coverage} of {len(briefs)} briefs** have a reviewed reference "
                 f"({payload['coverage_pct']} %). Held-out split: "
                 f"{payload['held_out_briefs']} briefs / {payload['tuning_briefs']} tuning, by a hash "
                 "of the brief id, with references drawn from a disjoint image split.", "",
                 "| source type | briefs covered |", "|---|---|"]
        for key in ("brand_asset", "public_licensed"):
            lines.append(f"| `{key}` | {counts.get(key, 0)} |")
        lines += ["| `synthetic` | **0 — excluded from pass-rate claims by construction** |", "",
                  f"Images available: {payload['images']['brand_asset']} brand assets, "
                  f"{payload['images']['public_licensed']} public licensed, "
                  f"{payload['images']['synthetic_excluded']} synthetic (excluded).",
                  f"**Visual review:** {payload['usable_images']} usable of "
                  f"{payload['usable_images'] + payload['rejected_by_review']} reviewed — "
                  f"{payload['rejected_by_review']} rejected as not a product "
                  "(`ty/reference_review.json`, sheet "
                  "`reports/ty/reference_public_contact.png`).", "",
                  "## Depth, not just coverage", "",
                  "A category with one reviewed image covers its briefs on paper and generalises "
                  "poorly. This is the number that says which:", "",
                  "| category | reviewed images | covered briefs |", "|---|---|---|"]
        per_cat: Dict[str, int] = {}
        for row in result["assigned"]:
            per_cat[row["category"]] = per_cat.get(row["category"], 0) + 1
        for cat in sorted(per_cat):
            lines.append(f"| `{cat}` | {payload['reviewed_depth'].get(cat, 0)} | {per_cat[cat]} |")
        if result["uncovered"]:
            lines += ["", "## Still uncovered", "",
                      ", ".join(f"`{b}`" for b in result["uncovered"])]
        lines += ["", "Neck Nirvana stays **unscorable**: there is no product photograph of it on this "
                  "machine, and a reference is not invented.", ""]
        REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
        print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
