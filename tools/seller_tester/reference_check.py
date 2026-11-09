"""Reference fidelity: printed text (OCR) and meaning (embeddings), not a colour threshold.

The product-picture service has exactly three inputs (ty/MANDATE.md): the prompt alone,
stored references from earlier generations, and references the user uploads. A reference-mode
brief is satisfied only if the produced picture actually contains the referenced product —
not merely plausible pixels.

The owner's instruction (2026-11-08) replaced the earlier design:

* the **0.60 colour proxy is not a gate** any more. It is measured and reported as a
  diagnostic, because a genuine pouch crop scored 0.603 while three dark-green UI screenshots
  scored 0.637 — it fails conservatively and cannot decide acceptance;
* a **printed-text match** (OCR on both pictures) decides fidelity where the reference carries
  legible brand text. OCR is noisy on real renders ("MOGRAORGAICS"), so matching is fuzzy and
  token-based rather than exact;
* an **embedding agreement** between the local vision model's descriptions of the two pictures
  decides shape and meaning where text is absent;
* composites are the preferred path for uploads, so the real product is cut out and placed in
  a generated scene and only the *scene* is generated.

`cannot_verify` is always a failure. Nothing here reports a pass it did not measure.
"""
from __future__ import annotations

import difflib
import os
import re
import sys
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[2]

# Only these trees may supply a reference asset.
REFERENCE_ROOTS = (
    "renders/",
    "generated_images/",
    "Northstar_backend/data/studio_generated/",
)

CHROMA_MIN = 30.0
HUE_BINS = 12
CORNER_PATCH = 16
BACKGROUND_DISTANCE = 28

#: Diagnostic only. It is reported, never used to accept or reject a picture.
DIAGNOSTIC_MIN_COLOUR = 0.62
DEFAULT_MAX_ASPECT_RATIO = 1.6

#: Fraction of the reference's key tokens the produced picture must show.
DEFAULT_MIN_TOKEN_RECALL = 0.6
#: Cosine between the two descriptions must clear this when text cannot decide.
DEFAULT_MIN_EMBEDDING = 0.72
#: A key token is an alphanumeric run at least this long.
MIN_TOKEN_LEN = 5
#: Fuzzy match ratio for OCR noise.
FUZZY_RATIO = 0.82

EMBED_MODEL = "qwen3-embedding:0.6b"
EMBED_URL = "http://127.0.0.1:11434/api/embeddings"


def _check(**kw: Any) -> Dict[str, Any]:
    kw.setdefault("skipped", False)
    kw.setdefault("cannot_verify", False)
    kw["ok"] = bool(kw.get("ok", False))
    kw["check"] = "reference_subject"
    return kw


def _cannot_verify(reason: str, **extra: Any) -> Dict[str, Any]:
    return _check(ok=False, cannot_verify=True, detail=f"cannot verify: {reason}", **extra)


def normalise_reference_path(value: Any, repo_root: str | Path = REPO_ROOT
                             ) -> Tuple[Optional[Path], str]:
    """Resolve a stored-asset reference inside the allowed trees."""
    if not isinstance(value, str) or not value.strip():
        return None, "reference path is empty"
    raw = value.strip().replace("\\", "/")
    if raw.startswith("/") or ":" in raw:
        return None, f"reference path must be repo-relative ({value!r})"
    if ".." in Path(raw).parts:
        return None, f"reference path escapes the repository ({value!r})"
    if not any(raw.startswith(root) for root in REFERENCE_ROOTS):
        return None, (f"reference path is outside the allowed asset roots "
                      f"{REFERENCE_ROOTS} ({value!r})")
    target = Path(repo_root) / raw
    if not target.is_file():
        return None, f"reference asset is not on disk ({raw})"
    return target, ""


# ------------------------------------------------------------------ pixels (diagnostic)
def subject_mask(rgb: np.ndarray) -> np.ndarray:
    height, width = rgb.shape[:2]
    size = max(4, min(CORNER_PATCH, height // 8, width // 8))
    patches = (rgb[:size, :size], rgb[:size, width - size:],
               rgb[height - size:, :size], rgb[height - size:, width - size:])
    background = np.median(
        np.array([np.median(p.reshape(-1, 3), axis=0) for p in patches]), axis=0)
    difference = np.abs(rgb.astype(np.int16) - background.astype(np.int16)).max(axis=2)
    mask = difference > BACKGROUND_DISTANCE
    if float(mask.mean()) > 0.90:
        return np.ones((height, width), dtype=bool)
    return mask


def dominant_hue(rgb: np.ndarray, chroma_min: float = CHROMA_MIN,
                 bins: int = HUE_BINS) -> Optional[np.ndarray]:
    mask = subject_mask(rgb)
    pixels = rgb[mask].reshape(-1, 3).astype(np.float32)
    if pixels.size == 0:
        return None
    high = pixels.max(axis=1)
    low = pixels.min(axis=1)
    chroma = high - low
    keep = chroma >= chroma_min
    if int(keep.sum()) < max(16, int(0.01 * pixels.shape[0])):
        return None
    pixels, chroma = pixels[keep], chroma[keep]
    red, green, blue = pixels[:, 0], pixels[:, 1], pixels[:, 2]
    hue = np.zeros(pixels.shape[0], dtype=np.float32)
    max_is_red = high[keep] == red
    max_is_green = (high[keep] == green) & ~max_is_red
    rest = ~max_is_red & ~max_is_green
    hue[max_is_red] = ((green[max_is_red] - blue[max_is_red]) / chroma[max_is_red]) % 6
    hue[max_is_green] = ((blue[max_is_green] - red[max_is_green]) / chroma[max_is_green]) + 2
    hue[rest] = ((red[rest] - green[rest]) / chroma[rest]) + 4
    hue *= 60.0
    histogram = np.zeros(bins, dtype=np.float32)
    np.add.at(histogram, (hue / (360.0 / bins)).astype(np.int32) % bins, chroma)
    total = float(histogram.sum())
    return None if total <= 0.0 else histogram / total


def colour_agreement(produced: np.ndarray, reference: np.ndarray) -> Optional[float]:
    """Diagnostic only. Kept because it is honest evidence, not because it decides."""
    a, b = dominant_hue(produced), dominant_hue(reference)
    if a is None or b is None:
        return None
    return float(np.minimum(a, b).sum())


def silhouette_aspect(rgb: np.ndarray) -> Optional[float]:
    mask = subject_mask(rgb)
    rows, columns = np.where(mask)
    if rows.size == 0:
        return None
    width = int(columns.max() - columns.min() + 1)
    height = int(rows.max() - rows.min() + 1)
    if width < 2 or height < 2:
        return None
    return width / float(height)


# ------------------------------------------------------------------ OCR
def ocr_text(rgb: np.ndarray) -> Dict[str, Any]:
    """Text visible in a picture, via the local ONNX OCR engine. No network, no cloud."""
    try:
        from rapidocr_onnxruntime import RapidOCR  # noqa: PLC0415

        engine = RapidOCR()
        result, _ = engine(np.ascontiguousarray(rgb[:, :, ::-1]))
    except Exception as exc:  # noqa: BLE001 - unreadable text is a named failure
        return {"ok": False, "items": [], "text": "", "reason": f"{type(exc).__name__}: {exc}"}
    items: List[Dict[str, Any]] = []
    for row in result or []:
        try:
            items.append({"text": str(row[1]), "score": float(row[2])})
        except (IndexError, TypeError, ValueError):
            continue
    return {"ok": bool(items), "items": items,
            "text": " ".join(item["text"] for item in items)}


def _norm(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(text or "").casefold())


def key_tokens(text: str) -> List[str]:
    """Tokens worth matching: brand and product words, plus sizes.

    OCR merges and mangles words ("MOGRAORGAICS"), so tokens are compared fuzzily and a
    token only counts once. Very short runs and pure numbers are dropped — '2023' appears on
    every pack and proves nothing.
    """
    raw = re.findall(r"[A-Za-z0-9][A-Za-z0-9'&.\-]*", str(text or ""))
    out: List[str] = []
    for token in raw:
        norm = _norm(token)
        if len(norm) < MIN_TOKEN_LEN or norm.isdigit():
            continue
        if norm not in out:
            out.append(norm)
    return out


def text_match(produced_text: str, reference_text: str, *,
               min_recall: float = DEFAULT_MIN_TOKEN_RECALL) -> Dict[str, Any]:
    """Does the produced picture print the reference's key words? Fuzzy, token-based."""
    wanted = key_tokens(reference_text)
    if not wanted:
        return _cannot_verify("the reference picture carries no legible text to match")
    haystack = [_norm(chunk) for chunk in str(produced_text or "").split()]
    haystack = [chunk for chunk in haystack if chunk]
    joined = "".join(haystack)
    matched, missing = [], []
    for token in wanted:
        best = max((difflib.SequenceMatcher(None, token, chunk).ratio()
                    for chunk in haystack), default=0.0)
        if best >= FUZZY_RATIO or token in joined:
            matched.append(token)
        else:
            missing.append(token)
    recall = len(matched) / len(wanted)
    return _check(ok=recall >= float(min_recall), cannot_verify=False,
                  detail=(f"{len(matched)}/{len(wanted)} key words present "
                          f"({recall:.2f}, min {float(min_recall):.2f})"),
                  matched=matched, missing=missing, recall=round(recall, 3),
                  min_recall=float(min_recall),
                  produced_text=str(produced_text or "")[:600],
                  reference_text=str(reference_text or "")[:600])


# ------------------------------------------------------------------ embeddings
def embed(text: str, *, model: str = EMBED_MODEL, url: str = EMBED_URL,
          timeout: float = 30.0) -> Optional[List[float]]:
    """A local text embedding. None when the model is unavailable — never a fake vector."""
    import json
    import urllib.request

    try:
        request = urllib.request.Request(
            url, data=json.dumps({"model": model, "prompt": str(text)[:4000]}).encode(),
            headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = json.loads(response.read().decode("utf-8", "replace") or "{}")
        vector = body.get("embedding")
        return [float(value) for value in vector] if vector else None
    except Exception:  # noqa: BLE001
        return None


def cosine(a: Optional[Sequence[float]], b: Optional[Sequence[float]]) -> Optional[float]:
    if not a or not b or len(a) != len(b):
        return None
    left, right = np.asarray(a, dtype=np.float32), np.asarray(b, dtype=np.float32)
    denominator = float(np.linalg.norm(left) * np.linalg.norm(right))
    if denominator <= 0.0:
        return None
    return float(np.dot(left, right) / denominator)


def semantic_agreement(produced_desc: str, reference_desc: str, *,
                       min_score: float = DEFAULT_MIN_EMBEDDING,
                       embedder: Optional[Callable[[str], Optional[List[float]]]] = None,
                       ) -> Dict[str, Any]:
    """Do two descriptions mean the same thing? Local embeddings, cosine.

    A blank description is not agreement: embedding nothing and comparing it with
    nothing would read as a perfect match, so it is `cannot_verify` instead.
    """
    if not str(produced_desc or "").strip() or not str(reference_desc or "").strip():
        return _cannot_verify("no description was produced for one of the pictures")
    call = embedder or embed
    score = cosine(call(produced_desc), call(reference_desc))
    if score is None:
        return _cannot_verify("no local embedding available for the two descriptions")
    return _check(ok=score >= float(min_score), cannot_verify=False,
                  detail=f"embedding agreement {score:.3f} (min {float(min_score):.2f})",
                  similarity=round(score, 4), min_similarity=float(min_score),
                  produced_desc=str(produced_desc)[:600],
                  reference_desc=str(reference_desc)[:600])


# ------------------------------------------------------------------ vision description
def describe_enabled() -> bool:
    """Is the local VLM describer switched on? `NORTHSTAR_VLM_DESCRIBE=0` turns it off.

    The judge is off by default because it was never measured. This describer is the
    opposite: the owner's instruction is that a reference check must carry a real
    vision description, so it is on unless explicitly disabled (a unit-test process
    says so, because its brief is "offline only").
    """
    return str(os.environ.get("NORTHSTAR_VLM_DESCRIBE", "1")).strip().lower() \
        not in ("0", "false", "no", "off")


def png_bytes(rgb: np.ndarray) -> bytes:
    """Encode a decoded picture back to PNG for the local model. In memory only."""
    from io import BytesIO

    from PIL import Image

    array = np.asarray(rgb)
    if array.dtype != np.uint8:
        array = np.clip(array, 0, 255).astype(np.uint8)
    buffer = BytesIO()
    Image.fromarray(array).save(buffer, format="PNG")
    return buffer.getvalue()


def describe_picture(rgb: np.ndarray) -> str:
    """A local VLM description of one picture, as text. "" when it cannot describe it.

    Wired to `tools.vision.understand.describe_page` — the read path that already sends a
    crop to qwen2.5vl and returns text (Chrome publishes no accessibility tree, so this is
    the same route the browser lane uses). A blank answer is preserved as blank: the
    caller must turn that into `cannot_verify`, never into a perfect match.
    """
    if not describe_enabled():
        return ""
    try:
        if str(REPO_ROOT) not in sys.path:
            sys.path.insert(0, str(REPO_ROOT))
        from tools.vision import understand  # noqa: PLC0415

        result = understand.describe_page(png=png_bytes(rgb))
    except Exception:  # noqa: BLE001 - no description is a named failure, not a crash
        return ""
    if not isinstance(result, dict) or not result.get("ok"):
        return ""
    return str(result.get("text") or "").strip()


def _describe_one(describe: Optional[Callable[[np.ndarray], str]],
                  rgb: np.ndarray) -> Tuple[str, str]:
    """(description, error). An error leaves the description empty."""
    if describe is None:
        return "", "no describer was supplied"
    try:
        return str(describe(rgb) or "").strip(), ""
    except Exception as exc:  # noqa: BLE001 - a description failure is not a pass
        return "", f"{type(exc).__name__}: {exc}"


# ------------------------------------------------------------------ the verdict
def check_reference_for_brief(produced_rgb: np.ndarray, reference_rgb: np.ndarray,
                              brief: Dict[str, Any], *,
                              produced_text: Optional[str] = None,
                              reference_text: Optional[str] = None,
                              produced_desc: str = "", reference_desc: str = "",
                              ocr: Optional[Callable[[np.ndarray], Dict[str, Any]]] = None,
                              embedder: Optional[Callable[[str], Optional[List[float]]]] = None,
                              ) -> Dict[str, Any]:
    """Decide fidelity from text and meaning; report colour as a diagnostic.

    Order matters: printed text is the strongest evidence when it exists, meaning is the
    fallback, and colour is never the deciding vote.
    """
    spec = (brief.get("reference") or {}).get("check") or {}
    ocr_fn = ocr or ocr_text

    def _ocr(rgb: np.ndarray, known: Optional[str]) -> Dict[str, Any]:
        if known is not None:
            return {"ok": bool(str(known).strip()), "text": str(known or "")}
        return ocr_fn(rgb)

    produced_ocr = _ocr(produced_rgb, produced_text)
    reference_ocr = _ocr(reference_rgb, reference_text)
    text_verdict = text_match(produced_ocr.get("text", ""), reference_ocr.get("text", ""),
                              min_recall=float(spec.get("min_token_recall",
                                                        DEFAULT_MIN_TOKEN_RECALL)))
    meaning = semantic_agreement(produced_desc, reference_desc,
                                 min_score=float(spec.get("min_embedding",
                                                          DEFAULT_MIN_EMBEDDING)),
                                 embedder=embedder)
    agreement = colour_agreement(produced_rgb, reference_rgb)
    produced_aspect, reference_aspect = silhouette_aspect(produced_rgb), silhouette_aspect(
        reference_rgb)

    decided_by = ""
    ok = False
    if not text_verdict.get("cannot_verify"):
        decided_by = "printed_text"
        ok = bool(text_verdict["ok"])
    elif not meaning.get("cannot_verify"):
        decided_by = "embedding"
        ok = bool(meaning["ok"])

    if not decided_by:
        return _cannot_verify(
            "neither printed text nor an embedding could be measured",
            text=text_verdict, meaning=meaning,
            diagnostic={"colour_agreement": None if agreement is None else round(agreement, 4)})

    return _check(
        ok=ok, cannot_verify=False, decided_by=decided_by,
        detail=(f"{decided_by}: {'pass' if ok else 'fail'} — {text_verdict.get('detail') or meaning.get('detail')}"),
        text=text_verdict, meaning=meaning,
        diagnostic={
            "colour_agreement": None if agreement is None else round(agreement, 4),
            "colour_gate": False,
            "produced_aspect": None if produced_aspect is None else round(produced_aspect, 3),
            "reference_aspect": None if reference_aspect is None else round(reference_aspect, 3),
        },
    )


def load_reference_rgb(reference: Dict[str, Any], *,
                       repo_root: str | Path = REPO_ROOT
                       ) -> Tuple[Optional[np.ndarray], str, Optional[str]]:
    if not isinstance(reference, dict):
        return None, "brief declares no reference object", None
    kind = reference.get("kind")
    if kind == "stored_asset":
        path, reason = normalise_reference_path(reference.get("path"), repo_root)
    elif kind == "uploaded_file":
        descriptor = reference.get("descriptor") or {}
        filename = str(descriptor.get("filename") or "").strip()
        path, reason = normalise_reference_path(reference.get("path"), repo_root)
        if path is None and reason.startswith("reference path is empty"):
            reason = (f"no local copy of the uploaded file "
                      f"({filename or 'unnamed upload'}); the upload was not "
                      "present in this checkout")
    else:
        return None, f"unknown reference kind {kind!r}", None

    if path is None:
        return None, reason, None
    try:
        from .scorers import load_image

        loaded = load_image(Path(path).read_bytes())
    except (OSError, ValueError) as exc:
        return None, f"reference asset is unreadable ({type(exc).__name__})", str(path)
    return loaded.rgb, "", str(path)


def reference_check_for_brief(produced_rgb: np.ndarray, brief: Dict[str, Any], *,
                              repo_root: str | Path = REPO_ROOT,
                              produced_text: Optional[str] = None,
                              embedder: Optional[Callable[[str], Optional[List[float]]]] = None,
                              describe: Optional[Callable[[np.ndarray], str]] = None,
                              ) -> Dict[str, Any]:
    """Full reference check for one brief: resolve, load, compare, or refuse."""
    mode = brief.get("source_mode") or "unclassified"
    if mode == "prompt_only":
        return {"ok": True, "skipped": True, "cannot_verify": False,
                "detail": "prompt-only brief: there is no reference to verify",
                "check": "reference_subject"}
    if mode not in ("stored_reference", "uploaded_reference"):
        return _cannot_verify(f"brief has no usable input mode ({mode!r})")

    reference = brief.get("reference")
    rgb, reason, resolved = load_reference_rgb(reference, repo_root=repo_root)
    if rgb is None:
        return _cannot_verify(reason, reference_path=resolved)

    produced_desc = reference_desc = ""
    produced_error = reference_error = ""
    if describe is not None:
        produced_desc, produced_error = _describe_one(describe, produced_rgb)
        reference_desc, reference_error = _describe_one(describe, rgb)

    verdict = check_reference_for_brief(
        produced_rgb, rgb, brief, produced_text=produced_text,
        produced_desc=produced_desc, reference_desc=reference_desc, embedder=embedder)
    verdict["reference_path"] = resolved
    verdict["reference_kind"] = (reference or {}).get("kind")
    verdict["description"] = {
        "requested": describe is not None,
        "produced": bool(produced_desc),
        "reference": bool(reference_desc),
        "produced_chars": len(produced_desc),
        "reference_chars": len(reference_desc),
        "produced_error": produced_error,
        "reference_error": reference_error,
        "produced_text": produced_desc[:600],
        "reference_text": reference_desc[:600],
    }
    return verdict


__all__ = [
    "CHROMA_MIN", "DEFAULT_MAX_ASPECT_RATIO", "DIAGNOSTIC_MIN_COLOUR", "DEFAULT_MIN_EMBEDDING",
    "DEFAULT_MIN_TOKEN_RECALL", "EMBED_MODEL", "HUE_BINS", "REFERENCE_ROOTS",
    "check_reference_for_brief", "colour_agreement", "cosine", "describe_enabled",
    "describe_picture", "dominant_hue", "embed", "key_tokens", "load_reference_rgb",
    "normalise_reference_path", "ocr_text", "png_bytes", "reference_check_for_brief",
    "semantic_agreement", "silhouette_aspect", "subject_mask", "text_match",
]
