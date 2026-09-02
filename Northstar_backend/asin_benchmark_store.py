"""Offline-only ASIN benchmark repository (Phase 2 of the benchmark
validation task; plan: docs/asin-benchmark-validation-plan.md).

Builds a versioned, normalized reference artifact from the two user-provided
benchmark CSVs. PURE OFFLINE — no network, no provider clients, no .env, no
production cache/catalog writes. Everything lives in its own directory
(data/benchmarks/, env-overridable), kept separate from the scanner catalog,
scanner cache, live provider snapshots, Costco source data and invoice
imports. The scanner CSV contract is never touched.

Layout (all paths env-overridable for tests):
  - data/benchmarks/raw/<user CSV files>      byte-for-byte raw copies
  - data/benchmarks/manifest.json             provenance manifest (sha256,
                                               byte size, imported_at UTC)
  - data/benchmarks/asin_benchmark_reference.json  normalized artifact

Honesty invariants:
  - Unknown benchmark values are null/None, never 0.
  - Raw rows are preserved verbatim; nothing is discarded.
  - Every ASIN keeps ALL its observations; a canonical view is produced only
    when values agree or a deterministic documented rule applies (see
    CANONICAL_RULES) and every disagreement is flagged for review.
  - Capture timestamp is null unless a timestamp column exists (it does not
    in the current files) -> capture_time_status "unknown" everywhere.
"""

import csv
import hashlib
import json
import os
import re
import shutil
from typing import Any, Dict, List, Optional

BENCHMARK_SCHEMA_VERSION = 1

SOURCE_FILES = (
    "BSR-proxyrank-Product-ASIN-Reviews-Price-PrimeFBA.csv",
    "Rank-Product-ASIN-Reviews-Price-BSR.csv",
)

FILE_A = SOURCE_FILES[0]  # proxy rank, Product, ASIN, Reviews, Price, Prime/FBA
FILE_B = SOURCE_FILES[1]  # Rank, Product, ASIN, Reviews, Price, BSR

DEFAULT_BENCHMARK_DIR = "data/benchmarks"
DEFAULT_RAW_DIR = os.path.join(DEFAULT_BENCHMARK_DIR, "raw")
DEFAULT_REFERENCE_PATH = os.path.join(DEFAULT_BENCHMARK_DIR, "asin_benchmark_reference.json")
DEFAULT_MANIFEST_PATH = os.path.join(DEFAULT_BENCHMARK_DIR, "manifest.json")

MANIFEST_NOTE = (
    "Reference benchmark for validating future ASIN market snapshots. "
    "Not a live-feed source and not proof of current market conditions."
)

ASIN_PATTERN = re.compile(r"^[A-Za-z0-9]{10}$")

_PRICE_RE = re.compile(r"^\s*\$?\s*([\d,]+(?:\.\d{1,2})?)\s*$")
_INT_RE = re.compile(r"^\s*([\d,]+)\s*$")
_BSR_NUM_RE = re.compile(r"#([\d,]+)")
_BSR_CAT_RE = re.compile(r"in\s+([^#;]+)")
_TRAILING_AMAZON_RE = re.compile(r"\s*amazon\s*$", re.IGNORECASE)

_PRIME_FBA_MAP = {
    "yes": ("yes", None),
    "no": ("no", None),
    "no (amazon-shipped, non-prime badge)": ("no", "Amazon-shipped, non-Prime badge"),
}


def _env_path(name: str, default: str) -> str:
    return os.environ.get(name) or default


def raw_dir() -> str:
    return _env_path("BENCHMARK_RAW_DIR", DEFAULT_RAW_DIR)


def reference_path() -> str:
    return _env_path("BENCHMARK_REFERENCE_PATH", DEFAULT_REFERENCE_PATH)


def manifest_path() -> str:
    return _env_path("BENCHMARK_MANIFEST_PATH", DEFAULT_MANIFEST_PATH)


def import_dir() -> Optional[str]:
    value = os.environ.get("BENCHMARK_IMPORT_DIR")
    return value if value else None


def sha256_file(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


# ---------------------------------------------------------------------------
# Parsers (null-first; a malformed/unparseable value is null, never 0)
# ---------------------------------------------------------------------------

def parse_price(raw: Any) -> Optional[float]:
    if raw is None:
        return None
    text = str(raw).strip()
    if not text or text.lower() in ("n/a", "not listed"):
        return None
    match = _PRICE_RE.match(text)
    if not match:
        return None
    try:
        return float(match.group(1).replace(",", ""))
    except ValueError:
        return None


def parse_int(raw: Any) -> Optional[int]:
    if raw is None:
        return None
    text = str(raw).strip()
    if not text or text.lower() in ("n/a", "not listed"):
        return None
    if not _INT_RE.match(text):
        return None
    try:
        return int(text.replace(",", ""))
    except ValueError:
        return None


def parse_prime_fba(raw: Any) -> Dict[str, Any]:
    """Raw text preserved plus a normalized state (yes | no | unknown)."""
    if raw is None:
        return {"raw": None, "state": None, "note": None}
    text = str(raw).strip()
    state, note = _PRIME_FBA_MAP.get(text.lower(), ("unknown", None))
    return {"raw": text, "state": state, "note": note}


def parse_bsr(raw: Any) -> Dict[str, Any]:
    """Extract primary + secondary '#N in Category' fragments; raw kept.

    The BSR source can carry multiple ranked categories (e.g.
    "#2,300 in Beauty & Personal Care; #15 in Hair Regrowth Treatments").
    The first is primary; any second is secondary. Raw is preserved.

    Category text carries a scraping artifact (trailing "amazon") which is
    stripped. A missing/empty/"not listed" value yields all-null, never 0.
    """
    empty = {
        "raw": None,
        "rank_number": None,
        "category": None,
        "secondary_rank_number": None,
        "secondary_category": None,
    }
    if raw is None:
        return empty
    text = str(raw).strip()
    if not text or "not listed" in text.lower():
        return {
            "raw": text,
            "rank_number": None,
            "category": None,
            "secondary_rank_number": None,
            "secondary_category": None,
        }
    pairs: List[tuple] = []
    for num_match in _BSR_NUM_RE.finditer(text):
        try:
            rank = int(num_match.group(1).replace(",", ""))
        except ValueError:
            rank = None
        cat = None
        cat_m = _BSR_CAT_RE.search(text, num_match.end())
        if cat_m:
            cat = _TRAILING_AMAZON_RE.sub("", cat_m.group(1)).strip()
            if not cat:
                cat = None
        pairs.append((rank, cat))
    primary = pairs[0] if pairs else (None, None)
    secondary = pairs[1] if len(pairs) > 1 else (None, None)
    return {
        "raw": text,
        "rank_number": primary[0],
        "category": primary[1],
        "secondary_rank_number": secondary[0],
        "secondary_category": secondary[1],
    }


def normalize_title(title: Any) -> Optional[str]:
    if title is None:
        return None
    text = " ".join(str(title).split())
    text = re.sub(r"[^\w\s]", "", text, flags=re.UNICODE)
    return text.lower()


_PACK_PATTERNS = (
    (re.compile(r"(\d+)\s*(?:pk|pack|packs)\b", re.IGNORECASE), "pack"),
    (re.compile(r"(\d+)\s*ct\b", re.IGNORECASE), "count"),
    (re.compile(r"pack of\s+(\d+)", re.IGNORECASE), "pack"),
    (re.compile(r"(\d+)\s*(?:bottle|bottles)\b", re.IGNORECASE), "bottles"),
    (re.compile(r"(\d+)\s*(?:spray|sprays)\b", re.IGNORECASE), "sprays"),
    (re.compile(r"(\d+)\s*mo\b", re.IGNORECASE), "months"),
    (re.compile(r"(\d+)\s*(?:caplet|caplets|tablet|tablets|capsule|capsules)\b", re.IGNORECASE), "units"),
)


def pack_tokens(title: Any) -> List[tuple]:
    """Extract a normalized pack-size signal: [(kind, count), ...] or []."""
    if title is None:
        return []
    text = str(title)
    tokens: List[tuple] = []
    for pattern, kind in _PACK_PATTERNS:
        for match in pattern.finditer(text):
            try:
                tokens.append((kind, int(match.group(1))))
            except ValueError:
                continue
    return tokens


# ---------------------------------------------------------------------------
# Row parsing / normalization
# ---------------------------------------------------------------------------

def process_csv(path: str, source_file: str) -> List[Dict[str, Any]]:
    observations: List[Dict[str, Any]] = []
    with open(path, encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            asin = (row.get("ASIN") or "").strip().upper()
            obs: Dict[str, Any] = {
                "asin": asin,
                "source_file": source_file,
                "title": (row.get("Product") or "").strip() or None,
                "title_normalized": None,
                "price": parse_price(row.get("Price")),
                "reviews": parse_int(row.get("Reviews")),
                "proxy_rank": None,
                "source_rank": None,
                "prime_fba_raw": None,
                "prime_fba": None,
                "prime_fba_note": None,
                "bsr_raw": None,
                "bsr_rank_number": None,
                "bsr_category": None,
                "bsr_secondary_rank_number": None,
                "bsr_secondary_category": None,
                "capture_timestamp": None,
                "capture_time_status": "unknown",
                "confidence": "user_provided_benchmark_observation",
                "malformed_asin": not bool(ASIN_PATTERN.fullmatch(asin)),
            }
            if source_file == FILE_A:
                obs["proxy_rank"] = parse_int(row.get("# (BSR-proxy rank)"))
                prime = parse_prime_fba(row.get("Prime/FBA"))
                obs["prime_fba_raw"] = prime["raw"]
                obs["prime_fba"] = prime["state"]
                obs["prime_fba_note"] = prime["note"]
            else:
                obs["source_rank"] = parse_int(row.get("Rank"))
                bsr = parse_bsr(row.get("BSR"))
                obs["bsr_raw"] = bsr["raw"]
                obs["bsr_rank_number"] = bsr["rank_number"]
                obs["bsr_category"] = bsr["category"]
                obs["bsr_secondary_rank_number"] = bsr["secondary_rank_number"]
                obs["bsr_secondary_category"] = bsr["secondary_category"]
            obs["title_normalized"] = normalize_title(obs["title"])
            observations.append(obs)
    return observations


# ---------------------------------------------------------------------------
# Canonical view (deterministic, documented rules) + conflict flags
# ---------------------------------------------------------------------------

CANONICAL_RULES = (
    "1. price/reviews: canonical when values agree across files; a disagreement "
    "sets the canonical value to null and flags a conflict.",
    "2. prime_fba: only file A carries it -> canonical from file A.",
    "3. bsr/rank: only file B carries BSR and Rank -> canonical from file B.",
    "4. title: file A is the 47-row primary reference; on disagreement the "
    "canonical title is file A's, flagged title_conflict for review.",
    "5. capture timestamp: no timestamp column exists -> null, "
    "capture_time_status 'unknown' (reference only, not freshness proof).",
)


def build_canonical(observations: List[Dict[str, Any]]) -> Dict[str, Any]:
    by_asin: Dict[str, List[Dict[str, Any]]] = {}
    for obs in observations:
        if obs["malformed_asin"]:
            continue
        by_asin.setdefault(obs["asin"], []).append(obs)

    asins: Dict[str, Any] = {}
    conflicts: List[Dict[str, Any]] = []
    for asin in sorted(by_asin):
        rows = by_asin[asin]
        file_a = [r for r in rows if r["source_file"] == FILE_A]
        file_b = [r for r in rows if r["source_file"] == FILE_B]
        a = file_a[0] if file_a else None
        b = file_b[0] if file_b else None

        prices = {r["price"] for r in rows if r["price"] is not None}
        reviews = {r["reviews"] for r in rows if r["reviews"] is not None}
        titles = {r["title"] for r in rows if r["title"] is not None}

        price_conflict = len(prices) > 1
        review_conflict = len(reviews) > 1
        title_conflict = len(titles) > 1

        canonical_price = None if price_conflict else next(iter(prices), None)
        canonical_reviews = None if review_conflict else next(iter(reviews), None)
        canonical_title = a["title"] if a else None
        if title_conflict:
            canonical_title = a["title"] if a else canonical_title

        for flag, name in (
            (price_conflict, "price"),
            (review_conflict, "reviews"),
            (title_conflict, "title"),
        ):
            if flag:
                conflicts.append(
                    {
                        "asin": asin,
                        "field": name,
                        "type": "cross_file_disagreement",
                        "values": sorted({str(v) for v in (prices if name == "price" else (reviews if name == "reviews" else titles))}),
                        "note": "values differ across observations; canonical kept per CANONICAL_RULES",
                    }
                )

        asins[asin] = {
            "asin": asin,
            "title": canonical_title,
            "title_normalized": normalize_title(canonical_title),
            "price": canonical_price,
            "reviews": canonical_reviews,
            "proxy_rank": a["proxy_rank"] if a else None,
            "source_rank": b["source_rank"] if b else None,
            "prime_fba_raw": a["prime_fba_raw"] if a else None,
            "prime_fba": a["prime_fba"] if a else None,
            "prime_fba_note": a["prime_fba_note"] if a else None,
            "bsr_raw": b["bsr_raw"] if b else None,
            "bsr_rank_number": b["bsr_rank_number"] if b else None,
            "bsr_category": b["bsr_category"] if b else None,
            "bsr_secondary_rank_number": b["bsr_secondary_rank_number"] if b else None,
            "bsr_secondary_category": b["bsr_secondary_category"] if b else None,
            "capture_timestamp": None,
            "capture_time_status": "unknown",
            "confidence": "user_provided_benchmark_observation",
            "title_conflict": title_conflict,
            "price_conflict": price_conflict,
            "review_conflict": review_conflict,
            "source_files": sorted({r["source_file"] for r in rows}),
            "observation_count": len(rows),
        }
    return {"asins": asins, "conflicts": conflicts}


def build_store(source_files_dir: Optional[str] = None) -> Dict[str, Any]:
    """Read the raw CSVs and produce the full store artifact (no writes)."""
    src = source_files_dir or raw_dir()
    provenance: List[Dict[str, Any]] = []
    observations: List[Dict[str, Any]] = []
    missing: List[str] = []
    for name in SOURCE_FILES:
        path = os.path.join(src, name)
        if not os.path.isfile(path):
            missing.append(name)
            continue
        provenance.append(
            {
                "name": name,
                "path": path,
                "sha256": sha256_file(path),
                "capture_timestamp": None,
                "capture_time_status": "unknown",
            }
        )
        observations.extend(process_csv(path, name))
    if missing:
        raise FileNotFoundError(f"benchmark source files missing: {missing}")

    canonical = build_canonical(observations)

    asins = sorted({r["asin"] for r in observations if not r["malformed_asin"]})
    malformed = [r for r in observations if r["malformed_asin"]]
    inventory = {
        "observation_count": len(observations),
        "unique_asin_count": len(asins),
        "malformed_asin_count": len(malformed),
        "duplicate_asins_within_file": _within_file_duplicates(observations),
        "cross_file_conflict_count": len(canonical["conflicts"]),
    }
    return {
        "schema_version": BENCHMARK_SCHEMA_VERSION,
        "kind": "asin-benchmark-store",
        "generated_at": _now_iso(),
        "source_files": provenance,
        "canonical_rules": list(CANONICAL_RULES),
        "inventory": inventory,
        "observations": observations,
        "canonical": canonical["asins"],
        "conflicts": canonical["conflicts"],
    }


def _within_file_duplicates(observations: List[Dict[str, Any]]) -> Dict[str, int]:
    result: Dict[str, int] = {}
    for obs in observations:
        if obs["malformed_asin"]:
            continue
        key = f"{obs['source_file']}:{obs['asin']}"
        result[key] = result.get(key, 0) + 1
    return {k: v for k, v in result.items() if v > 1}


def _now_iso() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Writes (only to the isolated benchmark location)
# ---------------------------------------------------------------------------

def import_raw_files(import_from: str, target: Optional[str] = None) -> List[Dict[str, Any]]:
    """Copy the two known CSVs byte-for-byte into the raw dir.

    Skips re-copying when an identical sha256 file already exists (idempotent).
    """
    target_dir = target or raw_dir()
    os.makedirs(target_dir, exist_ok=True)
    copied: List[Dict[str, Any]] = []
    for name in SOURCE_FILES:
        src_path = os.path.join(import_from, name)
        if not os.path.isfile(src_path):
            raise FileNotFoundError(f"import source missing: {src_path}")
        dst_path = os.path.join(target_dir, name)
        src_sha = sha256_file(src_path)
        action = "unchanged"
        if os.path.isfile(dst_path) and sha256_file(dst_path) == src_sha:
            action = "skipped_same_sha"
        else:
            shutil.copyfile(src_path, dst_path)
            action = "copied"
        copied.append(
            {
                "name": name,
                "action": action,
                "sha256": src_sha,
                "bytes": os.path.getsize(dst_path),
            }
        )
    return copied


def _manifest_entries(source_files_dir: Optional[str] = None) -> List[Dict[str, Any]]:
    """Per-file manifest rows for the raw CSV copies."""
    src = source_files_dir or raw_dir()
    rows: List[Dict[str, Any]] = []
    for name in SOURCE_FILES:
        path = os.path.join(src, name)
        if not os.path.isfile(path):
            continue
        rows.append(
            {
                "source_filename": name,
                "destination_filename": path,
                "sha256": sha256_file(path),
                "bytes": os.path.getsize(path),
                "imported_at": _now_iso(),
                "source_type": "user_provided_reference",
                "capture_time": None,
                "capture_time_status": "unknown",
                "notes": MANIFEST_NOTE,
            }
        )
    return rows


def build_manifest(source_files_dir: Optional[str] = None) -> Dict[str, Any]:
    return {
        "schema_version": 1,
        "kind": "benchmark-provenance-manifest",
        "imported_at": _now_iso(),
        "entries": _manifest_entries(source_files_dir),
    }


def write_reference(store: Dict[str, Any], path: Optional[str] = None) -> str:
    """Write the normalized reference artifact (and its manifest)."""
    target = path or reference_path()
    os.makedirs(os.path.dirname(target) or ".", exist_ok=True)
    with open(target, "w", encoding="utf-8") as fh:
        json.dump(store, fh, indent=2, ensure_ascii=False)
    manifest_target = manifest_path()
    os.makedirs(os.path.dirname(manifest_target) or ".", exist_ok=True)
    with open(manifest_target, "w", encoding="utf-8") as fh:
        json.dump(build_manifest(), fh, indent=2, ensure_ascii=False)
    return target


def load_reference(path: Optional[str] = None) -> Dict[str, Any]:
    """Load the normalized reference artifact only.

    Returns an EMPTY benchmark state (no observations, no canonical rows)
    when the artifact is absent — callers must handle empty state, never
    fabricate values.
    """
    target = path or reference_path()
    if not os.path.isfile(target):
        return {
            "schema_version": BENCHMARK_SCHEMA_VERSION,
            "kind": "asin-benchmark-store",
            "generated_at": None,
            "source_files": [],
            "inventory": {
                "observation_count": 0,
                "unique_asin_count": 0,
                "malformed_asin_count": 0,
                "duplicate_asins_within_file": {},
                "cross_file_conflict_count": 0,
            },
            "observations": [],
            "canonical": {},
            "conflicts": [],
            "loaded_from": None,
        }
    with open(target, encoding="utf-8") as fh:
        store = json.load(fh)
    store["loaded_from"] = target
    return store


# ---------------------------------------------------------------------------
# CLI (offline)
# ---------------------------------------------------------------------------

def _cli() -> None:
    import sys

    args = sys.argv[1:]
    command = args[0] if args else "status"
    if command == "build":
        import_from = args[1] if len(args) > 1 else import_dir()
        if import_from:
            print("import:", import_raw_files(import_from))
        store = build_store()
        path = write_reference(store)
        print(f"reference artifact written: {path}")
        print(f"manifest written: {manifest_path()}")
        print(f"observations={store['inventory']['observation_count']} "
              f"unique_asins={store['inventory']['unique_asin_count']} "
              f"conflicts={store['inventory']['cross_file_conflict_count']}")
    elif command == "status":
        store = load_reference()
        print(json.dumps(store.get("inventory"), indent=2))
        print("source_files:", [f["name"] for f in store.get("source_files", [])])
        print("loaded_from:", store.get("loaded_from"))
    elif command == "inspect":
        store = load_reference()
        asin = args[1].upper() if len(args) > 1 else None
        for key, row in store.get("canonical", {}).items():
            if asin and key != asin:
                continue
            print(f"{key} | {row['title']} | ${row['price']} | {row['reviews']} reviews "
                  f"| prime={row['prime_fba']} | bsr={row['bsr_rank_number']} {row['bsr_category']} "
                  f"| capture={row['capture_time_status']} | conflicts(title={row['title_conflict']},"
                  f"price={row['price_conflict']},reviews={row['review_conflict']})")
    else:
        raise SystemExit(f"unknown command: {command} (build | status | inspect)")


if __name__ == "__main__":
    _cli()
